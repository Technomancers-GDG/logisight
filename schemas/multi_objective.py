from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict
from schemas.core import ORMModel

class ParetoFrontRead(BaseModel):
    objectives: list[float]
    genome: list[dict[str, Any]]
    rank: int
    crowding_distance: float


NodeType = Literal["warehouse", "port", "railhead", "mine"]
TransportMode = Literal["road", "rail", "water"]
