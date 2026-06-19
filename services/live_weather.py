"""Live weather integration via Open-Meteo (free, no API key required).

Fetches current conditions for Indian logistics cities and translates
them into closure_risk / eta_multiplier values compatible with the
simulation engine's WeatherEvent model.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# Lat/lng for key logistics hubs tracked by the simulation
CITY_COORDS: dict[str, tuple[float, float]] = {
    "Delhi": (28.61, 77.23),
    "Mumbai": (19.08, 72.88),
    "Chennai": (13.08, 80.27),
    "Bengaluru": (12.97, 77.59),
    "Kolkata": (22.57, 88.36),
    "Hyderabad": (17.39, 78.49),
    "Pune": (18.52, 73.86),
    "Ahmedabad": (23.02, 72.57),
    "Jaipur": (26.91, 75.79),
    "Lucknow": (26.85, 80.95),
    "Nagpur": (21.15, 79.09),
    "Surat": (21.17, 72.83),
    "Bhopal": (23.26, 77.41),
    "Chandigarh": (30.73, 76.78),
    "Guwahati": (26.14, 91.74),
    "Bhubaneswar": (20.30, 85.82),
    "Patna": (25.59, 85.14),
    "Indore": (22.72, 75.86),
    "Coimbatore": (11.02, 76.96),
    "Kochi": (9.93, 76.27),
    "Visakhapatnam": (17.69, 83.22),
    "Varanasi": (25.32, 82.97),
    "Agra": (27.18, 78.02),
    "Nashik": (19.99, 73.79),
    "Madurai": (9.93, 78.12),
}


@dataclass
class LiveWeatherReading:
    city: str
    max_temp_c: float
    min_temp_c: float
    precipitation_mm: float
    closure_risk: float
    eta_multiplier: float
    fetched_at: datetime


def _compute_risk(
    precipitation_mm: float, max_temp_c: float, min_temp_c: float
) -> tuple[float, float]:
    closure_risk = 0.03
    eta_multiplier = 1.0
    if precipitation_mm >= 40:
        closure_risk += 0.52
        eta_multiplier += 0.35
    elif precipitation_mm >= 20:
        closure_risk += 0.26
        eta_multiplier += 0.18
    elif precipitation_mm >= 5:
        closure_risk += 0.12
        eta_multiplier += 0.08
    if max_temp_c >= 42 or min_temp_c <= 4:
        closure_risk += 0.08
        eta_multiplier += 0.05
    return round(min(0.95, closure_risk), 3), round(eta_multiplier, 3)


async def fetch_city_weather(city: str) -> LiveWeatherReading | None:
    """Fetch current weather for *city* from the Open-Meteo free API.

    Returns ``None`` on network error or if the city is unknown.
    """
    coords = CITY_COORDS.get(city.title())
    if coords is None:
        logger.warning("Unknown city for live weather: %s", city)
        return None

    lat, lon = coords
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        f"&forecast_days=1"
        f"&timezone=auto"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("Open-Meteo request failed for %s: %s", city, exc)
        return None

    daily = data.get("daily", {})
    temps_max = daily.get("temperature_2m_max", [])
    temps_min = daily.get("temperature_2m_min", [])
    precips = daily.get("precipitation_sum", [])

    if not temps_max:
        logger.warning("Open-Meteo returned empty daily data for %s", city)
        return None

    max_temp = float(temps_max[0])
    min_temp = float(temps_min[0]) if temps_min else max_temp
    precip = float(precips[0]) if precips else 0.0
    closure_risk, eta_multiplier = _compute_risk(precip, max_temp, min_temp)

    return LiveWeatherReading(
        city=city.title(),
        max_temp_c=max_temp,
        min_temp_c=min_temp,
        precipitation_mm=precip,
        closure_risk=closure_risk,
        eta_multiplier=eta_multiplier,
        fetched_at=datetime.now(datetime.UTC),
    )


async def fetch_all_cities() -> dict[str, LiveWeatherReading]:
    """Fetch live weather for every known logistics city in parallel."""
    results: dict[str, LiveWeatherReading] = {}
    tasks = {city: fetch_city_weather(city) for city in CITY_COORDS}
    for city, task in tasks.items():
        result = await task
        if result is not None:
            results[city] = result
    return results
