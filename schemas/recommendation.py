from __future__ import annotations

from datetime import datetime, date
from typing import Any
from pydantic import BaseModel, ConfigDict
from schemas.core import ORMModel

class RecommendationRead(ORMModel):
    id: int
    created_at: datetime
    simulation_time: datetime
    vehicle_id: int
    objective_id: int
    current_facility_id: int | None
    original_destination_id: int
    recommended_destination_id: int | None
    action: str
    explanation: str
    structured_explanation: dict[str, Any] = {}
    counterfactual: str = ""
    score_breakdown: dict[str, Any]
    baseline_cost: float
    recommended_cost: float
    financial_impact_usd: float
    status: str
    confidence: float | None = None


class DriverDecisionRead(ORMModel):
    id: int
    decided_at: datetime
    recommendation_id: int
    driver_profile_id: int
    vehicle_id: int
    decision: str
    actual_trip_cost: float
    recommended_trip_cost: float
    rating_delta: float
    note: str
