from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from schemas.core import ORMModel


class IntegrationStatus(BaseModel):
    version: str = "1.0"
    api_version: str = "v1"
    status: str = "ok"


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str


class BatchResult(BaseModel):
    success: bool
    imported: int = 0
    updated: int = 0
    errors: list[ErrorDetail] = Field(default_factory=list)


class PaginationMeta(BaseModel):
    page: int = 1
    per_page: int = 50
    total: int = 0


class Envelope(BaseModel):
    success: bool
    data: Any = None
    meta: PaginationMeta | None = None
    error: ErrorDetail | None = None


class RefCodeMixin(BaseModel):
    ref_code: str | None = Field(default=None, max_length=120, description="Client's external identifier for this entity")


class FacilityImport(RefCodeMixin):
    name: str = Field(min_length=1, max_length=120)
    city: str = Field(max_length=80)
    facility_type: Literal["warehouse", "port"] = "warehouse"
    latitude: float
    longitude: float
    base_capacity_units: int = Field(default=10000, ge=0)
    current_inventory_units: int = Field(default=0, ge=0)
    queue_capacity_units: int = Field(default=0, ge=0)
    active: bool = True


class FacilityImportBatch(BaseModel):
    facilities: list[FacilityImport] = Field(min_length=1, max_length=500)


class FacilityExport(ORMModel):
    id: int
    name: str
    city: str
    facility_type: str
    latitude: float
    longitude: float
    base_capacity_units: int
    current_inventory_units: int
    queue_capacity_units: int
    active: bool
    ref_code: str | None = None
    created_at: datetime


class VehicleImport(RefCodeMixin):
    identifier: str = Field(min_length=1, max_length=80)
    vehicle_type: str = Field(default="truck", max_length=40)
    payload_capacity_units: int = Field(ge=0)
    home_facility_name: str = Field(min_length=1, description="Mapped via facility name")
    average_speed_kmph: float = Field(default=48.0, ge=0)
    emission_kg_per_km: float = Field(default=1.6, ge=0)
    status: str = Field(default="idle", max_length=40)


class VehicleImportBatch(BaseModel):
    vehicles: list[VehicleImport] = Field(min_length=1, max_length=500)


class VehicleExport(ORMModel):
    id: int
    identifier: str
    vehicle_type: str
    payload_capacity_units: int
    home_facility_id: int
    current_facility_id: int | None
    driver_profile_id: int | None
    average_speed_kmph: float
    emission_kg_per_km: float
    status: str
    ref_code: str | None = None
    created_at: datetime


class DriverImport(RefCodeMixin):
    name: str = Field(min_length=1, max_length=120)
    active: bool = True


class DriverImportBatch(BaseModel):
    drivers: list[DriverImport] = Field(min_length=1, max_length=200)


class DriverExport(ORMModel):
    id: int
    name: str
    active: bool
    ref_code: str | None = None


class ObjectiveImport(RefCodeMixin):
    name: str = Field(min_length=1, max_length=120)
    commodity: str = Field(max_length=80)
    origin_facility_name: str = Field(min_length=1)
    destination_facility_name: str = Field(min_length=1)
    dispatch_interval_minutes: int = Field(default=120, ge=0)
    sla_minutes: int = Field(default=720, ge=0)
    priority: int = Field(default=1, ge=1, le=10)
    active: bool = True


class ObjectiveImportBatch(BaseModel):
    objectives: list[ObjectiveImport] = Field(min_length=1, max_length=100)


class ObjectiveExport(ORMModel):
    id: int
    name: str
    commodity: str
    origin_facility_id: int
    destination_facility_id: int
    dispatch_interval_minutes: int
    sla_minutes: int
    priority: int
    active: bool
    ref_code: str | None = None


class ShipmentImport(BaseModel):
    shipment_reference: str = Field(min_length=1, max_length=120)
    origin_node_key: str = Field(min_length=1, max_length=120)
    destination_node_key: str = Field(min_length=1, max_length=120)
    cargo_type: str = Field(default="general", max_length=100)
    quantity_units: int = Field(default=0, ge=0)
    status: str = Field(default="created", max_length=40)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ShipmentImportBatch(BaseModel):
    shipments: list[ShipmentImport] = Field(min_length=1, max_length=200)


class ShipmentExport(ORMModel):
    id: int
    shipment_reference: str
    origin_node_key: str
    destination_node_key: str
    current_location_node_key: str | None
    cargo_type: str
    quantity_units: int
    status: str
    assigned_driver_id: int | None
    assigned_vehicle_id: int | None
    created_at: datetime


class IncidentImport(BaseModel):
    city: str = Field(max_length=80)
    incident_type: str = Field(max_length=80)
    severity: float = Field(default=0.6, ge=0.0, le=1.0)
    note: str = Field(default="")
    driver_name: str | None = Field(default=None, max_length=120)
    vehicle_identifier: str | None = Field(default=None, max_length=80)
    timestamp: str | None = None


class IncidentExport(ORMModel):
    id: int
    city: str
    incident_type: str
    severity: float
    note: str
    driver_profile_id: int | None
    vehicle_id: int | None
    reported_at: datetime


class InventoryUpdate(BaseModel):
    facility_id: int
    adjustments: int = Field(description="Positive to add, negative to remove")
    reason: str = Field(default="client-adjustment", max_length=200)


class InventoryUpdateBatch(BaseModel):
    updates: list[InventoryUpdate] = Field(min_length=1, max_length=100)


class EventImport(BaseModel):
    event_type: str = Field(default="disruption", max_length=80)
    city: str = Field(max_length=80)
    headline: str = Field(max_length=500)
    severity: float = Field(default=0.5, ge=0.0, le=1.0)
    impact_type: str = Field(default="general", max_length=80)
    impact_score: float = Field(default=0.5, ge=0.0, le=1.0)
    eta_multiplier: float = Field(default=1.0, ge=1.0)


class EventImportBatch(BaseModel):
    events: list[EventImport] = Field(min_length=1, max_length=100)


class IntegrationSnapshot(BaseModel):
    simulation_status: str
    simulation_time: str | None = None
    speed_multiplier: float = 1.0
    ticks: int = 0
    facilities: list[FacilityExport] = Field(default_factory=list)
    vehicles: list[VehicleExport] = Field(default_factory=list)
    drivers: list[DriverExport] = Field(default_factory=list)
    objectives: list[ObjectiveExport] = Field(default_factory=list)


class MetricsExport(BaseModel):
    co2_saved_kg: float = 0.0
    idle_minutes_prevented: float = 0.0
    on_time_delivery_pct: float = 100.0
    warehouse_utilization_pct: float = 0.0
    reroute_count: int = 0
    active_trucks: int = 0
    queued_trucks: int = 0
    financial_costs_saved_usd: float = 0.0
    financial_costs_incurred_usd: float = 0.0
    timestamp: str | None = None


class DecisionExport(ORMModel):
    id: int
    vehicle_id: int
    objective_id: int
    action: str
    explanation: str
    status: str
    confidence: float
    baseline_cost: float
    recommended_cost: float
    financial_impact_usd: float
    created_at: datetime


class WebhookCreate(BaseModel):
    callback_url: str = Field(min_length=1, max_length=500)
    events: list[str] = Field(min_length=1, description="Event types to subscribe to")
    retry_count: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=10, ge=1, le=60)


class WebhookUpdate(BaseModel):
    callback_url: str | None = None
    events: list[str] | None = None
    retry_count: int | None = Field(default=None, ge=0, le=10)
    timeout_seconds: int | None = Field(default=None, ge=1, le=60)
    enabled: bool | None = None


class WebhookExport(BaseModel):
    id: int
    client_id: int
    callback_url: str
    events: list[str]
    retry_count: int
    timeout_seconds: int
    enabled: bool
    created_at: datetime


class WebhookDeliveryExport(BaseModel):
    id: int
    event_type: str
    success: bool
    attempt_number: int
    response_status: int | None
    attempted_at: datetime


class OptimizeDispatchRequest(BaseModel):
    facility_ids: list[int] = Field(min_length=1, description="Facilities to optimize dispatch for")
    max_solutions: int = Field(default=5, ge=1, le=20)


class SimulationDecideRequest(BaseModel):
    state_vector: list[float] = Field(min_length=10, max_length=10, description="10-dim RL state vector")


class SimulationDecideResponse(BaseModel):
    action: str
    action_index: int
    confidence: float
    q_values: list[float] = Field(default_factory=list)
