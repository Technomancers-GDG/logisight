"""Simulation, demo, and scenario routes."""
from __future__ import annotations

from math import ceil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_state import simulation_engine, inventory_optimizer
from database import get_session
from models import (
    Facility,
    NewsEvent,
    Objective,
    PortLink,
    ScenarioPreset,
    Vehicle,
    DriverProfile,
)
from schemas import (
    DashboardSnapshot,
    MetricsSummary,
    RecommendationRead,
    DriverDecisionRead,
    RecommendationDecisionRequest,
    DriverInstructionRead,
    DriverMobileSnapshot,
    DriverResponseRequest,
    DriverIncidentCreate,
    DriverIncidentRead,
    DriverMetricsRead,
    ScenarioPresetRead,
    SimulationControlRequest,
    SpeedChangeRequest,
    SimulationStatus,
    FleetScaleRequest,
    FleetScaleResult,
    ScenarioComparisonMetrics,
    ScenarioComparisonRead,
)
from services.driver_performance import DriverPerformanceService

simulation_router = APIRouter(tags=["Simulation & Demo"])


def _execute_fleet_scale(
    session: Session,
    target_vehicle_count: int,
) -> FleetScaleResult:
    """Shared fleet-scale DB logic used by both scale-fleet and judge-mode endpoints."""
    objectives = session.scalars(
        select(Objective).where(Objective.active.is_(True)).order_by(Objective.priority.desc(), Objective.id)
    ).all()
    if not objectives:
        raise HTTPException(status_code=400, detail="No active objectives available to scale fleet")

    vehicles = list(session.scalars(select(Vehicle).order_by(Vehicle.id)).all())
    drivers = list(session.scalars(select(DriverProfile).order_by(DriverProfile.id)).all())
    if not drivers:
        raise HTTPException(status_code=400, detail="No drivers available")

    previous_vehicle_count = len(vehicles)
    previous_driver_count = len(drivers)

    if target_vehicle_count < previous_vehicle_count:
        vehicles_to_remove = vehicles[target_vehicle_count:]
        removed_vehicle_ids = {v.id for v in vehicles_to_remove}
        removed_driver_ids = {v.driver_profile_id for v in vehicles_to_remove}
        for v in vehicles_to_remove:
            session.delete(v)
        for objective in objectives:
            if objective.assigned_vehicle_ids:
                objective.assigned_vehicle_ids = [vid for vid in objective.assigned_vehicle_ids if vid not in removed_vehicle_ids]
        for driver in drivers:
            if driver.id in removed_driver_ids:
                still_has = session.scalar(select(Vehicle).where(Vehicle.driver_profile_id == driver.id).limit(1))
                if still_has is None:
                    session.delete(driver)
        session.commit()
        vehicles = list(session.scalars(select(Vehicle).order_by(Vehicle.id)).all())
        drivers = list(session.scalars(select(DriverProfile).order_by(DriverProfile.id)).all())

    new_vehicle_count = len(vehicles)
    new_driver_count = len(drivers)
    vehicles_to_create = max(0, target_vehicle_count - new_vehicle_count)
    desired_driver_count = max(new_driver_count, ceil(target_vehicle_count * 0.6))
    existing_driver_names = {driver.name for driver in drivers}
    driver_seq = 1
    while len(drivers) < desired_driver_count:
        while True:
            candidate_name = f"Ops Driver {driver_seq:03d}"
            driver_seq += 1
            if candidate_name not in existing_driver_names:
                break
        driver = DriverProfile(name=candidate_name, override_rating=1.0, confidence=0.58, accept_recommendation_bias=0.55, active=True)
        session.add(driver)
        drivers.append(driver)
        existing_driver_names.add(candidate_name)
    session.flush()

    objective_vehicle_templates: dict[int, list[Vehicle]] = {objective.id: [] for objective in objectives}
    for vehicle in vehicles:
        if vehicle.default_objective_id in objective_vehicle_templates:
            objective_vehicle_templates[vehicle.default_objective_id].append(vehicle)
    fallback_template = vehicles[0] if vehicles else None
    if fallback_template is None:
        raise HTTPException(status_code=400, detail="No base vehicle available for scaling")
    for objective in objectives:
        if not objective_vehicle_templates[objective.id]:
            assigned = set(objective.assigned_vehicle_ids or [])
            seeded = [vehicle for vehicle in vehicles if vehicle.id in assigned]
            objective_vehicle_templates[objective.id] = seeded or [fallback_template]

    existing_identifiers = {vehicle.identifier for vehicle in vehicles}
    identifier_sequence = new_vehicle_count + 1

    def next_identifier() -> str:
        nonlocal identifier_sequence
        while True:
            candidate = f"OPS-{identifier_sequence:04d}"
            identifier_sequence += 1
            if candidate not in existing_identifiers:
                existing_identifiers.add(candidate)
                return candidate

    created_vehicles_by_objective: dict[int, list[Vehicle]] = {objective.id: [] for objective in objectives}
    for index in range(vehicles_to_create):
        objective = objectives[index % len(objectives)]
        template_pool = objective_vehicle_templates[objective.id] or [fallback_template]
        template = template_pool[index % len(template_pool)]
        driver = drivers[index % len(drivers)]
        capacity_factor = 0.9 + (index % 6) * 0.035
        speed_factor = 0.92 + (index % 5) * 0.02
        emission_factor = 0.9 + (index % 4) * 0.03
        vehicle = Vehicle(
            identifier=next_identifier(),
            vehicle_type=template.vehicle_type,
            payload_capacity_units=max(500, int(template.payload_capacity_units * capacity_factor)),
            home_facility_id=objective.origin_facility_id,
            current_facility_id=objective.origin_facility_id,
            driver_profile_id=driver.id,
            default_objective_id=objective.id,
            average_speed_kmph=round(max(32.0, template.average_speed_kmph * speed_factor), 2),
            emission_kg_per_km=round(max(0.9, template.emission_kg_per_km * emission_factor), 3),
            rest_every_hours=template.rest_every_hours,
            rest_duration_minutes=template.rest_duration_minutes,
            status="idle",
        )
        session.add(vehicle)
        created_vehicles_by_objective[objective.id].append(vehicle)
    session.flush()

    objective_assignment_counts: dict[str, int] = {}
    for objective in objectives:
        new_ids = [vehicle.id for vehicle in created_vehicles_by_objective[objective.id]]
        merged_ids = list(dict.fromkeys([*(objective.assigned_vehicle_ids or []), *new_ids]))
        objective.assigned_vehicle_ids = merged_ids
        objective_assignment_counts[objective.name] = len(merged_ids)
    session.commit()

    return FleetScaleResult(
        previous_vehicle_count=previous_vehicle_count,
        new_vehicle_count=target_vehicle_count,
        created_vehicles=vehicles_to_create,
        previous_driver_count=previous_driver_count,
        new_driver_count=len(drivers),
        created_drivers=max(0, len(drivers) - previous_driver_count),
        objective_assignment_counts=objective_assignment_counts,
        simulation=SimulationStatus(status="idle", simulation_time="", speed_multiplier=0, ticks=0),
    )


# --- Simulation Control ---
@simulation_router.post("/api/simulation/start", response_model=SimulationStatus)
async def start_simulation(payload: SimulationControlRequest | None = None) -> SimulationStatus:
    speed = payload.speed_multiplier if payload and payload.speed_multiplier else None
    return await simulation_engine.start(speed_multiplier=speed)


@simulation_router.post("/api/simulation/pause", response_model=SimulationStatus)
async def pause_simulation() -> SimulationStatus:
    return await simulation_engine.pause()


@simulation_router.post("/api/simulation/resume", response_model=SimulationStatus)
async def resume_simulation() -> SimulationStatus:
    return await simulation_engine.resume()


@simulation_router.post("/api/simulation/reset", response_model=SimulationStatus)
async def reset_simulation() -> SimulationStatus:
    return await simulation_engine.reset()


@simulation_router.get("/api/simulation/status", response_model=SimulationStatus)
def simulation_status() -> SimulationStatus:
    return simulation_engine.snapshot_status()


@simulation_router.put("/api/simulation/speed", response_model=SimulationStatus)
async def set_simulation_speed(payload: SpeedChangeRequest) -> SimulationStatus:
    return await simulation_engine.set_speed(payload.speed_multiplier)


# --- Demo Fleet Scaling ---
@simulation_router.post("/api/demo/scale-fleet", response_model=FleetScaleResult)
async def scale_demo_fleet(
    payload: FleetScaleRequest,
    session: Session = Depends(get_session),
) -> FleetScaleResult:
    result = _execute_fleet_scale(session, payload.target_vehicle_count)
    if payload.reset_simulation:
        await simulation_engine.reset()
        if payload.auto_start:
            sim_status = await simulation_engine.start(speed_multiplier=payload.speed_multiplier)
        else:
            sim_status = simulation_engine.snapshot_status()
    else:
        sim_status = simulation_engine.snapshot_status()
    result.simulation = sim_status
    return result


@simulation_router.post("/api/demo/simulate-driver-decision")
async def simulate_driver_decision(session: Session = Depends(get_session)) -> dict[str, Any]:
    """Simulate the driver accepting the latest pending recommendation
    for any vehicle — bypasses the mobile PWA for demo reliability."""
    latest = session.scalar(
        select(Recommendation).where(Recommendation.status == "suggested")
        .order_by(Recommendation.created_at.desc()).limit(1)
    )
    if latest is None:
        return {"status": "no_pending", "detail": "No pending recommendations found"}
    vehicle = session.get(Vehicle, latest.vehicle_id)
    if vehicle is None:
        return {"status": "error", "detail": "Vehicle not found"}
    driver = session.get(DriverProfile, vehicle.driver_profile_id)
    if driver is None:
        return {"status": "error", "detail": "Driver not found"}
    latest.status = "accepted"
    driver.override_rating = round(min(2.0, driver.override_rating + 0.05), 3)
    decision = DriverDecision(
        recommendation_id=latest.id, driver_profile_id=driver.id, vehicle_id=vehicle.id,
        decision="accepted",
        actual_trip_cost=latest.recommended_cost,
        recommended_trip_cost=latest.recommended_cost,
        rating_delta=0.05,
        note="Auto-accepted (demo bypass).",
    )
    session.add(decision)
    session.commit()
    return {
        "status": "accepted",
        "recommendation_id": latest.id,
        "vehicle_id": vehicle.id,
        "driver_id": driver.id,
        "action": latest.action,
    }


@simulation_router.post("/api/demo/judge-mode")
async def judge_demo_mode(session: Session = Depends(get_session)) -> dict[str, Any]:
    """One-click demo for judges: scale fleet, trigger disruption, start simulation."""
    _execute_fleet_scale(session, target_vehicle_count=60)
    await simulation_engine.reset()
    await simulation_engine.start(speed_multiplier=180)

    scenario = session.scalar(
        select(ScenarioPreset).where(ScenarioPreset.scenario_key == "chennai_flood", ScenarioPreset.active.is_(True))
    )
    if scenario is None:
        scenario = session.scalar(
            select(ScenarioPreset).where(ScenarioPreset.active.is_(True)).order_by(ScenarioPreset.severity.desc())
        )
    if scenario:
        event_date = simulation_engine.simulation_time.date()
        event = NewsEvent(
            original_date=event_date,
            simulation_date=event_date,
            city=scenario.event_city,
            category="Scenario Trigger",
            headline=f"Judge Demo: {scenario.name}",
            relevant=True,
            impact_type=scenario.event_type,
            impact_score=min(0.99, max(0.0, scenario.severity)),
            model_probability=min(0.99, max(0.0, scenario.severity)),
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        simulation_engine.update_news_event_map(event)

    return {
        "status": "judge_demo_started",
        "fleet_size": 60,
        "simulation_speed": 180,
        "scenario_triggered": scenario.name if scenario else None,
    }


# --- Scenarios ---
@simulation_router.get("/api/scenarios", response_model=list[ScenarioPresetRead])
def list_scenarios(session: Session = Depends(get_session)) -> list[ScenarioPreset]:
    return session.scalars(
        select(ScenarioPreset).where(ScenarioPreset.active.is_(True)).order_by(ScenarioPreset.name)
    ).all()


@simulation_router.post("/api/scenarios/{scenario_key}/trigger")
def trigger_scenario(scenario_key: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    scenario = session.scalar(select(ScenarioPreset).where(ScenarioPreset.scenario_key == scenario_key, ScenarioPreset.active.is_(True)))
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    event_date = simulation_engine.simulation_time.date()
    event = NewsEvent(
        original_date=event_date, simulation_date=event_date, city=scenario.event_city,
        category="Scenario Trigger", headline=f"Scenario triggered: {scenario.name}",
        relevant=True, impact_type=scenario.event_type,
        impact_score=min(0.99, max(0.0, scenario.severity)),
        model_probability=min(0.99, max(0.0, scenario.severity)),
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    simulation_engine.update_news_event_map(event)

    # Cascade propagation
    cascade = []
    affected_city = str(scenario.event_city).strip().lower()
    for facility in session.scalars(select(Facility)).all():
        if str(facility.city).strip().lower() == affected_city:
            for link in session.scalars(select(PortLink)).all():
                if link.warehouse_id == facility.id or link.port_id == facility.id:
                    other = session.get(Facility, link.port_id if link.warehouse_id == facility.id else link.warehouse_id)
                    if other:
                        cascade.append({"from_facility_id": facility.id, "from_facility_name": facility.name, "to_facility_id": other.id, "to_facility_name": other.name, "link_type": "port_spillover", "severity": scenario.severity})

    proactive = []
    if cascade:
        affected_ids = {link["from_facility_id"] for link in cascade} | {link["to_facility_id"] for link in cascade}
        for rec in inventory_optimizer.recommend_proactive_dispatches(session):
            if rec.origin_facility_id in affected_ids or rec.destination_facility_id in affected_ids:
                proactive.append({"origin": rec.origin_facility_id, "destination": rec.destination_facility_id, "units": rec.recommended_units, "urgency": rec.urgency, "reason": rec.reason})

    # Demand-shock cascade
    demand_shock = []
    affected_cities = {scenario.event_city.lower()}
    for facility in session.scalars(select(Facility)).all():
        if str(facility.city).strip().lower() == scenario.event_city.lower():
            affected_cities.add(str(facility.city).strip().lower())
    for objective in session.scalars(select(Objective).where(Objective.active.is_(True))).all():
        origin = session.get(Facility, objective.origin_facility_id)
        dest = session.get(Facility, objective.destination_facility_id)
        for place, pressure in [(origin, "origin"), (dest, "destination")]:
            if place and str(place.city).strip().lower() in affected_cities:
                old_interval = objective.dispatch_interval_minutes
                new_interval = max(30, int(old_interval * (1.0 - scenario.severity * (0.35 if pressure == "origin" else 0.25))))
                objective.dispatch_interval_minutes = new_interval
                demand_shock.append({"objective_id": objective.id, "objective_name": objective.name, "city": place.city, "old_interval": old_interval, "new_interval": new_interval, "pressure": pressure})
    if demand_shock:
        session.commit()

    return {"status": "triggered", "scenario_key": scenario.scenario_key, "event_city": scenario.event_city, "severity": scenario.severity, "cascade_affected_links": cascade, "cascade_count": len(cascade), "proactive_dispatches": proactive, "proactive_count": len(proactive), "demand_shock": demand_shock, "demand_shock_count": len(demand_shock)}


@simulation_router.get("/api/scenarios/{scenario_key}/compare", response_model=ScenarioComparisonRead)
def compare_scenario(scenario_key: str, session: Session = Depends(get_session)) -> ScenarioComparisonRead:
    scenario = session.scalar(select(ScenarioPreset).where(ScenarioPreset.scenario_key == scenario_key, ScenarioPreset.active.is_(True)))
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    comparison = simulation_engine.compare_scenario(session, scenario)
    return ScenarioComparisonRead(
        scenario_key=scenario.scenario_key, scenario_name=scenario.name,
        baseline=ScenarioComparisonMetrics(**comparison["baseline"]),
        ai=ScenarioComparisonMetrics(**comparison["ai"]),
        improvement_summary=comparison["improvement"],
    )


@simulation_router.get("/api/dashboard", response_model=DashboardSnapshot)
def dashboard(session: Session = Depends(get_session)) -> DashboardSnapshot:
    return simulation_engine.dashboard_snapshot(session)