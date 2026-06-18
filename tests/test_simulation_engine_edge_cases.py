from __future__ import annotations

import heapq
from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database import Base
from models import (
    DriverProfile,
    Facility,
    NewsEvent,
    Objective,
    PortLink,
    RouteTemplate,
    Vehicle,
    WeatherEvent,
)
from services.simulation import (
    LiveVehicleState,
    SimulationEngine,
)
from services.route_planner import RoutePlanner


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", echo=False)
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    session = TestingSession()
    return session


@pytest.fixture
def engine() -> SimulationEngine:
    planner = RoutePlanner(osrm_base_url="http://localhost:5000")
    return SimulationEngine(route_planner=planner)


@pytest.fixture
def seeded_session(db_session: Session) -> Session:
    wh = Facility(
        id=1, name="Warehouse A", city="Nagpur", facility_type="warehouse",
        latitude=21.1458, longitude=79.0882,
        base_capacity_units=5000, current_inventory_units=2000,
        initial_inventory_units=2000, queue_capacity_units=1000, active=True,
    )
    dest = Facility(
        id=2, name="Distribution B", city="Pune", facility_type="warehouse",
        latitude=18.5204, longitude=73.8567,
        base_capacity_units=4000, current_inventory_units=1500,
        initial_inventory_units=1500, queue_capacity_units=800, active=True,
    )
    db_session.add_all([wh, dest])

    obj = Objective(
        id=1, name="Deliver Medicine", commodity="medicine",
        origin_facility_id=1, destination_facility_id=2,
        fallback_facility_ids=[], priority=5,
        dispatch_interval_minutes=120, sla_minutes=600,
        loading_duration_minutes=15, unloading_duration_minutes=10,
        active=True,
    )
    db_session.add(obj)

    driver = DriverProfile(
        id=1, name="Test Driver", override_rating=1.0,
        confidence=0.6, accept_recommendation_bias=0.5, active=True,
    )
    db_session.add(driver)

    vehicle = Vehicle(
        id=1, identifier="VH-0001", vehicle_type="truck",
        payload_capacity_units=500, home_facility_id=1,
        current_facility_id=1, driver_profile_id=1,
        default_objective_id=1, average_speed_kmph=45.0,
        emission_kg_per_km=1.2, rest_every_hours=4,
        rest_duration_minutes=30, status="idle",
    )
    db_session.add(vehicle)

    route = RouteTemplate(
        id=1, route_key="1:2", origin_facility_id=1,
        destination_facility_id=2, distance_km=250.0,
        duration_minutes=300.0,
    )
    db_session.add(route)

    port_link = PortLink(
        id=1, port_id=2, warehouse_id=1, active=True,
        spillover_threshold_pct=80.0,
    )
    db_session.add(port_link)

    db_session.commit()
    return db_session


# ── Edge: Empty State ─────────────────────────────────────────────


def test_load_state_empty_db_does_not_crash(engine: SimulationEngine, db_session: Session) -> None:
    engine.load_state(db_session)
    assert engine.facilities == {}
    assert engine.vehicles == {}
    assert engine.live_vehicle_states == {}
    assert engine.routes == {}


def test_dashboard_snapshot_with_empty_db(engine: SimulationEngine, db_session: Session) -> None:
    snapshot = engine.dashboard_snapshot(db_session)
    assert snapshot.simulation.status == "idle"
    assert snapshot.facilities == []
    assert snapshot.vehicles == []


def test_dashboard_snapshot_populates_state_from_db(engine: SimulationEngine, seeded_session: Session) -> None:
    snapshot = engine.dashboard_snapshot(seeded_session)
    assert len(snapshot.facilities) == 2
    assert len(snapshot.vehicles) == 1


# ── Edge: Dispatch with missing vehicle ──────────────────────────


def test_handle_dispatch_missing_vehicle_does_not_crash(engine: SimulationEngine, seeded_session: Session) -> None:
    engine.load_state(seeded_session)
    from services.simulation.models import ScheduledEvent
    event = ScheduledEvent(
        due_at=engine.simulation_time, priority=1, sequence=1,
        event_type="dispatch", vehicle_id=999, objective_id=1,
        payload={"leg": "outbound"},
    )
    engine._handle_dispatch(seeded_session, event)
    assert True


def test_handle_dispatch_no_objective_returns_gracefully(engine: SimulationEngine, seeded_session: Session) -> None:
    engine.load_state(seeded_session)
    from services.simulation.models import ScheduledEvent
    event = ScheduledEvent(
        due_at=engine.simulation_time, priority=1, sequence=1,
        event_type="dispatch", vehicle_id=1, objective_id=999,
        payload={"leg": "outbound"},
    )
    engine._handle_dispatch(seeded_session, event)
    assert True


# ── Edge: Spotlight resolve with missing route ───────────────────


def test_resolve_spotlight_no_route_does_not_schedule(engine: SimulationEngine, seeded_session: Session) -> None:
    engine.load_state(seeded_session)
    vehicle = engine.vehicles[1]
    state = engine.live_vehicle_states[1]
    state.status = "waiting_for_human"

    from models import Recommendation
    rec = Recommendation(
        id=1, vehicle_id=1, objective_id=1,
        current_facility_id=1, original_destination_id=2,
        recommended_destination_id=999,
        action="reroute_warehouse",
        explanation="Test reroute",
        simulation_time=datetime.now(),
        created_at=datetime.now(),
    )
    seeded_session.add(rec)
    seeded_session.commit()

    from models import Objective
    obj = seeded_session.get(Objective, 1)

    queue_before = len(engine.event_queue)
    engine.resolve_spotlight_decision(vehicle, rec, obj, "accepted")
    assert len(engine.event_queue) == queue_before
    assert engine.live_vehicle_states[1].status == "loading"


def test_resolve_spotlight_no_state_returns_early(engine: SimulationEngine, seeded_session: Session) -> None:
    vehicle = Vehicle(id=999, identifier="GHOST")
    from models import Recommendation
    rec = Recommendation(id=1, vehicle_id=999)
    engine.resolve_spotlight_decision(vehicle, rec, None, "accepted")
    assert True


# ── Edge: Route risk with no weather/news ────────────────────────


def test_route_risk_with_no_events_returns_defaults(engine: SimulationEngine, seeded_session: Session) -> None:
    engine.load_state(seeded_session)
    risk = engine._route_risk("Nagpur", "Pune")
    assert risk["route_risk"] == 0.0
    assert risk["eta_multiplier"] == 1.0
    assert risk["active_event_count"] == 0.0


def test_route_risk_with_weather_present(engine: SimulationEngine, seeded_session: Session) -> None:
    engine.load_state(seeded_session)
    sim_key = engine.simulation_time.date().isoformat()
    weather = WeatherEvent(
        id=1, city="Nagpur", simulation_date=engine.simulation_time.date(),
        closure_risk=0.5, eta_multiplier=1.3, precipitation_mm=25.0,
    )
    engine.update_weather_event_map(weather)
    risk = engine._route_risk("Nagpur", "Pune")
    assert risk["route_risk"] == 0.5
    assert risk["eta_multiplier"] == 1.3


# ── Edge: Trip estimation without route ──────────────────────────


def test_estimate_trip_minutes_with_loaded_route(engine: SimulationEngine, seeded_session: Session) -> None:
    engine.load_state(seeded_session)
    objective = seeded_session.get(Objective, 1)
    minutes = engine._estimate_trip_minutes(objective)
    assert minutes == 325.0  # 300 (route) + 15 (loading) + 10 (unloading)


# ── Edge: Critical / Perishable detection ────────────────────────


def test_is_critical_high_priority(engine: SimulationEngine, seeded_session: Session) -> None:
    objective = seeded_session.get(Objective, 1)
    objective.priority = 5
    assert engine._is_critical_objective(objective) is True


def test_is_critical_low_priority_non_essential(engine: SimulationEngine, seeded_session: Session) -> None:
    objective = seeded_session.get(Objective, 1)
    objective.priority = 1
    objective.name = "Steel Bars"
    objective.commodity = "construction"
    assert engine._is_critical_objective(objective) is False


def test_is_critical_name_match(engine: SimulationEngine, seeded_session: Session) -> None:
    objective = seeded_session.get(Objective, 1)
    objective.priority = 1
    objective.commodity = "vaccine"
    assert engine._is_critical_objective(objective) is True


def test_is_perishable_medicine(engine: SimulationEngine, seeded_session: Session) -> None:
    objective = seeded_session.get(Objective, 1)
    objective.commodity = "insulin"
    assert engine._is_perishable_objective(objective) is True


def test_is_perishable_non_food(engine: SimulationEngine, seeded_session: Session) -> None:
    objective = seeded_session.get(Objective, 1)
    objective.commodity = "electronics"
    objective.name = "Laptops"
    assert engine._is_perishable_objective(objective) is False


# ── Edge: Stable random value ────────────────────────────────────


def test_stable_random_is_deterministic(engine: SimulationEngine) -> None:
    val1 = engine._stable_random_value("test-key")
    val2 = engine._stable_random_value("test-key")
    assert val1 == val2
    assert 0.0 <= val1 <= 1.0


def test_stable_random_different_keys_differ(engine: SimulationEngine) -> None:
    val1 = engine._stable_random_value("key-a")
    val2 = engine._stable_random_value("key-b")
    assert val1 != val2


# ── Edge: Snapshot status ────────────────────────────────────────


def test_snapshot_status_reflects_state(engine: SimulationEngine) -> None:
    status = engine.snapshot_status()
    assert status.status == "idle"
    assert status.queued_events == 0


def test_snapshot_status_after_seed_queue(engine: SimulationEngine, seeded_session: Session) -> None:
    engine.load_state(seeded_session)
    objective = seeded_session.get(Objective, 1)
    objective.assigned_vehicle_ids = [1]
    seeded_session.commit()
    engine.load_state(seeded_session)
    engine.seed_dispatch_queue()
    status = engine.snapshot_status()
    assert status.queued_events >= 1


# ── Edge: Compare scenario with no data ──────────────────────────


def test_compare_scenario_empty_returns_zeros(engine: SimulationEngine, db_session: Session) -> None:
    result = engine.compare_scenario(db_session, None)
    assert result["baseline"]["on_time_delivery_pct"] == 0.0
    assert result["improvement"]["on_time_delta_pct"] == 0.0


# ── Edge: Event map updates ──────────────────────────────────────


def test_update_news_map_skips_irrelevant(engine: SimulationEngine) -> None:
    news = NewsEvent(
        id=1, city="Delhi", simulation_date=date(2026, 6, 1),
        category="Test", headline="irrelevant", relevant=False,
        impact_score=0.8,
    )
    engine.update_news_event_map(news)
    assert len(engine.news_map) == 0


def test_update_news_map_stores_relevant(engine: SimulationEngine) -> None:
    news = NewsEvent(
        id=1, city="Delhi", simulation_date=date(2026, 6, 1),
        category="Test", headline="disruption", relevant=True,
        impact_score=0.8, impact_type="weather_disruption",
    )
    engine.update_news_event_map(news)
    assert len(engine.news_map) == 1


def test_update_news_map_takes_highest_impact(engine: SimulationEngine) -> None:
    news1 = NewsEvent(
        id=1, city="Delhi", simulation_date=date(2026, 6, 1),
        category="Test", headline="mild", relevant=True,
        impact_score=0.3, impact_type="weather_disruption",
    )
    news2 = NewsEvent(
        id=2, city="Delhi", simulation_date=date(2026, 6, 1),
        category="Test", headline="severe", relevant=True,
        impact_score=0.9, impact_type="road_blockage",
    )
    engine.update_news_event_map(news1)
    engine.update_news_event_map(news2)
    key = ("2026-06-01", "Delhi")
    assert engine.news_map[key]["impact_score"] == 0.9
    assert engine.news_map[key]["headline"] == "severe"


def test_update_weather_map_always_stores(engine: SimulationEngine) -> None:
    weather = WeatherEvent(
        id=1, city="Mumbai", simulation_date=date(2026, 6, 1),
        closure_risk=0.4, eta_multiplier=1.2, precipitation_mm=50.0,
    )
    engine.update_weather_event_map(weather)
    key = ("2026-06-01", "Mumbai")
    assert engine.weather_map[key]["closure_risk"] == 0.4


# ── Edge: Progress calculation ───────────────────────────────────


def test_progress_for_state_not_in_transit(engine: SimulationEngine) -> None:
    state = LiveVehicleState(
        vehicle_id=1, identifier="VH-0001", status="idle",
        current_facility_id=1, progress_pct=50.0,
    )
    pct = engine._progress_for_state(state)
    assert pct == 50.0


def test_progress_for_state_post_eta(engine: SimulationEngine) -> None:
    state = LiveVehicleState(
        vehicle_id=1, identifier="VH-0001", status="in_transit",
        current_facility_id=1,
        eta=engine.simulation_time - timedelta(minutes=10),
        route_distance_km=250.0, progress_pct=0.0,
    )
    pct = engine._progress_for_state(state)
    assert pct == 100.0


def test_progress_for_state_zero_remaining(engine: SimulationEngine) -> None:
    state = LiveVehicleState(
        vehicle_id=1, identifier="VH-0001", status="in_transit",
        current_facility_id=1,
        eta=engine.simulation_time,
        route_distance_km=250.0, progress_pct=0.0,
    )
    pct = engine._progress_for_state(state)
    assert pct == 100.0


# ── Edge: Queue operations ───────────────────────────────────────


def test_queue_empty_after_seed(engine: SimulationEngine) -> None:
    engine.seed_dispatch_queue()
    assert len(engine.event_queue) == 0


def test_schedule_adds_to_queue(engine: SimulationEngine) -> None:
    engine._schedule(
        engine.simulation_time + timedelta(minutes=10),
        "dispatch", vehicle_id=1, objective_id=1,
        payload={"leg": "outbound"},
    )
    assert engine.queue_size() == 1


def test_schedule_multiple_orders_by_time(engine: SimulationEngine) -> None:
    engine._schedule(
        engine.simulation_time + timedelta(minutes=30),
        "dispatch", vehicle_id=2, objective_id=1,
    )
    engine._schedule(
        engine.simulation_time + timedelta(minutes=10),
        "dispatch", vehicle_id=1, objective_id=1,
    )
    popped = heapq.heappop(engine.event_queue)
    assert popped.vehicle_id == 1  # earlier time pops first
