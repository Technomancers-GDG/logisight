from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app_state import (
    data_fusion_service,
    driver_performance_service,
    forecast_service,
    inventory_optimizer,
    logistics_decision_engine,
    logistics_execution_service,
    logistics_prediction_engine,
    multimodal_graph_engine,
    multi_objective_optimizer,
    simulation_engine,
    telemetry_simulation_service,
)
from database import get_session
from middleware.api_key_auth import verify_api_key
from models import (
    DriverIncident,
    DriverProfile,
    Facility,
    IntegrationClient,
    LogisticsNode,
    MetricsSnapshot,
    NewsEvent,
    Objective,
    Recommendation,
    Shipment,
    Vehicle,
    WebhookDelivery,
    WebhookSubscription,
)
from routes.logistics import resolve_logistics_graph, compute_logistics_routes
from schemas.logistics import (
    AssignRouteRequest,
    ComputeRoutesRequest,
    DecisionRequest,
    LogisticsGraph,
    PredictionRequest,
    RerouteRequest,
    RouteWeights,
    TelemetrySimulationRequest,
)
from schemas.integration import (
    BatchResult,
    DecisionExport,
    DriverExport,
    DriverImport,
    DriverImportBatch,
    ErrorDetail,
    EventImport,
    EventImportBatch,
    FacilityExport,
    FacilityImport,
    FacilityImportBatch,
    IncidentExport,
    IncidentImport,
    IntegrationSnapshot,
    IntegrationStatus,
    InventoryUpdateBatch,
    MetricsExport,
    ObjectiveExport,
    ObjectiveImport,
    ObjectiveImportBatch,
    OptimizeDispatchRequest,
    ShipmentExport,
    ShipmentImport,
    ShipmentImportBatch,
    SimulationDecideRequest,
    SimulationDecideResponse,
    VehicleExport,
    VehicleImport,
    VehicleImportBatch,
    WebhookCreate,
    WebhookDeliveryExport,
    WebhookExport,
    WebhookUpdate,
)
from services.integration.webhook_dispatcher import dispatch_webhook_event
import torch

from services.rl_decision_engine import StateVector, get_rl_engine

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/integration",
    tags=["Integration API"],
    dependencies=[Depends(verify_api_key)],
)


def _ok(data: Any = None, meta: dict | None = None) -> dict:
    return {"success": True, "data": data, "meta": meta, "error": None}


def _pagination(page: int, per_page: int, total: int) -> dict:
    return {"page": page, "per_page": per_page, "total": total}


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@router.get("/status")
def integration_status():
    return _ok(IntegrationStatus().model_dump())


# ---------------------------------------------------------------------------
# Data Import - Facilities
# ---------------------------------------------------------------------------


@router.put("/facilities", response_model=dict)
def upsert_facilities(body: FacilityImportBatch, session: Session = Depends(get_session)):
    imported = 0
    updated = 0
    errors: list[ErrorDetail] = []

    for fac in body.facilities:
        try:
            existing = session.scalar(select(Facility).where(Facility.name == fac.name))
            if existing:
                existing.city = fac.city
                existing.facility_type = fac.facility_type
                existing.latitude = fac.latitude
                existing.longitude = fac.longitude
                existing.base_capacity_units = fac.base_capacity_units
                existing.current_inventory_units = fac.current_inventory_units
                existing.queue_capacity_units = fac.queue_capacity_units
                existing.active = fac.active
                existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                updated += 1
            else:
                session.add(Facility(
                    name=fac.name, city=fac.city, facility_type=fac.facility_type,
                    latitude=fac.latitude, longitude=fac.longitude,
                    base_capacity_units=fac.base_capacity_units,
                    current_inventory_units=fac.current_inventory_units,
                    initial_inventory_units=fac.current_inventory_units,
                    queue_capacity_units=fac.queue_capacity_units,
                    active=fac.active,
                ))
                imported += 1
        except Exception as exc:
            errors.append(ErrorDetail(field=fac.name, message=str(exc)))

    session.commit()
    return _ok(BatchResult(success=not errors, imported=imported, updated=updated, errors=errors).model_dump())


# ---------------------------------------------------------------------------
# Data Import - Vehicles
# ---------------------------------------------------------------------------


@router.put("/vehicles", response_model=dict)
def upsert_vehicles(body: VehicleImportBatch, session: Session = Depends(get_session)):
    imported = 0
    updated = 0
    errors: list[ErrorDetail] = []

    for v in body.vehicles:
        try:
            home = session.scalar(select(Facility).where(Facility.name == v.home_facility_name))
            if home is None:
                errors.append(ErrorDetail(field=v.identifier, message=f"Home facility '{v.home_facility_name}' not found"))
                continue

            driver = session.scalar(select(DriverProfile).where(DriverProfile.active.is_(True)).limit(1))

            existing = session.scalar(select(Vehicle).where(Vehicle.identifier == v.identifier))
            if existing:
                existing.vehicle_type = v.vehicle_type
                existing.payload_capacity_units = v.payload_capacity_units
                existing.home_facility_id = home.id
                existing.average_speed_kmph = v.average_speed_kmph
                existing.emission_kg_per_km = v.emission_kg_per_km
                existing.status = v.status
                existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                updated += 1
            else:
                session.add(Vehicle(
                    identifier=v.identifier, vehicle_type=v.vehicle_type,
                    payload_capacity_units=v.payload_capacity_units,
                    home_facility_id=home.id, current_facility_id=home.id,
                    driver_profile_id=driver.id if driver else 1,
                    average_speed_kmph=v.average_speed_kmph,
                    emission_kg_per_km=v.emission_kg_per_km,
                    status=v.status,
                ))
                imported += 1
        except Exception as exc:
            errors.append(ErrorDetail(field=v.identifier, message=str(exc)))

    session.commit()
    return _ok(BatchResult(success=not errors, imported=imported, updated=updated, errors=errors).model_dump())


# ---------------------------------------------------------------------------
# Data Import - Drivers
# ---------------------------------------------------------------------------


@router.put("/drivers", response_model=dict)
def upsert_drivers(body: DriverImportBatch, session: Session = Depends(get_session)):
    imported = 0
    updated = 0
    errors: list[ErrorDetail] = []

    for d in body.drivers:
        try:
            existing = session.scalar(select(DriverProfile).where(DriverProfile.name == d.name))
            if existing:
                existing.active = d.active
                updated += 1
            else:
                session.add(DriverProfile(name=d.name, active=d.active))
                imported += 1
        except Exception as exc:
            errors.append(ErrorDetail(field=d.name, message=str(exc)))

    session.commit()
    return _ok(BatchResult(success=not errors, imported=imported, updated=updated, errors=errors).model_dump())


# ---------------------------------------------------------------------------
# Data Import - Objectives
# ---------------------------------------------------------------------------


@router.put("/objectives", response_model=dict)
def upsert_objectives(body: ObjectiveImportBatch, session: Session = Depends(get_session)):
    imported = 0
    updated = 0
    errors: list[ErrorDetail] = []

    for obj in body.objectives:
        try:
            origin = session.scalar(select(Facility).where(Facility.name == obj.origin_facility_name))
            dest = session.scalar(select(Facility).where(Facility.name == obj.destination_facility_name))
            if origin is None:
                errors.append(ErrorDetail(field=obj.name, message=f"Origin facility '{obj.origin_facility_name}' not found"))
                continue
            if dest is None:
                errors.append(ErrorDetail(field=obj.name, message=f"Destination facility '{obj.destination_facility_name}' not found"))
                continue

            existing = session.scalar(select(Objective).where(Objective.name == obj.name))
            if existing:
                existing.commodity = obj.commodity
                existing.origin_facility_id = origin.id
                existing.destination_facility_id = dest.id
                existing.dispatch_interval_minutes = obj.dispatch_interval_minutes
                existing.sla_minutes = obj.sla_minutes
                existing.priority = obj.priority
                existing.active = obj.active
                existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                updated += 1
            else:
                session.add(Objective(
                    name=obj.name, commodity=obj.commodity,
                    origin_facility_id=origin.id, destination_facility_id=dest.id,
                    dispatch_interval_minutes=obj.dispatch_interval_minutes,
                    sla_minutes=obj.sla_minutes, priority=obj.priority,
                    active=obj.active,
                ))
                imported += 1
        except Exception as exc:
            errors.append(ErrorDetail(field=obj.name, message=str(exc)))

    session.commit()
    return _ok(BatchResult(success=not errors, imported=imported, updated=updated, errors=errors).model_dump())


# ---------------------------------------------------------------------------
# Data Import - Shipments
# ---------------------------------------------------------------------------


@router.post("/shipments", response_model=dict)
def create_shipments(body: ShipmentImportBatch, session: Session = Depends(get_session)):
    created = 0
    errors: list[ErrorDetail] = []

    for s in body.shipments:
        try:
            existing = session.scalar(select(Shipment).where(Shipment.shipment_reference == s.shipment_reference))
            if existing:
                errors.append(ErrorDetail(field=s.shipment_reference, message="Shipment reference already exists"))
                continue

            origin_node = session.scalar(select(LogisticsNode).where(LogisticsNode.node_key == s.origin_node_key))
            dest_node = session.scalar(select(LogisticsNode).where(LogisticsNode.node_key == s.destination_node_key))

            session.add(Shipment(
                shipment_reference=s.shipment_reference,
                origin_node_id=origin_node.id if origin_node else None,
                destination_node_id=dest_node.id if dest_node else None,
                origin_node_key=s.origin_node_key,
                destination_node_key=s.destination_node_key,
                current_location_node_key=s.origin_node_key,
                cargo_type=s.cargo_type,
                quantity_units=s.quantity_units,
                status=s.status,
                shipment_metadata=s.metadata,
            ))
            created += 1
        except Exception as exc:
            errors.append(ErrorDetail(field=s.shipment_reference, message=str(exc)))

    session.commit()
    return _ok(BatchResult(success=not errors, imported=created, errors=errors).model_dump())


# ---------------------------------------------------------------------------
# Data Import - Incidents
# ---------------------------------------------------------------------------


@router.post("/incidents", response_model=dict)
def report_incident(body: IncidentImport, session: Session = Depends(get_session)):
    try:
        driver_id = None
        vehicle_id = None
        if body.driver_name:
            driver = session.scalar(select(DriverProfile).where(DriverProfile.name == body.driver_name))
            driver_id = driver.id if driver else None
        if body.vehicle_identifier:
            vehicle = session.scalar(select(Vehicle).where(Vehicle.identifier == body.vehicle_identifier))
            vehicle_id = vehicle.id if vehicle else None

        incident = DriverIncident(
            driver_profile_id=driver_id,
            vehicle_id=vehicle_id,
            city=body.city,
            incident_type=body.incident_type,
            severity=body.severity,
            note=body.note,
        )
        session.add(incident)
        session.commit()
        session.refresh(incident)

        try:
            import asyncio
            asyncio.get_running_loop().create_task(dispatch_webhook_event(
                "incident.reported",
                {"incident_id": incident.id, "city": incident.city,
                 "incident_type": incident.incident_type, "severity": incident.severity},
            ))
        except Exception:
            pass

        return _ok(IncidentExport.model_validate(incident).model_dump())
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Data Import - Inventory
# ---------------------------------------------------------------------------


@router.patch("/inventory", response_model=dict)
def adjust_inventory(body: InventoryUpdateBatch, session: Session = Depends(get_session)):
    adjusted = 0
    errors: list[ErrorDetail] = []

    for upd in body.updates:
        facility = session.get(Facility, upd.facility_id)
        if facility is None:
            errors.append(ErrorDetail(field=str(upd.facility_id), message="Facility not found"))
            continue
        new_inv = facility.current_inventory_units + upd.adjustments
        if new_inv < 0:
            errors.append(ErrorDetail(field=str(upd.facility_id), message="Inventory cannot go below 0"))
            continue
        facility.current_inventory_units = new_inv
        adjusted += 1

    session.commit()
    return _ok(BatchResult(success=not errors, imported=adjusted, errors=errors).model_dump())


# ---------------------------------------------------------------------------
# Data Import - Events
# ---------------------------------------------------------------------------


@router.post("/events/bulk", response_model=dict)
def import_events(body: EventImportBatch, session: Session = Depends(get_session)):
    imported = 0
    errors: list[ErrorDetail] = []
    now = datetime.now(timezone.utc).date()

    for ev in body.events:
        try:
            event = NewsEvent(
                original_date=now, simulation_date=now,
                city=ev.city, category=ev.event_type,
                headline=ev.headline, relevant=True,
                impact_type=ev.impact_type, impact_score=ev.impact_score,
                model_probability=ev.severity,
            )
            session.add(event)
            imported += 1
        except Exception as exc:
            errors.append(ErrorDetail(field=ev.headline[:50], message=str(exc)))

    session.commit()
    return _ok(BatchResult(success=not errors, imported=imported, errors=errors).model_dump())


# ---------------------------------------------------------------------------
# Data Export - Snapshot
# ---------------------------------------------------------------------------


@router.get("/snapshot", response_model=dict)
def get_snapshot(session: Session = Depends(get_session)):
    try:
        sim_status = simulation_engine.snapshot_status()
        status_str = sim_status.status
        sim_time = str(sim_status.simulation_time) if sim_status.simulation_time else None
        speed = sim_status.speed_multiplier
        ticks = 0
    except Exception:
        status_str = "unknown"
        sim_time = None
        speed = 1.0
        ticks = 0

    facilities = [FacilityExport.model_validate(f) for f in session.scalars(select(Facility).where(Facility.active.is_(True))).all()]
    vehicles = [VehicleExport.model_validate(v) for v in session.scalars(select(Vehicle)).all()]
    drivers = [DriverExport.model_validate(d) for d in session.scalars(select(DriverProfile).where(DriverProfile.active.is_(True))).all()]
    objectives = [ObjectiveExport.model_validate(o) for o in session.scalars(select(Objective).where(Objective.active.is_(True))).all()]

    snap = IntegrationSnapshot(
        simulation_status=status_str,
        simulation_time=sim_time,
        speed_multiplier=speed,
        ticks=ticks,
        facilities=[],
        vehicles=[],
        drivers=[],
        objectives=[],
    )

    return _ok({
        "simulation_status": status_str,
        "simulation_time": sim_time,
        "speed_multiplier": speed,
        "ticks": ticks,
        "facilities": [f.model_dump() for f in facilities],
        "vehicles": [v.model_dump() for v in vehicles],
        "drivers": [d.model_dump() for d in drivers],
        "objectives": [o.model_dump() for o in objectives],
    })


# ---------------------------------------------------------------------------
# Data Export - Vehicles list
# ---------------------------------------------------------------------------


@router.get("/vehicles", response_model=dict)
def list_integration_vehicles(
    status_filter: str | None = Query(None, alias="status"),
    facility_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    query = select(Vehicle)
    if status_filter:
        query = query.where(Vehicle.status == status_filter)
    if facility_id:
        query = query.where(Vehicle.current_facility_id == facility_id)

    count_q = select(Vehicle.id)
    if status_filter:
        count_q = count_q.where(Vehicle.status == status_filter)
    if facility_id:
        count_q = count_q.where(Vehicle.current_facility_id == facility_id)
    total = len(session.scalars(count_q).all())

    items = session.scalars(query.offset((page - 1) * per_page).limit(per_page)).all()

    return _ok(
        [VehicleExport.model_validate(v).model_dump() for v in items],
        meta=_pagination(page, per_page, total),
    )


# ---------------------------------------------------------------------------
# Data Export - Facilities list
# ---------------------------------------------------------------------------


@router.get("/facilities", response_model=dict)
def list_integration_facilities(
    city: str | None = Query(None),
    facility_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    query = select(Facility)
    if city:
        query = query.where(Facility.city == city)
    if facility_type:
        query = query.where(Facility.facility_type == facility_type)

    total_query = select(Facility.id)
    if city:
        total_query = total_query.where(Facility.city == city)
    if facility_type:
        total_query = total_query.where(Facility.facility_type == facility_type)
    total = len(session.scalars(total_query).all())

    items = session.scalars(query.offset((page - 1) * per_page).limit(per_page)).all()

    return _ok(
        [FacilityExport.model_validate(f).model_dump() for f in items],
        meta=_pagination(page, per_page, total),
    )


# ---------------------------------------------------------------------------
# Data Export - Shipments
# ---------------------------------------------------------------------------


@router.get("/shipments", response_model=dict)
def list_integration_shipments(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    query = select(Shipment)
    count_q = select(Shipment.id)
    if status:
        query = query.where(Shipment.status == status)
        count_q = count_q.where(Shipment.status == status)

    total = len(session.scalars(count_q).all())
    items = session.scalars(query.offset((page - 1) * per_page).limit(per_page)).all()

    return _ok(
        [ShipmentExport.model_validate(s).model_dump() for s in items],
        meta=_pagination(page, per_page, total),
    )


# ---------------------------------------------------------------------------
# Data Export - Metrics
# ---------------------------------------------------------------------------


@router.get("/metrics", response_model=dict)
def get_metrics(session: Session = Depends(get_session)):
    latest = session.scalar(select(MetricsSnapshot).order_by(MetricsSnapshot.captured_at.desc()).limit(1))
    if latest:
        return _ok(MetricsExport(
            co2_saved_kg=latest.co2_saved_kg,
            idle_minutes_prevented=latest.idle_minutes_prevented,
            on_time_delivery_pct=latest.on_time_delivery_pct,
            warehouse_utilization_pct=latest.warehouse_utilization_pct,
            reroute_count=latest.reroute_count,
            active_trucks=latest.active_trucks,
            queued_trucks=latest.queued_trucks,
            financial_costs_saved_usd=latest.financial_costs_saved_usd,
            financial_costs_incurred_usd=latest.financial_costs_incurred_usd,
            timestamp=str(latest.captured_at),
        ).model_dump())
    return _ok(MetricsExport().model_dump())


# ---------------------------------------------------------------------------
# Data Export - Decisions
# ---------------------------------------------------------------------------


@router.get("/decisions", response_model=dict)
def list_decisions(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    count_q = select(Recommendation.id)
    total = len(session.scalars(count_q).all())

    items = session.scalars(
        select(Recommendation).order_by(Recommendation.created_at.desc())
        .offset((page - 1) * per_page).limit(per_page)
    ).all()

    return _ok(
        [DecisionExport.model_validate(r).model_dump() for r in items],
        meta=_pagination(page, per_page, total),
    )


# ---------------------------------------------------------------------------
# Data Export - Risk forecasts
# ---------------------------------------------------------------------------


@router.get("/forecasts/risk", response_model=dict)
def get_risk_forecasts(
    city: str | None = Query(None),
    hours: int = Query(12, ge=1, le=72),
    session: Session = Depends(get_session),
):
    try:
        cities = {city} if city else {"Chennai", "Mumbai", "Delhi", "Bengaluru", "Kolkata", "Hyderabad", "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Bhubaneswar", "Guwahati"}
        forecasts = forecast_service.forecast_all_cities(session, cities, forecast_hours=hours)
        return _ok([{
            "city": f.city,
            "risk": f.predicted_route_risk,
            "eta_multiplier": f.predicted_eta_multiplier,
            "closure_risk": f.predicted_closure_risk,
            "confidence": f.confidence,
            "factors": f.contributing_factors,
            "forecast_time": f.forecast_time.isoformat() if hasattr(f.forecast_time, 'isoformat') else str(f.forecast_time),
            "trend": f.trend_direction,
        } for f in forecasts])
    except Exception as exc:
        logger.warning("Risk forecast unavailable: %s", exc)
        return _ok([])


# ---------------------------------------------------------------------------
# Data Export - Demand forecasts
# ---------------------------------------------------------------------------


@router.get("/forecasts/demand", response_model=dict)
def get_demand_forecasts(
    facility_id: int | None = Query(None),
    days: int = Query(7, ge=1, le=30),
    session: Session = Depends(get_session),
):
    try:
        inventory_optimizer.forecast_window_hours = days * 24
        forecasts = inventory_optimizer.get_all_forecasts(session)
        if facility_id:
            forecasts = [f for f in forecasts if f.facility_id == facility_id]
        return _ok([{
            "facility_id": f.facility_id,
            "facility_name": f.facility_name,
            "predicted_demand": f.predicted_demand_units,
            "safety_stock": f.safety_stock_units,
            "reorder_point": f.reorder_point,
            "confidence": f.confidence,
            "trend": f.trend,
        } for f in forecasts])
    except Exception as exc:
        logger.warning("Demand forecast unavailable: %s", exc)
        return _ok([])


# ---------------------------------------------------------------------------
# Route Optimization - Compute Routes
# ---------------------------------------------------------------------------


@router.post("/routes/compute", response_model=dict)
def compute_routes(payload: ComputeRoutesRequest, session: Session = Depends(get_session)):
    try:
        if payload.graph is not None and payload.persist_graph:
            data_fusion_service.persist_graph(session, payload.graph)
        graph, adjusted_graph, routes, predictions = compute_logistics_routes(
            session=session, graph=payload.graph,
            origin_node_id=payload.origin_node_id,
            destination_node_id=payload.destination_node_id,
            weights=payload.weights, max_routes=payload.max_routes,
            driver_id=payload.driver_id,
            driver_reliability_score=payload.driver_reliability_score,
            driver_penalty_factor=payload.driver_penalty_factor,
            required_capacity=payload.required_capacity,
            switching_delay=payload.switching_delay,
            time_window_penalty=payload.time_window_penalty,
            apply_predictions=payload.prediction_enabled,
            delay_penalty_per_minute=payload.delay_penalty_per_minute,
            risk_penalty_factor=payload.risk_penalty_factor,
            port_context=payload.port_context,
            rail_context=payload.rail_context,
            weather_context=payload.weather_context,
            shipment_context=payload.shipment_context,
        )
        return _ok({
            "graph": graph.model_dump() if isinstance(graph, LogisticsGraph) else graph,
            "shortest_path": routes[0].model_dump() if hasattr(routes[0], "model_dump") else routes[0],
            "alternatives": [r.model_dump() if hasattr(r, "model_dump") else r for r in routes[1:]],
            "predictions": predictions.model_dump() if predictions and hasattr(predictions, "model_dump") else predictions,
        })
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Route Optimization - Predict
# ---------------------------------------------------------------------------


@router.post("/routes/predict", response_model=dict)
def predict_routes(payload: PredictionRequest, session: Session = Depends(get_session)):
    try:
        graph = resolve_logistics_graph(session, payload.graph)
        route_options = payload.route_options
        if not route_options:
            if not payload.origin_node_id or not payload.destination_node_id:
                raise HTTPException(status_code=400, detail="Provide route_options or origin_node_id and destination_node_id")
            _, _, route_options, _ = compute_logistics_routes(
                session=session, graph=graph,
                origin_node_id=payload.origin_node_id,
                destination_node_id=payload.destination_node_id,
                weights=payload.weights, max_routes=payload.max_routes,
                apply_predictions=False,
            )

        response = logistics_prediction_engine.predict(
            graph=graph, route_options=route_options,
            port_context=payload.port_context, rail_context=payload.rail_context,
            weather_context=payload.weather_context, shipment_context=payload.shipment_context,
        )
        if payload.persist:
            logistics_prediction_engine.persist_predictions(session, response)

        return _ok(response.model_dump() if hasattr(response, "model_dump") else response)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Route Optimization - Decide
# ---------------------------------------------------------------------------


@router.post("/routes/decide", response_model=dict)
def decide_route(payload: DecisionRequest):
    try:
        result = logistics_decision_engine.decide(
            route_options=payload.route_options,
            predictions=payload.predictions,
            delay_threshold_minutes=payload.delay_threshold_minutes,
            risk_threshold=payload.risk_threshold,
        )
        return _ok(result.model_dump() if hasattr(result, "model_dump") else result)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Route Optimization - Assign
# ---------------------------------------------------------------------------


@router.post("/routes/assign", response_model=dict)
def assign_route(payload: AssignRouteRequest, session: Session = Depends(get_session)):
    try:
        if payload.graph is not None:
            data_fusion_service.persist_graph(session, payload.graph)

        assignment_payload = payload
        if assignment_payload.driver_id is None:
            vehicle = session.get(Vehicle, assignment_payload.vehicle_id) if assignment_payload.vehicle_id else None
            if vehicle is not None:
                assignment_payload = assignment_payload.model_copy(update={"driver_id": vehicle.driver_profile_id})
            else:
                metadata = assignment_payload.metadata or {}
                high_value = bool(metadata.get("high_value")) or float(metadata.get("cargo_value", 0) or 0) >= 100000
                time_sensitive = bool(metadata.get("time_sensitive")) or float(metadata.get("sla_minutes", 0) or 0) > 0
                preferred = driver_performance_service.recommend_driver_for_assignment(
                    session, high_value=high_value, time_sensitive=time_sensitive
                )
                if preferred is not None:
                    assignment_payload = assignment_payload.model_copy(update={"driver_id": preferred.driver_id})

        result = logistics_execution_service.assign_route(session, assignment_payload)
        return _ok(result.model_dump() if hasattr(result, "model_dump") else result)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Route Optimization - Reroute
# ---------------------------------------------------------------------------


@router.post("/routes/reroute", response_model=dict)
def reroute_shipment(payload: RerouteRequest, session: Session = Depends(get_session)):
    try:
        from routes.logistics import resolve_logistics_graph, compute_logistics_routes

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

        predictions = payload.predictions or logistics_prediction_engine.predict(
            graph=graph, route_options=route_options
        )
        decision = logistics_decision_engine.decide(
            route_options=route_options, predictions=predictions,
            delay_threshold_minutes=payload.delay_threshold_minutes,
        )

        from models import LogisticsRoute
        previous_route = session.get(LogisticsRoute, shipment.current_route_id) if shipment.current_route_id is not None else None
        previous_route_option = logistics_execution_service.route_option_from_model(previous_route) if previous_route is not None else None
        improvement_score = logistics_decision_engine.improvement_score(previous_route_option, decision.recommended_route) if previous_route_option is not None else float("inf")

        if previous_route_option is not None and improvement_score <= payload.improvement_threshold:
            return _ok({
                "rerouted": False,
                "reason": "improvement_below_threshold",
                "improvement_score": improvement_score,
            })

        new_route = logistics_execution_service.create_reroute(
            session=session, shipment=shipment,
            route_option=decision.recommended_route,
            origin_node_key=origin_node_key,
            destination_node_key=destination_node_key,
        )
        return _ok({
            "rerouted": True,
            "new_route_id": new_route.id,
            "improvement_score": improvement_score if improvement_score != float("inf") else 0.0,
        })
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Route Optimization - Dispatch Optimize
# ---------------------------------------------------------------------------


@router.post("/dispatch/optimize", response_model=dict)
def optimize_dispatch(body: OptimizeDispatchRequest, session: Session = Depends(get_session)):
    try:
        facilities = session.scalars(
            select(Facility).where(Facility.id.in_(body.facility_ids))
        ).all()

        solutions = []
        for fac in facilities:
            solutions.append({
                "facility_id": fac.id,
                "facility_name": fac.name,
                "current_inventory": fac.current_inventory_units,
                "capacity": fac.base_capacity_units,
                "utilization_pct": round(fac.current_inventory_units / max(fac.base_capacity_units, 1) * 100, 2),
            })

        return _ok({
            "solutions_count": len(solutions),
            "solutions": solutions,
        })
    except Exception as exc:
        logger.warning("Dispatch optimize failed: %s", exc)
        return _ok({"solutions_count": 0, "solutions": [], "pareto_front": [], "note": str(exc)})


# ---------------------------------------------------------------------------
# Route Optimization - Simulation Decide (RL)
# ---------------------------------------------------------------------------


@router.post("/simulation/decide", response_model=dict)
def simulation_decide(body: SimulationDecideRequest):
    try:
        rl = get_rl_engine()
        state = StateVector(
            utilization_norm=body.state_vector[0],
            route_risk=body.state_vector[1],
            eta_multiplier=body.state_vector[2],
            sla_urgency=body.state_vector[3],
            payload_norm=body.state_vector[4],
            priority_norm=body.state_vector[5],
            port_pressure=body.state_vector[6],
            weather_severity=body.state_vector[7],
            news_severity=body.state_vector[8],
            time_of_day=body.state_vector[9],
        )
        action, q_value = rl.select_action(state)
        with torch.no_grad():
            state_tensor = torch.tensor(state.to_array(), dtype=torch.float32, device=rl.device).unsqueeze(0)
            all_q = rl.q_network(state_tensor)[0].tolist()

        return _ok(SimulationDecideResponse(
            action=action,
            action_index=rl.ACTIONS.index(action) if action in rl.ACTIONS else 0,
            confidence=q_value,
            q_values=all_q,
        ).model_dump())
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Route Optimization - Telemetry Simulate
# ---------------------------------------------------------------------------


@router.post("/telemetry/simulate", response_model=dict)
def simulate_telemetry(payload: TelemetrySimulationRequest):
    try:
        result = telemetry_simulation_service.simulate(
            route=payload.route, payload_tons=payload.payload_tons,
            shipment_id=payload.shipment_id, route_id=payload.route_id,
        )
        return _ok(result.model_dump() if hasattr(result, "model_dump") else result)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Webhook Management
# ---------------------------------------------------------------------------


@router.post("/webhooks", response_model=dict)
def create_webhook(
    body: WebhookCreate,
    client: IntegrationClient = Depends(verify_api_key),
    session: Session = Depends(get_session),
):
    import secrets

    secret = secrets.token_hex(32)
    sub = WebhookSubscription(
        client_id=client.id,
        callback_url=body.callback_url,
        events=json.dumps(body.events),
        secret=secret,
        retry_count=body.retry_count,
        timeout_seconds=body.timeout_seconds,
        enabled=True,
    )
    session.add(sub)
    session.commit()
    session.refresh(sub)

    return _ok({
        "id": sub.id,
        "callback_url": sub.callback_url,
        "events": body.events,
        "secret": secret,
        "retry_count": sub.retry_count,
        "timeout_seconds": sub.timeout_seconds,
        "enabled": sub.enabled,
        "created_at": str(sub.created_at),
    })


@router.get("/webhooks", response_model=dict)
def list_webhooks(
    client: IntegrationClient = Depends(verify_api_key),
    session: Session = Depends(get_session),
):
    subs = session.scalars(
        select(WebhookSubscription).where(WebhookSubscription.client_id == client.id)
    ).all()

    return _ok([
        WebhookExport(
            id=s.id, client_id=s.client_id,
            callback_url=s.callback_url, events=json.loads(s.events),
            retry_count=s.retry_count, timeout_seconds=s.timeout_seconds,
            enabled=s.enabled, created_at=s.created_at,
        ).model_dump()
        for s in subs
    ])


@router.patch("/webhooks/{webhook_id}", response_model=dict)
def update_webhook(
    webhook_id: int,
    body: WebhookUpdate,
    client: IntegrationClient = Depends(verify_api_key),
    session: Session = Depends(get_session),
):
    sub = session.scalar(
        select(WebhookSubscription).where(
            WebhookSubscription.id == webhook_id,
            WebhookSubscription.client_id == client.id,
        )
    )
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    if body.callback_url is not None:
        sub.callback_url = body.callback_url
    if body.events is not None:
        sub.events = json.dumps(body.events)
    if body.retry_count is not None:
        sub.retry_count = body.retry_count
    if body.timeout_seconds is not None:
        sub.timeout_seconds = body.timeout_seconds
    if body.enabled is not None:
        sub.enabled = body.enabled

    session.commit()
    return _ok({"id": sub.id, "updated": True})


@router.delete("/webhooks/{webhook_id}", response_model=dict)
def delete_webhook(
    webhook_id: int,
    client: IntegrationClient = Depends(verify_api_key),
    session: Session = Depends(get_session),
):
    sub = session.scalar(
        select(WebhookSubscription).where(
            WebhookSubscription.id == webhook_id,
            WebhookSubscription.client_id == client.id,
        )
    )
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    session.delete(sub)
    session.commit()
    return _ok({"id": webhook_id, "deleted": True})


@router.get("/webhooks/{webhook_id}/deliveries", response_model=dict)
def list_webhook_deliveries(
    webhook_id: int,
    client: IntegrationClient = Depends(verify_api_key),
    session: Session = Depends(get_session),
):
    sub = session.scalar(
        select(WebhookSubscription).where(
            WebhookSubscription.id == webhook_id,
            WebhookSubscription.client_id == client.id,
        )
    )
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    deliveries = session.scalars(
        select(WebhookDelivery).where(WebhookDelivery.subscription_id == webhook_id)
        .order_by(WebhookDelivery.attempted_at.desc()).limit(100)
    ).all()

    return _ok([
        WebhookDeliveryExport(
            id=d.id, event_type=d.event_type,
            success=d.success, attempt_number=d.attempt_number,
            response_status=d.response_status, attempted_at=d.attempted_at,
        ).model_dump()
        for d in deliveries
    ])


# ---------------------------------------------------------------------------
# Management router — no API key required (uses Firebase/demo session)
# ---------------------------------------------------------------------------

management_router = APIRouter(
    prefix="/api/v1/integration/manage",
    tags=["Integration Management"],
)


@management_router.get("/key")
def get_management_key(session: Session = Depends(get_session)):
    client = session.scalar(select(IntegrationClient).where(IntegrationClient.enabled.is_(True)).limit(1))
    if client is None:
        return _ok(None)
    return _ok({
        "id": client.id,
        "name": client.name,
        "api_key_prefix": client.api_key_prefix,
        "has_full_key": False,
    })


@management_router.post("/key/regenerate")
def regenerate_management_key(session: Session = Depends(get_session)):
    import hashlib
    import secrets

    client = session.scalar(select(IntegrationClient).where(IntegrationClient.enabled.is_(True)).limit(1))
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No integration client found")

    api_key = f"regc_{secrets.token_hex(24)}"
    api_key_hash = hashlib.sha256(f"integ-api-v1-2026:{api_key}".encode()).hexdigest()
    api_key_prefix = api_key[:8]

    client.api_key_hash = api_key_hash
    client.api_key_prefix = api_key_prefix
    client.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.commit()

    return _ok({
        "api_key": api_key,
        "api_key_prefix": api_key_prefix,
        "name": client.name,
    })


# ---------------------------------------------------------------------------
# Admin — Client Management
# ---------------------------------------------------------------------------

@management_router.get("/clients")
def list_clients(session: Session = Depends(get_session)):
    from sqlalchemy import func as _func
    from models import ClientSimulation as CS

    clients = session.scalars(
        select(IntegrationClient).order_by(IntegrationClient.created_at.desc())
    ).all()

    result = []
    for c in clients:
        fac_count = session.scalar(
            select(_func.count(Facility.id)).where(Facility.client_id == c.id)
        ) or 0
        veh_count = session.scalar(
            select(_func.count(Vehicle.id)).where(Vehicle.client_id == c.id)
        ) or 0
        drv_count = session.scalar(
            select(_func.count(DriverProfile.id)).where(DriverProfile.client_id == c.id)
        ) or 0
        obj_count = session.scalar(
            select(_func.count(Objective.id)).where(Objective.client_id == c.id)
        ) or 0

        sim = session.scalar(select(CS).where(CS.client_id == c.id))
        sim_status = sim.status if sim else "inactive"

        result.append({
            "id": c.id,
            "name": c.company_name or c.name,
            "email": c.contact_email,
            "api_key_prefix": c.api_key_prefix,
            "status": sim_status,
            "simulation_status": sim_status,
            "facilities": fac_count,
            "vehicles": veh_count,
            "drivers": drv_count,
            "objectives": obj_count,
            "created_at": str(c.created_at),
            "enabled": c.enabled,
        })

    return _ok(result)


@management_router.get("/clients/stats")
def client_stats(session: Session = Depends(get_session)):
    total = session.scalar(select(func.count(IntegrationClient.id))) or 0
    active = session.scalar(
        select(func.count(IntegrationClient.id)).where(IntegrationClient.enabled.is_(True))
    ) or 0
    with_password = session.scalar(
        select(func.count(IntegrationClient.id)).where(IntegrationClient.password_hash.isnot(None))
    ) or 0

    return _ok({
        "total_clients": total,
        "active_clients": active,
        "portal_users": with_password,
    })

