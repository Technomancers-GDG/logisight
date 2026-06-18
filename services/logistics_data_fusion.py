from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import LogisticsEdge, LogisticsNode
from schemas import (
    DataFusionRequest,
    DataFusionResponse,
    LogisticsEdgeInput,
    LogisticsGraph,
    LogisticsNodeInput,
)


class DataFusionService:
    """Normalizes multimodal network feeds into one graph contract."""

    def fuse(self, payload: DataFusionRequest | LogisticsGraph) -> DataFusionResponse:
        graph = LogisticsGraph(
            nodes=[self._normalize_node(node) for node in payload.nodes],
            edges=[],
            constraints=dict(payload.constraints or {}),
        )
        node_ids = {node.id for node in graph.nodes}
        seen_edges: set[str] = set()

        for edge in payload.edges:
            normalized = self._normalize_edge(edge)
            if normalized.from_node_id not in node_ids or normalized.to_node_id not in node_ids:
                raise ValueError(
                    f"Edge {normalized.id} references unknown node "
                    f"{normalized.from_node_id}->{normalized.to_node_id}"
                )
            if normalized.id in seen_edges:
                raise ValueError(f"Duplicate edge id: {normalized.id}")
            seen_edges.add(normalized.id or "")
            graph.edges.append(normalized)

        return DataFusionResponse(
            nodes=graph.nodes,
            edges=graph.edges,
            constraints=graph.constraints,
            node_count=len(graph.nodes),
            edge_count=len(graph.edges),
        )

    def persist_graph(self, session: Session, graph: LogisticsGraph) -> None:
        fused = self.fuse(graph)
        db_nodes: dict[str, LogisticsNode] = {}

        for node in fused.nodes:
            existing = session.scalar(select(LogisticsNode).where(LogisticsNode.node_key == node.id))
            if existing is None:
                existing = LogisticsNode(node_key=node.id)
                session.add(existing)
            existing.name = node.name
            existing.node_type = node.node_type
            existing.city = node.city
            existing.latitude = node.latitude
            existing.longitude = node.longitude
            existing.capacity_units = node.capacity_units
            existing.node_metadata = dict(node.metadata)
            existing.active = node.active
            db_nodes[node.id] = existing

        session.flush()

        for edge in fused.edges:
            edge_id = edge.id or self.edge_id(edge)
            existing_edge = session.scalar(
                select(LogisticsEdge).where(LogisticsEdge.edge_key == edge_id)
            )
            if existing_edge is None:
                existing_edge = LogisticsEdge(edge_key=edge_id)
                session.add(existing_edge)

            existing_edge.from_node_id = db_nodes[edge.from_node_id].id
            existing_edge.to_node_id = db_nodes[edge.to_node_id].id
            existing_edge.transport_mode = edge.transport_mode
            existing_edge.cost = edge.cost
            existing_edge.time_minutes = edge.time
            existing_edge.risk = edge.risk
            existing_edge.distance_km = edge.distance_km
            existing_edge.capacity_units = max(int(edge.capacity or edge.capacity_units or 0), 0)
            existing_edge.bidirectional = edge.bidirectional
            existing_edge.constraints = {
                **dict(edge.constraints),
                "capacity": edge.capacity,
                "time_window": list(edge.time_window) if edge.time_window else None,
                "mode_switch_penalty": edge.mode_switch_penalty,
            }
            existing_edge.edge_metadata = dict(edge.metadata)
            existing_edge.active = edge.active

        session.commit()

    def graph_from_db(self, session: Session) -> LogisticsGraph:
        nodes = session.scalars(
            select(LogisticsNode).where(LogisticsNode.active.is_(True)).order_by(LogisticsNode.node_key)
        ).all()
        node_by_pk = {node.id: node for node in nodes}
        edges = session.scalars(
            select(LogisticsEdge).where(LogisticsEdge.active.is_(True)).order_by(LogisticsEdge.edge_key)
        ).all()

        return LogisticsGraph(
            nodes=[
                LogisticsNodeInput(
                    id=node.node_key,
                    name=node.name,
                    node_type=node.node_type,
                    city=node.city,
                    latitude=node.latitude,
                    longitude=node.longitude,
                    capacity_units=node.capacity_units,
                    metadata=node.node_metadata or {},
                    active=node.active,
                )
                for node in nodes
            ],
            edges=[
                LogisticsEdgeInput(
                    id=edge.edge_key,
                    from_node_id=node_by_pk[edge.from_node_id].node_key,
                    to_node_id=node_by_pk[edge.to_node_id].node_key,
                    transport_mode=edge.transport_mode,
                    cost=edge.cost,
                    time=edge.time_minutes,
                    risk=edge.risk,
                    capacity=(edge.constraints or {}).get("capacity", edge.capacity_units),
                    time_window=(
                        tuple((edge.constraints or {}).get("time_window"))
                        if (edge.constraints or {}).get("time_window")
                        else None
                    ),
                    mode_switch_penalty=float((edge.constraints or {}).get("mode_switch_penalty", 0.0) or 0.0),
                    distance_km=edge.distance_km,
                    capacity_units=edge.capacity_units,
                    bidirectional=edge.bidirectional,
                    constraints=edge.constraints or {},
                    metadata=edge.edge_metadata or {},
                    active=edge.active,
                )
                for edge in edges
                if edge.from_node_id in node_by_pk and edge.to_node_id in node_by_pk
            ],
            constraints={},
        )

    def _normalize_node(self, node: LogisticsNodeInput) -> LogisticsNodeInput:
        return LogisticsNodeInput(
            id=node.id.strip(),
            name=node.name.strip(),
            node_type=node.node_type,
            city=node.city.strip() if node.city else None,
            latitude=node.latitude,
            longitude=node.longitude,
            capacity_units=node.capacity_units,
            metadata=dict(node.metadata),
            active=node.active,
        )

    def _normalize_edge(self, edge: LogisticsEdgeInput) -> LogisticsEdgeInput:
        normalized = LogisticsEdgeInput(
            id=(edge.id or self.edge_id(edge)).strip(),
            from_node_id=edge.from_node_id.strip(),
            to_node_id=edge.to_node_id.strip(),
            transport_mode=edge.transport_mode,
            cost=edge.cost,
            time=edge.time,
            risk=edge.risk,
            capacity=edge.capacity if edge.capacity is not None else (
                float(edge.capacity_units) if edge.capacity_units is not None else None
            ),
            time_window=edge.time_window,
            mode_switch_penalty=edge.mode_switch_penalty,
            distance_km=edge.distance_km,
            capacity_units=edge.capacity_units,
            bidirectional=edge.bidirectional,
            constraints=dict(edge.constraints),
            metadata=dict(edge.metadata),
            active=edge.active,
        )
        if normalized.from_node_id == normalized.to_node_id:
            raise ValueError(f"Edge {normalized.id} cannot connect a node to itself")
        return normalized

    @staticmethod
    def edge_id(edge: LogisticsEdgeInput) -> str:
        return f"{edge.from_node_id}:{edge.to_node_id}:{edge.transport_mode}"
