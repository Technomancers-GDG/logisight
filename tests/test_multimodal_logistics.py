from __future__ import annotations

from schemas import (
    DataFusionRequest,
    LogisticsEdgeInput,
    LogisticsGraph,
    LogisticsNodeInput,
    RouteWeights,
)
from services.logistics_data_fusion import DataFusionService
from services.logistics_decision_engine import LogisticsDecisionEngine
from services.logistics_prediction import LogisticsPredictionEngine
from services.driver_performance import DriverPerformanceService
from services.multimodal_graph_engine import MultimodalGraphEngine


def sample_graph_payload() -> dict:
    return sample_graph().model_dump()


def sample_graph() -> LogisticsGraph:
    return LogisticsGraph(
        nodes=[
            LogisticsNodeInput(id="mine-1", name="Mine", node_type="mine", city="Keonjhar"),
            LogisticsNodeInput(id="wh-1", name="Warehouse", node_type="warehouse", city="Nagpur"),
            LogisticsNodeInput(id="rail-1", name="Railhead", node_type="railhead", city="Raipur"),
            LogisticsNodeInput(
                id="port-1",
                name="Port",
                node_type="port",
                city="Paradip",
                metadata={"congestion_index": 0.9},
            ),
        ],
        edges=[
            LogisticsEdgeInput(
                id="mine-wh-road",
                from_node_id="mine-1",
                to_node_id="wh-1",
                transport_mode="road",
                cost=1200,
                time=240,
                risk=0.18,
            ),
            LogisticsEdgeInput(
                id="mine-rail-road",
                from_node_id="mine-1",
                to_node_id="rail-1",
                transport_mode="road",
                cost=600,
                time=120,
                risk=0.08,
            ),
            LogisticsEdgeInput(
                id="rail-port-rail",
                from_node_id="rail-1",
                to_node_id="port-1",
                transport_mode="rail",
                cost=900,
                time=300,
                risk=0.12,
            ),
            LogisticsEdgeInput(
                id="wh-port-water",
                from_node_id="wh-1",
                to_node_id="port-1",
                transport_mode="water",
                cost=700,
                time=420,
                risk=0.1,
            ),
        ],
        constraints={"max_risk": 0.75},
    )


def test_data_fusion_outputs_structured_graph() -> None:
    service = DataFusionService()
    graph = sample_graph()
    response = service.fuse(DataFusionRequest(**graph.model_dump()))

    assert response.node_count == 4
    assert response.edge_count == 4
    assert response.constraints == {"max_risk": 0.75}


def test_multimodal_graph_engine_prefers_weighted_shortest_path() -> None:
    engine = MultimodalGraphEngine()
    routes = engine.compute_routes(
        sample_graph(),
        "mine-1",
        "port-1",
        RouteWeights(w1=1.0, w2=1.0, w3=500.0),
        max_routes=2,
    )

    assert routes
    assert routes[0].node_sequence == ["mine-1", "rail-1", "port-1"]
    assert routes[0].transport_modes == ["road", "rail"]
    assert routes[0].score > 0


def test_prediction_and_decision_auto_switch_when_delay_exceeds_threshold() -> None:
    graph = sample_graph()
    routes = MultimodalGraphEngine().compute_routes(
        graph,
        "mine-1",
        "port-1",
        RouteWeights(w1=1.0, w2=1.0, w3=1.0),
        max_routes=2,
    )
    predictions = LogisticsPredictionEngine().predict(
        graph=graph,
        route_options=routes,
        port_context={"port-1": {"queue_hours": 5, "congestion_index": 1.0}},
    )
    decision = LogisticsDecisionEngine().decide(
        route_options=routes,
        predictions=predictions,
        delay_threshold_minutes=120,
    )

    assert decision.delay_exceeded is True
    assert decision.recommended_route.node_sequence
    assert "delay" in decision.reasoning


def test_compute_routes_api_accepts_inline_graph() -> None:
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    response = client.post(
        "/api/compute-routes",
        json={
            "origin_node_id": "mine-1",
            "destination_node_id": "port-1",
            "graph": sample_graph_payload(),
            "weights": {"w1": 1, "w2": 1, "w3": 1},
            "max_routes": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["shortest_path"]["node_sequence"][0] == "mine-1"
    assert payload["shortest_path"]["node_sequence"][-1] == "port-1"
    assert payload["predictions"]["port_delays"]
    assert payload["shortest_path"]["business_metrics"]["fuel_estimate"] > 0


def test_constraint_routing_rejects_edges_below_required_capacity() -> None:
    graph = LogisticsGraph(
        nodes=[
            LogisticsNodeInput(id="a", name="A", node_type="mine"),
            LogisticsNodeInput(id="b", name="B", node_type="railhead"),
            LogisticsNodeInput(id="c", name="C", node_type="port"),
        ],
        edges=[
            LogisticsEdgeInput(
                id="low-cap-rail",
                from_node_id="a",
                to_node_id="c",
                transport_mode="rail",
                cost=100,
                time=60,
                risk=0.05,
                capacity=10,
            ),
            LogisticsEdgeInput(
                id="road-a-b",
                from_node_id="a",
                to_node_id="b",
                transport_mode="road",
                cost=300,
                time=90,
                risk=0.1,
                capacity=100,
            ),
            LogisticsEdgeInput(
                id="road-b-c",
                from_node_id="b",
                to_node_id="c",
                transport_mode="road",
                cost=300,
                time=90,
                risk=0.1,
                capacity=100,
            ),
        ],
    )

    routes = MultimodalGraphEngine().compute_routes(
        graph,
        "a",
        "c",
        RouteWeights(w1=1, w2=1, w3=1),
        required_capacity=50,
    )

    assert routes[0].edge_sequence == ["road-a-b", "road-b-c"]


def test_mode_switch_and_time_window_penalties_are_applied_to_segments() -> None:
    graph = LogisticsGraph(
        nodes=[
            LogisticsNodeInput(id="a", name="A", node_type="warehouse"),
            LogisticsNodeInput(id="b", name="B", node_type="railhead"),
            LogisticsNodeInput(id="c", name="C", node_type="port"),
        ],
        edges=[
            LogisticsEdgeInput(
                id="road-leg",
                from_node_id="a",
                to_node_id="b",
                transport_mode="road",
                cost=100,
                time=80,
                risk=0.05,
                time_window=(0, 200),
            ),
            LogisticsEdgeInput(
                id="rail-leg",
                from_node_id="b",
                to_node_id="c",
                transport_mode="rail",
                cost=100,
                time=80,
                risk=0.05,
                mode_switch_penalty=250,
                time_window=(0, 120),
            ),
        ],
    )

    route = MultimodalGraphEngine().compute_routes(
        graph,
        "a",
        "c",
        RouteWeights(w1=1, w2=1, w3=1),
        switching_delay=30,
        time_window_penalty=5,
    )[0]

    rail_segment = route.segments[-1]
    assert rail_segment.mode_switch_penalty_applied == 250
    assert rail_segment.switching_delay_applied == 30
    assert rail_segment.time_window_violation_minutes > 0


def test_driver_reliability_penalty_changes_route_cost() -> None:
    graph = sample_graph()
    engine = MultimodalGraphEngine()

    high_reliability = engine.compute_routes(
        graph,
        "mine-1",
        "port-1",
        RouteWeights(w1=1, w2=1, w3=1),
        max_routes=3,
        driver_reliability_score=0.95,
        driver_penalty_factor=100,
    )[0]
    low_reliability = engine.compute_routes(
        graph,
        "mine-1",
        "port-1",
        RouteWeights(w1=1, w2=1, w3=1),
        max_routes=3,
        driver_reliability_score=0.55,
        driver_penalty_factor=100,
    )[0]

    assert low_reliability.total_cost > high_reliability.total_cost
    assert low_reliability.segments[0].driver_penalty_applied > high_reliability.segments[0].driver_penalty_applied


def test_driver_performance_scoring_is_explainable() -> None:
    service = DriverPerformanceService()

    assert service.classify(0.82) == "high"
    assert service.classify(0.61) == "medium"
    assert service.classify(0.40) == "low"
    assert service._efficiency_score(actual_time=150, expected_time=100) < service._efficiency_score(actual_time=100, expected_time=100)
    assert service._idle_score(idle_time=35, expected_time=100) < service._idle_score(idle_time=5, expected_time=100)
    assert service._adherence_score(route_deviation=0.2) < service._adherence_score(route_deviation=0.02)
