"""Logistics routes: graph fusion, routing, prediction, decision, assignment, reroute, telemetry."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app_state import (
    data_fusion_service, multimodal_graph_engine, logistics_prediction_engine,
    logistics_decision_engine, logistics_execution_service, telemetry_simulation_service,
    route_planner, driver_performance_service,
)
from database import get_session
from models import Shipment, LogisticsRoute, Vehicle
from schemas import (
    DataFusionRequest, DataFusionResponse,
    ComputeRoutesRequest, ComputeRoutesResponse,
    PredictionRequest, PredictionResponse,
    DecisionRequest, DecisionResponse,
    AssignRouteRequest, AssignmentResponse,
    RerouteRequest, RerouteResponse,
    TelemetrySimulationRequest, TelemetrySimulationResponse,
    LogisticsGraph, RouteWeights, RouteOptionRead,
)

logistics_router = APIRouter(tags=["Logistics"])


def resolve_logistics_graph(session: Session, graph: LogisticsGraph | None) -> LogisticsGraph:
    if graph is not None:
        try:
            fused = data_fusion_service.fuse(graph)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return LogisticsGraph(nodes=fused.nodes, edges=fused.edges, constraints=fused.constraints)
    db_graph = data_fusion_service.graph_from_db(session)
    if not db_graph.nodes or not db_graph.edges:
        raise HTTPException(status_code=400, detail="No logistics graph provided and no persisted nodes/edges are available")
    return db_graph


def compute_logistics_routes(
    *, session: Session, graph: LogisticsGraph | None, origin_node_id: str, destination_node_id: str,
    weights: RouteWeights, max_routes: int, driver_id: int | None = None,
    driver_reliability_score: float | None = None, driver_penalty_factor: float = 100.0,
    required_capacity: float = 0.0, switching_delay: float = 0.0, time_window_penalty: float = 10.0,
    apply_predictions: bool = True, delay_penalty_per_minute: float = 1.0, risk_penalty_factor: float = 500.0,
    port_context: dict | None = None, rail_context: dict | None = None,
    weather_context: dict | None = None, shipment_context: dict | None = None,
) -> tuple[LogisticsGraph, LogisticsGraph | None, list[RouteOptionRead], PredictionResponse | None]:
    resolved_graph = resolve_logistics_graph(session, graph)
    adjusted_graph: LogisticsGraph | None = None
    predictions: PredictionResponse | None = None
    routing_reliability = driver_reliability_score
    if driver_id is not None and routing_reliability is None:
        try:
            routing_reliability = driver_performance_service.get_or_compute_driver_metrics(session, driver_id).reliability_score
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        routing_graph = resolved_graph
        if apply_predictions:
            preliminary_routes = multimodal_graph_engine.compute_routes(resolved_graph, origin_node_id, destination_node_id, weights, max_routes=max_routes, required_capacity=required_capacity, switching_delay=switching_delay, time_window_penalty=time_window_penalty, driver_reliability_score=routing_reliability, driver_penalty_factor=driver_penalty_factor)
            if preliminary_routes:
                predictions = logistics_prediction_engine.predict(graph=resolved_graph, route_options=preliminary_routes, port_context=port_context, rail_context=rail_context, weather_context=weather_context, shipment_context=shipment_context)
                adjusted_graph = logistics_prediction_engine.adjust_graph_for_predictions(graph=resolved_graph, predictions=predictions, route_options=preliminary_routes, delay_penalty_per_minute=delay_penalty_per_minute, risk_penalty_factor=risk_penalty_factor)
                routing_graph = adjusted_graph
        routes = multimodal_graph_engine.compute_routes(routing_graph, origin_node_id, destination_node_id, weights, max_routes=max_routes, required_capacity=required_capacity, switching_delay=switching_delay, time_window_penalty=time_window_penalty, driver_reliability_score=routing_reliability, driver_penalty_factor=driver_penalty_factor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not routes:
        raise HTTPException(status_code=404, detail="No feasible route found")
    return resolved_graph, adjusted_graph, routes, predictions


@logistics_router.post("/api/fusion/graph", response_model=DataFusionResponse)
def fuse_logistics_graph(payload: DataFusionRequest, session: Session = Depends(get_session)) -> DataFusionResponse:
    try:
        fused = data_fusion_service.fuse(payload)
        if payload.persist:
            data_fusion_service.persist_graph(session, fused)
        return fused
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@logistics_router.post("/api/compute-routes", response_model=ComputeRoutesResponse)
def compute_routes(payload: ComputeRoutesRequest, session: Session = Depends(get_session)) -> ComputeRoutesResponse:
    if payload.graph is not None and payload.persist_graph:
        data_fusion_service.persist_graph(session, payload.graph)
    graph, adjusted_graph, routes, predictions = compute_logistics_routes(
        session=session, graph=payload.graph, origin_node_id=payload.origin_node_id,
        destination_node_id=payload.destination_node_id, weights=payload.weights,
        max_routes=payload.max_routes, driver_id=payload.driver_id,
        driver_reliability_score=payload.driver_reliability_score,
        driver_penalty_factor=payload.driver_penalty_factor,
        required_capacity=payload.required_capacity, switching_delay=payload.switching_delay,
        time_window_penalty=payload.time_window_penalty,
        apply_predictions=payload.prediction_enabled,
        delay_penalty_per_minute=payload.delay_penalty_per_minute,
        risk_penalty_factor=payload.risk_penalty_factor,
        port_context=payload.port_context, rail_context=payload.rail_context,
        weather_context=payload.weather_context, shipment_context=payload.shipment_context,
    )
    return ComputeRoutesResponse(
        graph=graph, adjusted_graph=adjusted_graph, shortest_path=routes[0],
        alternatives=routes[1:], constraints=graph.constraints, predictions=predictions,
    )


@logistics_router.post("/api/predict", response_model=PredictionResponse)
def predict_logistics(payload: PredictionRequest, session: Session = Depends(get_session)) -> PredictionResponse:
    graph = resolve_logistics_graph(session, payload.graph)
    route_options = payload.route_options
    if not route_options:
        if not payload.origin_node_id or not payload.destination_node_id:
            raise HTTPException(status_code=400, detail="Provide route_options or origin_node_id and destination_node_id")
        _, _, route_options, _ = compute_logistics_routes(
            session=session, graph=graph, origin_node_id=payload.origin_node_id,
            destination_node_id=payload.destination_node_id, weights=payload.weights,
            max_routes=payload.max_routes, apply_predictions=False,
        )
    response = logistics_prediction_engine.predict(
        graph=graph, route_options=route_options, port_context=payload.port_context,
        rail_context=payload.rail_context, weather_context=payload.weather_context,
        shipment_context=payload.shipment_context,
    )
    if payload.persist:
        logistics_prediction_engine.persist_predictions(session, response)
    return response


@logistics_router.post("/api/decide-route", response_model=DecisionResponse)
def decide_route(payload: DecisionRequest) -> DecisionResponse:
    try:
        return logistics_decision_engine.decide(
            route_options=payload.route_options, predictions=payload.predictions,
            delay_threshold_minutes=payload.delay_threshold_minutes,
            risk_threshold=payload.risk_threshold,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@logistics_router.post("/api/assign-route", response_model=AssignmentResponse)
def assign_route(payload: AssignRouteRequest, session: Session = Depends(get_session)) -> AssignmentResponse:
    if payload.graph is not None:
        data_fusion_service.persist_graph(session, payload.graph)
    try:
        assignment_payload = payload
        if assignment_payload.driver_id is None:
            vehicle = session.get(Vehicle, assignment_payload.vehicle_id) if assignment_payload.vehicle_id else None
            if vehicle is not None:
                assignment_payload = assignment_payload.model_copy(update={"driver_id": vehicle.driver_profile_id})
            else:
                metadata = assignment_payload.metadata or {}
                high_value = bool(metadata.get("high_value")) or float(metadata.get("cargo_value", 0) or 0) >= 100000
                time_sensitive = bool(metadata.get("time_sensitive")) or float(metadata.get("sla_minutes", 0) or 0) > 0
                preferred = driver_performance_service.recommend_driver_for_assignment(session, high_value=high_value, time_sensitive=time_sensitive)
                if preferred is not None:
                    assignment_payload = assignment_payload.model_copy(update={"driver_id": preferred.driver_id})
        return logistics_execution_service.assign_route(session, assignment_payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@logistics_router.post("/api/reroute", response_model=RerouteResponse)
def reroute_shipment(payload: RerouteRequest, session: Session = Depends(get_session)) -> RerouteResponse:
    shipment = session.get(Shipment, payload.shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if payload.graph is not None:
        data_fusion_service.persist_graph(session, payload.graph)

    origin_node_key = payload.current_location_node_id or shipment.current_location_node_key or shipment.origin_node_key
    destination_node_key = payload.destination_node_id or shipment.destination_node_key
    graph = resolve_logistics_graph(session, payload.graph)
    route_options = payload.route_options
    if not route_options:
        _, _, route_options, _ = compute_logistics_routes(
            session=session, graph=graph, origin_node_id=origin_node_key,
            destination_node_id=destination_node_key, weights=payload.weights,
            max_routes=payload.max_routes, driver_id=shipment.assigned_driver_id,
            required_capacity=payload.required_capacity, switching_delay=payload.switching_delay,
        )

    predictions = payload.predictions or logistics_prediction_engine.predict(graph=graph, route_options=route_options)
    decision = logistics_decision_engine.decide(
        route_options=route_options, predictions=predictions,
        delay_threshold_minutes=payload.delay_threshold_minutes,
    )

    previous_route = session.get(LogisticsRoute, shipment.current_route_id) if shipment.current_route_id is not None else None
    previous_route_option = logistics_execution_service.route_option_from_model(previous_route) if previous_route is not None else None
    improvement_score = logistics_decision_engine.improvement_score(previous_route_option, decision.recommended_route) if previous_route_option is not None else float("inf")

    if previous_route_option is not None and improvement_score <= payload.improvement_threshold:
        kept_reason = f"{decision.reasoning} Kept current route because improvement score {improvement_score:.2f} did not exceed threshold {payload.improvement_threshold:.2f}."
        decision = decision.model_copy(update={"recommended_route": previous_route_option, "reasoning": kept_reason, "switched": False})
        return RerouteResponse(shipment_id=shipment.id, previous_route=previous_route_option, new_route=previous_route_option, decision=decision, status="kept_current_route", rerouted=False, improvement_score=improvement_score)

    new_route = logistics_execution_service.create_reroute(session=session, shipment=shipment, route_option=decision.recommended_route, origin_node_key=origin_node_key, destination_node_key=destination_node_key)
    new_route_option = decision.recommended_route.model_copy(update={"route_id": new_route.id})
    decision = decision.model_copy(update={"recommended_route": new_route_option})
    return RerouteResponse(shipment_id=shipment.id, previous_route=previous_route_option, new_route=new_route_option, decision=decision, status=shipment.status, rerouted=True, improvement_score=improvement_score if improvement_score != float("inf") else 0.0)


@logistics_router.post("/api/telemetry/simulate", response_model=TelemetrySimulationResponse)
def simulate_logistics_telemetry(payload: TelemetrySimulationRequest) -> TelemetrySimulationResponse:
    return telemetry_simulation_service.simulate(route=payload.route, payload_tons=payload.payload_tons, shipment_id=payload.shipment_id, route_id=payload.route_id)