from __future__ import annotations

from dataclasses import dataclass, field, replace
import heapq
from typing import Iterable

from schemas import (
    LogisticsEdgeInput,
    LogisticsGraph,
    RouteBusinessMetrics,
    RouteOptionRead,
    RouteSegmentRead,
    RouteWeights,
)


@dataclass(frozen=True, slots=True)
class TraversalEdge:
    edge_id: str
    from_node_id: str
    to_node_id: str
    transport_mode: str
    cost: float
    time: float
    risk: float
    base_cost: float
    base_time: float
    base_risk: float
    predicted_delay: float = 0.0
    risk_penalty: float = 0.0
    capacity: float | None = None
    time_window: tuple[float, float] | None = None
    mode_switch_penalty: float = 0.0
    distance_km: float | None = None
    reversed: bool = False
    mode_switch_penalty_applied: float = 0.0
    switching_delay_applied: float = 0.0
    time_window_violation_minutes: float = 0.0
    driver_penalty_applied: float = 0.0


@dataclass(order=True, slots=True)
class QueueItem:
    score: float
    node_id: str = field(compare=False)
    node_sequence: list[str] = field(compare=False)
    edges: list[TraversalEdge] = field(compare=False)
    prev_mode: str | None = field(compare=False, default=None)
    total_cost: float = field(compare=False, default=0.0)
    total_time: float = field(compare=False, default=0.0)
    total_risk: float = field(compare=False, default=0.0)


class MultimodalGraphEngine:
    """Graph search over road, rail, and water edges using weighted scoring."""

    FUEL_LITERS_PER_KM = {
        "road": 0.34,
        "rail": 0.08,
        "water": 0.045,
    }
    CO2_KG_PER_LITER = 2.68
    MODE_SPEED_KMPH = {
        "road": 42.0,
        "rail": 55.0,
        "water": 18.0,
    }

    def compute_routes(
        self,
        graph: LogisticsGraph,
        origin_node_id: str,
        destination_node_id: str,
        weights: RouteWeights,
        max_routes: int = 3,
        *,
        required_capacity: float = 0.0,
        switching_delay: float = 0.0,
        time_window_penalty: float = 10.0,
        driver_reliability_score: float | None = None,
        driver_penalty_factor: float = 100.0,
    ) -> list[RouteOptionRead]:
        self._validate_graph(graph, origin_node_id, destination_node_id)
        adjacency = self._build_adjacency(graph)
        first_path = self._dijkstra(
            adjacency,
            origin_node_id,
            destination_node_id,
            weights,
            required_capacity=required_capacity,
            switching_delay=switching_delay,
            time_window_penalty=time_window_penalty,
            driver_reliability_score=driver_reliability_score,
            driver_penalty_factor=driver_penalty_factor,
        )
        if first_path is None:
            return []

        accepted = [first_path]
        candidates: list[tuple[float, int, RouteOptionRead]] = []
        seen_signatures = {self._signature(first_path)}
        candidate_sequence = 0

        # Yen-style alternatives: remove one edge from accepted routes and search a spur.
        while len(accepted) < max_routes:
            source_path = accepted[-1]
            for spur_index in range(len(source_path.node_sequence) - 1):
                root_nodes = source_path.node_sequence[: spur_index + 1]
                root_segments = source_path.segments[:spur_index]
                disabled_edges = self._disabled_edges_for_root(accepted, root_nodes, spur_index)
                disabled_nodes = set(root_nodes[:-1])
                spur = self._dijkstra(
                    adjacency,
                    root_nodes[-1],
                    destination_node_id,
                    weights,
                    disabled_edges=disabled_edges,
                    disabled_nodes=disabled_nodes,
                    required_capacity=required_capacity,
                    switching_delay=switching_delay,
                    time_window_penalty=time_window_penalty,
                    driver_reliability_score=driver_reliability_score,
                    driver_penalty_factor=driver_penalty_factor,
                )
                if spur is None:
                    continue

                merged = self._merge_paths(root_nodes, root_segments, spur, weights)
                signature = self._signature(merged)
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
                candidate_sequence += 1
                heapq.heappush(candidates, (merged.score, candidate_sequence, merged))

            if not candidates:
                break
            accepted.append(heapq.heappop(candidates)[2])

        road_baseline = self._dijkstra(
            adjacency,
            origin_node_id,
            destination_node_id,
            weights,
            required_capacity=required_capacity,
            switching_delay=switching_delay,
            time_window_penalty=time_window_penalty,
            driver_reliability_score=driver_reliability_score,
            driver_penalty_factor=driver_penalty_factor,
            allowed_modes={"road"},
        )
        return self._attach_business_metrics(accepted, road_baseline or first_path)

    def _dijkstra(
        self,
        adjacency: dict[str, list[TraversalEdge]],
        origin_node_id: str,
        destination_node_id: str,
        weights: RouteWeights,
        *,
        disabled_edges: set[str] | None = None,
        disabled_nodes: set[str] | None = None,
        allowed_modes: set[str] | None = None,
        required_capacity: float = 0.0,
        switching_delay: float = 0.0,
        time_window_penalty: float = 10.0,
        driver_reliability_score: float | None = None,
        driver_penalty_factor: float = 100.0,
    ) -> RouteOptionRead | None:
        disabled_edges = disabled_edges or set()
        disabled_nodes = disabled_nodes or set()
        queue = [
            QueueItem(
                score=0.0,
                node_id=origin_node_id,
                node_sequence=[origin_node_id],
                edges=[],
            )
        ]
        best_score: dict[tuple[str, str | None], float] = {(origin_node_id, None): 0.0}

        while queue:
            item = heapq.heappop(queue)
            if item.node_id == destination_node_id:
                return self._to_route_option(item.node_sequence, item.edges, weights)
            if item.score > best_score.get((item.node_id, item.prev_mode), float("inf")):
                continue

            for edge in adjacency.get(item.node_id, []):
                if edge.edge_id in disabled_edges or edge.to_node_id in disabled_nodes:
                    continue
                if edge.to_node_id in item.node_sequence:
                    continue
                if allowed_modes is not None and edge.transport_mode not in allowed_modes:
                    continue
                # Capacity is a hard constraint: an edge that cannot move the
                # requested load is excluded instead of merely made expensive.
                if required_capacity and edge.capacity is not None and edge.capacity < required_capacity:
                    continue

                edge_with_penalties = self._apply_runtime_penalties(
                    edge=edge,
                    previous_mode=item.prev_mode,
                    current_route_time=item.total_time,
                    switching_delay=switching_delay,
                    time_window_penalty=time_window_penalty,
                    driver_reliability_score=driver_reliability_score,
                    driver_penalty_factor=driver_penalty_factor,
                )
                next_cost = item.total_cost + edge_with_penalties.cost
                next_time = item.total_time + edge_with_penalties.time
                next_risk = item.total_risk + edge_with_penalties.risk
                next_score = self._score(next_cost, next_time, next_risk, weights)
                best_key = (edge.to_node_id, edge.transport_mode)
                if next_score >= best_score.get(best_key, float("inf")):
                    continue
                best_score[best_key] = next_score
                heapq.heappush(
                    queue,
                    QueueItem(
                        score=next_score,
                        node_id=edge.to_node_id,
                        node_sequence=[*item.node_sequence, edge.to_node_id],
                        edges=[*item.edges, edge_with_penalties],
                        prev_mode=edge.transport_mode,
                        total_cost=next_cost,
                        total_time=next_time,
                        total_risk=next_risk,
                    ),
                )
        return None

    def _apply_runtime_penalties(
        self,
        *,
        edge: TraversalEdge,
        previous_mode: str | None,
        current_route_time: float,
        switching_delay: float,
        time_window_penalty: float,
        driver_reliability_score: float | None,
        driver_penalty_factor: float,
    ) -> TraversalEdge:
        mode_penalty = 0.0
        switch_delay = 0.0
        if previous_mode is not None and previous_mode != edge.transport_mode:
            mode_penalty = edge.mode_switch_penalty
            switch_delay = switching_delay
        driver_penalty = 0.0
        if driver_reliability_score is not None:
            reliability = min(1.0, max(0.0, driver_reliability_score))
            driver_penalty = (1.0 - reliability) * driver_penalty_factor

        # Time windows are soft constraints. Early arrival is modeled as wait
        # time; late traversal is modeled as delay. Both increase score.
        window_violation = 0.0
        if edge.time_window is not None:
            window_start, window_end = edge.time_window
            start_time = current_route_time + switch_delay
            finish_time = start_time + edge.time
            if start_time < window_start:
                window_violation += window_start - start_time
            if finish_time > window_end:
                window_violation += finish_time - window_end

        return replace(
            edge,
            cost=edge.cost + mode_penalty + window_violation * time_window_penalty + driver_penalty,
            time=edge.time + switch_delay + window_violation,
            mode_switch_penalty_applied=mode_penalty,
            switching_delay_applied=switch_delay,
            time_window_violation_minutes=round(window_violation, 3),
            driver_penalty_applied=round(driver_penalty, 3),
        )

    def _build_adjacency(self, graph: LogisticsGraph) -> dict[str, list[TraversalEdge]]:
        adjacency: dict[str, list[TraversalEdge]] = {}
        for edge in graph.edges:
            edge_id = edge.id or f"{edge.from_node_id}:{edge.to_node_id}:{edge.transport_mode}"
            forward = self._traversal_edge(edge, edge_id=edge_id, reversed=False)
            adjacency.setdefault(edge.from_node_id, []).append(forward)
            if edge.bidirectional:
                reverse = self._traversal_edge(edge, edge_id=edge_id, reversed=True)
                adjacency.setdefault(edge.to_node_id, []).append(reverse)
        return adjacency

    @staticmethod
    def _traversal_edge(edge: LogisticsEdgeInput, *, edge_id: str, reversed: bool) -> TraversalEdge:
        adjustment = edge.metadata.get("prediction_adjustment", {}) if edge.metadata else {}
        base_cost = float(adjustment.get("base_cost", edge.cost))
        base_time = float(adjustment.get("base_time", edge.time))
        base_risk = float(adjustment.get("base_risk", edge.risk))
        return TraversalEdge(
            edge_id=edge_id,
            from_node_id=edge.to_node_id if reversed else edge.from_node_id,
            to_node_id=edge.from_node_id if reversed else edge.to_node_id,
            transport_mode=edge.transport_mode,
            cost=edge.cost,
            time=edge.time,
            risk=edge.risk,
            base_cost=base_cost,
            base_time=base_time,
            base_risk=base_risk,
            predicted_delay=float(adjustment.get("predicted_delay", max(0.0, edge.time - base_time)) or 0.0),
            risk_penalty=float(adjustment.get("risk_penalty", max(0.0, edge.cost - base_cost)) or 0.0),
            capacity=edge.capacity if edge.capacity is not None else (
                float(edge.capacity_units) if edge.capacity_units is not None else None
            ),
            time_window=edge.time_window,
            mode_switch_penalty=edge.mode_switch_penalty,
            distance_km=edge.distance_km,
            reversed=reversed,
        )

    def _to_route_option(
        self,
        node_sequence: list[str],
        edges: Iterable[TraversalEdge],
        weights: RouteWeights,
    ) -> RouteOptionRead:
        edge_list = list(edges)
        total_cost = round(sum(edge.cost for edge in edge_list), 3)
        total_time = round(sum(edge.time for edge in edge_list), 3)
        total_risk = round(sum(edge.risk for edge in edge_list), 3)
        score = round(self._score(total_cost, total_time, total_risk, weights), 3)
        modes = list(dict.fromkeys(edge.transport_mode for edge in edge_list))
        segments = [
            RouteSegmentRead(
                edge_id=edge.edge_id,
                from_node_id=edge.from_node_id,
                to_node_id=edge.to_node_id,
                transport_mode=edge.transport_mode,  # type: ignore[arg-type]
                cost=edge.cost,
                time=edge.time,
                risk=edge.risk,
                base_cost=edge.base_cost,
                base_time=edge.base_time,
                base_risk=edge.base_risk,
                predicted_delay=edge.predicted_delay,
                risk_penalty=edge.risk_penalty,
                mode_switch_penalty_applied=edge.mode_switch_penalty_applied,
                switching_delay_applied=edge.switching_delay_applied,
                time_window_violation_minutes=edge.time_window_violation_minutes,
                driver_penalty_applied=edge.driver_penalty_applied,
                capacity=edge.capacity,
                time_window=edge.time_window,
                distance_km=edge.distance_km,
                reversed=edge.reversed,
            )
            for edge in edge_list
        ]
        return RouteOptionRead(
            node_sequence=node_sequence,
            edge_sequence=[edge.edge_id for edge in edge_list],
            segments=segments,
            transport_modes=modes,  # type: ignore[arg-type]
            total_cost=total_cost,
            total_time=total_time,
            total_risk=total_risk,
            score=score,
            summary=f"{' -> '.join(node_sequence)} via {', '.join(modes) if modes else 'direct'}",
        )

    def _merge_paths(
        self,
        root_nodes: list[str],
        root_segments: list[RouteSegmentRead],
        spur: RouteOptionRead,
        weights: RouteWeights,
    ) -> RouteOptionRead:
        root_edges = [self._segment_to_edge(segment) for segment in root_segments]
        spur_edges = [self._segment_to_edge(segment) for segment in spur.segments]
        nodes = [*root_nodes, *spur.node_sequence[1:]]
        return self._to_route_option(nodes, [*root_edges, *spur_edges], weights)

    @staticmethod
    def _segment_to_edge(segment: RouteSegmentRead) -> TraversalEdge:
        return TraversalEdge(
            edge_id=segment.edge_id,
            from_node_id=segment.from_node_id,
            to_node_id=segment.to_node_id,
            transport_mode=segment.transport_mode,
            cost=segment.cost,
            time=segment.time,
            risk=segment.risk,
            base_cost=segment.base_cost if segment.base_cost is not None else segment.cost,
            base_time=segment.base_time if segment.base_time is not None else segment.time,
            base_risk=segment.base_risk if segment.base_risk is not None else segment.risk,
            predicted_delay=segment.predicted_delay,
            risk_penalty=segment.risk_penalty,
            capacity=segment.capacity,
            time_window=segment.time_window,
            distance_km=segment.distance_km,
            reversed=segment.reversed,
            mode_switch_penalty_applied=segment.mode_switch_penalty_applied,
            switching_delay_applied=segment.switching_delay_applied,
            time_window_violation_minutes=segment.time_window_violation_minutes,
            driver_penalty_applied=segment.driver_penalty_applied,
        )

    def _attach_business_metrics(
        self,
        routes: list[RouteOptionRead],
        baseline: RouteOptionRead,
    ) -> list[RouteOptionRead]:
        enriched: list[RouteOptionRead] = []
        for route in routes:
            fuel = self._estimate_fuel(route)
            metrics = RouteBusinessMetrics(
                cost=route.total_cost,
                time=route.total_time,
                risk=route.total_risk,
                fuel_estimate=fuel,
                co2_estimate=round(fuel * self.CO2_KG_PER_LITER, 2),
                cost_savings_vs_baseline=round(baseline.total_cost - route.total_cost, 2),
                time_saved_vs_baseline=round(baseline.total_time - route.total_time, 2),
            )
            enriched.append(route.model_copy(update={"business_metrics": metrics}))
        return enriched

    def _estimate_fuel(self, route: RouteOptionRead) -> float:
        fuel = 0.0
        for segment in route.segments:
            distance = segment.distance_km
            if distance is None:
                speed = self.MODE_SPEED_KMPH.get(segment.transport_mode, 42.0)
                distance = speed * ((segment.base_time or segment.time) / 60.0)
            fuel += distance * self.FUEL_LITERS_PER_KM.get(segment.transport_mode, 0.34)
        return round(fuel, 2)

    @staticmethod
    def _disabled_edges_for_root(
        paths: list[RouteOptionRead], root_nodes: list[str], spur_index: int
    ) -> set[str]:
        disabled: set[str] = set()
        for path in paths:
            if path.node_sequence[: len(root_nodes)] == root_nodes and len(path.edge_sequence) > spur_index:
                disabled.add(path.edge_sequence[spur_index])
        return disabled

    @staticmethod
    def _score(cost: float, time: float, risk: float, weights: RouteWeights) -> float:
        return weights.w1 * cost + weights.w2 * time + weights.w3 * risk

    @staticmethod
    def _signature(route: RouteOptionRead) -> str:
        return "|".join(route.node_sequence) + "::" + "|".join(route.edge_sequence)

    @staticmethod
    def _validate_graph(graph: LogisticsGraph, origin_node_id: str, destination_node_id: str) -> None:
        node_ids = {node.id for node in graph.nodes}
        if origin_node_id not in node_ids:
            raise ValueError(f"Unknown origin node: {origin_node_id}")
        if destination_node_id not in node_ids:
            raise ValueError(f"Unknown destination node: {destination_node_id}")
        if origin_node_id == destination_node_id:
            raise ValueError("Origin and destination must be different nodes")
