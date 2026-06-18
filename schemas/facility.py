from __future__ import annotations

from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, Field
from schemas.core import ORMModel

class FacilityBase(BaseModel):
    name: str
    city: str
    facility_type: str = Field(pattern="^(warehouse|port)$")
    latitude: float
    longitude: float
    base_capacity_units: int
    current_inventory_units: int = 0
    initial_inventory_units: int = 0
    queue_capacity_units: int = 0
    active: bool = True


class FacilityCreate(FacilityBase):
    pass


class FacilityUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    base_capacity_units: int | None = None
    current_inventory_units: int | None = None
    initial_inventory_units: int | None = None
    queue_capacity_units: int | None = None
    active: bool | None = None


class FacilityRead(FacilityBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class PortLinkBase(BaseModel):
    warehouse_id: int
    port_id: int
    reserved_capacity_units: int = 0
    spillover_threshold_pct: float = 80.0
    max_spillover_units: int = 0
    active: bool = True


class PortLinkCreate(PortLinkBase):
    pass


class PortLinkRead(PortLinkBase, ORMModel):
    id: int


class FacilityLoadView(BaseModel):
    facility_id: int
    facility_name: str
    facility_type: str
    city: str
    latitude: float
    longitude: float
    utilization_pct: float
    effective_available_units: int
    queue_capacity_units: int
    current_inventory_units: int
