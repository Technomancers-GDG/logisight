"""Data models / dataclasses used by the simulation engine."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class LiveVehicleState:
    vehicle_id: int
    identifier: str
    status: str
    current_facility_id: int | None
    next_facility_id: int | None = None
    objective_id: int | None = None
    route_template_id: int | None = None
    route_distance_km: float = 0.0
    baseline_route_distance_km: float = 0.0
    eta: datetime | None = None
    payload_units: int = 0
    progress_pct: float = 0.0
    duty_minutes_since_rest: float = 0.0
    last_recommendation_action: str | None = None
    stockout_risk_avoided: bool = False
    critical_payload: bool = False
    perishable_payload: bool = False
    last_rl_state: Any = None
    last_rl_action: str | None = None
    decision_trace: dict[str, Any] | None = None


@dataclass(slots=True, order=True)
class ScheduledEvent:
    due_at: datetime
    priority: int
    sequence: int
    event_type: str = field(compare=False)
    vehicle_id: int = field(compare=False)
    objective_id: int | None = field(compare=False, default=None)
    payload: dict[str, Any] = field(compare=False, default_factory=dict)


@dataclass(slots=True)
class CandidateDecision:
    action: str
    destination_id: int | None
    score: float
    baseline_cost: float
    recommended_cost: float
    explanation: str
    breakdown: dict[str, float]
    travel_minutes: float
    route_risk: float
    eta_multiplier: float
    ai_confidence: float = 0.85
    ai_engine: str = "Deterministic_Heuristics"
    counterfactual: str | None = None
    structured_explanation: dict[str, Any] | None = None