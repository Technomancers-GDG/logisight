"""CRUD routes for facilities, port-links, drivers, vehicles, objectives, routes, and events."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_session
from models import (
    DriverProfile,
    Facility,
    NewsEvent,
    Objective,
    PortLink,
    RouteTemplate,
    Vehicle,
    WeatherEvent,
)
from schemas import (
    FacilityCreate,
    FacilityRead,
    FacilityUpdate,
    PortLinkCreate,
    PortLinkRead,
    DriverProfileCreate,
    DriverProfileRead,
    VehicleCreate,
    VehicleRead,
    VehicleUpdate,
    ObjectiveCreate,
    ObjectiveRead,
    ObjectiveUpdate,
    RouteTemplateRead,
    ImportSummary,
    NewsEventRead,
    WeatherEventRead,
)
from services.event_ingestion import EventIngestionService
from services.news_relevance import NewsRelevanceService

crud_router = APIRouter(tags=["CRUD"])

news_model = NewsRelevanceService()
event_ingestion_service = EventIngestionService(news_model)


def apply_updates(instance, updates: dict):
    for field_name, value in updates.items():
        setattr(instance, field_name, value)
    return instance


# --- Facilities ---
@crud_router.get("/api/facilities", response_model=list[FacilityRead])
def list_facilities(session: Session = Depends(get_session)) -> list[Facility]:
    return session.scalars(
        select(Facility).where(Facility.client_id.is_(None)).order_by(Facility.name)
    ).all()


@crud_router.post("/api/facilities", response_model=FacilityRead)
def create_facility(payload: FacilityCreate, session: Session = Depends(get_session)) -> Facility:
    facility = Facility(**payload.model_dump())
    session.add(facility)
    session.commit()
    session.refresh(facility)
    return facility


@crud_router.patch("/api/facilities/{facility_id}", response_model=FacilityRead)
def update_facility(facility_id: int, payload: FacilityUpdate, session: Session = Depends(get_session)) -> Facility:
    facility = session.get(Facility, facility_id)
    if facility is None:
        raise HTTPException(status_code=404, detail="Facility not found")
    apply_updates(facility, payload.model_dump(exclude_unset=True))
    session.commit()
    session.refresh(facility)
    return facility


# --- Port Links ---
@crud_router.get("/api/port-links", response_model=list[PortLinkRead])
def list_port_links(session: Session = Depends(get_session)) -> list[PortLink]:
    return session.scalars(select(PortLink).order_by(PortLink.id.desc())).all()


@crud_router.post("/api/port-links", response_model=PortLinkRead)
def create_port_link(payload: PortLinkCreate, session: Session = Depends(get_session)) -> PortLink:
    port_link = PortLink(**payload.model_dump())
    session.add(port_link)
    session.commit()
    session.refresh(port_link)
    return port_link


# --- Drivers ---
@crud_router.get("/api/drivers", response_model=list[DriverProfileRead])
def list_drivers(session: Session = Depends(get_session)) -> list[DriverProfile]:
    return session.scalars(
        select(DriverProfile).where(DriverProfile.client_id.is_(None)).order_by(DriverProfile.name)
    ).all()


@crud_router.post("/api/drivers", response_model=DriverProfileRead)
def create_driver(payload: DriverProfileCreate, session: Session = Depends(get_session)) -> DriverProfile:
    driver = DriverProfile(**payload.model_dump())
    session.add(driver)
    session.commit()
    session.refresh(driver)
    return driver


# --- Vehicles ---
@crud_router.get("/api/vehicles", response_model=list[VehicleRead])
def list_vehicles(session: Session = Depends(get_session)) -> list[Vehicle]:
    return session.scalars(
        select(Vehicle).where(Vehicle.client_id.is_(None)).order_by(Vehicle.identifier)
    ).all()


@crud_router.post("/api/vehicles", response_model=VehicleRead)
def create_vehicle(payload: VehicleCreate, session: Session = Depends(get_session)) -> Vehicle:
    vehicle = Vehicle(**payload.model_dump())
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)
    return vehicle


@crud_router.get("/api/vehicles/{vehicle_id}", response_model=VehicleRead)
def get_vehicle(vehicle_id: int, session: Session = Depends(get_session)) -> Vehicle:
    vehicle = session.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


@crud_router.patch("/api/vehicles/{vehicle_id}", response_model=VehicleRead)
def update_vehicle(vehicle_id: int, payload: VehicleUpdate, session: Session = Depends(get_session)) -> Vehicle:
    vehicle = session.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    apply_updates(vehicle, payload.model_dump(exclude_unset=True))
    session.commit()
    session.refresh(vehicle)
    return vehicle


# --- Objectives ---
@crud_router.get("/api/objectives", response_model=list[ObjectiveRead])
def list_objectives(session: Session = Depends(get_session)) -> list[Objective]:
    return session.scalars(
        select(Objective).where(Objective.client_id.is_(None)).order_by(Objective.priority.desc(), Objective.name)
    ).all()


@crud_router.post("/api/objectives", response_model=ObjectiveRead)
def create_objective(payload: ObjectiveCreate, session: Session = Depends(get_session)) -> Objective:
    objective = Objective(**payload.model_dump())
    session.add(objective)
    session.commit()
    session.refresh(objective)
    return objective


@crud_router.patch("/api/objectives/{objective_id}", response_model=ObjectiveRead)
def update_objective(objective_id: int, payload: ObjectiveUpdate, session: Session = Depends(get_session)) -> Objective:
    objective = session.get(Objective, objective_id)
    if objective is None:
        raise HTTPException(status_code=404, detail="Objective not found")
    apply_updates(objective, payload.model_dump(exclude_unset=True))
    session.commit()
    session.refresh(objective)
    return objective


# --- Routes ---
@crud_router.get("/api/routes", response_model=list[RouteTemplateRead])
def list_routes(session: Session = Depends(get_session)) -> list[RouteTemplate]:
    demo_facility_ids = session.scalars(
        select(Facility.id).where(Facility.client_id.is_(None))
    ).all()
    if not demo_facility_ids:
        return []
    return session.scalars(
        select(RouteTemplate).where(
            RouteTemplate.origin_facility_id.in_(demo_facility_ids),
            RouteTemplate.destination_facility_id.in_(demo_facility_ids),
        ).order_by(RouteTemplate.refreshed_at.desc())
    ).all()


# --- Events ---
@crud_router.post("/api/events/import", response_model=ImportSummary)
def import_events(full_news_import: bool = Query(default=False), session: Session = Depends(get_session)) -> ImportSummary:
    return event_ingestion_service.import_all(session, full_news_import=full_news_import, sample_per_sheet=600)


@crud_router.get("/api/events/news", response_model=list[NewsEventRead])
def list_news_events(relevant_only: bool = Query(default=True), session: Session = Depends(get_session)) -> list[NewsEvent]:
    statement = select(NewsEvent).order_by(NewsEvent.simulation_date.desc()).limit(150)
    if relevant_only:
        statement = statement.where(NewsEvent.relevant.is_(True))
    return session.scalars(statement).all()


@crud_router.get("/api/events/weather", response_model=list[WeatherEventRead])
def list_weather_events(session: Session = Depends(get_session)) -> list[WeatherEvent]:
    return session.scalars(
        select(WeatherEvent).order_by(WeatherEvent.simulation_date.desc()).limit(150)
    ).all()