"""Client portal — dashboard endpoint and live data."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import delete, select, func
from sqlalchemy.orm import Session

from app_state import simulation_manager
from database import SessionLocal, get_session
from middleware.firebase_client import get_client_from_firebase
from models import (
    ClientSimulation,
    DriverDecision,
    DriverProfile,
    Facility,
    IntegrationClient,
    Objective,
    Recommendation,
    RouteTemplate,
    Shipment,
    SimEvent,
    Vehicle,
    WebhookDelivery,
    WebhookSubscription,
)
from schemas.client import DashboardResponse

logger = logging.getLogger(__name__)


def _compute_client_metrics(client_id: int, session: Session) -> dict:
    """Aggregate client-scoped KPI metrics from live engine state and DB records.

    Prefers live engine metrics when the client simulation is running.
    Falls back to DB-derived values for persistence across restarts.

    KPI mapping:
      financial_costs_saved_usd  → SUM accepted Recommendations.financial_impact_usd
      financial_costs_incurred_usd → SUM accepted recommended_cost + ignored baseline_cost
      reroute_count              → COUNT accepted Recommendations WHERE action ILIKE '%reroute%'
      active_trucks              → COUNT Vehicle WHERE client_id = cid AND status = 'in_transit'
      on_time_delivery_pct       → on_time / completed from recent SimEvents (estimation)
      co2_saved_kg               → from live engine if running, else 0
      stockouts_prevented        → from live engine if running, else 0
      critical_deliveries_saved  → from live engine if running, else 0
      beneficiary_locations_served → from live engine if running, else 0
      spoilage_or_wastage_prevented → from live engine if running, else 0
    """
    engine = simulation_manager.get_engine(client_id)
    live_metrics = getattr(engine, "current_metrics", None) if engine else None

    if live_metrics is not None and getattr(engine, "status", "idle") == "running":
        return {
            "financial_costs_saved_usd": live_metrics.financial_costs_saved_usd,
            "financial_costs_incurred_usd": live_metrics.financial_costs_incurred_usd,
            "reroute_count": live_metrics.reroute_count,
            "active_trucks": live_metrics.active_trucks,
            "on_time_delivery_pct": live_metrics.on_time_delivery_pct,
            "co2_saved_kg": live_metrics.co2_saved_kg,
            "stockouts_prevented": live_metrics.stockouts_prevented,
            "critical_deliveries_saved": live_metrics.critical_deliveries_saved,
            "beneficiary_locations_served": live_metrics.beneficiary_locations_served,
            "spoilage_or_wastage_prevented": live_metrics.spoilage_or_wastage_prevented,
        }

    # DB fallback: compute from persisted records
    vehicle_ids = session.scalars(
        select(Vehicle.id).where(Vehicle.client_id == client_id)
    ).all()

    accepted_recs = []
    all_recs = []
    if vehicle_ids:
        all_recs = session.scalars(
            select(Recommendation).where(Recommendation.vehicle_id.in_(vehicle_ids))
        ).all()
        accepted_recs = [r for r in all_recs if r.status == "accepted"]
        ignored_recs = [r for r in all_recs if r.status == "ignored"]

    financial_costs_saved_usd = sum(
        max(0, r.financial_impact_usd or 0) for r in accepted_recs
    )
    from config import load_settings
    settings = load_settings()
    
    financial_costs_incurred_usd = (sum(
        (r.recommended_cost or 0) for r in accepted_recs
    ) + sum((r.baseline_cost or 0) for r in all_recs if r.status == "ignored")) * settings.cost_point_to_inr

    reroute_count = sum(
        1 for r in accepted_recs
        if r.action and "reroute" in r.action.lower()
    )

    active_trucks = session.scalar(
        select(func.count(Vehicle.id)).where(
            Vehicle.client_id == client_id,
            Vehicle.status == "in_transit",
        )
    ) or 0

    completed_shipments = session.scalar(
        select(func.count(SimEvent.id)).where(
            SimEvent.client_id == client_id,
            SimEvent.event_type == "unload_complete",
        )
    ) or 0
    on_time_count = session.scalar(
        select(func.count(SimEvent.id)).where(
            SimEvent.client_id == client_id,
            SimEvent.event_type == "arrive",
        )
    ) or 0
    on_time_delivery_pct = round(
        min(on_time_count / max(completed_shipments, 1), 1.0) * 100, 1
    )

    return {
        "financial_costs_saved_usd": round(financial_costs_saved_usd, 2),
        "financial_costs_incurred_usd": round(financial_costs_incurred_usd, 2),
        "reroute_count": reroute_count,
        "active_trucks": active_trucks,
        "on_time_delivery_pct": on_time_delivery_pct,
        "co2_saved_kg": 0.0,
        "stockouts_prevented": 0,
        "critical_deliveries_saved": 0,
        "beneficiary_locations_served": 0,
        "spoilage_or_wastage_prevented": 0,
    }

router = APIRouter(prefix="/api/v1/client", tags=["Client Portal Dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
def client_dashboard(
    client: IntegrationClient = Depends(get_client_from_firebase),
    session: Session = Depends(get_session),
):
    cid = client.id

    facilities = session.scalars(
        select(Facility).where(Facility.client_id == cid)
    ).all()
    vehicles = session.scalars(
        select(Vehicle).where(Vehicle.client_id == cid)
    ).all()
    drivers = session.scalars(
        select(DriverProfile).where(DriverProfile.client_id == cid)
    ).all()
    objectives = session.scalars(
        select(Objective).where(Objective.client_id == cid)
    ).all()

    # Fleet list
    fleet = []
    vehicle_views = []
    for v in vehicles:
        home = session.get(Facility, v.home_facility_id) if v.home_facility_id else None
        current = session.get(Facility, v.current_facility_id) if v.current_facility_id else None
        obj = session.get(Objective, v.default_objective_id) if v.default_objective_id else None
        fleet.append({
            "id": v.id,
            "identifier": v.identifier,
            "status": v.status,
            "home_facility": home.name if home else None,
            "current_facility": current.name if current else None,
            "eta": str(v.available_at) if v.available_at else None,
            "payload_capacity": v.payload_capacity_units,
        })
        vehicle_views.append({
            "vehicle_id": v.id,
            "identifier": v.identifier,
            "status": v.status,
            "objective_id": v.default_objective_id,
            "current_facility_id": v.current_facility_id or v.home_facility_id,
            "next_facility_id": None,
            "progress_pct": 0.0,
            "payload_units": 0,
            "recommendation_action": None,
        })

    # Compute metrics from live engine + DB aggregation
    client_metrics = _compute_client_metrics(cid, session)

    # Recent decisions
    vehicle_ids = [v.id for v in vehicles]
    recent_decisions = []
    if vehicle_ids:
        decisions = session.scalars(
            select(Recommendation).where(Recommendation.vehicle_id.in_(vehicle_ids))
            .order_by(Recommendation.created_at.desc()).limit(10)
        ).all()
        for d in decisions:
            v = session.get(Vehicle, d.vehicle_id)
            recent_decisions.append({
                "id": d.id,
                "vehicle": v.identifier if v else f"Vehicle #{d.vehicle_id}",
                "action": d.action,
                "explanation": d.explanation,
                "baseline_cost": d.baseline_cost,
                "recommended_cost": d.recommended_cost,
                "financial_impact_usd": d.financial_impact_usd,
                "status": d.status,
                "confidence": d.confidence,
                "time": str(d.created_at),
            })

    # Webhook deliveries
    subs = session.scalars(
        select(WebhookSubscription).where(WebhookSubscription.client_id == cid)
    ).all()
    sub_ids = [s.id for s in subs]
    webhook_deliveries = []
    if sub_ids:
        deliveries = session.scalars(
            select(WebhookDelivery).where(WebhookDelivery.subscription_id.in_(sub_ids))
            .order_by(WebhookDelivery.attempted_at.desc()).limit(20)
        ).all()
        webhook_deliveries = [
            {
                "id": d.id,
                "event_type": d.event_type,
                "status": "delivered" if d.success else "failed",
                "attempted_at": str(d.attempted_at),
            }
            for d in deliveries
        ]

    completed_shipments = session.scalar(
        select(func.count(SimEvent.id)).where(
            SimEvent.client_id == cid,
            SimEvent.event_type == "unload_complete",
        )
    ) or 0

    engine = simulation_manager.get_engine(cid)
    sim_status = None
    if engine:
        sim_status = engine.snapshot_status().model_dump()
    else:
        sim_row = session.scalar(select(ClientSimulation).where(ClientSimulation.client_id == cid))
        if sim_row:
            sim_status = {
                "status": sim_row.status,
                "simulation_time": sim_row.simulation_time.isoformat() if sim_row.simulation_time else "",
                "speed_multiplier": sim_row.speed_multiplier,
                "queued_events": 0,
                "error_message": None,
            }
        else:
            sim_status = {
                "status": "idle",
                "simulation_time": "",
                "speed_multiplier": 0.0,
                "queued_events": 0,
                "error_message": None,
            }

    return DashboardResponse(
        client={
            "name": client.company_name or client.name,
            "api_key_prefix": client.api_key_prefix,
        },
        status={
            "facilities": len(facilities),
            "vehicles": len(vehicles),
            "drivers": len(drivers),
            "objectives": len(objectives),
        },
        fleet=fleet,
        facilities=[
            {
                "id": f.id,
                "name": f.name,
                "city": f.city,
                "facility_type": f.facility_type,
                "latitude": f.latitude,
                "longitude": f.longitude,
                "utilization_pct": round(f.current_inventory_units / max(f.base_capacity_units, 1) * 100, 1),
                "inventory": f.current_inventory_units,
                "capacity": f.base_capacity_units,
            }
            for f in facilities
        ],
        metrics={
            **client_metrics,
            "completed_shipments": completed_shipments,
            "total_api_calls": client.monthly_api_calls,
        },
        recent_decisions=recent_decisions,
        webhook_deliveries=webhook_deliveries,
        vehicles=vehicle_views,
        simulation=sim_status,
    )


@router.get("/upload-status")
def upload_status(
    client: IntegrationClient = Depends(get_client_from_firebase),
    session: Session = Depends(get_session),
):
    cid = client.id
    has_facilities = session.scalar(
        select(func.count(Facility.id)).where(Facility.client_id == cid)
    ) > 0
    has_vehicles = session.scalar(
        select(func.count(Vehicle.id)).where(Vehicle.client_id == cid)
    ) > 0
    has_drivers = session.scalar(
        select(func.count(DriverProfile.id)).where(DriverProfile.client_id == cid)
    ) > 0
    has_objectives = session.scalar(
        select(func.count(Objective.id)).where(Objective.client_id == cid)
    ) > 0

    sim = session.scalar(
        select(ClientSimulation).where(ClientSimulation.client_id == cid)
    )

    return {
        "facilities": has_facilities,
        "vehicles": has_vehicles,
        "drivers": has_drivers,
        "objectives": has_objectives,
        "all_complete": all([has_facilities, has_vehicles, has_drivers, has_objectives]),
        "simulation_status": sim.status if sim else None,
    }


@router.get("/facilities")
def client_facilities(
    client: IntegrationClient = Depends(get_client_from_firebase),
    session: Session = Depends(get_session),
):
    cid = client.id
    facilities = session.scalars(
        select(Facility).where(Facility.client_id == cid)
    ).all()
    return [
        {
            "id": f.id,
            "name": f.name,
            "city": f.city,
            "facility_type": f.facility_type,
            "latitude": f.latitude,
            "longitude": f.longitude,
            "base_capacity_units": f.base_capacity_units,
            "current_inventory_units": f.current_inventory_units,
            "initial_inventory_units": f.initial_inventory_units,
            "client_id": f.client_id,
        }
        for f in facilities
    ]


@router.get("/vehicles")
def client_vehicles(
    client: IntegrationClient = Depends(get_client_from_firebase),
    session: Session = Depends(get_session),
):
    cid = client.id
    vehicles = session.scalars(
        select(Vehicle).where(Vehicle.client_id == cid)
    ).all()
    return [
        {
            "id": v.id,
            "identifier": v.identifier,
            "vehicle_type": v.vehicle_type,
            "status": v.status,
            "payload_capacity_units": v.payload_capacity_units,
            "home_facility_id": v.home_facility_id,
            "current_facility_id": v.current_facility_id,
            "average_speed_kmph": v.average_speed_kmph,
            "client_id": v.client_id,
        }
        for v in vehicles
    ]


@router.get("/objectives")
def client_objectives(
    client: IntegrationClient = Depends(get_client_from_firebase),
    session: Session = Depends(get_session),
):
    cid = client.id
    objectives = session.scalars(
        select(Objective).where(Objective.client_id == cid)
    ).all()
    return [
        {
            "id": o.id,
            "name": o.name,
            "commodity": o.commodity,
            "origin_facility_id": o.origin_facility_id,
            "destination_facility_id": o.destination_facility_id,
            "dispatch_interval_minutes": o.dispatch_interval_minutes,
            "sla_minutes": o.sla_minutes,
            "priority": o.priority,
            "assigned_vehicle_ids": o.assigned_vehicle_ids,
            "client_id": o.client_id,
        }
        for o in objectives
    ]


@router.get("/routes")
def client_routes(
    client: IntegrationClient = Depends(get_client_from_firebase),
    session: Session = Depends(get_session),
):
    cid = client.id
    facility_ids = session.scalars(
        select(Facility.id).where(Facility.client_id == cid)
    ).all()
    if not facility_ids:
        return []
    routes = session.scalars(
        select(RouteTemplate).where(
            (RouteTemplate.origin_facility_id.in_(facility_ids))
            | (RouteTemplate.destination_facility_id.in_(facility_ids))
        )
    ).all()
    return [
        {
            "id": r.id,
            "route_key": r.route_key,
            "origin_facility_id": r.origin_facility_id,
            "destination_facility_id": r.destination_facility_id,
            "distance_km": r.distance_km,
            "duration_minutes": r.duration_minutes,
            "encoded_polyline": r.encoded_polyline,
            "source": r.source,
        }
        for r in routes
    ]


@router.get("/recommendations")
def client_recommendations(
    client: IntegrationClient = Depends(get_client_from_firebase),
    session: Session = Depends(get_session),
):
    cid = client.id
    recommendations = session.scalars(
        select(Recommendation)
        .join(Vehicle, Recommendation.vehicle_id == Vehicle.id)
        .where(Vehicle.client_id == cid)
        .order_by(Recommendation.created_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": r.id,
            "vehicle_id": r.vehicle_id,
            "objective_id": r.objective_id,
            "current_facility_id": r.current_facility_id,
            "original_destination_id": r.original_destination_id,
            "recommended_destination_id": r.recommended_destination_id,
            "action": r.action,
            "explanation": r.explanation,
            "structured_explanation": r.structured_explanation,
            "counterfactual": r.counterfactual,
            "score_breakdown": r.score_breakdown,
            "baseline_cost": r.baseline_cost,
            "recommended_cost": r.recommended_cost,
            "financial_impact_usd": r.financial_impact_usd,
            "status": r.status,
            "confidence": r.confidence,
            "simulation_time": str(r.simulation_time) if r.simulation_time else None,
            "created_at": str(r.created_at),
        }
        for r in recommendations
    ]


@router.get("/events")
def client_events(
    client: IntegrationClient = Depends(get_client_from_firebase),
    session: Session = Depends(get_session),
):
    cid = client.id
    events = session.scalars(
        select(SimEvent).where(SimEvent.client_id == cid)
        .order_by(SimEvent.processed_time.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "client_id": e.client_id,
            "scheduled_time": str(e.scheduled_time) if e.scheduled_time else None,
            "processed_time": str(e.processed_time) if e.processed_time else None,
            "vehicle_id": e.vehicle_id,
            "objective_id": e.objective_id,
            "facility_id": e.facility_id,
            "payload": e.payload,
        }
        for e in events
    ]


@router.delete("/reset")
def reset_workspace(
    client: IntegrationClient = Depends(get_client_from_firebase),
    session: Session = Depends(get_session),
):
    cid = client.id
    deleted = 0

    vehicle_ids = session.scalars(select(Vehicle.id).where(Vehicle.client_id == cid)).all()
    if vehicle_ids:
        result = session.execute(
            delete(Recommendation).where(Recommendation.vehicle_id.in_(vehicle_ids))
        )
        deleted += result.rowcount

    result = session.execute(delete(WebhookDelivery).where(WebhookDelivery.client_id == cid))
    deleted += result.rowcount

    result = session.execute(delete(SimEvent).where(SimEvent.client_id == cid))
    deleted += result.rowcount

    result = session.execute(delete(Objective).where(Objective.client_id == cid))
    deleted += result.rowcount

    result = session.execute(delete(Vehicle).where(Vehicle.client_id == cid))
    deleted += result.rowcount

    result = session.execute(delete(DriverProfile).where(DriverProfile.client_id == cid))
    deleted += result.rowcount

    result = session.execute(delete(Shipment).where(Shipment.client_id == cid))
    deleted += result.rowcount

    result = session.execute(delete(Facility).where(Facility.client_id == cid))
    deleted += result.rowcount

    result = session.execute(delete(ClientSimulation).where(ClientSimulation.client_id == cid))
    deleted += result.rowcount

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(simulation_manager.stop_client(cid))
    except RuntimeError:
        pass

from pydantic import BaseModel
class ClientSpeedChange(BaseModel):
    speed_multiplier: float

@router.put("/speed")
async def set_client_simulation_speed(
    payload: ClientSpeedChange,
    client: IntegrationClient = Depends(get_client_from_firebase),
):
    """Update the simulation speed multiplier for the client's live engine."""
    engine = simulation_manager.get_engine(client.id)
    if not engine:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Simulation engine not running for this client."
        )
    
    # engine.set_speed returns a SimulationStatus, but we can just return ok
    await engine.set_speed(payload.speed_multiplier)
    return {"ok": True, "speed_multiplier": payload.speed_multiplier}
