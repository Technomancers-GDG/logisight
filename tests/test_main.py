from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "app" in data


def test_auth_me_returns_unauthenticated_without_token(client: TestClient) -> None:
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is False


def test_simulation_status_idle_on_startup(client: TestClient) -> None:
    resp = client.get("/api/simulation/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("idle", "running", "paused")


def test_dashboard_endpoint(client: TestClient) -> None:
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "simulation" in data
    assert "metrics" in data
    assert "vehicles" in data


def test_list_scenarios_endpoint(client: TestClient) -> None:
    resp = client.get("/api/scenarios")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_facilities_endpoint(client: TestClient) -> None:
    resp = client.get("/api/facilities")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_drivers_endpoint(client: TestClient) -> None:
    resp = client.get("/api/drivers")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_vehicles_endpoint(client: TestClient) -> None:
    resp = client.get("/api/vehicles")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
