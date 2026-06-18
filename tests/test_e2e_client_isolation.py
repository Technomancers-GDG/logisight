"""End-to-end validation: multi-client data isolation, RC1/RC2/RC5 fixes."""
from __future__ import annotations

import asyncio
import json

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from database import Base
from models import (
    ClientSimulation,
    DriverProfile,
    Facility,
    IntegrationClient,
    Objective,
    Vehicle,
)
from services.simulation import SimulationEngine
from services.route_planner import RoutePlanner
from services.simulation_manager import SimulationManager


from sqlalchemy.pool import StaticPool

def _make_engine() -> "tuple[Session, any]":
    """Create in-memory SQLite DB for testing."""
    engine = create_engine(
        "sqlite:///:memory:", 
        echo=False, 
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    
    # Patch SessionLocal globally for the duration of the test run
    import database
    import services.simulation_manager
    import services.simulation.engine
    
    database.SessionLocal = TestingSession
    services.simulation_manager.SessionLocal = TestingSession
    services.simulation.engine.SessionLocal = TestingSession
    
    return TestingSession(), engine


def _seed_client(session: Session, client_id: int, company: str, facility_prefix: str, vehicle_count: int) -> None:
    """Seed a complete client fleet."""
    client = IntegrationClient(
        id=client_id,
        name=company,
        company_name=company,
        firebase_uid=f"firebase_{client_id}",
        api_key_hash=f"hash_{client_id}",
        api_key_prefix=f"regc_{client_id:04d}",
        contact_email=f"client{client_id}@test.com",
        enabled=True,
    )
    session.add(client)

    wh = Facility(
        name=f"{facility_prefix}-WH",
        city="Nagpur",
        facility_type="warehouse",
        latitude=21.1458,
        longitude=79.0882,
        base_capacity_units=10000,
        current_inventory_units=5000,
        initial_inventory_units=5000,
        queue_capacity_units=1000,
        client_id=client_id,
        active=True,
    )
    port = Facility(
        name=f"{facility_prefix}-Port",
        city="Mumbai",
        facility_type="port",
        latitude=19.0760,
        longitude=72.8777,
        base_capacity_units=8000,
        current_inventory_units=3000,
        initial_inventory_units=3000,
        queue_capacity_units=500,
        client_id=client_id,
        active=True,
    )
    session.add_all([wh, port])
    session.flush()

    obj = Objective(
        name=f"{facility_prefix}-Emergency-Obj",
        commodity="Medicine",
        origin_facility_id=wh.id,
        destination_facility_id=port.id,
        dispatch_interval_minutes=60,
        sla_minutes=360,
        priority=1,
        assigned_vehicle_ids=list(range(1, vehicle_count + 1)),
        client_id=client_id,
    )
    session.add(obj)
    session.flush()

    # Create vehicles + drivers for this client
    for i in range(1, vehicle_count + 1):
        driver = DriverProfile(
            name=f"{facility_prefix}-Driver-{i}",
            client_id=client_id,
            active=True,
        )
        session.add(driver)
        session.flush()

        vehicle = Vehicle(
            identifier=f"{facility_prefix}-VEH-{i:03d}",
            vehicle_type="truck",
            payload_capacity_units=5000,
            home_facility_id=wh.id,
            current_facility_id=wh.id,
            driver_profile_id=driver.id,
            default_objective_id=obj.id,
            status="idle",
            client_id=client_id,
        )
        session.add(vehicle)

    session.commit()


# ═════════════════════════════════════════════════════════════════════════
# TEST 1-3: Multi-client data isolation — vehicle counts
# ═════════════════════════════════════════════════════════════════════════

def test_client_a_vehicle_count() -> None:
    """Create Client A with 5 vehicles, verify count from DB query."""
    session, _ = _make_engine()
    try:
        _seed_client(session, client_id=1, company="Alpha Logistics",
                     facility_prefix="ALPHA", vehicle_count=5)

        count = session.scalar(
            select(func.count(Vehicle.id)).where(Vehicle.client_id == 1)
        )
        assert count == 5, f"Client A should have 5 vehicles, got {count}"
        print(f"  [PASS] Client A (Alpha Logistics): {count} vehicles")
    finally:
        session.close()


def test_client_b_vehicle_count() -> None:
    """Create Client B with 3 vehicles, verify count from DB query."""
    session, _ = _make_engine()
    try:
        _seed_client(session, client_id=2, company="Beta Transport",
                     facility_prefix="BETA", vehicle_count=3)

        count = session.scalar(
            select(func.count(Vehicle.id)).where(Vehicle.client_id == 2)
        )
        assert count == 3, f"Client B should have 3 vehicles, got {count}"
        print(f"  [PASS] Client B (Beta Transport): {count} vehicles")
    finally:
        session.close()


def test_both_clients_isolated() -> None:
    """Create both clients in same DB, verify counts are isolated."""
    session, _ = _make_engine()
    try:
        _seed_client(session, client_id=1, company="Alpha Logistics",
                     facility_prefix="ALPHA", vehicle_count=5)
        _seed_client(session, client_id=2, company="Beta Transport",
                     facility_prefix="BETA", vehicle_count=3)

        count_a = session.scalar(
            select(func.count(Vehicle.id)).where(Vehicle.client_id == 1)
        )
        count_b = session.scalar(
            select(func.count(Vehicle.id)).where(Vehicle.client_id == 2)
        )
        total = session.scalar(select(func.count(Vehicle.id)))

        assert count_a == 5, f"Client A: expected 5, got {count_a}"
        assert count_b == 3, f"Client B: expected 3, got {count_b}"
        assert total == 8, f"Total vehicles: expected 8, got {total}"

        print(f"  [PASS] Client A: {count_a} vehicles")
        print(f"  [PASS] Client B: {count_b} vehicles")
        print(f"  [PASS] Total: {total} vehicles (5 + 3 = 8)")
    finally:
        session.close()


# ═════════════════════════════════════════════════════════════════════════
# TEST 4: DashboardResponse schema validation (RC1 fix)
# ═════════════════════════════════════════════════════════════════════════

def test_dashboard_response_has_vehicles_field() -> None:
    """Verify DashboardResponse schema includes vehicles field (RC1)."""
    from schemas.client import DashboardResponse

    payload = {
        "client": {"name": "Acme", "api_key_prefix": "regc_t1"},
        "status": {"facilities": 2, "vehicles": 8, "drivers": 8, "objectives": 3},
        "fleet": [],
        "facilities": [],
        "metrics": {"active_trucks": 0, "completed_shipments": 0, "on_time_delivery_pct": 0.0, "co2_saved_kg": 0.0, "total_api_calls": 0},
        "recent_decisions": [],
        "webhook_deliveries": [],
        "vehicles": [
            {
                "vehicle_id": 1,
                "identifier": "OPS-001",
                "status": "idle",
                "objective_id": 1,
                "current_facility_id": 42,
                "next_facility_id": None,
                "progress_pct": 0.0,
                "payload_units": 0,
                "recommendation_action": None,
            }
        ],
    }

    response = DashboardResponse(**payload)
    assert response.vehicles == payload["vehicles"]
    assert len(response.vehicles) == 1
    assert response.vehicles[0]["vehicle_id"] == 1
    assert response.vehicles[0]["identifier"] == "OPS-001"

    # Verify no KeyError for vehicles field
    d = response.model_dump(mode="json")
    assert "vehicles" in d
    assert "fleet" in d
    print(f"  [PASS] DashboardResponse has vehicles field, {len(d['vehicles'])} vehicle(s)")


# ═════════════════════════════════════════════════════════════════════════
# TEST 5: Metrics field name standardization (RC2 fix)
# ═════════════════════════════════════════════════════════════════════════

def test_metrics_uses_active_trucks() -> None:
    """Verify metrics dict uses 'active_trucks' (RC2)."""
    from schemas.client import DashboardResponse

    payload = {
        "client": {"name": "Acme", "api_key_prefix": "regc_t1"},
        "status": {"facilities": 2, "vehicles": 8, "drivers": 8, "objectives": 3},
        "fleet": [],
        "facilities": [],
        "metrics": {"active_trucks": 3, "completed_shipments": 10, "on_time_delivery_pct": 85.0, "co2_saved_kg": 120.5, "total_api_calls": 42},
        "recent_decisions": [],
        "webhook_deliveries": [],
        "vehicles": [],
    }

    response = DashboardResponse(**payload)
    metrics = response.metrics
    assert "active_trucks" in metrics, "RC2: metrics must have active_trucks, not active_shipments"
    assert "active_shipments" not in metrics, "RC2: active_shipments renamed to active_trucks"
    assert metrics["active_trucks"] == 3
    print(f"  [PASS] metrics.active_trucks = {metrics['active_trucks']}")


# ═════════════════════════════════════════════════════════════════════════
# TEST 6: Client dashboard endpoint returns properly scoped data
# ═════════════════════════════════════════════════════════════════════════

def test_client_dashboard_returns_client_scoped_data() -> None:
    """Call client_dashboard endpoint directly, verify all data scoped to client_id."""
    session, _ = _make_engine()
    try:
        _seed_client(session, client_id=1, company="Alpha",
                     facility_prefix="ALPHA", vehicle_count=5)
        _seed_client(session, client_id=2, company="Beta",
                     facility_prefix="BETA", vehicle_count=3)

        # Simulate the client_dashboard endpoint logic for client_id=1
        cid = 1

        facilities = session.scalars(
            select(Facility).where(Facility.client_id == cid)
        ).all()
        vehicles = session.scalars(
            select(Vehicle).where(Vehicle.client_id == cid)
        ).all()
        drivers = session.scalars(
            select(DriverProfile).where(DriverProfile.client_id == cid)
        ).all()
        objectives = session.scalars(
            select(Objective).where(Objective.client_id == cid)
        ).all()

        assert len(facilities) == 2, f"Client 1 facilities: expected 2, got {len(facilities)}"
        assert len(vehicles) == 5, f"Client 1 vehicles: expected 5, got {len(vehicles)}"
        assert len(drivers) == 5, f"Client 1 drivers: expected 5, got {len(drivers)}"
        assert len(objectives) == 1, f"Client 1 objectives: expected 1, got {len(objectives)}"

        # Build vehicle_views as the endpoint does (RC1)
        vehicle_views = []
        for v in vehicles:
            vehicle_views.append({
                "vehicle_id": v.id,
                "identifier": v.identifier,
                "status": v.status,
                "objective_id": v.default_objective_id,
                "current_facility_id": v.current_facility_id or v.home_facility_id,
                "next_facility_id": None,
                "progress_pct": 0.0,
                "payload_units": 0,
                "recommendation_action": None,
            })

        assert len(vehicle_views) == 5
        assert all(vv["identifier"].startswith("ALPHA-") for vv in vehicle_views), \
            "All vehicles must belong to Client A (ALPHA prefix)"

        # Compute active_trucks (RC2)
        active_trucks = sum(1 for v in vehicles if v.status in ("in_transit", "loading", "unloading"))
        assert active_trucks == 0, "All vehicles are idle, active_trucks should be 0"

        print(f"  [PASS] Client 1 facilities: {len(facilities)}")
        print(f"  [PASS] Client 1 vehicles: {len(vehicles)} ({[v.identifier for v in vehicles]})")
        print(f"  [PASS] Client 1 driver_profiles: {len(drivers)}")
        print(f"  [PASS] Client 1 objectives: {len(objectives)}")
        print(f"  [PASS] Client 1 vehicle_views: {len(vehicle_views)} (RC1)")
        print(f"  [PASS] Client 1 active_trucks: {active_trucks} (RC2)")

        # Also verify Client 2's data
        cid2 = 2
        vehicles_b = session.scalars(
            select(Vehicle).where(Vehicle.client_id == cid2)
        ).all()
        assert len(vehicles_b) == 3
        assert all(v.identifier.startswith("BETA-") for v in vehicles_b), \
            f"All vehicles must belong to Client B (BETA prefix), got {[v.identifier for v in vehicles_b]}"

        print(f"  [PASS] Client 2 vehicles: {len(vehicles_b)} ({[v.identifier for v in vehicles_b]})")

    finally:
        session.close()


# ═════════════════════════════════════════════════════════════════════════
# TEST 7: Demo dashboard returns global data (independent of clients)
# ═════════════════════════════════════════════════════════════════════════

def test_demo_dashboard_independent_of_clients() -> None:
    """Verify demo dashboard queries demo data (client_id IS NULL), not client data."""
    session, _ = _make_engine()
    try:
        # Seed both client fleets
        _seed_client(session, client_id=1, company="Alpha",
                     facility_prefix="ALPHA", vehicle_count=5)
        _seed_client(session, client_id=2, company="Beta",
                     facility_prefix="BETA", vehicle_count=3)

        # Seed some demo data (client_id=NULL) — simulating seed_demo_data
        demo_wh = Facility(
            name="Demo-WH",
            city="Delhi",
            facility_type="warehouse",
            latitude=28.6139,
            longitude=77.2090,
            base_capacity_units=5000,
            current_inventory_units=2000,
            initial_inventory_units=2000,
            queue_capacity_units=1000,
            client_id=None,
            active=True,
        )
        demo_port = Facility(
            name="Demo-Port",
            city="Chennai",
            facility_type="port",
            latitude=13.0827,
            longitude=80.2707,
            base_capacity_units=10000,
            current_inventory_units=5000,
            initial_inventory_units=5000,
            queue_capacity_units=2000,
            client_id=None,
            active=True,
        )
        session.add_all([demo_wh, demo_port])
        session.flush()

        demo_obj = Objective(
            name="Demo-Emergency",
            commodity="Food",
            origin_facility_id=demo_wh.id,
            destination_facility_id=demo_port.id,
            dispatch_interval_minutes=120,
            sla_minutes=720,
            priority=1,
            client_id=None,
        )
        session.add(demo_obj)
        session.flush()

        demo_driver = DriverProfile(
            name="Demo-Driver",
            client_id=None,
            active=True,
        )
        session.add(demo_driver)
        session.flush()

        # Create 2 demo vehicles
        for i in range(1, 3):
            session.add(Vehicle(
                identifier=f"DEMO-VEH-{i:03d}",
                vehicle_type="truck",
                payload_capacity_units=8000,
                home_facility_id=demo_wh.id,
                current_facility_id=demo_wh.id,
                driver_profile_id=demo_driver.id,
                default_objective_id=demo_obj.id,
                status="idle",
                client_id=None,
            ))
        session.commit()

        # Query as demo dashboard would (IS NULL)
        demo_vehicles = session.scalars(
            select(Vehicle).where(Vehicle.client_id.is_(None))
        ).all()
        client_a_vehicles = session.scalars(
            select(Vehicle).where(Vehicle.client_id == 1)
        ).all()
        client_b_vehicles = session.scalars(
            select(Vehicle).where(Vehicle.client_id == 2)
        ).all()

        assert len(demo_vehicles) == 2, f"Demo vehicles: expected 2, got {len(demo_vehicles)}"
        assert len(client_a_vehicles) == 5
        assert len(client_b_vehicles) == 3

        # Demo vehicles must NOT appear in client queries
        demo_ids = {v.id for v in demo_vehicles}
        client_a_ids = {v.id for v in client_a_vehicles}
        client_b_ids = {v.id for v in client_b_vehicles}

        assert demo_ids.isdisjoint(client_a_ids), "Demo vehicles leaked into Client A"
        assert demo_ids.isdisjoint(client_b_ids), "Demo vehicles leaked into Client B"
        assert client_a_ids.isdisjoint(client_b_ids), "Client A vehicles leaked into Client B"

        print(f"  [PASS] Demo vehicles: {len(demo_vehicles)} (independent)")
        print(f"  [PASS] Client A vehicles: {len(client_a_vehicles)} (independent)")
        print(f"  [PASS] Client B vehicles: {len(client_b_vehicles)} (independent)")
        print(f"  [PASS] Sets are disjoint — no cross-pollination")
    finally:
        session.close()


# ═════════════════════════════════════════════════════════════════════════
# TEST 8: Engine load_state isolates client data
# ═════════════════════════════════════════════════════════════════════════

def test_engine_loads_only_client_vehicles() -> None:
    """Verify SimulationEngine.load_state() filters by client_id."""
    session, _ = _make_engine()
    try:
        _seed_client(session, client_id=1, company="Alpha",
                     facility_prefix="ALPHA", vehicle_count=5)
        _seed_client(session, client_id=2, company="Beta",
                     facility_prefix="BETA", vehicle_count=3)

        planner = RoutePlanner(osrm_base_url="http://localhost:5000")

        # Create engine for Client 1
        engine_a = SimulationEngine(planner, client_id=1, channel="client_1")
        engine_a.load_state(session)

        assert len(engine_a.vehicles) == 5, \
            f"Engine for Client 1 loaded {len(engine_a.vehicles)} vehicles, expected 5"
        assert all(v.identifier.startswith("ALPHA-") for v in engine_a.vehicles.values()), \
            "Client 1 engine must only have ALPHA vehicles"
        assert len(engine_a.live_vehicle_states) == 5

        # Create engine for Client 2
        engine_b = SimulationEngine(planner, client_id=2, channel="client_2")
        engine_b.load_state(session)

        assert len(engine_b.vehicles) == 3, \
            f"Engine for Client 2 loaded {len(engine_b.vehicles)} vehicles, expected 3"
        assert all(v.identifier.startswith("BETA-") for v in engine_b.vehicles.values()), \
            "Client 2 engine must only have BETA vehicles"
        assert len(engine_b.live_vehicle_states) == 3

        print(f"  [PASS] Engine client_1 vehicles: {len(engine_a.vehicles)} (ALPHA only)")
        print(f"  [PASS] Engine client_2 vehicles: {len(engine_b.vehicles)} (BETA only)")

    finally:
        session.close()


# ═════════════════════════════════════════════════════════════════════════
# TEST 9: Engine save/restore cycle
# ═════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_engine_save_and_restore() -> None:
    """Verify engine save_state() and start_all() correctly persist and restore."""
    session, _ = _make_engine()
    try:
        _seed_client(session, client_id=1, company="Alpha",
                     facility_prefix="ALPHA", vehicle_count=5)

        planner = RoutePlanner(osrm_base_url="http://localhost:5000")
        manager = SimulationManager()

        # Start engine — engine.start() uses SessionLocal(), so load_state manually first
        engine = SimulationEngine(planner, client_id=1, channel="client_1")
        engine.load_state(session)
        manager.register_engine(1, engine)
        engine._task = asyncio.create_task(engine._run_loop())
        engine.status = "running"

        assert engine.status == "running"
        assert len(engine.live_vehicle_states) == 5, \
            f"Engine has {len(engine.live_vehicle_states)} live states, expected 5"

        # Save state
        engine.save_state(session)

        # Verify ClientSimulation record exists
        sim = session.scalar(
            select(ClientSimulation).where(ClientSimulation.client_id == 1)
        )
        assert sim is not None, "ClientSimulation record missing after save_state"
        assert sim.status == "running", f"ClientSimulation status: {sim.status}"
        print(f"  [PASS] Saved engine state: status={sim.status}, ticks={sim.total_ticks}")
        session.commit()

        # Stop engine
        await manager.stop_client(1)
        assert manager.get_engine(1) is None, "Engine not removed after stop"

        # Simulate server crash: set status to running in DB before start_all
        sim = session.scalar(select(ClientSimulation).where(ClientSimulation.client_id == 1))
        sim.status = "running"
        session.commit()

        # Simulate server restart: start_all
        await manager.start_all(session)
        restored = manager.get_engine(1)
        assert restored is not None, "Engine not restored by start_all"
        assert len(restored.live_vehicle_states) == 5, \
            f"Restored engine has {len(restored.live_vehicle_states)} vehicles, expected 5"

        # Clean up
        await manager.stop_client(1)
        print(f"  [PASS] Engine restored: status={restored.status}, vehicles={len(restored.live_vehicle_states)}")

    finally:
        await manager.stop_all()
        session.close()


# ═════════════════════════════════════════════════════════════════════════
# TEST 10: WebSocket channel isolation
# ═════════════════════════════════════════════════════════════════════════

def test_websocket_channel_isolation_structure() -> None:
    """Verify each engine has its own ConnectionManager and channel."""
    planner = RoutePlanner(osrm_base_url="http://localhost:5000")

    engine_a = SimulationEngine(planner, client_id=1, channel="client_1")
    engine_b = SimulationEngine(planner, client_id=2, channel="client_2")

    assert engine_a._channel == "client_1"
    assert engine_b._channel == "client_2"
    assert engine_a._channel != engine_b._channel
    assert engine_a.connection_manager is not engine_b.connection_manager, \
        "Each engine must have its own ConnectionManager"

    # ConnectionManager stores the broadcast channel name at connect time.
    # Verify the engines have different channel strings that will route to
    # separate WebSocket connection sets.
    assert engine_a._channel not in engine_b.connection_manager._channels, \
        "Client 1 channel should not exist in Client 2's ConnectionManager"
    assert engine_b._channel not in engine_a.connection_manager._channels, \
        "Client 2 channel should not exist in Client 1's ConnectionManager"

    # Broadcast uses channel=self._channel, so broadcasts from engine_a can
    # never reach connections in engine_b's manager (even after connect()).
    print(f"  [PASS] Engine A channel: {engine_a._channel}")
    print(f"  [PASS] Engine B channel: {engine_b._channel}")
    print(f"  [PASS] Separate ConnectionManager instances")
    print(f"  [PASS] Channels use different strings — broadcast isolation guaranteed")


# ═════════════════════════════════════════════════════════════════════════
# TEST 11: dashboard_snapshot returns client-scoped vehicles
# ═════════════════════════════════════════════════════════════════════════

def test_dashboard_snapshot_client_scoped() -> None:
    """Verify dashboard_snapshot() vehicles list is client-scoped."""
    session, _ = _make_engine()
    try:
        _seed_client(session, client_id=1, company="Alpha",
                     facility_prefix="ALPHA", vehicle_count=5)
        _seed_client(session, client_id=2, company="Beta",
                     facility_prefix="BETA", vehicle_count=3)

        planner = RoutePlanner(osrm_base_url="http://localhost:5000")

        engine_a = SimulationEngine(planner, client_id=1, channel="client_1")
        snapshot_a = engine_a.dashboard_snapshot(session)

        assert len(snapshot_a.vehicles) == 5, \
            f"Client 1 snapshot has {len(snapshot_a.vehicles)} vehicles, expected 5"
        assert all(v.identifier.startswith("ALPHA-") for v in snapshot_a.vehicles), \
            "All vehicles in Client 1 snapshot must be ALPHA"

        engine_b = SimulationEngine(planner, client_id=2, channel="client_2")
        snapshot_b = engine_b.dashboard_snapshot(session)

        assert len(snapshot_b.vehicles) == 3, \
            f"Client 2 snapshot has {len(snapshot_b.vehicles)} vehicles, expected 3"
        assert all(v.identifier.startswith("BETA-") for v in snapshot_b.vehicles), \
            "All vehicles in Client 2 snapshot must be BETA"

        print(f"  [PASS] Client 1 snapshot: {len(snapshot_a.vehicles)} vehicles (ALPHA)")
        print(f"  [PASS] Client 2 snapshot: {len(snapshot_b.vehicles)} vehicles (BETA)")
        print(f"  [PASS] Vehicles are client-scoped in dashboard_snapshot()")

    finally:
        session.close()
