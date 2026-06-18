"""Client portal — data upload routes (CSV + JSON)."""
from __future__ import annotations

import asyncio
import csv
import io
import json as _json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_session
from middleware.firebase_client import get_or_create_client
from models import (
    ClientSimulation,
    DriverProfile,
    Facility,
    IntegrationClient,
    Objective,
    Vehicle,
)
from schemas.client import UploadResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/client/upload", tags=["Client Portal Upload"])

INDIA_LAT_MIN, INDIA_LAT_MAX = 6.5, 37.0
INDIA_LON_MIN, INDIA_LON_MAX = 68.0, 97.5


def _validate_coordinates(lat: float, lng: float) -> bool:
    return (
        INDIA_LAT_MIN <= lat <= INDIA_LAT_MAX
        and INDIA_LON_MIN <= lng <= INDIA_LON_MAX
    )


def _parse_csv(content: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(content))
    rows = []
    for row in reader:
        stripped = {k.strip(): v.strip() for k, v in row.items() if k.strip()}
        rows.append(stripped)
    return rows


def _parse_json(content: str) -> list[dict[str, Any]]:
    data = _json.loads(content)
    if isinstance(data, dict):
        data = [data]
    return data


def _check_auto_start(client_id: int, session: Session) -> bool:
    has_facilities = session.scalar(
        select(func.count(Facility.id)).where(Facility.client_id == client_id)
    ) > 0
    has_vehicles = session.scalar(
        select(func.count(Vehicle.id)).where(Vehicle.client_id == client_id)
    ) > 0
    has_drivers = session.scalar(
        select(func.count(DriverProfile.id)).where(DriverProfile.client_id == client_id)
    ) > 0
    has_objectives = session.scalar(
        select(func.count(Objective.id)).where(Objective.client_id == client_id)
    ) > 0

    if not all([has_facilities, has_vehicles, has_drivers, has_objectives]):
        return False

    sim = session.scalar(
        select(ClientSimulation).where(ClientSimulation.client_id == client_id)
    )
    if sim is None:
        sim = ClientSimulation(client_id=client_id, status="idle")
        session.add(sim)
        session.commit()

    # Trigger engine start in background
    from services.simulation_manager import simulation_manager

    async def _start_and_log():
        try:
            await simulation_manager.start_client(client_id, session)
            logger.info("[DIAG] _check_auto_start: engine started successfully for client_id=%s", client_id)
        except Exception as exc:
            logger.error("[DIAG] _check_auto_start: engine start FAILED for client_id=%s: %s", client_id, exc)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_start_and_log())
    except RuntimeError:
        logger.warning("[DIAG] _check_auto_start: no event loop, skipping engine start for client_id=%s", client_id)
        pass  # No event loop available (test environment)

    return True


@router.post("/facilities", response_model=UploadResult)
async def upload_facilities(
    request: Request,
    client: IntegrationClient = Depends(get_or_create_client),
    session: Session = Depends(get_session),
):
    rows = await _read_rows(request)
    imported = 0
    updated = 0
    errors: list[dict[str, Any]] = []

    for i, row in enumerate(rows):
        try:
            name = str(row.get("name", "")).strip()
            if not name:
                errors.append({"row": i + 1, "field": "name", "message": "Required"})
                continue
            city = str(row.get("city", "")).strip()
            if not city:
                errors.append({"row": i + 1, "field": "city", "message": "Required"})
                continue
            ftype = str(row.get("facility_type", "warehouse")).strip()
            if ftype not in ("warehouse", "port"):
                errors.append({"row": i + 1, "field": "facility_type", "message": "Must be warehouse or port"})
                continue
            lat = float(row.get("latitude", 0))
            lng = float(row.get("longitude", 0))
            if not _validate_coordinates(lat, lng):
                errors.append({"row": i + 1, "field": "latitude/longitude", "message": f"Coordinates ({lat}, {lng}) must be within India bounds (lat {INDIA_LAT_MIN}-{INDIA_LAT_MAX}, lon {INDIA_LON_MIN}-{INDIA_LON_MAX})"})
                continue
            cap = int(row.get("base_capacity_units", 10000))

            existing = session.scalar(
                select(Facility).where(Facility.name == name, Facility.client_id == client.id)
            )
            if existing:
                existing.city = city
                existing.facility_type = ftype
                existing.latitude = lat
                existing.longitude = lng
                existing.base_capacity_units = cap
                existing.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(tzinfo=None)
                updated += 1
            else:
                session.add(Facility(
                    name=name, city=city, facility_type=ftype,
                    latitude=lat, longitude=lng,
                    base_capacity_units=cap,
                    current_inventory_units=0,
                    initial_inventory_units=0,
                    client_id=client.id,
                ))
                imported += 1
        except Exception as exc:
            errors.append({"row": i + 1, "message": str(exc)})

    session.commit()
    auto_started = _check_auto_start(client.id, session)

    return UploadResult(success=len(errors) == 0, imported=imported, updated=updated, errors=errors, auto_started=auto_started)


@router.post("/vehicles", response_model=UploadResult)
async def upload_vehicles(
    request: Request,
    client: IntegrationClient = Depends(get_or_create_client),
    session: Session = Depends(get_session),
):
    rows = await _read_rows(request)
    imported = 0
    updated = 0
    errors: list[dict[str, Any]] = []

    for i, row in enumerate(rows):
        try:
            identifier = str(row.get("identifier", "")).strip()
            if not identifier:
                errors.append({"row": i + 1, "field": "identifier", "message": "Required"})
                continue
            payload = int(row.get("payload_capacity_units", 0))
            if payload <= 0:
                errors.append({"row": i + 1, "field": "payload_capacity_units", "message": "Must be > 0"})
                continue
            home_name = str(row.get("home_facility_name", "")).strip()
            if not home_name:
                errors.append({"row": i + 1, "field": "home_facility_name", "message": "Required"})
                continue
            vtype = str(row.get("vehicle_type", "truck")).strip()
            speed = float(row.get("average_speed_kmph", 48))

            home_fac = session.scalar(
                select(Facility).where(Facility.name == home_name, Facility.client_id == client.id)
            )
            if home_fac is None:
                errors.append({"row": i + 1, "field": "home_facility_name", "message": f"Facility '{home_name}' not found"})
                continue

            driver = session.scalar(
                select(DriverProfile).where(DriverProfile.client_id == client.id).limit(1)
            )

            existing = session.scalar(
                select(Vehicle).where(Vehicle.identifier == identifier, Vehicle.client_id == client.id)
            )
            if existing:
                existing.vehicle_type = vtype
                existing.payload_capacity_units = payload
                existing.home_facility_id = home_fac.id
                existing.average_speed_kmph = speed
                updated += 1
            else:
                session.add(Vehicle(
                    identifier=identifier, vehicle_type=vtype,
                    payload_capacity_units=payload,
                    home_facility_id=home_fac.id,
                    current_facility_id=home_fac.id,
                    driver_profile_id=driver.id if driver else 1,
                    average_speed_kmph=speed,
                    client_id=client.id,
                ))
                imported += 1
        except Exception as exc:
            errors.append({"row": i + 1, "message": str(exc)})

    session.commit()
    auto_started = _check_auto_start(client.id, session)
    return UploadResult(success=len(errors) == 0, imported=imported, updated=updated, errors=errors, auto_started=auto_started)


@router.post("/drivers", response_model=UploadResult)
async def upload_drivers(
    request: Request,
    client: IntegrationClient = Depends(get_or_create_client),
    session: Session = Depends(get_session),
):
    rows = await _read_rows(request)
    imported = 0
    updated = 0
    errors: list[dict[str, Any]] = []

    for i, row in enumerate(rows):
        try:
            name = str(row.get("name", "")).strip()
            if not name:
                errors.append({"row": i + 1, "field": "name", "message": "Required"})
                continue
            active = str(row.get("active", "true")).lower() in ("true", "1", "yes")

            existing = session.scalar(
                select(DriverProfile).where(DriverProfile.name == name, DriverProfile.client_id == client.id)
            )
            if existing:
                existing.active = active
                updated += 1
            else:
                session.add(DriverProfile(name=name, active=active, client_id=client.id))
                imported += 1
        except Exception as exc:
            errors.append({"row": i + 1, "message": str(exc)})

    session.commit()
    auto_started = _check_auto_start(client.id, session)
    return UploadResult(success=len(errors) == 0, imported=imported, updated=updated, errors=errors, auto_started=auto_started)


@router.post("/objectives", response_model=UploadResult)
async def upload_objectives(
    request: Request,
    client: IntegrationClient = Depends(get_or_create_client),
    session: Session = Depends(get_session),
):
    rows = await _read_rows(request)
    imported = 0
    updated = 0
    errors: list[dict[str, Any]] = []

    for i, row in enumerate(rows):
        try:
            name = str(row.get("name", "")).strip()
            if not name:
                errors.append({"row": i + 1, "field": "name", "message": "Required"})
                continue
            origin_name = str(row.get("origin_facility_name", "")).strip()
            dest_name = str(row.get("destination_facility_name", "")).strip()
            if not origin_name:
                errors.append({"row": i + 1, "field": "origin_facility_name", "message": "Required"})
                continue
            if not dest_name:
                errors.append({"row": i + 1, "field": "destination_facility_name", "message": "Required"})
                continue

            origin = session.scalar(
                select(Facility).where(Facility.name == origin_name, Facility.client_id == client.id)
            )
            dest = session.scalar(
                select(Facility).where(Facility.name == dest_name, Facility.client_id == client.id)
            )
            if origin is None:
                errors.append({"row": i + 1, "field": "origin_facility_name", "message": f"Facility '{origin_name}' not found"})
                continue
            if dest is None:
                errors.append({"row": i + 1, "field": "destination_facility_name", "message": f"Facility '{dest_name}' not found"})
                continue

            commodity = str(row.get("commodity", "General")).strip()
            interval = int(row.get("dispatch_interval_minutes", 120))
            sla = int(row.get("sla_minutes", 720))
            priority = int(row.get("priority", 1))

            existing = session.scalar(
                select(Objective).where(Objective.name == name, Objective.client_id == client.id)
            )
            if existing:
                existing.commodity = commodity
                existing.origin_facility_id = origin.id
                existing.destination_facility_id = dest.id
                existing.dispatch_interval_minutes = interval
                existing.sla_minutes = sla
                existing.priority = priority
                updated += 1
            else:
                # Assign vehicles from the same client
                vehicles = session.scalars(
                    select(Vehicle).where(Vehicle.client_id == client.id)
                ).all()
                assigned_ids = [v.id for v in vehicles[:min(len(vehicles), 4)]]

                session.add(Objective(
                    name=name, commodity=commodity,
                    origin_facility_id=origin.id,
                    destination_facility_id=dest.id,
                    dispatch_interval_minutes=interval,
                    sla_minutes=sla,
                    priority=priority,
                    assigned_vehicle_ids=assigned_ids,
                    client_id=client.id,
                ))
                imported += 1
        except Exception as exc:
            errors.append({"row": i + 1, "message": str(exc)})

    session.commit()
    auto_started = _check_auto_start(client.id, session)
    return UploadResult(success=len(errors) == 0, imported=imported, updated=updated, errors=errors, auto_started=auto_started)


async def _read_rows(request: Request) -> list[dict[str, Any]]:
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    text = body.decode("utf-8")

    if "application/json" in content_type:
        return _parse_json(text)
    elif "text/csv" in content_type:
        return _parse_csv(text)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use Content-Type: application/json or text/csv",
        )
