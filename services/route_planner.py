from __future__ import annotations

from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt

import httpx
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from models import Facility, RouteTemplate

logger = logging.getLogger(__name__)

INDIA_LAT_MIN, INDIA_LAT_MAX = 6.5, 37.0
INDIA_LON_MIN, INDIA_LON_MAX = 68.0, 97.5


def clamp_to_india(lat: float, lon: float) -> tuple[float, float]:
    return (
        max(INDIA_LAT_MIN, min(INDIA_LAT_MAX, lat)),
        max(INDIA_LON_MIN, min(INDIA_LON_MAX, lon)),
    )


def encode_polyline(points: list[tuple[float, float]]) -> str:
    """Basic Google Polyline encoding for lat/lng pairs."""
    def encode_val(val):
        val = int(round(val * 1e5))
        val = ~(val << 1) if val < 0 else (val << 1)
        res = ""
        while val >= 0x20:
            res += chr((0x20 | (val & 0x1F)) + 63)
            val >>= 5
        res += chr(val + 63)
        return res

    res = ""
    last_lat, last_lng = 0, 0
    for lat, lng in points:
        res += encode_val(lat - last_lat)
        res += encode_val(lng - last_lng)
        last_lat, last_lng = lat, lng
    return res


def _decode_polyline(encoded: str, precision: int = 5) -> list[tuple[float, float]]:
    """Decode a Google Polyline encoded string into lat/lng pairs."""
    if not encoded:
        return []
    coordinates = []
    index = 0
    latitude = 0
    longitude = 0
    factor = 10 ** precision
    while index < len(encoded):
        result = 0
        shift = 0
        while True:
            if index >= len(encoded):
                return coordinates
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        lat_change = ~(result >> 1) if (result & 1) else (result >> 1)
        latitude += lat_change
        result = 0
        shift = 0
        while True:
            if index >= len(encoded):
                return coordinates
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        lon_change = ~(result >> 1) if (result & 1) else (result >> 1)
        longitude += lon_change
        coordinates.append((latitude / factor, longitude / factor))
    return coordinates


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)
    a = (
        sin(delta_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(delta_lon / 2) ** 2
    )
    return 2 * radius_km * asin(sqrt(a))


class RoutePlanner:
    def __init__(self, osrm_base_url: str | None = None) -> None:
        self.osrm_base_url = (osrm_base_url or settings.osrm_base_url).rstrip("/")
        self.use_osrm = settings.route_use_osrm
        self.logger = logging.getLogger(__name__)

    def route_key(self, origin_id: int, destination_id: int) -> str:
        return f"{origin_id}:{destination_id}"

    def get_or_create_template(
        self, session: Session, origin: Facility, destination: Facility
    ) -> RouteTemplate:
        key = self.route_key(origin.id, destination.id)
        existing = session.scalar(select(RouteTemplate).where(RouteTemplate.route_key == key))
        if existing is not None:
            session.expunge(existing)
            return existing

        route_data = None
        if self.use_osrm:
            route_data = self._fetch_osrm_route(origin, destination)
        if route_data is None:
            route_data = self._estimated_route(origin, destination)

        route = RouteTemplate(
            route_key=key,
            origin_facility_id=origin.id,
            destination_facility_id=destination.id,
            distance_km=route_data["distance_km"],
            duration_minutes=route_data["duration_minutes"],
            encoded_polyline=route_data["encoded_polyline"],
            steps=route_data["steps"],
            source=route_data["source"],
            refreshed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(route)
        session.flush()
        session.expunge(route)
        return route

    def prewarm_objective_routes(
        self,
        session: Session,
        facilities: dict[int, Facility],
        objective_destinations: list[tuple[int, list[int]]],
    ) -> None:
        for origin_id, destinations in objective_destinations:
            origin = facilities.get(origin_id)
            if origin is None:
                logger.warning("prewarm: origin facility %s not found, skipping", origin_id)
                continue
            for destination_id in destinations:
                destination = facilities.get(destination_id)
                if destination is None:
                    logger.warning("prewarm: destination facility %s not found, skipping", destination_id)
                    continue
                # outbound
                self.get_or_create_template(session, origin, destination)
                # return (common case for round-trip objectives)
                self.get_or_create_template(session, destination, origin)

    def _sanitize_polyline(self, encoded: str) -> str:
        if not encoded:
            return encoded
        points = _decode_polyline(encoded, 5)
        if not points:
            return encoded
        clamped = [clamp_to_india(lat, lon) for lat, lon in points]
        return encode_polyline(clamped)

    def _fetch_osrm_route(
        self, origin: Facility, destination: Facility
    ) -> dict[str, object] | None:
        coordinates = (
            f"{origin.longitude},{origin.latitude};"
            f"{destination.longitude},{destination.latitude}"
        )
        url = (
            f"{self.osrm_base_url}/route/v1/driving/{coordinates}"
            "?overview=full&steps=true&geometries=polyline"
        )
        try:
            import time
            if "router.project-osrm.org" in self.osrm_base_url:
                time.sleep(0.2)
            with httpx.Client(timeout=8.0) as client:
                response = client.get(url)
            # Will raise HTTPStatusError for 4xx/5xx
            response.raise_for_status()
            payload = response.json()
            routes = payload.get("routes", [])
            if not routes:
                self.logger.warning("OSRM returned empty routes array; URL=%s", url)
                self.logger.debug("OSRM response payload: %s", payload)
                return None
            route = routes[0]
            leg = route["legs"][0]
            steps = [
                {
                    "name": step.get("name") or step.get("ref") or "Unnamed segment",
                    "distance_km": round(step.get("distance", 0.0) / 1000, 2),
                    "duration_minutes": round(step.get("duration", 0.0) / 60, 2),
                }
                for step in leg.get("steps", [])[:12]
            ]
            return {
                "distance_km": round(route.get("distance", 0.0) / 1000, 2),
                "duration_minutes": round(route.get("duration", 0.0) / 60, 2),
                "encoded_polyline": self._sanitize_polyline(route.get("geometry", "")),
                "steps": steps,
                "source": "osrm",
            }
        except httpx.HTTPStatusError as e:
            resp = getattr(e, "response", None)
            status = getattr(resp, "status_code", None)
            body = None
            try:
                body = resp.text if resp is not None else None
            except Exception:
                body = None
            self.logger.exception(
                "OSRM HTTP error: %s URL=%s status=%s body=%s", e, url, status, body
            )
            return None
        except Exception as e:
            self.logger.exception("OSRM request failed: %s URL=%s", e, url)
            return None

    def _estimated_route(self, origin: Facility, destination: Facility) -> dict[str, object]:
        straight_line = haversine_km(
            origin.latitude, origin.longitude, destination.latitude, destination.longitude
        )
        road_distance = max(12.0, straight_line * 1.22)
        average_speed_kmph = 48.0
        duration_minutes = road_distance / average_speed_kmph * 60
        
        lat1, lon1 = clamp_to_india(origin.latitude, origin.longitude)
        lat2, lon2 = clamp_to_india(destination.latitude, destination.longitude)
        
        d_lat = lat2 - lat1
        d_lon = lon2 - lon1
        
        perp_lat = d_lon * 0.02
        perp_lon = -d_lat * 0.02
        
        points = [(lat1, lon1)]
        segments = 20
        for i in range(1, segments):
            t = i / segments
            base_lat = lat1 + d_lat * t
            base_lon = lon1 + d_lon * t
            
            curve_strength = 1.0 - abs(t - 0.5) * 2.0
            sine_offset = (
                (t * 6.28 * 1.5) +
                (t * 6.28 * 3.2 * 0.3) +
                (t * 6.28 * 5.7 * 0.15)
            )
            
            lat_offset = perp_lat * curve_strength * (0.5 + 0.5 * sin(sine_offset))
            lon_offset = perp_lon * curve_strength * (0.5 + 0.5 * sin(sine_offset + 1.2))
            
            points.append(clamp_to_india(base_lat + lat_offset, base_lon + lon_offset))
        
        points.append((lat2, lon2))
        polyline = encode_polyline(points)
        
        steps = [
            {
                "name": f"Depart {origin.city}",
                "distance_km": round(road_distance * 0.15, 2),
                "duration_minutes": round(duration_minutes * 0.18, 2),
            },
            {
                "name": "Highway merge",
                "distance_km": round(road_distance * 0.25, 2),
                "duration_minutes": round(duration_minutes * 0.22, 2),
            },
            {
                "name": "National highway corridor",
                "distance_km": round(road_distance * 0.35, 2),
                "duration_minutes": round(duration_minutes * 0.32, 2),
            },
            {
                "name": f"Approach {destination.city}",
                "distance_km": round(road_distance * 0.15, 2),
                "duration_minutes": round(duration_minutes * 0.18, 2),
            },
            {
                "name": f"Arrive {destination.city}",
                "distance_km": round(road_distance * 0.1, 2),
                "duration_minutes": round(duration_minutes * 0.1, 2),
            },
        ]
        return {
            "distance_km": round(road_distance, 2),
            "duration_minutes": round(duration_minutes, 2),
            "encoded_polyline": polyline,
            "steps": steps,
            "source": "estimated",
        }
