from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict
from schemas.core import ORMModel

class EdgeSyncStatusRead(BaseModel):
    driver_profile_id: int
    pending_operations: list[dict[str, Any]]
    last_sync_at: str | None
    offline_since: str | None
    cached_routes: list[dict[str, Any]]
    cached_recommendations: list[dict[str, Any]]
    pending_count: int


class CloudHealthRead(BaseModel):
    firebase_rtdb: dict[str, Any]
    pubsub: dict[str, Any]
    vertex_ai: dict[str, Any]
    bigquery: dict[str, Any]
    fcm: dict[str, Any]
    overall: str
