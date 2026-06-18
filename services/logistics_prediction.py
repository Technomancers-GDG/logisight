from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from typing import Any

from sqlalchemy.orm import Session

from models import Prediction
from schemas import (
    LogisticsEdgeInput,
    LogisticsGraph,
    PortDelayPrediction,
    PredictionResponse,
    RakeAvailabilityPrediction,
    RouteOptionRead,
    RouteRiskPrediction,
)


class LogisticsPredictionEngine:
    """Rule-based prediction service with deterministic mock fallbacks."""

    def predict(
        self,
        *,
        graph: LogisticsGraph,
        route_options: list[RouteOptionRead],
        port_context: dict[str, Any] | None = None,
        rail_context: dict[str, Any] | None = None,
        weather_context: dict[str, Any] | None = None,
        shipment_context: dict[str, Any] | None = None,
    ) -> PredictionResponse:
        port_context = port_context or {}
        rail_context = rail_context or {}
        weather_context = weather_context or {}
        shipment_context = shipment_context or {}
        node_by_id = {node.id: node for node in graph.nodes}

        port_ids = {
            node_id
            for route in route_options
            for node_id in route.node_sequence
            if node_by_id.get(node_id) and node_by_id[node_id].node_type == "port"
        }
        railhead_ids = {
            node_id
            for route in route_options
            for node_id in route.node_sequence
            if node_by_id.get(node_id) and node_by_id[node_id].node_type == "railhead"
        }

        port_delays = [
            self._predict_port_delay(node_id, node_by_id[node_id].metadata, port_context)
            for node_id in sorted(port_ids)
        ]
        rake_availability = [
            self._predict_rakes(node_id, node_by_id[node_id].metadata, rail_context)
            for node_id in sorted(railhead_ids)
        ]
        route_risks = [
            self._predict_route_risk(
                route_index=index,
                route=route,
                port_delays=port_delays,
                rake_availability=rake_availability,
                weather_context=weather_context,
                shipment_context=shipment_context,
            )
            for index, route in enumerate(route_options)
        ]

        return PredictionResponse(
            generated_at=datetime.now(UTC).replace(tzinfo=None),
            port_delays=port_delays,
            rake_availability=rake_availability,
            route_risks=route_risks,
            assumptions=[
                "Port delay uses queue/congestion metadata when present, otherwise deterministic mock congestion.",
                "Rake availability uses provided rail context when present, otherwise deterministic mock availability.",
                "Route risk combines edge risk, predicted waiting time, weather severity, and cargo sensitivity.",
            ],
        )

    def persist_predictions(
        self,
        session: Session,
        response: PredictionResponse,
        *,
        shipment_id: int | None = None,
        route_id: int | None = None,
    ) -> None:
        for prediction in response.port_delays:
            session.add(
                Prediction(
                    shipment_id=shipment_id,
                    route_id=route_id,
                    prediction_type="port_delay",
                    target_key=prediction.node_id,
                    value=prediction.delay_minutes,
                    confidence=prediction.confidence,
                    payload=prediction.model_dump(),
                )
            )
        for prediction in response.rake_availability:
            session.add(
                Prediction(
                    shipment_id=shipment_id,
                    route_id=route_id,
                    prediction_type="rake_availability",
                    target_key=prediction.node_id,
                    value=prediction.available_rakes,
                    confidence=prediction.confidence,
                    payload=prediction.model_dump(),
                )
            )
        for prediction in response.route_risks:
            session.add(
                Prediction(
                    shipment_id=shipment_id,
                    route_id=route_id,
                    prediction_type="route_risk",
                    target_key=prediction.route_signature,
                    value=prediction.risk,
                    confidence=prediction.confidence,
                    payload=prediction.model_dump(),
                )
            )
        session.commit()

    def adjust_graph_for_predictions(
        self,
        *,
        graph: LogisticsGraph,
        predictions: PredictionResponse,
        route_options: list[RouteOptionRead],
        delay_penalty_per_minute: float = 1.0,
        risk_penalty_factor: float = 500.0,
    ) -> LogisticsGraph:
        """Return a graph whose edge weights already include prediction impact."""
        delay_by_node = {prediction.node_id: prediction.delay_minutes for prediction in predictions.port_delays}
        for prediction in predictions.rake_availability:
            delay_by_node[prediction.node_id] = delay_by_node.get(prediction.node_id, 0.0) + prediction.wait_minutes

        risk_penalty_by_edge: dict[str, float] = {}
        risk_by_edge: dict[str, float] = {}
        for route_risk in predictions.route_risks:
            if route_risk.route_index >= len(route_options):
                continue
            route = route_options[route_risk.route_index]
            edge_count = max(len(route.edge_sequence), 1)
            per_edge_penalty = route_risk.risk * risk_penalty_factor / edge_count
            for edge_id in route.edge_sequence:
                risk_penalty_by_edge[edge_id] = max(risk_penalty_by_edge.get(edge_id, 0.0), per_edge_penalty)
                risk_by_edge[edge_id] = max(risk_by_edge.get(edge_id, 0.0), route_risk.risk)

        adjusted_edges: list[LogisticsEdgeInput] = []
        for edge in graph.edges:
            edge_id = edge.id or f"{edge.from_node_id}:{edge.to_node_id}:{edge.transport_mode}"
            predicted_delay = delay_by_node.get(edge.to_node_id, 0.0)
            risk_penalty = risk_penalty_by_edge.get(edge_id, 0.0)
            route_risk = risk_by_edge.get(edge_id, 0.0)
            metadata = {
                **dict(edge.metadata),
                "prediction_adjustment": {
                    "base_cost": edge.cost,
                    "base_time": edge.time,
                    "base_risk": edge.risk,
                    "predicted_delay": predicted_delay,
                    "delay_penalty": predicted_delay * delay_penalty_per_minute,
                    "risk_penalty": risk_penalty,
                    "route_risk": route_risk,
                },
            }
            adjusted_edges.append(
                edge.model_copy(
                    update={
                        "cost": round(edge.cost + predicted_delay * delay_penalty_per_minute + risk_penalty, 3),
                        "time": round(edge.time + predicted_delay, 3),
                        "risk": round(min(1.0, edge.risk + route_risk * 0.15), 3),
                        "metadata": metadata,
                    }
                )
            )

        return LogisticsGraph(
            nodes=graph.nodes,
            edges=adjusted_edges,
            constraints={
                **dict(graph.constraints),
                "prediction_adjusted": True,
                "delay_penalty_per_minute": delay_penalty_per_minute,
                "risk_penalty_factor": risk_penalty_factor,
            },
        )

    def _predict_port_delay(
        self,
        node_id: str,
        metadata: dict[str, Any],
        port_context: dict[str, Any],
    ) -> PortDelayPrediction:
        context = port_context.get(node_id, {}) if isinstance(port_context.get(node_id, {}), dict) else {}
        queue_hours = float(context.get("queue_hours", metadata.get("queue_hours", 0.0)) or 0.0)
        congestion = float(
            context.get(
                "congestion_index",
                metadata.get("congestion_index", self._stable_fraction(f"port:{node_id}")),
            )
            or 0.0
        )
        congestion = min(1.0, max(0.0, congestion))
        delay = queue_hours * 60 + 30 + congestion * 210
        severity = "severe" if delay >= 180 else "moderate" if delay >= 90 else "normal"
        factors = [f"congestion_index={congestion:.2f}"]
        if queue_hours:
            factors.append(f"queue_hours={queue_hours:.1f}")
        return PortDelayPrediction(
            node_id=node_id,
            delay_minutes=round(delay, 2),
            confidence=round(0.62 + congestion * 0.25, 2),
            severity=severity,
            factors=factors,
        )

    def _predict_rakes(
        self,
        node_id: str,
        metadata: dict[str, Any],
        rail_context: dict[str, Any],
    ) -> RakeAvailabilityPrediction:
        context = rail_context.get(node_id, {}) if isinstance(rail_context.get(node_id, {}), dict) else {}
        available = int(
            context.get(
                "available_rakes",
                metadata.get("available_rakes", round(self._stable_fraction(f"rail:{node_id}") * 9)),
            )
            or 0
        )
        demand = int(context.get("required_rakes", metadata.get("required_rakes", 3)) or 3)
        shortage = max(0, demand - available)
        wait_minutes = shortage * 75.0
        status = "constrained" if shortage >= 2 else "tight" if shortage == 1 else "available"
        return RakeAvailabilityPrediction(
            node_id=node_id,
            available_rakes=max(0, available),
            wait_minutes=round(wait_minutes, 2),
            confidence=0.7,
            status=status,
        )

    def _predict_route_risk(
        self,
        *,
        route_index: int,
        route: RouteOptionRead,
        port_delays: list[PortDelayPrediction],
        rake_availability: list[RakeAvailabilityPrediction],
        weather_context: dict[str, Any],
        shipment_context: dict[str, Any],
    ) -> RouteRiskPrediction:
        route_nodes = set(route.node_sequence)
        port_delay = sum(p.delay_minutes for p in port_delays if p.node_id in route_nodes)
        rail_wait = sum(r.wait_minutes for r in rake_availability if r.node_id in route_nodes)
        edge_risk = min(1.0, route.total_risk / max(len(route.segments), 1))
        weather_severity = float(weather_context.get("severity", weather_context.get("risk", 0.0)) or 0.0)
        cargo_sensitivity = float(shipment_context.get("risk_sensitivity", 0.0) or 0.0)

        risk = min(
            1.0,
            edge_risk * 0.62
            + min(port_delay / 360.0, 1.0) * 0.18
            + min(rail_wait / 240.0, 1.0) * 0.12
            + min(max(weather_severity, 0.0), 1.0) * 0.06
            + min(max(cargo_sensitivity, 0.0), 1.0) * 0.02,
        )
        predicted_delay = port_delay + rail_wait + weather_severity * 45 + risk * 30
        factors = [f"edge_risk={edge_risk:.2f}"]
        if port_delay:
            factors.append(f"port_delay_minutes={port_delay:.0f}")
        if rail_wait:
            factors.append(f"rail_wait_minutes={rail_wait:.0f}")
        if weather_severity:
            factors.append(f"weather_severity={weather_severity:.2f}")

        return RouteRiskPrediction(
            route_index=route_index,
            route_signature=self.route_signature(route),
            risk=round(risk, 3),
            predicted_delay_minutes=round(predicted_delay, 2),
            confidence=round(0.66 + min(len(route.segments), 5) * 0.03, 2),
            factors=factors,
        )

    @staticmethod
    def route_signature(route: RouteOptionRead) -> str:
        return "|".join(route.node_sequence)

    @staticmethod
    def _stable_fraction(key: str) -> float:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) / 0xFFFFFFFF
