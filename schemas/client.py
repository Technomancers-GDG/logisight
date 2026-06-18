"""Pydantic schemas for the client portal."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class ClientRegisterRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class ClientLoginRequest(BaseModel):
    email: EmailStr
    password: str


class ClientAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    client_id: int
    company_name: str
    email: str
    api_key: str | None = None


class ClientLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    client_id: int
    company_name: str
    email: str


class ClientProfileResponse(BaseModel):
    id: int
    name: str
    company_name: str | None
    email: str
    api_key_prefix: str | None
    created_at: datetime | None
    monthly_api_calls: int
    data_complete: bool
    simulation_status: str | None


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DashboardResponse(BaseModel):
    client: dict[str, Any]
    status: dict[str, int]
    fleet: list[dict[str, Any]]
    facilities: list[dict[str, Any]]
    metrics: dict[str, Any]
    recent_decisions: list[dict[str, Any]]
    webhook_deliveries: list[dict[str, Any]]
    vehicles: list[dict[str, Any]] = Field(default_factory=list)
    simulation: dict[str, Any] | None = None


class UploadResult(BaseModel):
    success: bool
    imported: int = 0
    updated: int = 0
    errors: list[dict[str, Any]] = Field(default_factory=list)
    auto_started: bool = False


class ApiKeyResponse(BaseModel):
    api_key_prefix: str | None
    has_full_key: bool = False


class ApiKeyRegenerateResponse(BaseModel):
    api_key: str
    api_key_prefix: str
