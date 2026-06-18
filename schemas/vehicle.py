from __future__ import annotations

from datetime import datetime, date
from typing import Any
from pydantic import BaseModel, ConfigDict
from schemas.core import ORMModel

class VehicleBase(BaseModel):
    identifier: str
    vehicle_type: str = "truck"
    payload_capacity_units: int
    home_facility_id: int
    current_facility_id: int | None = None
    driver_profile_id: int
    default_objective_id: int | None = None
    average_speed_kmph: float = 48.0
    emission_kg_per_km: float = 1.6
    rest_every_hours: float = 8.0
    rest_duration_minutes: int = 45
    status: str = "idle"


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    current_facility_id: int | None = None
    default_objective_id: int | None = None
    status: str | None = None


class VehicleRead(VehicleBase, ORMModel):
    id: int
    available_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class VehicleStateView(BaseModel):
    vehicle_id: int
    identifier: str
    status: str
    objective_id: int | None
    current_facility_id: int | None
    next_facility_id: int | None
    progress_pct: float
    eta: datetime | None
    payload_units: int
    recommendation_action: str | None = None
    decision_trace: dict[str, Any] | None = None
