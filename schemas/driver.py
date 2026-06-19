from __future__ import annotations

from datetime import datetime, date
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from schemas.core import ORMModel

class DriverProfileBase(BaseModel):
    name: str
    override_rating: float = 1.0
    confidence: float = 0.5
    accept_recommendation_bias: float = 0.5
    active: bool = True


class DriverProfileCreate(DriverProfileBase):
    pass


class DriverProfileRead(DriverProfileBase, ORMModel):
    id: int


class DriverInstructionRead(BaseModel):
    recommendation_id: int
    created_at: datetime
    vehicle_id: int
    vehicle_identifier: str
    objective_name: str
    action: str
    explanation: str
    status: str


class DriverResponseRequest(BaseModel):
    recommendation_id: int
    decision: str = Field(pattern="^(accepted|ignored)$")
    note: str = ""


class SpotlightRequest(BaseModel):
    driver_id: int | None = None


class RecommendationDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(accept|ignore)$")


class DriverIncidentCreate(BaseModel):
    driver_profile_id: int
    vehicle_id: int | None = None
    city: str
    incident_type: str
    severity: float = 0.6
    note: str = ""


class DriverIncidentRead(ORMModel):
    id: int
    reported_at: datetime
    driver_profile_id: int
    vehicle_id: int | None
    city: str
    incident_type: str
    severity: float
    note: str
    linked_news_event_id: int | None


class DriverMobileSnapshot(BaseModel):
    driver_id: int
    driver_name: str
    override_rating: float
    confidence: float
    pending_instructions: list[DriverInstructionRead]
    recent_incidents: list[DriverIncidentRead]


class DriverMetricsRead(ORMModel):
    driver_id: int
    efficiency_score: float
    reliability_score: float
    route_adherence_score: float
    idle_time_score: float
    risk_score: float
    classification_label: str
    sample_count: int
    updated_at: datetime
    scoring_metadata: dict[str, Any] = Field(default_factory=dict)
