from __future__ import annotations

from datetime import date
from pydantic import BaseModel, ConfigDict
from schemas.core import ORMModel

class NewsEventRead(ORMModel):
    id: int
    original_date: date
    simulation_date: date
    city: str
    category: str
    headline: str
    relevant: bool
    impact_type: str
    impact_score: float
    model_probability: float


class WeatherEventRead(ORMModel):
    id: int
    original_date: date
    simulation_date: date
    city: str
    max_temp_c: float
    min_temp_c: float
    precipitation_mm: float
    closure_risk: float
    eta_multiplier: float


class ImportSummary(BaseModel):
    news_imported: int = 0
    weather_imported: int = 0
    news_model_accuracy: float | None = None
    validation_samples: int | None = None
