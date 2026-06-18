from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from schemas.core import ORMModel

class RiskForecastRead(BaseModel):
    city: str
    risk: float
    eta_multiplier: float
    closure_risk: float
    confidence: float
    factors: list[str]
    forecast_time: str
    prediction_interval: list[float] | None = None
    trend: str | None = None


class InventoryForecastRead(BaseModel):
    facility_id: int
    facility_name: str
    predicted_demand_units: int
    safety_stock_units: int
    reorder_point: int
    recommended_dispatch_count: int
    confidence: float
    forecast_period_hours: int
    trend: str


class ProactiveDispatchRead(BaseModel):
    origin_facility_id: int
    destination_facility_id: int
    recommended_units: int
    urgency: str
    reason: str
    eta_hours: float
