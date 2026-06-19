"""Integration test: end-to-end reroute decision through the simulation engine.

Seeds a vehicle, facility, objective and a weather disruption, then
asserts the decision engine produces a reroute action with confidence.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database import Base
from models import Facility, Objective, Vehicle, WeatherEvent
from services.route_planner import RoutePlanner
from services.simulation import DecisionEngine, SimulationEngine


def test_integration_reroute_under_disruption() -> None:
    """A near-capacity destination + weather disruption should trigger a reroute."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    with TestingSession() as session:
        origin = Facility(
            id=1, name="Delhi Hub", city="Delhi", facility_type="warehouse",
            latitude=28.61, longitude=77.23,
            base_capacity_units=10000, current_inventory_units=3500,
            initial_inventory_units=3500, queue_capacity_units=500, active=True,
        )
        destination = Facility(
            id=2, name="Chennai Port", city="Chennai", facility_type="port",
            latitude=13.08, longitude=80.27,
            base_capacity_units=12000, current_inventory_units=11000,
            initial_inventory_units=11000, queue_capacity_units=800, active=True,
        )
        fallback = Facility(
            id=3, name="Bengaluru Warehouse", city="Bengaluru", facility_type="warehouse",
            latitude=12.97, longitude=77.59,
            base_capacity_units=12000, current_inventory_units=4000,
            initial_inventory_units=4000, queue_capacity_units=600, active=True,
        )
        vehicle = Vehicle(
            id=1, identifier="TRK-001", payload_capacity_units=1000,
            home_facility_id=1, current_facility_id=1, driver_profile_id=1,
            default_objective_id=1, average_speed_kmph=48,
            emission_kg_per_km=1.5, rest_every_hours=8, rest_duration_minutes=45,
            status="idle",
        )
        objective = Objective(
            id=1, name="Iron Ore Run", commodity="Iron Ore",
            origin_facility_id=1, destination_facility_id=2,
            fallback_facility_ids=[3],
            dispatch_interval_minutes=120, loading_duration_minutes=30,
            unloading_duration_minutes=35, sla_minutes=1400, priority=2,
            assigned_vehicle_ids=[1], active=True,
        )
        weather = WeatherEvent(
            id=1, original_date=date(2026, 1, 1), simulation_date=date(2026, 1, 1),
            city="Chennai", max_temp_c=38.0, min_temp_c=26.0,
            closure_risk=0.72, eta_multiplier=1.55, precipitation_mm=85.0,
        )
        for obj in [origin, destination, fallback, vehicle, objective, weather]:
            session.add(obj)
        session.commit()

        planner = RoutePlanner(osrm_base_url="http://127.0.0.1:9999")
        sim = SimulationEngine(route_planner=planner)
        sim.simulation_time = datetime(2026, 1, 1, 8, 0)
        sim.load_state(session)

        vehicle = sim.vehicles[1]
        objective = sim.objectives[1]
        current_facility = sim.facilities[1]

        destinations = [objective.destination_facility_id, *objective.fallback_facility_ids]
        route_data = {}
        risk_lookup = {}
        for dest_id in destinations:
            dest = sim.facilities.get(dest_id)
            if dest is None:
                continue
            route = sim.route_planner.get_or_create_template(session, current_facility, dest)
            route_data[dest_id] = route
            risk_lookup[dest_id] = sim._route_risk(current_facility.city, dest.city)

        decision = sim._select_dispatch_decision(
            session=session, vehicle=vehicle, objective=objective,
            current_facility=current_facility,
            route_data=route_data, risk_lookup=risk_lookup,
        )

        assert decision.action != "continue", (
            f"Expected reroute/wait/defer but got {decision.action} "
            f"(overflow={decision.breakdown.get('baseline_overload_risk', 0.0):.2f}, "
            f"severity={decision.breakdown.get('baseline_event_severity', 0.0):.2f})"
        )
        assert decision.destination_id is not None, "Decision must pick a destination"
        assert decision.ai_confidence > 0.0, "Decision must have positive confidence"


def test_integration_continue_under_healthy_conditions() -> None:
    """When capacity is comfortable and no disruption, action should be 'continue'."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    with TestingSession() as session:
        origin = Facility(
            id=1, name="Delhi Hub", city="Delhi", facility_type="warehouse",
            latitude=28.61, longitude=77.23,
            base_capacity_units=10000, current_inventory_units=2500,
            initial_inventory_units=2500, queue_capacity_units=500, active=True,
        )
        destination = Facility(
            id=2, name="Jaipur Warehouse", city="Jaipur", facility_type="warehouse",
            latitude=26.91, longitude=75.79,
            base_capacity_units=8000, current_inventory_units=3000,
            initial_inventory_units=3000, queue_capacity_units=400, active=True,
        )
        vehicle = Vehicle(
            id=1, identifier="TRK-002", payload_capacity_units=1000,
            home_facility_id=1, current_facility_id=1, driver_profile_id=1,
            default_objective_id=1, average_speed_kmph=48,
            emission_kg_per_km=1.5, rest_every_hours=8, rest_duration_minutes=45,
            status="idle",
        )
        objective = Objective(
            id=1, name="Consumer Goods", commodity="Consumer Goods",
            origin_facility_id=1, destination_facility_id=2,
            fallback_facility_ids=[], dispatch_interval_minutes=120,
            loading_duration_minutes=20, unloading_duration_minutes=25,
            sla_minutes=800, priority=1, assigned_vehicle_ids=[1], active=True,
        )
        for obj in [origin, destination, vehicle, objective]:
            session.add(obj)
        session.commit()

        planner = RoutePlanner(osrm_base_url="http://127.0.0.1:9999")
        sim = SimulationEngine(route_planner=planner)
        sim.simulation_time = datetime(2026, 1, 1, 8, 0)
        sim.load_state(session)

        vehicle = sim.vehicles[1]
        objective = sim.objectives[1]
        current_facility = sim.facilities[1]
        destination = sim.facilities[2]

        route = sim.route_planner.get_or_create_template(session, current_facility, destination)
        risk_lookup = {2: sim._route_risk(current_facility.city, destination.city)}

        decision = sim._select_dispatch_decision(
            session=session, vehicle=vehicle, objective=objective,
            current_facility=current_facility,
            route_data={2: route}, risk_lookup=risk_lookup,
        )

        assert decision.action == "continue", (
            f"Expected 'continue' for healthy conditions, got {decision.action}"
        )
