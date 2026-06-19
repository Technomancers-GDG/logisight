"""Driver-facing routes: mobile snapshot, decisions, incidents, and performance metrics."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_state import simulation_engine
from database import get_session
from models import (
    DriverDecision,
    DriverIncident,
    DriverMetric,
    DriverProfile,
    NewsEvent,
    Objective,
    Recommendation,
    Vehicle,
)
from schemas import (
    DriverDecisionRead,
    DriverIncidentCreate,
    DriverIncidentRead,
    DriverInstructionRead,
    DriverMetricsRead,
    DriverMobileSnapshot,
    DriverResponseRequest,
    RecommendationDecisionRequest,
    RecommendationRead,
    SpotlightRequest,
)

driver_router = APIRouter(tags=["Driver"])


def normalize_incident_impact_type(incident_type: str) -> str:
    mapping = {
        "road_blockage": "road_blockage", "blockage": "road_blockage",
        "strike": "labor_disruption", "delay": "logistics_delay",
        "port_congestion": "port_congestion", "weather": "weather_disruption",
    }
    return mapping.get(incident_type.strip().lower().replace(" ", "_"), "logistics_disruption")


# --- Recommendations ---
@driver_router.get("/api/recommendations", response_model=list[RecommendationRead])
def list_recommendations(session: Session = Depends(get_session)) -> list[Recommendation]:
    return session.scalars(
        select(Recommendation).order_by(Recommendation.created_at.desc()).limit(100)
    ).all()


@driver_router.post("/api/recommendations/{recommendation_id}/decision", response_model=DriverDecisionRead)
def recommendation_decision(
    recommendation_id: int,
    payload: RecommendationDecisionRequest,
    session: Session = Depends(get_session),
) -> DriverDecision:
    recommendation = session.get(Recommendation, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    existing = session.scalar(select(DriverDecision).where(DriverDecision.recommendation_id == recommendation.id))
    if existing is not None:
        return existing

    vehicle = session.get(Vehicle, recommendation.vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    driver = session.get(DriverProfile, vehicle.driver_profile_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")

    backend_decision = "accepted" if payload.decision == "accept" else "ignored"
    recommendation.status = backend_decision
    rating_delta = 0.05 if backend_decision == "accepted" else -0.08
    driver.override_rating = round(max(0.2, driver.override_rating + rating_delta), 3)

    decision = DriverDecision(
        recommendation_id=recommendation.id, driver_profile_id=driver.id, vehicle_id=vehicle.id,
        decision=backend_decision,
        actual_trip_cost=recommendation.recommended_cost if backend_decision == "accepted" else recommendation.baseline_cost,
        recommended_trip_cost=recommendation.recommended_cost, rating_delta=rating_delta,
        note="Driver accepted mobile recommendation." if backend_decision == "accepted" else "Driver ignored mobile recommendation.",
    )
    session.add(decision)
    session.commit()
    session.refresh(decision)
    return decision


# --- Driver Decisions ---
@driver_router.get("/api/driver-decisions", response_model=list[DriverDecisionRead])
def list_driver_decisions(session: Session = Depends(get_session)) -> list[DriverDecision]:
    return session.scalars(select(DriverDecision).order_by(DriverDecision.decided_at.desc()).limit(100)).all()


# --- Driver Mobile ---
@driver_router.get("/api/driver/{driver_id}/mobile", response_model=DriverMobileSnapshot)
def driver_mobile_snapshot(driver_id: int, session: Session = Depends(get_session)) -> DriverMobileSnapshot:
    driver = session.get(DriverProfile, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")

    driver_vehicles = session.scalars(select(Vehicle).where(Vehicle.driver_profile_id == driver_id)).all()
    vehicle_ids = {vehicle.id for vehicle in driver_vehicles}
    vehicle_lookup = {vehicle.id: vehicle for vehicle in driver_vehicles}
    objective_lookup = {objective.id: objective for objective in session.scalars(select(Objective)).all()}

    recent_recommendations = session.scalars(select(Recommendation).order_by(Recommendation.created_at.desc()).limit(200)).all()
    pending_instructions: list[DriverInstructionRead] = []
    for rec in recent_recommendations:
        if rec.vehicle_id not in vehicle_ids or rec.status != "suggested":
            continue
        vehicle = vehicle_lookup[rec.vehicle_id]
        objective = objective_lookup.get(rec.objective_id)
        pending_instructions.append(DriverInstructionRead(
            recommendation_id=rec.id, created_at=rec.created_at, vehicle_id=vehicle.id,
            vehicle_identifier=vehicle.identifier, objective_name=objective.name if objective else "Unassigned Objective",
            action=rec.action, explanation=rec.explanation, status=rec.status,
        ))
        if len(pending_instructions) >= 20:
            break

    recent_incidents = session.scalars(
        select(DriverIncident).where(DriverIncident.driver_profile_id == driver_id)
        .order_by(DriverIncident.reported_at.desc()).limit(20)
    ).all()

    return DriverMobileSnapshot(
        driver_id=driver.id, driver_name=driver.name, override_rating=driver.override_rating,
        confidence=driver.confidence, pending_instructions=pending_instructions, recent_incidents=recent_incidents,
    )


# --- Driver Decision Submit ---
@driver_router.post("/api/driver/decision", response_model=DriverDecisionRead)
def submit_driver_decision(
    payload: DriverResponseRequest,
    session: Session = Depends(get_session),
) -> DriverDecision:
    recommendation = session.get(Recommendation, payload.recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    existing = session.scalar(select(DriverDecision).where(DriverDecision.recommendation_id == recommendation.id))
    if existing is not None:
        return existing

    vehicle = session.get(Vehicle, recommendation.vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    driver = session.get(DriverProfile, vehicle.driver_profile_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")

    recommendation.status = payload.decision
    rating_delta = 0.05 if payload.decision == "accepted" else -0.08
    driver.override_rating = round(max(0.2, driver.override_rating + rating_delta), 3)
    note = payload.note.strip() or ("Driver accepted mobile recommendation." if payload.decision == "accepted" else "Driver ignored mobile recommendation.")

    decision = DriverDecision(
        recommendation_id=recommendation.id, driver_profile_id=driver.id, vehicle_id=vehicle.id,
        decision=payload.decision,
        actual_trip_cost=recommendation.recommended_cost if payload.decision == "accepted" else recommendation.baseline_cost,
        recommended_trip_cost=recommendation.recommended_cost, rating_delta=rating_delta, note=note,
    )
    session.add(decision)
    session.commit()

    objective = session.get(Objective, recommendation.objective_id)
    if objective:
        simulation_engine.resolve_spotlight_decision(vehicle, recommendation, objective, payload.decision)
    session.refresh(decision)
    return decision


# --- Spotlight ---
@driver_router.post("/api/simulation/spotlight")
def set_spotlight(payload: SpotlightRequest) -> dict:
    simulation_engine.spotlight_driver_id = payload.driver_id
    return {"spotlight_driver_id": simulation_engine.spotlight_driver_id}


# --- Incidents ---
@driver_router.post("/api/driver/incidents", response_model=DriverIncidentRead)
def report_driver_incident(payload: DriverIncidentCreate, session: Session = Depends(get_session)) -> DriverIncident:
    if session.get(DriverProfile, payload.driver_profile_id) is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    if payload.vehicle_id is not None and session.get(Vehicle, payload.vehicle_id) is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    severity = min(0.99, max(0.0, payload.severity))
    incident_date = simulation_engine.simulation_time.date()
    news_event = NewsEvent(
        original_date=incident_date, simulation_date=incident_date, city=payload.city,
        category="Driver Incident", headline=f"Driver report: {payload.incident_type} in {payload.city}",
        relevant=True, impact_type=normalize_incident_impact_type(payload.incident_type),
        impact_score=severity, model_probability=severity,
    )
    session.add(news_event)
    session.flush()

    incident = DriverIncident(
        driver_profile_id=payload.driver_profile_id, vehicle_id=payload.vehicle_id,
        city=payload.city, incident_type=payload.incident_type, severity=severity,
        note=payload.note, linked_news_event_id=news_event.id,
    )
    session.add(incident)
    session.commit()
    session.refresh(incident)
    session.refresh(news_event)
    simulation_engine.update_news_event_map(news_event)
    return incident


@driver_router.get("/api/driver/incidents", response_model=list[DriverIncidentRead])
def list_driver_incidents(session: Session = Depends(get_session)) -> list[DriverIncident]:
    return session.scalars(
        select(DriverIncident).order_by(DriverIncident.reported_at.desc()).limit(120)
    ).all()


# --- Driver Performance ---
@driver_router.get("/api/drivers/performance", response_model=list[DriverMetricsRead])
def list_driver_performance(
    refresh: bool = Query(default=False), session: Session = Depends(get_session),
) -> list[DriverMetric]:
    from app_state import driver_performance_service
    return driver_performance_service.list_driver_metrics(session, refresh=refresh)


@driver_router.get("/api/drivers/{driver_id}/score", response_model=DriverMetricsRead)
def get_driver_score(
    driver_id: int, refresh: bool = Query(default=False), session: Session = Depends(get_session),
) -> DriverMetric:
    from app_state import driver_performance_service
    try:
        return driver_performance_service.get_or_compute_driver_metrics(session, driver_id, refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc