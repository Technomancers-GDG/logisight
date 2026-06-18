from __future__ import annotations

from datetime import datetime, date
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from schemas.core import ORMModel

class ObjectiveBase(BaseModel):
    name: str
    commodity: str
    origin_facility_id: int
    destination_facility_id: int
    dispatch_interval_minutes: int = 120
    loading_duration_minutes: int = 30
    unloading_duration_minutes: int = 35
    sla_minutes: int = 720
    priority: int = 1
    assigned_vehicle_ids: list[int] = Field(default_factory=list)
    fallback_facility_ids: list[int] = Field(default_factory=list)
    active: bool = True


class ObjectiveCreate(ObjectiveBase):
    pass


class ObjectiveUpdate(BaseModel):
    assigned_vehicle_ids: list[int] | None = None
    fallback_facility_ids: list[int] | None = None
    dispatch_interval_minutes: int | None = None
    loading_duration_minutes: int | None = None
    unloading_duration_minutes: int | None = None
    sla_minutes: int | None = None
    priority: int | None = None
    active: bool | None = None


class ObjectiveRead(ObjectiveBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class RouteTemplateRead(ORMModel):
    id: int
    route_key: str
    origin_facility_id: int
    destination_facility_id: int
    distance_km: float
    duration_minutes: float
    encoded_polyline: str
    steps: list[dict[str, Any]]
    source: str
    refreshed_at: datetime
