from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

class RLDecisionRequest(BaseModel):
    facility_utilization: float
    route_risk: float
    eta_multiplier: float
    sla_remaining_minutes: float
    sla_total_minutes: float
    payload_capacity: int
    facility_capacity: int
    priority: int
    port_pressure: float
    weather_severity: float
    news_severity: float
    simulation_hour: int
    valid_actions: list[str] | None = None

class RLDecisionResponse(BaseModel):
    action: str
    confidence: float
    action_probs: dict[str, float]
    engine: str = "dqn_numpy"

class AIChatRequest(BaseModel):
    query: str
    history: list[dict[str, str]] | None = None
    vehicle_id: int | None = None
    stream: bool = True

    @field_validator("history", mode="before")
    @classmethod
    def sanitize_history(cls, v):
        if v is None:
            return None
        if not isinstance(v, list):
            return []
        sanitized = []
        for entry in v:
            if not isinstance(entry, dict):
                sanitized.append({"role": "user", "content": str(entry)})
                continue
            role = entry.get("role")
            if isinstance(role, str) and role.lower() in ("none", "null", ""):
                role = "user"
            elif not isinstance(role, str) or not role.strip():
                role = "user"
            content = entry.get("content")
            if not isinstance(content, str) or content is None:
                content = ""
            sanitized.append({"role": role, "content": content})
        return sanitized

class AIChatResponse(BaseModel):
    response: str
    model: str = ""
    suggestions: list[str] = Field(default_factory=list)
