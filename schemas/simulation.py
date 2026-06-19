from __future__ import annotations

from datetime import datetime, date
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from schemas.core import ORMModel
from schemas.facility import FacilityLoadView
from schemas.vehicle import VehicleStateView
from schemas.recommendation import RecommendationRead

class SimulationControlRequest(BaseModel):
    speed_multiplier: float | None = None


class SpeedChangeRequest(BaseModel):
    speed_multiplier: float = Field(default=120.0)


class SimulationStatus(BaseModel):
    status: str
    simulation_time: datetime
    speed_multiplier: float
    queued_events: int
    error_message: str | None = None


class FleetScaleRequest(BaseModel):
    target_vehicle_count: int = Field(default=80, ge=12, le=2000)
    reset_simulation: bool = True
    auto_start: bool = True
    speed_multiplier: float = 180.0


class FleetScaleResult(BaseModel):
    previous_vehicle_count: int
    new_vehicle_count: int
    created_vehicles: int
    previous_driver_count: int
    new_driver_count: int
    created_drivers: int
    objective_assignment_counts: dict[str, int]
    simulation: SimulationStatus


class MetricsSnapshotRead(ORMModel):
    id: int
    captured_at: datetime
    co2_saved_kg: float
    idle_minutes_prevented: float
    on_time_delivery_pct: float
    warehouse_utilization_pct: float
    reroute_count: int
    active_trucks: int
    queued_trucks: int
    financial_costs_saved_usd: float
    financial_costs_incurred_usd: float
    stockouts_prevented: int = 0
    critical_deliveries_saved: int = 0
    beneficiary_locations_served: int = 0
    spoilage_or_wastage_prevented: int = 0


class MetricsSummary(BaseModel):
    co2_saved_kg: float
    idle_minutes_prevented: float
    on_time_delivery_pct: float
    warehouse_utilization_pct: float
    reroute_count: int
    active_trucks: int
    queued_trucks: int
    financial_costs_saved_usd: float = 0.0
    financial_costs_incurred_usd: float = 0.0
    stockouts_prevented: int = 0
    critical_deliveries_saved: int = 0
    beneficiary_locations_served: int = 0
    spoilage_or_wastage_prevented: int = 0


class DashboardSnapshot(BaseModel):
    simulation: SimulationStatus
    facilities: list[FacilityLoadView]
    vehicles: list[VehicleStateView]
    alerts: list[RecommendationRead]
    metrics: MetricsSummary
    active_events: list[dict[str, Any]]
    objectives: list[dict[str, Any]] = []
    route_templates: list[dict[str, Any]] = []


class ScenarioPresetRead(ORMModel):
    id: int
    scenario_key: str
    name: str
    description: str
    event_city: str
    event_type: str
    severity: float
    eta_multiplier: float
    inventory_pressure_pct: float
    active: bool


class ScenarioComparisonMetrics(BaseModel):
    on_time_delivery_pct: float
    average_delay_minutes: float
    average_cost_usd: float
    overflow_events: int
    reroute_count: int
    idle_minutes_prevented: float
    co2_saved_kg: float
    stockouts_prevented: int


class ScenarioComparisonRead(BaseModel):
    scenario_key: str
    scenario_name: str
    baseline: ScenarioComparisonMetrics
    ai: ScenarioComparisonMetrics
    improvement_summary: dict[str, float]


class TriggerScenarioRequest(BaseModel):
    severity_override: float | None = None
