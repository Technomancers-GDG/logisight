"""AI/ML routes: RL decision engine, forecasting, multi-objective optimization, inventory."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from app_state import (
    simulation_engine, forecast_service, inventory_optimizer,
    route_planner, logistics_prediction_engine,
)
from database import get_session
from models import (
    NewsEvent, Facility, Objective, Vehicle, MetricsSnapshot, Recommendation, RouteTemplate,
)
from schemas import (
    RLDecisionRequest, RLDecisionResponse,
    RiskForecastRead, ParetoFrontRead,
    InventoryForecastRead, ProactiveDispatchRead,
    MetricsSummary, PredictionRequest, PredictionResponse,
)
from services.rl_decision_engine import get_rl_engine, StateVector
from services.multi_objective_optimizer import NSGA2Optimizer

ai_router = APIRouter(tags=["AI & Intelligence"])


# --- RL Decision Engine ---
@ai_router.post("/api/ai/rl-decision", response_model=RLDecisionResponse)
def rl_decision(payload: RLDecisionRequest) -> RLDecisionResponse:
    if not settings.use_rl_engine:
        raise HTTPException(status_code=503, detail="RL engine is disabled")
    engine = get_rl_engine()
    state = StateVector.from_sim_context(
        facility_utilization=payload.facility_utilization, route_risk=payload.route_risk,
        eta_multiplier=payload.eta_multiplier, sla_remaining_minutes=payload.sla_remaining_minutes,
        sla_total_minutes=payload.sla_total_minutes, payload_capacity=payload.payload_capacity,
        facility_capacity=payload.facility_capacity, priority=payload.priority,
        port_pressure=payload.port_pressure, weather_severity=payload.weather_severity,
        news_severity=payload.news_severity, simulation_hour=payload.simulation_hour,
    )
    action, confidence = engine.select_action(state, payload.valid_actions)
    return RLDecisionResponse(action=action, confidence=confidence, action_probs=engine.get_action_confidence(state))


@ai_router.post("/api/ai/rl-train")
def rl_train() -> dict[str, Any]:
    if not settings.use_rl_engine:
        raise HTTPException(status_code=503, detail="RL engine is disabled")
    engine = get_rl_engine()
    result = engine.train_step_update()
    if result is None:
        return {"status": "insufficient_data", "buffer_size": len(engine.replay_buffer)}
    engine.save_weights()
    return {"status": "trained", **result}


# --- Forecasting ---
@ai_router.get("/api/forecast/risk", response_model=list[RiskForecastRead])
def risk_forecast(
    hours: int = Query(default=12, ge=1, le=72), session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    cities = {f.city for f in session.scalars(select(Facility)).all()}
    sim_date = simulation_engine.simulation_time.date()
    data = forecast_service.get_heatmap_data(session, cities, forecast_hours=hours, reference_date=sim_date)
    return [RiskForecastRead(**d).model_dump() for d in data]


@ai_router.get("/api/forecast/city/{city}")
def city_forecast(
    city: str, hours: int = Query(default=12, ge=1, le=72), session: Session = Depends(get_session),
) -> dict[str, Any] | None:
    sim_date = simulation_engine.simulation_time.date()
    fc = forecast_service.forecast_city(session, city, forecast_hours=hours, reference_date=sim_date)
    if fc is None:
        raise HTTPException(status_code=404, detail=f"No forecast data for {city}")
    return {
        "city": fc.city, "predicted_route_risk": fc.predicted_route_risk,
        "predicted_eta_multiplier": fc.predicted_eta_multiplier,
        "predicted_closure_risk": fc.predicted_closure_risk, "confidence": fc.confidence,
        "contributing_factors": fc.contributing_factors, "forecast_time": fc.forecast_time.isoformat(),
    }


# --- Multi-Objective Optimization ---
@ai_router.get("/api/optimizer/pareto-front")
def get_pareto_front(session: Session = Depends(get_session)) -> dict[str, Any]:
    simulation_engine.load_state(session)
    points: list[dict[str, Any]] = []
    for objective in [o for o in simulation_engine.objectives.values() if o.active][:25]:
        vehicle_id = objective.assigned_vehicle_ids[0] if objective.assigned_vehicle_ids else None
        if vehicle_id is None:
            continue
        vehicle = simulation_engine.vehicles.get(vehicle_id)
        if vehicle is None:
            continue
        current_facility = simulation_engine.facilities.get(vehicle.current_facility_id or objective.origin_facility_id)
        if current_facility is None:
            continue
        destination_ids = [objective.destination_facility_id, *objective.fallback_facility_ids]
        route_data: dict[int, RouteTemplate] = {}
        risk_lookup: dict[int, dict[str, float]] = {}
        for dest_id in destination_ids:
            dest = simulation_engine.facilities.get(dest_id)
            if dest is None:
                continue
            route = route_planner.get_or_create_template(session, current_facility, dest)
            route_data[dest_id] = route
            risk_lookup[dest_id] = simulation_engine._route_risk(current_facility.city, dest.city)
        if not route_data:
            continue
        decision = simulation_engine.decision_engine.score_dispatch_options(
            sim_time=simulation_engine.simulation_time, vehicle=vehicle, objective=objective,
            current_facility=current_facility, facilities=simulation_engine.facilities,
            port_links=simulation_engine.port_links, inbound_reserved=simulation_engine.inbound_reserved,
            route_data=route_data, risk_lookup=risk_lookup,
        )
        points.append({
            "co2": decision.breakdown.get("co2_delta_kg", 0.0),
            "delivery_time": decision.travel_minutes * decision.eta_multiplier,
            "cost": decision.score, "action": decision.action, "objective": objective.name,
            "vehicle": vehicle.identifier,
            "overload_risk": decision.breakdown.get("overload_risk", 0.0),
            "sla_penalty": decision.breakdown.get("sla_penalty", 0.0),
        })

    pareto_indices = set()
    for i, p in enumerate(points):
        dominated = False
        for j, q in enumerate(points):
            if i == j:
                continue
            if q["cost"] <= p["cost"] and q["delivery_time"] <= p["delivery_time"] and q["co2"] <= p["co2"]:
                if q["cost"] < p["cost"] or q["delivery_time"] < p["delivery_time"] or q["co2"] < p["co2"]:
                    dominated = True
                    break
        if not dominated:
            pareto_indices.add(i)
    for i, p in enumerate(points):
        p["is_pareto"] = i in pareto_indices
    return {"points": points, "pareto_count": len(pareto_indices), "total": len(points)}


@ai_router.post("/api/ai/optimize-dispatch", response_model=list[ParetoFrontRead])
def optimize_dispatch(session: Session = Depends(get_session)) -> list[ParetoFrontRead]:
    if not settings.use_nsga2_optimizer:
        raise HTTPException(status_code=503, detail="NSGA-II optimizer is disabled")
    objectives = session.scalars(select(Objective).where(Objective.active.is_(True))).all()
    vehicles = session.scalars(select(Vehicle)).all()
    if not objectives or not vehicles:
        raise HTTPException(status_code=400, detail="No active objectives or vehicles")

    available_destinations = [
        [objective.destination_facility_id, *objective.fallback_facility_ids] for objective in objectives
    ]

    def eval_fn(genome):
        total_time = total_co2 = overload = sla_violations = total_cost = 0.0
        for gene, objective in zip(genome, objectives):
            duration = 120.0
            if gene.action in ("reroute_warehouse", "reroute_port"):
                duration *= 1.15
                total_co2 += 5.0
            elif gene.action == "wait":
                duration += 40.0
            elif gene.action == "defer_dispatch":
                duration += objective.dispatch_interval_minutes
            total_time += duration
            if duration > objective.sla_minutes:
                sla_violations += 1.0
            total_cost += duration * 0.5 + overload * 10.0
        return [total_time, total_co2, overload, sla_violations, total_cost]

    optimizer = NSGA2Optimizer(population_size=40, generations=20)
    pareto = optimizer.optimize(len(objectives), available_destinations, eval_fn)
    return [
        ParetoFrontRead(
            objectives=ind.objectives.tolist(),
            genome=[{"action": g.action, "destination_id": g.destination_id} for g in ind.genome],
            rank=ind.rank, crowding_distance=ind.crowding_distance,
        ) for ind in pareto
    ]


# --- Inventory ---
@ai_router.get("/api/inventory/forecasts", response_model=list[InventoryForecastRead])
def inventory_forecasts(session: Session = Depends(get_session)) -> list[InventoryForecastRead]:
    return [
        InventoryForecastRead(
            facility_id=f.facility_id, facility_name=f.facility_name,
            predicted_demand_units=f.predicted_demand_units, safety_stock_units=f.safety_stock_units,
            reorder_point=f.reorder_point, recommended_dispatch_count=f.recommended_dispatch_count,
            confidence=f.confidence, forecast_period_hours=f.forecast_period_hours, trend=f.trend,
        ) for f in inventory_optimizer.get_all_forecasts(session)
    ]


@ai_router.get("/api/inventory/proactive-dispatches", response_model=list[ProactiveDispatchRead])
def proactive_dispatches(session: Session = Depends(get_session)) -> list[ProactiveDispatchRead]:
    return [
        ProactiveDispatchRead(
            origin_facility_id=r.origin_facility_id, destination_facility_id=r.destination_facility_id,
            recommended_units=r.recommended_units, urgency=r.urgency, reason=r.reason, eta_hours=r.eta_hours,
        ) for r in inventory_optimizer.recommend_proactive_dispatches(session)
    ]


# --- Metrics ---
@ai_router.get("/api/metrics/sdg", response_model=MetricsSummary)
def sdg_metrics(session: Session = Depends(get_session)) -> MetricsSummary:
    snapshot = session.scalar(select(MetricsSnapshot).order_by(MetricsSnapshot.captured_at.desc()).limit(1))
    current = simulation_engine.current_metrics
    if snapshot is None:
        return current
    return MetricsSummary(
        co2_saved_kg=snapshot.co2_saved_kg, idle_minutes_prevented=snapshot.idle_minutes_prevented,
        on_time_delivery_pct=snapshot.on_time_delivery_pct,
        warehouse_utilization_pct=snapshot.warehouse_utilization_pct,
        reroute_count=snapshot.reroute_count, active_trucks=snapshot.active_trucks,
        queued_trucks=snapshot.queued_trucks,
        stockouts_prevented=getattr(snapshot, "stockouts_prevented", current.stockouts_prevented),
        critical_deliveries_saved=getattr(snapshot, "critical_deliveries_saved", current.critical_deliveries_saved),
        beneficiary_locations_served=getattr(snapshot, "beneficiary_locations_served", current.beneficiary_locations_served),
        spoilage_or_wastage_prevented=getattr(snapshot, "spoilage_or_wastage_prevented", current.spoilage_or_wastage_prevented),
    )


@ai_router.get("/api/metrics/ai-activity")
def ai_activity_metrics(session: Session = Depends(get_session)) -> dict[str, Any]:
    metrics = simulation_engine.current_metrics
    rl_stats = {"enabled": settings.use_rl_engine, "train_step": 0, "epsilon": 1.0, "replay_buffer_size": 0}
    if settings.use_rl_engine:
        try:
            engine = get_rl_engine()
            rl_stats.update({"train_step": engine.train_step, "epsilon": round(engine.epsilon, 4), "replay_buffer_size": len(engine.replay_buffer)})
        except Exception:
            pass

    recs = session.scalars(select(Recommendation).order_by(Recommendation.created_at.desc()).limit(50)).all()
    action_counts: dict[str, int] = {}
    accepted = ignored = 0
    for rec in recs:
        action_counts[rec.action] = action_counts.get(rec.action, 0) + 1
        if rec.status == "accepted":
            accepted += 1
        elif rec.status == "ignored":
            ignored += 1

    cascade_events = session.scalars(
        select(NewsEvent).where(
            NewsEvent.category.in_(["Autonomous Cascade Detection", "Cascade Propagation"]),
            NewsEvent.simulation_date >= simulation_engine.simulation_time.date(),
        )
    ).all()

    return {
        "reroute_count": metrics.reroute_count, "co2_saved_kg": round(metrics.co2_saved_kg, 2),
        "idle_minutes_prevented": round(metrics.idle_minutes_prevented, 1),
        "stockouts_prevented": metrics.stockouts_prevented,
        "on_time_delivery_pct": metrics.on_time_delivery_pct,
        "rl_engine": rl_stats,
        "recent_action_breakdown": action_counts,
        "driver_acceptance_rate": round(
            accepted / max(accepted + ignored, 1) * 100, 1
        ),
        "cascade_detections_today": len(cascade_events),
        "completed_trips": simulation_engine.completed_trips,
    }

from schemas.ai import AIChatRequest, AIChatResponse
from services.ai_service import chat_stream
from fastapi.responses import StreamingResponse

@ai_router.post("/api/ai/chat")
async def ai_chat(request: Request, payload: AIChatRequest, session: Session = Depends(get_session)):
    """
    AI chat with streaming support and automatic fallback.
    
    When stream=true (default): returns SSE stream with chunk/meta/done/error events.
    When stream=false: returns a single JSON AIChatResponse.
    """
    async def event_stream():
        import json
        async for event in chat_stream(
            query=payload.query,
            history=payload.history or [],
            vehicle_id=payload.vehicle_id,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    if payload.stream:
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming fallback for legacy clients
    full_text = ""
    model_used = ""
    suggestions = []
    async for event in chat_stream(
        query=payload.query,
        history=payload.history or [],
        vehicle_id=payload.vehicle_id,
    ):
        if event["type"] == "chunk":
            full_text += event["content"]
        elif event["type"] == "meta":
            model_used = event.get("model", "")
            suggestions = event.get("suggestions", [])
        elif event["type"] == "error":
            raise HTTPException(status_code=503, detail=event.get("detail", "AI service unavailable"))

    return AIChatResponse(response=full_text, model=model_used, suggestions=suggestions)
