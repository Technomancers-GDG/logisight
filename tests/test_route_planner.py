from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models import Facility


class TestHaversine:
    def test_haversine_km_delhi_mumbai(self):
        from services.route_planner import haversine_km
        dist = haversine_km(28.6139, 77.2090, 19.0760, 72.8777)
        assert 1000 < dist < 1300

    def test_haversine_km_same_point(self):
        from services.route_planner import haversine_km
        dist = haversine_km(28.6139, 77.2090, 28.6139, 77.2090)
        assert dist == 0

    def test_haversine_km_chennai_bangalore(self):
        from services.route_planner import haversine_km
        dist = haversine_km(13.0827, 80.2707, 12.9716, 77.5946)
        assert 250 < dist < 350


class TestClampToIndia:
    def test_clamp_within_bounds(self):
        from services.route_planner import clamp_to_india
        lat, lon = clamp_to_india(20.0, 80.0)
        assert lat == 20.0
        assert lon == 80.0

    def test_clamp_outside_bounds(self):
        from services.route_planner import clamp_to_india
        lat, lon = clamp_to_india(40.0, 100.0)
        assert lat == 37.0
        assert lon == 97.5

    def test_clamp_below_bounds(self):
        from services.route_planner import clamp_to_india
        lat, lon = clamp_to_india(0.0, 50.0)
        assert lat == 6.5
        assert lon == 68.0


class TestPolylineEncoding:
    def test_encode_decode_roundtrip(self):
        from services.route_planner import encode_polyline, _decode_polyline
        points = [(28.6139, 77.2090), (19.0760, 72.8777), (13.0827, 80.2707)]
        encoded = encode_polyline(points)
        decoded = _decode_polyline(encoded)
        assert len(decoded) == len(points)
        for (orig_lat, orig_lon), (dec_lat, dec_lon) in zip(points, decoded):
            assert abs(orig_lat - dec_lat) < 0.001
            assert abs(orig_lon - dec_lon) < 0.001

    def test_decode_empty_string(self):
        from services.route_planner import _decode_polyline
        assert _decode_polyline("") == []
        assert _decode_polyline(None) == []


class TestRoutePlanner:
    def test_route_planner_initialization(self):
        from services.route_planner import RoutePlanner
        rp = RoutePlanner(osrm_base_url="https://router.project-osrm.org")
        assert rp.osrm_base_url == "https://router.project-osrm.org"

    def test_route_key(self):
        from services.route_planner import RoutePlanner
        rp = RoutePlanner()
        assert rp.route_key(1, 2) == "1:2"

    def test_estimated_route(self):
        from services.route_planner import RoutePlanner
        rp = RoutePlanner()

        origin = MagicMock(spec=Facility)
        origin.latitude = 28.6139
        origin.longitude = 77.2090
        origin.city = "Delhi"
        destination = MagicMock(spec=Facility)
        destination.latitude = 19.0760
        destination.longitude = 72.8777
        destination.city = "Mumbai"

        route = rp._estimated_route(origin, destination)
        assert route["distance_km"] > 0
        assert route["duration_minutes"] > 0
        assert route["source"] == "estimated"
        assert len(route["steps"]) == 5
        assert route["steps"][0]["name"] == "Depart Delhi"
        assert route["steps"][-1]["name"] == "Arrive Mumbai"
        assert "encoded_polyline" in route

    def test_sanitize_polyline_empty(self):
        from services.route_planner import RoutePlanner
        rp = RoutePlanner()
        assert rp._sanitize_polyline("") == ""

    def test_sanitize_polyline_clamps_coords(self):
        from services.route_planner import RoutePlanner, encode_polyline
        rp = RoutePlanner()
        points = [(40.0, 100.0), (28.6, 77.2)]
        encoded = encode_polyline(points)
        sanitized = rp._sanitize_polyline(encoded)
        from services.route_planner import _decode_polyline
        decoded = _decode_polyline(sanitized)
        for lat, lon in decoded:
            assert 6.5 <= lat <= 37.0
            assert 68.0 <= lon <= 97.5
