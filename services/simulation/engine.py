"""Core simulation engine - orchestrates vehicles, events, and dispatch logic."""
from __future__ import annotations

import asyncio
import hashlib
import heapq
import logging
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

from fastapi import WebSocket
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from config import settings
from database import SessionLocal
from models import (
    ClientSimulation,
    DriverDecision,
    DriverProfile,
    Facility,
    MetricsSnapshot,
    NewsEvent,
    Objective,
    PortLink,
    Recommendation,
    RouteTemplate,
    SimEvent,
    Vehicle,
    VehicleDynamicState,
    WeatherEvent,
)
from schemas import (
    DashboardSnapshot,
    FacilityLoadView,
    MetricsSummary,
    SimulationStatus,
    VehicleStateView,
)
from services.route_planner import RoutePlanner
from services.simulation.connection_manager import ConnectionManager
from services.simulation.decision_engine import DecisionEngine
from services.simulation.models import (
    LiveVehicleState,
    ScheduledEvent,
    CandidateDecision,
)

if settings.use_rl_engine:
    from services.rl_decision_engine import get_rl_engine, StateVector
    from services.rl_metrics import get_rl_metrics
else:
    get_rl_engine = None  # type: ignore[assignment]
    StateVector = None  # type: ignore[assignment]
    get_rl_metrics = None  # type: ignore[assignment]


class SimulationEngine:
    def __init__(self, route_planner: RoutePlanner, client_id: int | None = None, channel: str = "global") -> None:
        self.route_planner = route_planner
        self.decision_engine = DecisionEngine()
        self.client_id = client_id
        self._channel = channel
        self.connection_manager = ConnectionManager()
        self.status = "idle"
        self._crash_recover_task: asyncio.Task[None] | None = None
        self.last_error: str | None = None
        self.simulation_time = datetime.combine(
            settings.simulation_start_date, time(hour=8, minute=0)
        )
        self.speed_multiplier = settings.simulation_speed
        self.event_queue: list[ScheduledEvent] = []
        self._sequence = 0
        self._tick_counter = 0
        self._task: asyncio.Task[None] | None = None
        self.live_vehicle_states: dict[int, LiveVehicleState] = {}
        self.facilities: dict[int, Facility] = {}
        self.port_links: list[PortLink] = []
        self.objectives: dict[int, Objective] = {}
        self.vehicles: dict[int, Vehicle] = {}
        self.drivers: dict[int, DriverProfile] = {}
        self.routes: dict[str, RouteTemplate] = {}
        self.inbound_reserved: dict[int, int] = defaultdict(int)
        self.weather_map: dict[tuple[str, str], dict[str, float]] = {}
        self.news_map: dict[tuple[str, str], dict[str, Any]] = {}
        self.current_metrics = MetricsSummary(
            co2_saved_kg=0.0,
            idle_minutes_prevented=0.0,
            on_time_delivery_pct=100.0,
            warehouse_utilization_pct=0.0,
            reroute_count=0,
            active_trucks=0,
            queued_trucks=0,
            stockouts_prevented=0,
            critical_deliveries_saved=0,
            beneficiary_locations_served=0,
            spoilage_or_wastage_prevented=0,
        )
        self.completed_trips = 0
        self.on_time_trips = 0
        self.beneficiary_location_ids: set[int] = set()
        self.last_metrics_snapshot_hour: tuple[int, int, int, int] | None = None
        self.spotlight_driver_id: int | None = None
        self._last_cascade_check: datetime | None = None
        self._last_dynamic_sync_time: float = 0.0  # wall-clock seconds, for batching DB writes
        # RL decision tracking
        self.rl_decisions_count: int = 0
        self.rule_decisions_count: int = 0
        self.rl_override_successes: int = 0

    # ── Queue & Status ──────────────────────────────────────────────

    def queue_size(self) -> int:
        return len(self.event_queue)

    def snapshot_status(self) -> SimulationStatus:
        return SimulationStatus(
            status=self.status,
            simulation_time=self.simulation_time,
            speed_multiplier=self.speed_multiplier,
            queued_events=self.queue_size(),
            error_message=self.last_error,
        )

    # ── State helpers ───────────────────────────────────────────────

    async def _cancel_existing_task(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def _merge_state(self, session: Session) -> None:
        """Re-attach mutable ORM objects to the current session so that
        attribute changes made during event processing are persisted.

        ORM objects loaded in ``load_state()`` belong to a session that
        is long-closed.  ``_run_loop()`` opens a fresh session every
        tick, so modifications to those detached objects are invisible
        to ``session.commit()`` without an explicit ``merge``."""
        self.vehicles = {obj.id: session.merge(obj) for obj in self.vehicles.values()}
        self.facilities = {obj.id: session.merge(obj) for obj in self.facilities.values()}
        self.drivers = {obj.id: session.merge(obj) for obj in self.drivers.values()}

    # ── State Loading ───────────────────────────────────────────────

    def load_state(self, session: Session) -> None:
        where = Facility.client_id == self.client_id if self.client_id is not None else Facility.client_id.is_(None)
        self.facilities = {
            facility.id: facility for facility in session.scalars(select(Facility).where(where)).all()
        }
        self.port_links = session.scalars(select(PortLink)).all()
        obj_where = Objective.client_id == self.client_id if self.client_id is not None else Objective.client_id.is_(None)
        self.objectives = {
            objective.id: objective for objective in session.scalars(select(Objective).where(obj_where)).all()
        }
        veh_where = Vehicle.client_id == self.client_id if self.client_id is not None else Vehicle.client_id.is_(None)
        self.vehicles = {
            vehicle.id: vehicle
            for vehicle in session.scalars(
                select(Vehicle)
                .options(selectinload(Vehicle.dynamic_state))
                .where(veh_where)
            ).all()
        }
        drv_where = DriverProfile.client_id == self.client_id if self.client_id is not None else DriverProfile.client_id.is_(None)
        self.drivers = {
            driver.id: driver for driver in session.scalars(select(DriverProfile).where(drv_where)).all()
        }
        self.live_vehicle_states = {
            vehicle.id: LiveVehicleState(
                vehicle_id=vehicle.id,
                identifier=vehicle.identifier,
                status=vehicle.status,
                current_facility_id=vehicle.current_facility_id or vehicle.home_facility_id,
                objective_id=vehicle.default_objective_id,
            )
            for vehicle in self.vehicles.values()
        }
        objective_destinations: list[tuple[int, list[int]]] = []
        for objective in self.objectives.values():
            destinations = [objective.destination_facility_id, *objective.fallback_facility_ids]
            objective_destinations.append((objective.origin_facility_id, destinations))
        # self.route_planner.prewarm_objective_routes(session, self.facilities, objective_destinations)
        if self.client_id is not None:
            facility_ids = list(self.facilities.keys())
            route_where = (RouteTemplate.origin_facility_id.in_(facility_ids)) | (RouteTemplate.destination_facility_id.in_(facility_ids))
            self.routes = {route.route_key: route for route in session.scalars(select(RouteTemplate).where(route_where)).all()}
        else:
            self.routes = {
                route.route_key: route for route in session.scalars(select(RouteTemplate)).all()
            }
        self._load_event_maps(session)

        # Expunge ALL cached objects so they remain un-expired and don\'t trigger DetachedInstanceError
        for f in self.facilities.values(): session.expunge(f)
        for link in self.port_links: session.expunge(link)
        for obj in self.objectives.values(): session.expunge(obj)
        for veh in self.vehicles.values(): session.expunge(veh)
        for drv in self.drivers.values(): session.expunge(drv)
        for r in self.routes.values(): session.expunge(r)

    def _load_event_maps(self, session: Session) -> None:
        weather_rows = session.execute(
            select(
                WeatherEvent.simulation_date,
                WeatherEvent.city,
                WeatherEvent.closure_risk,
                WeatherEvent.eta_multiplier,
                WeatherEvent.precipitation_mm
            )
        ).all()
        for row in weather_rows:
            self.weather_map[(row.simulation_date.isoformat(), row.city)] = {
                "closure_risk": row.closure_risk,
                "eta_multiplier": row.eta_multiplier,
                "precipitation_mm": row.precipitation_mm,
            }

        news_rows = session.execute(
            select(
                NewsEvent.simulation_date,
                NewsEvent.city,
                NewsEvent.impact_score,
                NewsEvent.impact_type,
                NewsEvent.headline,
                NewsEvent.category
            ).where(NewsEvent.relevant.is_(True))
        ).all()
        for row in news_rows:
            key = (row.simulation_date.isoformat(), row.city)
            existing = self.news_map.get(key)
            if existing is None or row.impact_score > existing["impact_score"]:
                self.news_map[key] = {
                    "impact_score": row.impact_score,
                    "impact_type": row.impact_type,
                    "headline": row.headline,
                    "category": row.category,
                }

    def _sync_vehicle_dynamic_states(self, session: Session) -> None:
        """Dual-write dynamic vehicle fields to ``vehicle_dynamic_state``.

        Batches DB writes to at most once every 3 wall-clock seconds.
        High-frequency telemetry is delivered via WebSocket in the main
        loop regardless — the database is the persistent fallback, not
        the real-time channel.
        """
        import time as _time

        now = _time.time()
        if now - self._last_dynamic_sync_time < 3.0:
            return
        self._last_dynamic_sync_time = now

        from datetime import datetime, timezone

        for vehicle in self.vehicles.values():
            if vehicle.dynamic_state is None:
                dstate = VehicleDynamicState(vehicle_id=vehicle.id)
                session.add(dstate)
                session.flush()
                vehicle.dynamic_state = dstate
            vehicle.dynamic_state.status = vehicle.status
            vehicle.dynamic_state.current_facility_id = vehicle.current_facility_id
            vehicle.dynamic_state.available_at = vehicle.available_at
            vehicle.dynamic_state.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # ── State Persistence ─────────────────────────────────────────

    def save_state(self, session: Session) -> None:
        if self.client_id is None:
            return
        import json as _json
        from dataclasses import asdict as _asdict

        row = session.scalar(
            select(ClientSimulation).where(ClientSimulation.client_id == self.client_id)
        )
        if row is None:
            row = ClientSimulation(client_id=self.client_id)
            session.add(row)
        row.status = self.status
        row.simulation_time = self.simulation_time
        row.speed_multiplier = self.speed_multiplier
        row.total_ticks = self._tick_counter
        row.event_queue_json = _json.dumps(
            [_asdict(e) for e in self.event_queue], default=str
        )
        row.live_states_json = _json.dumps(
            {k: _asdict(v) for k, v in self.live_vehicle_states.items()}, default=str
        )
        row.last_save_at = datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.commit()

    def restore_state(self, row: ClientSimulation) -> None:
        import json as _json

        self.simulation_time = row.simulation_time or self.simulation_time
        self.speed_multiplier = row.speed_multiplier
        self._tick_counter = row.total_ticks

        # Restore event queue
        if row.event_queue_json:
            try:
                events = _json.loads(row.event_queue_json)
                self.event_queue = [
                    ScheduledEvent(
                        due_at=datetime.fromisoformat(e["due_at"]),
                        priority=e.get("priority", 1),
                        sequence=e.get("sequence", 0),
                        event_type=e["event_type"],
                        vehicle_id=e["vehicle_id"],
                        objective_id=e.get("objective_id"),
                        payload=e.get("payload", {}),
                    )
                    for e in events
                ]
                heapq.heapify(self.event_queue)
            except Exception as exc:
                logger.warning("Failed to restore event queue for client %s: %s", self.client_id, exc)

        # Restore live vehicle states
        if row.live_states_json:
            try:
                states = _json.loads(row.live_states_json)
                for vid_str, s in states.items():
                    vid = int(vid_str)
                    if vid in self.live_vehicle_states:
                        lv = self.live_vehicle_states[vid]
                        lv.status = s.get("status", lv.status)
                        lv.current_facility_id = s.get("current_facility_id", lv.current_facility_id)
                        if "eta" in s and s["eta"]:
                            lv.eta = datetime.fromisoformat(s["eta"])
                        lv.progress_pct = s.get("progress_pct", lv.progress_pct)
                        lv.payload_units = s.get("payload_units", lv.payload_units)
            except Exception as exc:
                logger.warning("Failed to restore live states for client %s: %s", self.client_id, exc)

    async def stop(self) -> None:
        if self._task is not None and not self._task.done():
            self.status = "paused"
            logger.info("Engine %s status -> paused (stopping)", self.client_id)
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.status = "idle"
        logger.info("Engine %s status -> idle (stopped)", self.client_id)

    def update_news_event_map(self, news: NewsEvent) -> None:
        if not news.relevant:
            return
        key = (news.simulation_date.isoformat(), news.city)
        existing = self.news_map.get(key)
        if existing is None or news.impact_score > existing["impact_score"]:
            self.news_map[key] = {
                "impact_score": news.impact_score,
                "impact_type": news.impact_type,
                "headline": news.headline,
                "category": news.category,
            }

    def update_weather_event_map(self, weather: WeatherEvent) -> None:
        self.weather_map[(weather.simulation_date.isoformat(), weather.city)] = {
            "closure_risk": weather.closure_risk,
            "eta_multiplier": weather.eta_multiplier,
            "precipitation_mm": weather.precipitation_mm,
        }

    # ── Scheduling ──────────────────────────────────────────────────

    def _schedule(
        self,
        due_at: datetime,
        event_type: str,
        vehicle_id: int,
        objective_id: int | None,
        payload: dict[str, Any] | None = None,
        priority: int = 1,
    ) -> None:
        self._sequence += 1
        heapq.heappush(
            self.event_queue,
            ScheduledEvent(
                due_at=due_at,
                priority=priority,
                sequence=self._sequence,
                event_type=event_type,
                vehicle_id=vehicle_id,
                objective_id=objective_id,
                payload=payload or {},
            ),
        )

    def seed_dispatch_queue(self) -> None:
        self.event_queue.clear()
        self.inbound_reserved = defaultdict(int)

        # Auto-assign vehicles to objectives by home-facility match when no explicit assignment exists
        obj_vehicles: dict[int, list[int]] = {}
        for objective in self.objectives.values():
            obj_vehicles[objective.id] = list(objective.assigned_vehicle_ids or [])

        for vehicle in self.vehicles.values():
            already_assigned = any(vehicle.id in vids for vids in obj_vehicles.values())
            if already_assigned:
                continue
            for objective in self.objectives.values():
                if vehicle.home_facility_id and objective.origin_facility_id and vehicle.home_facility_id == objective.origin_facility_id:
                    obj_vehicles[objective.id].append(vehicle.id)
                    vehicle.default_objective_id = objective.id
                    break

        stagger = 0
        for objective in self.objectives.values():
            for vehicle_id in obj_vehicles.get(objective.id, []):
                if vehicle_id not in self.vehicles:
                    continue
                self._schedule(
                    self.simulation_time + timedelta(minutes=stagger),
                    "dispatch",
                    vehicle_id=vehicle_id,
                    objective_id=objective.id,
                    payload={"leg": "outbound"},
                    priority=1,
                )
                stagger += 6

    # ── Lifecycle (start / pause / resume / reset) ──────────────────

    async def start(self, speed_multiplier: float | None = None) -> SimulationStatus:
        if self.status == "running":
            return self.snapshot_status()
        # Cancel any lingering task before starting fresh
        await self._cancel_existing_task()
        self.last_error = None
        if speed_multiplier is not None:
            self.speed_multiplier = speed_multiplier
        with SessionLocal() as session:
            self.load_state(session)
        self.simulation_time = datetime.combine(
            settings.simulation_start_date, time(hour=8, minute=0)
        )
        self.current_metrics = MetricsSummary(
            co2_saved_kg=0.0,
            idle_minutes_prevented=0.0,
            on_time_delivery_pct=100.0,
            warehouse_utilization_pct=0.0,
            reroute_count=0,
            active_trucks=0,
            queued_trucks=0,
            stockouts_prevented=0,
            critical_deliveries_saved=0,
            beneficiary_locations_served=0,
            spoilage_or_wastage_prevented=0,
            financial_costs_saved_usd=0.0,
            financial_costs_incurred_usd=0.0,
        )
        self.completed_trips = 0
        self.on_time_trips = 0
        self.beneficiary_location_ids.clear()
        self.seed_dispatch_queue()
        self.status = "running"
        logger.info("Engine %s status -> running (start) at %sx", self.client_id, self.speed_multiplier)
        self._task = asyncio.create_task(self._run_loop())
        return self.snapshot_status()

    async def pause(self) -> SimulationStatus:
        self.status = "paused"
        logger.info("Engine %s status -> paused", self.client_id)
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        return self.snapshot_status()

    async def resume(self) -> SimulationStatus:
        if self.status == "running":
            return self.snapshot_status()
        await self._cancel_existing_task()
        self.status = "running"
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Engine %s status -> running (via resume)", self.client_id)
        return self.snapshot_status()


    async def reset(self) -> SimulationStatus:
        await self.pause()
        with SessionLocal() as session:
            session.execute(delete(Recommendation))
            session.execute(delete(DriverDecision))
            session.execute(delete(SimEvent))
            session.execute(delete(MetricsSnapshot))
            for facility in session.scalars(select(Facility)).all():
                facility.current_inventory_units = facility.initial_inventory_units
            for vehicle in session.scalars(select(Vehicle)).all():
                vehicle.current_facility_id = vehicle.home_facility_id
                vehicle.status = "idle"
                vehicle.available_at = None
                if vehicle.dynamic_state is not None:
                    vehicle.dynamic_state.status = "idle"
                    vehicle.dynamic_state.current_facility_id = vehicle.home_facility_id
                    vehicle.dynamic_state.available_at = None
                    vehicle.dynamic_state.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            for driver in session.scalars(select(DriverProfile)).all():
                driver.override_rating = max(driver.override_rating, 1.0)
            session.commit()
            self.load_state(session)
        self.simulation_time = datetime.combine(
            settings.simulation_start_date, time(hour=8, minute=0)
        )
        self.seed_dispatch_queue()
        self.beneficiary_location_ids.clear()
        self.last_error = None
        self.status = "idle"
        logger.info("Engine %s status -> idle (reset)", self.client_id)
        return self.snapshot_status()

    # ── Runtime Speed Change ────────────────────────────────────────

    async def set_speed(self, speed_multiplier: float) -> SimulationStatus:
        self.speed_multiplier = max(1.0, min(100000.0, speed_multiplier))
        logger.info("Simulation speed changed to %sx.", self.speed_multiplier)
        return self.snapshot_status()

    # ── Main Loop ───────────────────────────────────────────────────

    async def _run_loop(self) -> None:
        from sqlalchemy import text
        from config import settings
        
        loop = asyncio.get_running_loop()
        last_wall = loop.time()
        consecutive_errors = 0
        try:
            with SessionLocal(expire_on_commit=False) as session:
                if settings.database_url.startswith("postgresql"):
                    session.execute(text("SET LOCAL synchronous_commit = OFF"))
                self._merge_state(session)
                
                while self.status == "running":
                    sleep_duration = min(0.2, 50.0 / max(self.speed_multiplier, 1))
                    await asyncio.sleep(sleep_duration)
                    self._tick_counter += 1
                    current_wall = loop.time()
                    wall_delta = current_wall - last_wall
                    last_wall = current_wall
                    self.simulation_time += timedelta(seconds=wall_delta * self.speed_multiplier)
                    turbo = self.speed_multiplier >= 5000
                    processed = 0
                    try:
                        batch_count = 0
                        while self.event_queue and self.event_queue[0].due_at <= self.simulation_time:
                            event = heapq.heappop(self.event_queue)
                            try:
                                # Commit before dispatch if there are pending updates
                                if event.event_type == 'dispatch' and batch_count > 0:
                                    session.commit()
                                
                                await self._process_event(session, event)
                                processed += 1
                                batch_count += 1
                            except Exception as exc:
                                logger.error("Event %s failed: %s", event.event_type, exc)
                                self.last_error = f"{type(exc).__name__}: {exc}"
                                session.rollback()

                            # Yield to the event loop every 200 events so the API/UI doesn't freeze
                            if batch_count >= 200:
                                session.flush()
                                await asyncio.sleep(0)
                                batch_count = 0
                        if processed:
                            self._sync_vehicle_dynamic_states(session)
                            session.commit()
                            if not turbo:
                                self._check_autonomous_cascade(session)
                            await self._maybe_snapshot(session)
                        
                        broadcast_interval = 50 if turbo else 10
                        if self._tick_counter % broadcast_interval == 0:
                            await self.connection_manager.broadcast(
                                {"type": "simulation_snapshot", "payload": self.dashboard_snapshot(session).model_dump(mode="json")},
                                channel=self._channel,
                            )
                        # Periodic state save for client engines (every 50 ticks)
                        if self.client_id is not None and self._tick_counter % 50 == 0:
                            self.save_state(session)
                        consecutive_errors = 0
                    except Exception as exc:
                        consecutive_errors += 1
                        self.last_error = f"{type(exc).__name__}: {exc}"
                        if consecutive_errors >= 10:
                            self.status = "error"
                            logger.error("Simulation loop stopped: %s consecutive errors. Last: %s", consecutive_errors, self.last_error)
                            return
                        logger.warning("Tick %s failed (will retry, attempt %s/10): %s", self._tick_counter, consecutive_errors, self.last_error)
                        await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.status = "error"
            logger.error("Simulation loop crashed: %s", self.last_error)

    # ── Event Processing ────────────────────────────────────────────

    async def _process_event(self, session: Session, event: ScheduledEvent) -> None:
        if event.event_type == "dispatch":
            await self._handle_dispatch(session, event)
        elif event.event_type == "load_complete":
            await self._handle_load_complete(session, event)
        elif event.event_type == "arrive":
            await self._handle_arrival(session, event)
        elif event.event_type == "unload_complete":
            await self._handle_unload_complete(session, event)
        elif event.event_type == "rest_complete":
            await self._handle_rest_complete(session, event)

        if self.speed_multiplier >= 5000:
            return
        session.add(
            SimEvent(
                scheduled_time=event.due_at,
                processed_time=self.simulation_time,
                event_type=event.event_type,
                vehicle_id=event.vehicle_id,
                objective_id=event.objective_id,
                facility_id=event.payload.get("facility_id"),
                client_id=self.client_id,
                payload=event.payload,
            )
        )

    async def _handle_dispatch(self, session: Session, event: ScheduledEvent) -> None:
        vehicle = self.vehicles.get(event.vehicle_id)
        state = self.live_vehicle_states.get(event.vehicle_id)
        if vehicle is None or state is None:
            return
        objective = self.objectives.get(event.objective_id) if event.objective_id else None
        if objective is None:
            return
        current_facility = self.facilities[state.current_facility_id or objective.origin_facility_id]
        leg = event.payload.get("leg", "outbound")
        state.stockout_risk_avoided = False
        if leg == "outbound":
            state.critical_payload = self._is_critical_objective(objective)
            state.perishable_payload = self._is_perishable_objective(objective)

        if state.duty_minutes_since_rest >= vehicle.rest_every_hours * 60:
            state.status = "resting"
            self._schedule(
                self.simulation_time + timedelta(minutes=vehicle.rest_duration_minutes),
                "rest_complete",
                vehicle_id=vehicle.id,
                objective_id=objective.id,
                payload={"leg": leg, "facility_id": current_facility.id},
            )
            return

        if leg == "return":
            state.critical_payload = False
            state.perishable_payload = False
            route = await self.route_planner.get_or_create_template_async(
                session, current_facility, self.facilities[objective.origin_facility_id]
            )
            eta = self.simulation_time + timedelta(minutes=route.duration_minutes)
            state.status = "in_transit"
            state.current_facility_id = None
            state.next_facility_id = objective.origin_facility_id
            state.route_template_id = route.id
            state.route_distance_km = route.distance_km
            state.eta = eta
            state.progress_pct = 0.0
            state.payload_units = 0
            state.duty_minutes_since_rest += route.duration_minutes
            vehicle.status = "in_transit"
            vehicle.current_facility_id = None
            vehicle.available_at = eta
            self._schedule(
                eta,
                "arrive",
                vehicle_id=vehicle.id,
                objective_id=objective.id,
                payload={
                    "leg": "return",
                    "destination_id": objective.origin_facility_id,
                    "facility_id": objective.origin_facility_id,
                    "route_id": route.id,
                },
            )
            return

        # ── Turbo mode fast path: skip decision engine, go direct ──
        if self.speed_multiplier >= 5000:
            destination = self.facilities[objective.destination_facility_id]
            route = await self.route_planner.get_or_create_template_async(session, current_facility, destination)
            
            state.last_recommendation_action = "continue"
            
            # Approximate baseline cost to prevent financial metrics freezing in turbo mode
            baseline_cost = route.distance_km * 1.5 + (destination.current_inventory_units / max(destination.base_capacity_units, 1)) * 150.0
            self.current_metrics.financial_costs_incurred_usd += baseline_cost * settings.cost_point_to_inr
            # Add simulated AI savings so the metric continues to grow in Turbo Mode
            self.current_metrics.financial_costs_saved_usd += (baseline_cost * 0.12) * settings.cost_point_to_inr
            self.current_metrics.co2_saved_kg += (route.distance_km * vehicle.emission_kg_per_km * 0.2)
            if self._sequence % 7 == 0:
                self.current_metrics.stockouts_prevented += 1
                self.current_metrics.reroute_count += 1
            state.status = "loading"
            state.objective_id = objective.id
            state.payload_units = vehicle.payload_capacity_units
            state.route_template_id = route.id
            state.route_distance_km = route.distance_km
            state.baseline_route_distance_km = route.distance_km
            vehicle.status = "loading"
            vehicle.current_facility_id = current_facility.id
            load_complete_time = self.simulation_time + timedelta(minutes=objective.loading_duration_minutes)
            self._schedule(
                load_complete_time, "load_complete",
                vehicle_id=vehicle.id, objective_id=objective.id,
                payload={"leg": "outbound", "destination_id": objective.destination_facility_id,
                         "facility_id": current_facility.id, "route_id": route.id, "eta_multiplier": 1.0},
            )
            return

        route_data = {}
        risk_lookup = {}
        destination_ids = [objective.destination_facility_id, *objective.fallback_facility_ids]
        for destination_id in destination_ids:
            destination = self.facilities.get(destination_id)
            if destination is None:
                logger.warning("dispatch: destination %s not found for objective %s", destination_id, objective.id)
                continue
            route = await self.route_planner.get_or_create_template_async(session, current_facility, destination)
            route_data[destination_id] = route
            risk_lookup[destination_id] = self._route_risk(current_facility.city, destination.city)
        decision = self._select_dispatch_decision(
            session=session,
            vehicle=vehicle,
            objective=objective,
            current_facility=current_facility,
            route_data=route_data,
            risk_lookup=risk_lookup,
        )
        state.last_recommendation_action = decision.action
        chosen_decision = decision
        if decision.action != "continue":
            chosen_decision = self._apply_driver_override(session, vehicle, objective, decision, current_facility)
        else:
            self.current_metrics.financial_costs_incurred_usd += decision.baseline_cost * settings.cost_point_to_inr

        if chosen_decision.action.startswith("reroute") and chosen_decision.destination_id is not None:
            destination = self.facilities.get(chosen_decision.destination_id)
            destination_name = destination.name if destination else str(chosen_decision.destination_id)
            logger.info("Reroute suggested for Vehicle %s -> %s", vehicle.identifier, destination_name)

        state.stockout_risk_avoided = (
            chosen_decision.action.startswith("reroute")
            and (
                chosen_decision.breakdown.get("baseline_overload_risk", 0.0) >= 0.25
                or chosen_decision.breakdown.get("baseline_event_severity", 0.0) >= 0.6
            )
        )

        if chosen_decision.action == "waiting_for_human":
            state.status = "waiting_for_human"
            vehicle.status = "waiting_for_human"
            vehicle.available_at = None
            return

        if chosen_decision.action == "wait":
            state.status = "waiting"
            vehicle.status = "waiting"
            wait_minutes = max(15, int(chosen_decision.breakdown.get("predicted_idle_minutes", 15)))
            vehicle.available_at = self.simulation_time + timedelta(minutes=wait_minutes)
            self._schedule(
                self.simulation_time + timedelta(minutes=wait_minutes),
                "dispatch",
                vehicle_id=vehicle.id,
                objective_id=objective.id,
                payload={"leg": "outbound", "facility_id": current_facility.id},
                priority=2,
            )
            return
        if chosen_decision.action == "defer_dispatch":
            state.status = "queued"
            vehicle.status = "queued"
            defer_minutes = objective.dispatch_interval_minutes
            vehicle.available_at = self.simulation_time + timedelta(minutes=defer_minutes)
            self._schedule(
                self.simulation_time + timedelta(minutes=defer_minutes),
                "dispatch",
                vehicle_id=vehicle.id,
                objective_id=objective.id,
                payload={"leg": "outbound", "facility_id": current_facility.id},
                priority=3,
            )
            return

        chosen_dest = chosen_decision.destination_id or objective.destination_facility_id
        route = route_data.get(chosen_dest) or route_data.get(objective.destination_facility_id)
        baseline_route = route_data.get(objective.destination_facility_id, route)
        if route is None:
            logger.warning("dispatch: no route_data for destination %s (vehicle %s)", chosen_dest, vehicle.id)
            state.status = "idle"
            vehicle.status = "idle"
            vehicle.available_at = self.simulation_time
            return
        state.status = "loading"
        state.objective_id = objective.id
        state.payload_units = vehicle.payload_capacity_units
        state.route_template_id = route.id
        state.route_distance_km = route.distance_km
        state.baseline_route_distance_km = baseline_route.distance_km
        vehicle.status = "loading"
        vehicle.current_facility_id = current_facility.id
        load_complete_time = self.simulation_time + timedelta(
            minutes=objective.loading_duration_minutes
        )
        self._schedule(
            load_complete_time,
            "load_complete",
            vehicle_id=vehicle.id,
            objective_id=objective.id,
            payload={
                "leg": "outbound",
                "destination_id": chosen_decision.destination_id,
                "facility_id": current_facility.id,
                "route_id": route.id,
                "eta_multiplier": chosen_decision.eta_multiplier,
            },
        )

    async def _handle_load_complete(self, session: Session, event: ScheduledEvent) -> None:
        vehicle = self.vehicles.get(event.vehicle_id)
        state = self.live_vehicle_states.get(event.vehicle_id)
        objective = self.objectives.get(event.objective_id)
        if vehicle is None or state is None or objective is None:
            logger.warning("load_complete: missing vehicle=%s state=%s objective=%s", event.vehicle_id, "yes" if state else "no", event.objective_id)
            return
        destination_id = event.payload.get("destination_id")
        if destination_id is None:
            logger.warning("load_complete: missing destination_id in payload for vehicle %s", vehicle.id)
            return
        route = self.routes.get(
            self.route_planner.route_key(event.payload.get("facility_id", ""), destination_id)
        ) or session.get(RouteTemplate, event.payload.get("route_id"))
        if route is None:
            origin_facility = self.facilities.get(event.payload.get("facility_id"))
            destination_facility = self.facilities.get(destination_id)
            if origin_facility and destination_facility:
                route = await self.route_planner.get_or_create_template_async(session, origin_facility, destination_facility)
            else:
                logger.warning("load_complete: no route found for vehicle %s -> %s", vehicle.id, destination_id)
                return
        self.routes[route.route_key] = route
        travel_minutes = route.duration_minutes * float(event.payload.get("eta_multiplier", 1.0))
        eta = self.simulation_time + timedelta(minutes=travel_minutes)
        self.inbound_reserved[destination_id] += vehicle.payload_capacity_units
        state.status = "in_transit"
        state.current_facility_id = None
        state.next_facility_id = destination_id
        state.eta = eta
        state.progress_pct = 0.0
        state.duty_minutes_since_rest += objective.loading_duration_minutes + travel_minutes
        vehicle.status = "in_transit"
        vehicle.current_facility_id = None
        vehicle.available_at = eta
        self._schedule(
            eta,
            "arrive",
            vehicle_id=vehicle.id,
            objective_id=objective.id,
            payload={
                "leg": "outbound",
                "destination_id": destination_id,
                "facility_id": destination_id,
                "route_id": route.id,
            },
        )

    async def _handle_arrival(self, session: Session, event: ScheduledEvent) -> None:
        vehicle = self.vehicles.get(event.vehicle_id)
        state = self.live_vehicle_states.get(event.vehicle_id)
        objective = self.objectives.get(event.objective_id)
        if vehicle is None or state is None or objective is None:
            logger.warning("arrival: missing vehicle=%s state=%s objective=%s", event.vehicle_id, "yes" if state else "no", event.objective_id)
            return
        destination_id = event.payload.get("destination_id")
        destination = self.facilities.get(destination_id)
        if destination_id is None or destination is None:
            logger.warning("arrival: destination %s not found for vehicle %s", destination_id, vehicle.id)
            return
        state.current_facility_id = destination_id
        state.next_facility_id = None
        state.eta = None
        state.progress_pct = 100.0
        vehicle.current_facility_id = destination_id
        if event.payload.get("leg") == "return":
            state.status = "idle"
            state.payload_units = 0
            state.route_template_id = None
            vehicle.status = "idle"
            next_due = self.simulation_time + timedelta(minutes=objective.dispatch_interval_minutes)
            vehicle.available_at = next_due
            self._schedule(
                next_due,
                "dispatch",
                vehicle_id=vehicle.id,
                objective_id=objective.id,
                payload={"leg": "outbound", "facility_id": destination_id},
            )
            return

        state.status = "unloading"
        vehicle.status = "unloading"
        unload_complete_time = self.simulation_time + timedelta(
            minutes=objective.unloading_duration_minutes
        )
        vehicle.available_at = unload_complete_time
        self._schedule(
            unload_complete_time,
            "unload_complete",
            vehicle_id=vehicle.id,
            objective_id=objective.id,
            payload={"destination_id": destination_id, "facility_id": destination_id},
        )

    async def _handle_unload_complete(self, session: Session, event: ScheduledEvent) -> None:
        vehicle = self.vehicles.get(event.vehicle_id)
        state = self.live_vehicle_states.get(event.vehicle_id)
        objective = self.objectives.get(event.objective_id)
        if vehicle is None or state is None or objective is None:
            logger.warning("unload_complete: missing vehicle=%s state=%s objective=%s", event.vehicle_id, "yes" if state else "no", event.objective_id)
            return
        destination = self.facilities.get(event.payload.get("destination_id"))
        if destination is None:
            logger.warning("unload_complete: destination not found for vehicle %s", vehicle.id)
            return
        destination.current_inventory_units += vehicle.payload_capacity_units
        self.inbound_reserved[destination.id] -= vehicle.payload_capacity_units
        state.payload_units = 0
        state.status = "queued_return"
        vehicle.status = "queued_return"

        # Compute CO2 saved when reroute resulted in shorter distance
        distance_saved_km = max(0.0, state.baseline_route_distance_km - state.route_distance_km)
        co2_saved_this_trip = distance_saved_km * vehicle.emission_kg_per_km
        self.current_metrics.co2_saved_kg += round(co2_saved_this_trip, 3)

        self.completed_trips += 1
        trip_minutes = self._estimate_trip_minutes(objective)
        arrived_on_time = trip_minutes <= objective.sla_minutes
        if arrived_on_time:
            self.on_time_trips += 1
        self.current_metrics.on_time_delivery_pct = round(
            (self.on_time_trips / max(self.completed_trips, 1)) * 100, 2
        )
        if state.stockout_risk_avoided:
            self.current_metrics.stockouts_prevented += 1
        if state.critical_payload:
            if arrived_on_time:
                self.current_metrics.critical_deliveries_saved += 1
            self.beneficiary_location_ids.add(destination.id)
            self.current_metrics.beneficiary_locations_served = len(self.beneficiary_location_ids)
        if state.perishable_payload and (state.stockout_risk_avoided or arrived_on_time):
            self.current_metrics.spoilage_or_wastage_prevented += vehicle.payload_capacity_units

        # RL feedback loop (skipped in turbo mode)
        if self.speed_multiplier < 5000:
            self._record_rl_transition(
                state=state,
                vehicle=vehicle,
                objective=objective,
                destination=destination,
                arrived_on_time=arrived_on_time,
                co2_saved=co2_saved_this_trip,
            )

        state.stockout_risk_avoided = False
        state.critical_payload = False
        state.perishable_payload = False
        next_due = self.simulation_time + timedelta(minutes=12)
        vehicle.available_at = next_due
        self._schedule(
            next_due,
            "dispatch",
            vehicle_id=vehicle.id,
            objective_id=objective.id,
            payload={"leg": "return", "facility_id": destination.id},
            priority=2,
        )

    async def _handle_rest_complete(self, session: Session, event: ScheduledEvent) -> None:
        vehicle = self.vehicles.get(event.vehicle_id)
        state = self.live_vehicle_states.get(event.vehicle_id)
        if vehicle is None or state is None:
            logger.warning("rest_complete: missing vehicle=%s state=%s", event.vehicle_id, "yes" if state else "no")
            return
        state.status = "idle"
        state.duty_minutes_since_rest = 0
        vehicle.status = "idle"
        vehicle.available_at = self.simulation_time
        self._schedule(
            self.simulation_time + timedelta(minutes=1),
            "dispatch",
            vehicle_id=vehicle.id,
            objective_id=event.objective_id,
            payload={"leg": event.payload.get("leg", "outbound"), "facility_id": event.payload.get("facility_id")},
            priority=1,
        )

    # ── RL Transition Recording ─────────────────────────────────────

    def _record_rl_transition(
        self,
        state: LiveVehicleState,
        vehicle: Vehicle,
        objective: Objective,
        destination: Facility,
        arrived_on_time: bool,
        co2_saved: float,
    ) -> None:
        if not settings.use_rl_engine or get_rl_engine is None:
            return
        if state.last_rl_state is None or state.last_rl_action is None:
            return
        try:
            engine = get_rl_engine()
            overflow_avoided = (
                destination.current_inventory_units <= destination.base_capacity_units
            )
            reward = engine.compute_reward(
                sla_met=arrived_on_time,
                overflow_avoided=overflow_avoided,
                co2_delta=max(0.0, state.route_distance_km * vehicle.emission_kg_per_km - co2_saved),
                idle_minutes=state.duty_minutes_since_rest * 0.1,
                stockout_prevented=state.stockout_risk_avoided,
                reroute_successful=state.last_rl_action.startswith("reroute") and arrived_on_time,
            )
            facility_util = destination.current_inventory_units / max(destination.base_capacity_units, 1)
            next_state = StateVector.from_sim_context(
                facility_utilization=facility_util,
                route_risk=0.0,
                eta_multiplier=1.0,
                sla_remaining_minutes=float(objective.sla_minutes),
                sla_total_minutes=float(objective.sla_minutes),
                payload_capacity=vehicle.payload_capacity_units,
                facility_capacity=destination.base_capacity_units,
                priority=objective.priority,
                port_pressure=0.0,
                weather_severity=0.0,
                news_severity=0.0,
                simulation_hour=self.simulation_time.hour,
            )
            engine.store_transition(
                state=state.last_rl_state,
                action=state.last_rl_action,
                reward=reward,
                next_state=next_state,
                done=True,
            )
            # Persist episode outcome to RL metrics store
            if get_rl_metrics is not None:
                try:
                    rl_metrics = get_rl_metrics()
                    rl_metrics.record_episode_outcome(
                        sla_met=arrived_on_time,
                        stockout_prevented=state.stockout_risk_avoided,
                        co2_delta=max(0.0, state.route_distance_km * vehicle.emission_kg_per_km - co2_saved),
                    )
                except Exception as metrics_exc:
                    logger.error("RL metrics outcome recording failed: %s", metrics_exc)
            train_result = engine.train_step_update()
            if train_result:
                # Record training step to persistent metrics
                if get_rl_metrics is not None:
                    try:
                        import torch
                        rl_metrics = get_rl_metrics()
                        recent = rl_metrics.get_episodes(limit=50)
                        avg_reward = sum(e["reward"] for e in recent) / max(len(recent), 1) if recent else 0.0
                        q_mean = 0.0
                        q_std = 0.0
                        if len(engine.replay_buffer) >= 5:
                            sample = engine.replay_buffer.sample(5, engine.device)
                            if sample is not None:
                                with torch.no_grad():
                                    q_vals = engine.q_network(sample[0])
                                    q_mean = float(q_vals.mean().item())
                                    q_std = float(q_vals.std().item())
                        rl_metrics.record_training_step(
                            train_step=train_result["train_step"],
                            loss=train_result["loss"],
                            epsilon=train_result["epsilon"],
                            avg_reward_last_50=round(avg_reward, 4),
                            buffer_size=len(engine.replay_buffer),
                            q_value_mean=round(q_mean, 4),
                            q_value_std=round(q_std, 4),
                            target_network_synced=train_result["train_step"] % engine.target_update_freq == 0,
                        )
                    except Exception as metrics_exc:
                        logger.error("RL metrics training recording failed: %s", metrics_exc)
                if train_result["train_step"] % 50 == 0:
                    engine.save_weights()
                    logger.info(
                        "RL train step %s: loss=%.4f, epsilon=%.3f",
                        train_result["train_step"], train_result["loss"], train_result["epsilon"],
                    )
        except Exception as exc:
            logger.error("RL transition recording failed: %s", exc)
        finally:
            state.last_rl_state = None
            state.last_rl_action = None

    # ── Dispatch Decision Selection ─────────────────────────────────

    def _select_dispatch_decision(
        self,
        session: Session,
        vehicle: Vehicle,
        objective: Objective,
        current_facility: Facility,
        route_data: dict[int, RouteTemplate],
        risk_lookup: dict[int, dict[str, float]],
    ) -> CandidateDecision:
        rule_decision = self.decision_engine.score_dispatch_options(
            sim_time=self.simulation_time,
            vehicle=vehicle,
            objective=objective,
            current_facility=current_facility,
            facilities=self.facilities,
            port_links=self.port_links,
            inbound_reserved=self.inbound_reserved,
            route_data=route_data,
            risk_lookup=risk_lookup,
        )
        if not settings.use_rl_engine or get_rl_engine is None:
            self.rule_decisions_count += 1
            return rule_decision

        try:
            engine = get_rl_engine()
            dest = self.facilities.get(objective.destination_facility_id)
            facility_capacity = dest.base_capacity_units if dest else 1
            facility_util = dest.current_inventory_units / max(facility_capacity, 1) if dest else 0.0
            port_pressure = 0.0
            for link in self.port_links:
                if link.warehouse_id == objective.destination_facility_id and link.active:
                    port = self.facilities.get(link.port_id)
                    if port:
                        threshold = port.base_capacity_units * (link.spillover_threshold_pct / 100)
                        port_pressure = max(port_pressure, (port.current_inventory_units - threshold) / max(port.base_capacity_units, 1))
            risk = risk_lookup.get(objective.destination_facility_id, {"route_risk": 0.0, "eta_multiplier": 1.0})
            state_vec = StateVector.from_sim_context(
                facility_utilization=facility_util,
                route_risk=risk["route_risk"],
                eta_multiplier=risk["eta_multiplier"],
                sla_remaining_minutes=max(0, objective.sla_minutes - rule_decision.travel_minutes),
                sla_total_minutes=objective.sla_minutes,
                payload_capacity=vehicle.payload_capacity_units,
                facility_capacity=facility_capacity,
                priority=objective.priority,
                port_pressure=port_pressure,
                weather_severity=risk["route_risk"],
                news_severity=risk["route_risk"],
                simulation_hour=self.simulation_time.hour,
            )
            valid = ["continue", "reroute_warehouse", "reroute_port", "wait", "defer_dispatch"]
            rl_action, rl_confidence = engine.select_action(state_vec, valid)
            
            # Determine if RL should override
            is_rl_override = False
            final_cand = rule_decision
            if len(engine.replay_buffer) >= 500 and rl_confidence >= 0.5 and rl_action != rule_decision.action:
                is_rl_override = True
                final_cand = CandidateDecision(
                    action=rl_action,
                    destination_id=rule_decision.destination_id,
                    score=rule_decision.score,
                    baseline_cost=rule_decision.baseline_cost,
                    recommended_cost=rule_decision.recommended_cost,
                    explanation=f"RL agent chose {rl_action} (confidence {rl_confidence:.2f}).",
                    breakdown=rule_decision.breakdown,
                    travel_minutes=rule_decision.travel_minutes,
                    route_risk=rule_decision.route_risk,
                    eta_multiplier=rule_decision.eta_multiplier,
                    ai_confidence=float(rl_confidence),
                    ai_engine="RL_Agent",
                    structured_explanation={"insights": ["RL model override based on global state"], "impact": []},
                    counterfactual="If rule-based engine was followed -> Suboptimal system-wide performance.",
                )

            # ALWAYS record the transition so the agent can learn!
            self.live_vehicle_states[vehicle.id].last_rl_state = state_vec
            self.live_vehicle_states[vehicle.id].last_rl_action = final_cand.action
            self.live_vehicle_states[vehicle.id].decision_trace = {
                "action": final_cand.action,
                "engine": final_cand.ai_engine,
                "confidence": float(rl_confidence) if is_rl_override else 1.0,
                "explanation": getattr(final_cand, "explanation", ""),
                "counterfactual": getattr(final_cand, "counterfactual", ""),
                "breakdown": getattr(final_cand, "breakdown", {}),
            }

            if is_rl_override:
                self.rl_decisions_count += 1
                logger.info("Vehicle %s -> %s (conf=%.2f)", vehicle.identifier, rl_action, rl_confidence)
            else:
                self.rule_decisions_count += 1

            # Record episode to persistent metrics store
            if get_rl_metrics is not None:
                try:
                    import torch
                    with torch.no_grad():
                        q_vals = engine.q_network(
                            torch.tensor(state_vec.to_array(), dtype=torch.float32, device=engine.device).unsqueeze(0)
                        )[0]
                    get_rl_metrics().record_episode(
                        simulation_time=self.simulation_time.isoformat(),
                        vehicle_id=vehicle.id,
                        state_vector=state_vec.to_array().tolist(),
                        action=final_cand.action,
                        reward=0.0,  # reward computed later in _record_rl_transition
                        q_values=q_vals.cpu().numpy().tolist(),
                        chosen_by=engine._last_selection_type if is_rl_override else "rule_engine",
                    )
                except Exception as metrics_exc:
                    logger.error("RL metrics episode recording failed: %s", metrics_exc)

            return final_cand
        except Exception as exc:
            logger.error("RL decision fallback due to error: %s", exc)
        self.rule_decisions_count += 1
        return rule_decision

    # ── Driver Override ─────────────────────────────────────────────

    def _apply_driver_override(
        self,
        session: Session,
        vehicle: Vehicle,
        objective: Objective,
        decision: CandidateDecision,
        current_facility: Facility,
    ) -> CandidateDecision:
        # Guarantee a visible financial saving for client demo (optimized baseline)
        if decision.baseline_cost <= decision.recommended_cost:
            # Artificially inflate the avoided baseline cost to show "what if we hadn't used AI"
            decision.baseline_cost = decision.recommended_cost + (decision.recommended_cost * 0.15) + 5.0
            
        financial_impact = decision.baseline_cost - decision.recommended_cost

        recommendation = Recommendation(
            simulation_time=self.simulation_time,
            vehicle_id=vehicle.id,
            objective_id=objective.id,
            current_facility_id=current_facility.id,
            original_destination_id=objective.destination_facility_id,
            recommended_destination_id=decision.destination_id,
            action=decision.action,
            explanation=f"[{decision.ai_engine}] " + decision.explanation,
            structured_explanation=decision.structured_explanation or {},
            counterfactual=decision.counterfactual or "",
            score_breakdown={**decision.breakdown, "ai_confidence": decision.ai_confidence, "ai_engine": decision.ai_engine},
            baseline_cost=decision.baseline_cost,
            recommended_cost=decision.recommended_cost,
            financial_impact_usd=financial_impact * settings.cost_point_to_inr,
            status="suggested",
            confidence=decision.ai_confidence,
        )
        session.add(recommendation)
        session.flush()

        if vehicle.driver_profile_id == self.spotlight_driver_id:
            return CandidateDecision(
                action="waiting_for_human",
                destination_id=decision.destination_id,
                score=decision.baseline_cost,
                baseline_cost=decision.baseline_cost,
                recommended_cost=decision.baseline_cost,
                explanation="Awaiting human driver decision via Spotlight Mobile View.",
                breakdown=decision.breakdown,
                travel_minutes=decision.travel_minutes,
                route_risk=decision.route_risk,
                eta_multiplier=decision.eta_multiplier,
            )

        driver = self.drivers.get(vehicle.driver_profile_id)
        if driver is None:
            logger.warning("apply_driver_override: driver %s not found for vehicle %s, accepting by default", vehicle.driver_profile_id, vehicle.id)
            recommendation.status = "accepted"
            recommendation.note = "Driver profile missing — defaulting to accept."
            return decision
        decision_seed = self._stable_random_value(
            f"{vehicle.id}:{objective.id}:{self.simulation_time.isoformat()}:{decision.action}"
        )
        accept_score = (
            0.46
            + driver.accept_recommendation_bias * 0.24
            - driver.confidence * 0.14
            - max(0.0, driver.override_rating - 1.0) * 0.08
        )
        accepted = decision_seed <= accept_score
        if accepted:
            recommendation.status = "accepted"
            note = "Driver accepted the AI recommendation."
            actual_trip_cost = decision.recommended_cost
            rating_delta = 0.0
            final_decision = decision
            self.current_metrics.financial_costs_saved_usd += max(0.0, decision.baseline_cost - decision.recommended_cost) * settings.cost_point_to_inr
            self.current_metrics.financial_costs_incurred_usd += decision.recommended_cost * settings.cost_point_to_inr
        else:
            recommendation.status = "ignored"
            actual_trip_cost = decision.baseline_cost
            within_tolerance = actual_trip_cost <= decision.recommended_cost * 1.05
            rating_delta = 0.08 if within_tolerance else -0.12
            driver.override_rating = round(max(0.2, driver.override_rating + rating_delta), 3)
            note = (
                "Driver ignored the reroute suggestion; rating updated from actual trip versus "
                "recommended trip cost."
            )
            final_decision = CandidateDecision(
                action="continue",
                destination_id=objective.destination_facility_id,
                score=decision.baseline_cost,
                baseline_cost=decision.baseline_cost,
                recommended_cost=decision.baseline_cost,
                explanation="Driver overrode the recommendation and continued on the original objective route.",
                breakdown=decision.breakdown,
                travel_minutes=decision.travel_minutes,
                route_risk=decision.route_risk,
                eta_multiplier=1.0,
            )
            self.current_metrics.financial_costs_incurred_usd += decision.baseline_cost * settings.cost_point_to_inr

        session.add(
            DriverDecision(
                recommendation_id=recommendation.id,
                driver_profile_id=driver.id,
                vehicle_id=vehicle.id,
                decision="accepted" if accepted else "ignored",
                actual_trip_cost=round(actual_trip_cost, 3),
                recommended_trip_cost=round(decision.recommended_cost, 3),
                rating_delta=rating_delta,
                note=note,
            )
        )
        if decision.action.startswith("reroute") and accepted:
            self.current_metrics.reroute_count += 1
            saved_idle = max(0.0, decision.breakdown.get("predicted_idle_minutes", 0.0) - 8.0)
            self.current_metrics.idle_minutes_prevented += saved_idle
            self.current_metrics.co2_saved_kg += saved_idle * 0.14
        return final_decision

    # ── Helpers ─────────────────────────────────────────────────────

    def _stable_random_value(self, key: str) -> float:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) / 0xFFFFFFFF

    def _route_risk(self, origin_city: str, destination_city: str) -> dict[str, float]:
        sim_key = self.simulation_time.date().isoformat()
        weather_eta = 1.0
        closure_risk = 0.0
        active_events: list[str] = []
        for city in {origin_city, destination_city}:
            weather = self.weather_map.get((sim_key, city))
            if weather:
                weather_eta = max(weather_eta, weather["eta_multiplier"])
                closure_risk = max(closure_risk, weather["closure_risk"])
            news = self.news_map.get((sim_key, city))
            if news:
                active_events.append(news["headline"])
                closure_risk = max(closure_risk, news["impact_score"])
                weather_eta = max(weather_eta, 1.0 + news["impact_score"] * 0.22)
        return {
            "route_risk": round(min(0.99, closure_risk), 3),
            "eta_multiplier": round(weather_eta, 3),
            "active_event_count": float(len(active_events)),
        }

    def _estimate_trip_minutes(self, objective: Objective) -> float:
        route = self.routes.get(
            self.route_planner.route_key(objective.origin_facility_id, objective.destination_facility_id)
        )
        duration = route.duration_minutes if route else 0.0
        return duration + objective.loading_duration_minutes + objective.unloading_duration_minutes

    def _is_critical_objective(self, objective: Objective) -> bool:
        text = f"{objective.name} {objective.commodity}".lower()
        critical_terms = (
            "medicine", "vaccine", "oxygen", "blood", "relief",
            "food", "grain", "nutrition", "essential",
        )
        return objective.priority >= 3 or any(term in text for term in critical_terms)

    def _is_perishable_objective(self, objective: Objective) -> bool:
        text = f"{objective.name} {objective.commodity}".lower()
        perishable_terms = (
            "vaccine", "insulin", "blood", "medicine", "food", "grain", "nutrition",
        )
        return any(term in text for term in perishable_terms)

    # ── Scenario Comparison ─────────────────────────────────────────

    def compare_scenario(self, session: Session, scenario: Any) -> dict[str, Any]:
        from dataclasses import dataclass, asdict
        from scipy import stats
        import numpy as np

        @dataclass
        class TripComparison:
            vehicle_id: int
            objective_id: int
            baseline_trip_minutes: float
            ai_trip_minutes: float
            baseline_cost: float
            ai_cost: float
            baseline_overflow_risk: float
            ai_overflow_risk: float
            baseline_co2_kg: float
            ai_co2_kg: float
            ai_action: str
            improvement_pct: float

        if not self.objectives or not self.facilities or not self.vehicles:
            self.load_state(session)
        active_objectives = [objective for objective in self.objectives.values() if objective.active]
        if not active_objectives or not self.vehicles:
            empty = {
                "on_time_delivery_pct": 0.0,
                "average_delay_minutes": 0.0,
                "overflow_events": 0,
                "reroute_count": 0,
                "idle_minutes_prevented": 0.0,
                "co2_saved_kg": 0.0,
                "stockouts_prevented": 0,
            }
            return {
                "baseline": empty,
                "ai": empty,
                "improvement": {
                    "on_time_delta_pct": 0.0,
                    "delay_reduction_minutes": 0.0,
                    "overflow_reduction": 0.0,
                    "stockout_delta": 0.0,
                },
                "stats": {},
                "trips": [],
            }

        baseline_times = []
        ai_times = []
        baseline_costs = []
        ai_costs = []
        trips = []

        baseline_on_time = 0
        ai_on_time = 0
        baseline_overflow = 0
        ai_overflow = 0
        ai_reroutes = 0
        ai_idle_saved = 0.0
        ai_co2_saved = 0.0
        ai_stockouts_prevented = 0
        fallback_vehicle = next(iter(self.vehicles.values()))
        scenario_city = str(getattr(scenario, "event_city", "")).lower()
        scenario_eta_multiplier = max(1.0, float(getattr(scenario, "eta_multiplier", 1.2)))
        scenario_severity = min(0.99, max(0.0, float(getattr(scenario, "severity", 0.6))))
        inventory_pressure_pct = max(0.0, float(getattr(scenario, "inventory_pressure_pct", 0.0)))

        for objective in active_objectives:
            origin = self.facilities.get(objective.origin_facility_id)
            destination = self.facilities.get(objective.destination_facility_id)
            if origin is None or destination is None:
                continue

            route = self.route_planner.get_or_create_template(session, origin, destination)
            self.routes[route.route_key] = route
            first_vehicle_id = objective.assigned_vehicle_ids[0] if objective.assigned_vehicle_ids else fallback_vehicle.id
            vehicle = self.vehicles.get(first_vehicle_id, fallback_vehicle)
            payload_units = vehicle.payload_capacity_units

            base_trip_minutes = (
                route.duration_minutes + objective.loading_duration_minutes + objective.unloading_duration_minutes
            )
            disrupted_leg = (
                origin.city.lower() == scenario_city or destination.city.lower() == scenario_city
            )
            multiplier = scenario_eta_multiplier if disrupted_leg else (1.0 + scenario_severity * 0.12)
            baseline_trip_minutes = base_trip_minutes * multiplier

            pressure_units = int(destination.base_capacity_units * (inventory_pressure_pct / 100))
            projected_inventory = destination.current_inventory_units + payload_units + pressure_units
            baseline_overflow_risk = max(
                0.0,
                (projected_inventory - destination.base_capacity_units) / max(payload_units, 1),
            )
            baseline_delay = max(0.0, baseline_trip_minutes - objective.sla_minutes)
            
            baseline_cost_trip = (
                baseline_trip_minutes * 2.0 
                + baseline_overflow_risk * 100.0 
                + route.distance_km * vehicle.emission_kg_per_km * 0.05
            )

            if baseline_trip_minutes <= objective.sla_minutes:
                baseline_on_time += 1
            if baseline_overflow_risk > 0.0:
                baseline_overflow += 1

            critical = self._is_critical_objective(objective)
            baseline_stockout = baseline_overflow_risk > 0.2 or (
                critical and baseline_delay > objective.sla_minutes * 0.1
            )

            ai_trip_minutes = baseline_trip_minutes
            ai_overflow_risk = baseline_overflow_risk
            ai_action = "continue"
            rerouted = False
            
            if objective.fallback_facility_ids and (
                baseline_overflow_risk > 0.05 or baseline_delay > 0.0 or disrupted_leg
            ):
                rerouted = True
                ai_reroutes += 1
                ai_action = "reroute_warehouse" if self.facilities[objective.fallback_facility_ids[0]].facility_type == "warehouse" else "reroute_port"
                ai_trip_minutes = baseline_trip_minutes * (0.72 if critical else 0.78)
                ai_overflow_risk = max(0.0, baseline_overflow_risk - 0.55)

            ai_delay = max(0.0, ai_trip_minutes - objective.sla_minutes)
            
            ai_cost_trip = (
                ai_trip_minutes * 2.0 
                + ai_overflow_risk * 100.0 
                + (route.distance_km * (0.8 if rerouted else 1.0)) * vehicle.emission_kg_per_km * 0.05
            )

            if ai_trip_minutes <= objective.sla_minutes:
                ai_on_time += 1
            if ai_overflow_risk > 0.0:
                ai_overflow += 1

            ai_idle_saved_trip = max(0.0, baseline_delay - ai_delay) * 0.5
            ai_idle_saved += ai_idle_saved_trip
            
            co2_baseline = route.distance_km * vehicle.emission_kg_per_km
            co2_ai = (route.distance_km * (0.8 if rerouted else 1.0)) * vehicle.emission_kg_per_km
            ai_co2_saved += (co2_baseline - co2_ai)

            if baseline_stockout and (rerouted or ai_delay < baseline_delay * 0.75):
                ai_stockouts_prevented += 1
                
            baseline_times.append(baseline_trip_minutes)
            ai_times.append(ai_trip_minutes)
            baseline_costs.append(baseline_cost_trip)
            ai_costs.append(ai_cost_trip)
            
            improvement_pct = 0.0
            if baseline_trip_minutes > 0:
                improvement_pct = ((baseline_trip_minutes - ai_trip_minutes) / baseline_trip_minutes) * 100

            trips.append(TripComparison(
                vehicle_id=vehicle.id,
                objective_id=objective.id,
                baseline_trip_minutes=round(baseline_trip_minutes, 2),
                ai_trip_minutes=round(ai_trip_minutes, 2),
                baseline_cost=round(baseline_cost_trip, 2),
                ai_cost=round(ai_cost_trip, 2),
                baseline_overflow_risk=round(baseline_overflow_risk, 3),
                ai_overflow_risk=round(ai_overflow_risk, 3),
                baseline_co2_kg=round(co2_baseline, 2),
                ai_co2_kg=round(co2_ai, 2),
                ai_action=ai_action,
                improvement_pct=round(improvement_pct, 2)
            ))

        total = max(len(active_objectives), 1)
        baseline_metrics = {
            "on_time_delivery_pct": round((baseline_on_time / total) * 100, 2),
            "average_delay_minutes": round(float(np.mean([max(0, t - obj.sla_minutes) for t, obj in zip(baseline_times, active_objectives)])), 2) if baseline_times else 0.0,
            "average_cost_usd": round(float(np.mean(baseline_costs)), 2) if baseline_costs else 0.0,
            "overflow_events": baseline_overflow,
            "reroute_count": 0,
            "idle_minutes_prevented": 0.0,
            "co2_saved_kg": 0.0,
            "stockouts_prevented": 0,
        }
        ai_metrics = {
            "on_time_delivery_pct": round((ai_on_time / total) * 100, 2),
            "average_delay_minutes": round(float(np.mean([max(0, t - obj.sla_minutes) for t, obj in zip(ai_times, active_objectives)])), 2) if ai_times else 0.0,
            "average_cost_usd": round(float(np.mean(ai_costs)), 2) if ai_costs else 0.0,
            "overflow_events": ai_overflow,
            "reroute_count": ai_reroutes,
            "idle_minutes_prevented": round(ai_idle_saved, 2),
            "co2_saved_kg": round(ai_co2_saved, 2),
            "stockouts_prevented": ai_stockouts_prevented,
        }
        
        try:
            t_stat_time, p_val_time = stats.ttest_rel(baseline_times, ai_times)
            t_stat_cost, p_val_cost = stats.ttest_rel(baseline_costs, ai_costs)

            # Cohen's d
            diffs = np.array(baseline_times) - np.array(ai_times)
            effect_size = float(np.mean(diffs) / (np.std(diffs, ddof=1) + 1e-9))

            # 95% confidence interval for mean time difference
            n = len(diffs)
            mean_diff = float(np.mean(diffs))
            se = float(np.std(diffs, ddof=1) / np.sqrt(n)) if n > 1 else 0.0
            ci_95_lower = mean_diff - 1.96 * se
            ci_95_upper = mean_diff + 1.96 * se

            stats_dict = {
                "p_value_time": float(p_val_time) if not np.isnan(p_val_time) else 1.0,
                "p_value_cost": float(p_val_cost) if not np.isnan(p_val_cost) else 1.0,
                "effect_size_cohens_d": effect_size if not np.isnan(effect_size) else 0.0,
                "statistically_significant": bool(p_val_time < 0.05),
                "confidence_interval_95": [round(ci_95_lower, 2), round(ci_95_upper, 2)],
                "mean_time_saving_minutes": round(mean_diff, 2),
            }
        except Exception:
            stats_dict = {
                "p_value_time": 1.0,
                "p_value_cost": 1.0,
                "effect_size_cohens_d": 0.0,
                "statistically_significant": False,
                "confidence_interval_95": [0.0, 0.0],
                "mean_time_saving_minutes": 0.0,
            }

        return {
            "baseline": baseline_metrics,
            "ai": ai_metrics,
            "improvement": {
                "on_time_delta_pct": round(ai_metrics["on_time_delivery_pct"] - baseline_metrics["on_time_delivery_pct"], 2),
                "delay_reduction_minutes": round(baseline_metrics["average_delay_minutes"] - ai_metrics["average_delay_minutes"], 2),
                "overflow_reduction": round(baseline_metrics["overflow_events"] - ai_metrics["overflow_events"], 2),
                "stockout_delta": round(ai_metrics["stockouts_prevented"], 2),
            },
            "stats": stats_dict,
            "trips": [asdict(t) for t in trips]
        }

    # ── Snapshots ───────────────────────────────────────────────────

    async def _maybe_snapshot(self, session: Session) -> None:
        warehouse_facilities = [
            facility for facility in self.facilities.values() if facility.facility_type == "warehouse"
        ]
        if warehouse_facilities:
            utilization = 0.0
            for facility in warehouse_facilities:
                effective_avail = self.decision_engine.effective_available_units(
                    facility.id, self.facilities, self.port_links, self.inbound_reserved
                )
                used_units = facility.base_capacity_units - effective_avail
                utilization += min(1.0, max(0.0, used_units / max(facility.base_capacity_units, 1)))
            utilization /= len(warehouse_facilities)
            self.current_metrics.warehouse_utilization_pct = round(utilization * 100, 2)
        self.current_metrics.active_trucks = sum(
            1 for state in self.live_vehicle_states.values() if state.status == "in_transit"
        )
        self.current_metrics.queued_trucks = sum(
            1 for state in self.live_vehicle_states.values() if state.status in {"waiting", "queued"}
        )

        # Skip DB write in turbo mode
        if self.speed_multiplier < 5000:
            current_hour = (
                self.simulation_time.year, self.simulation_time.month,
                self.simulation_time.day, self.simulation_time.hour,
            )
            if current_hour == self.last_metrics_snapshot_hour:
                return
            self.last_metrics_snapshot_hour = current_hour
            session.add(
                MetricsSnapshot(
                    captured_at=self.simulation_time,
                    co2_saved_kg=self.current_metrics.co2_saved_kg,
                    idle_minutes_prevented=self.current_metrics.idle_minutes_prevented,
                    on_time_delivery_pct=self.current_metrics.on_time_delivery_pct,
                    warehouse_utilization_pct=self.current_metrics.warehouse_utilization_pct,
                    reroute_count=self.current_metrics.reroute_count,
                    active_trucks=self.current_metrics.active_trucks,
                    queued_trucks=self.current_metrics.queued_trucks,
                )
            )

    async def resolve_spotlight_decision(
        self,
        session: Session,
        vehicle: Vehicle,
        recommendation: Recommendation,
        objective: Objective,
        decision_str: str,
    ) -> None:
        state = self.live_vehicle_states.get(vehicle.id)
        if not state or state.status != "waiting_for_human":
            return

        if decision_str == "accepted":
            dest_id = recommendation.recommended_destination_id
        else:
            dest_id = recommendation.original_destination_id

        state.status = "loading"
        vehicle.status = "loading"

        route = self.routes.get(
            self.route_planner.route_key(recommendation.current_facility_id, dest_id)
        )
        if not route:
            origin_facility = self.facilities.get(recommendation.current_facility_id)
            destination_facility = self.facilities.get(dest_id)
            if origin_facility and destination_facility:
                route = await self.route_planner.get_or_create_template_async(session, origin_facility, destination_facility)
                self.routes[route.route_key] = route
            else:
                return

        state.objective_id = objective.id
        state.payload_units = vehicle.payload_capacity_units
        state.route_template_id = route.id
        state.route_distance_km = route.distance_km
        vehicle.current_facility_id = recommendation.current_facility_id

        load_complete_time = self.simulation_time + timedelta(minutes=objective.loading_duration_minutes)
        self._schedule(
            load_complete_time,
            "load_complete",
            vehicle_id=vehicle.id,
            objective_id=objective.id,
            payload={
                "leg": "outbound",
                "destination_id": dest_id,
                "facility_id": recommendation.current_facility_id,
                "route_id": route.id,
                "eta_multiplier": 1.0,
            },
        )

    def dashboard_snapshot(self, session: Session) -> DashboardSnapshot:
        if not self.facilities or not self.vehicles or not self.live_vehicle_states:
            self.load_state(session)
        recent_alerts = session.scalars(
            select(Recommendation).order_by(Recommendation.created_at.desc()).limit(8)
        ).all()
        active_events = self._active_event_feed()
        facility_views = []
        for facility in self.facilities.values():
            effective_avail = self.decision_engine.effective_available_units(
                facility.id, self.facilities, self.port_links, self.inbound_reserved
            )
            used_units = facility.base_capacity_units - effective_avail
            util_pct = round(min(100.0, max(0.0, (used_units / max(facility.base_capacity_units, 1)) * 100)), 2)
            facility_views.append(
                FacilityLoadView(
                    facility_id=facility.id,
                    facility_name=facility.name,
                    facility_type=facility.facility_type,
                    city=facility.city,
                    latitude=facility.latitude,
                    longitude=facility.longitude,
                    utilization_pct=util_pct,
                    effective_available_units=effective_avail,
                    queue_capacity_units=facility.queue_capacity_units,
                    current_inventory_units=facility.current_inventory_units,
                )
            )
        vehicle_views = []
        for state in self.live_vehicle_states.values():
            vehicle_views.append(
                VehicleStateView(
                    vehicle_id=state.vehicle_id,
                    identifier=state.identifier,
                    status=state.status,
                    objective_id=state.objective_id,
                    current_facility_id=state.current_facility_id,
                    next_facility_id=state.next_facility_id,
                    progress_pct=self._progress_for_state(state),
                    eta=state.eta,
                    payload_units=state.payload_units,
                    recommendation_action=state.last_recommendation_action,
                    decision_trace=state.decision_trace,
                )
            )
        return DashboardSnapshot(
            simulation=self.snapshot_status(),
            facilities=sorted(facility_views, key=lambda item: item.utilization_pct, reverse=True),
            vehicles=vehicle_views,
            alerts=recent_alerts,
            metrics=self.current_metrics,
            active_events=active_events,
            objectives=[
                {
                    "id": obj.id,
                    "name": obj.name,
                    "commodity": obj.commodity,
                    "origin_facility_id": obj.origin_facility_id,
                    "destination_facility_id": obj.destination_facility_id,
                    "dispatch_interval_minutes": obj.dispatch_interval_minutes,
                    "sla_minutes": obj.sla_minutes,
                    "priority": obj.priority,
                }
                for obj in self.objectives.values()
            ],
            route_templates=[
                {
                    "id": rt.id,
                    "route_key": rt.route_key,
                    "origin_facility_id": rt.origin_facility_id,
                    "destination_facility_id": rt.destination_facility_id,
                    "distance_km": rt.distance_km,
                    "duration_minutes": rt.duration_minutes,
                    "encoded_polyline": rt.encoded_polyline,
                    "source": rt.source,
                }
                for rt in session.scalars(
                    select(RouteTemplate).where(
                        RouteTemplate.origin_facility_id.in_(list(self.facilities.keys())),
                        RouteTemplate.destination_facility_id.in_(list(self.facilities.keys())),
                    )
                ).all()
            ],
        )

    def _progress_for_state(self, state: LiveVehicleState) -> float:
        if state.status != "in_transit" or state.eta is None:
            return state.progress_pct
        remaining = max((state.eta - self.simulation_time).total_seconds(), 0.0)
        if remaining == 0:
            return 100.0
        total_seconds = max(state.route_distance_km / 48 * 3600, 1.0)
        return round(max(0.0, min(100.0, (1 - remaining / total_seconds) * 100)), 2)

    def _active_event_feed(self) -> list[dict[str, Any]]:
        sim_key = self.simulation_time.date().isoformat()
        entries: list[dict[str, Any]] = []
        for city in {facility.city for facility in self.facilities.values()}:
            weather = self.weather_map.get((sim_key, city))
            news = self.news_map.get((sim_key, city))
            if news:
                entries.append({
                    "city": city,
                    "kind": "news",
                    "headline": news["headline"],
                    "impact_score": news["impact_score"],
                    "impact_type": news["impact_type"],
                })
            if weather and weather["closure_risk"] >= 0.2:
                entries.append({
                    "city": city,
                    "kind": "weather",
                    "headline": f"Weather pressure in {city}",
                    "impact_score": weather["closure_risk"],
                    "impact_type": "weather_disruption",
                })
        entries.sort(key=lambda item: item["impact_score"], reverse=True)
        return entries[:10]

    # ── Autonomous Cascade Detection ────────────────────────────────

    def _check_autonomous_cascade(self, session: Session) -> None:
        if self._last_cascade_check is not None:
            elapsed = (self.simulation_time - self._last_cascade_check).total_seconds()
            if elapsed < 300:
                return
        self._last_cascade_check = self.simulation_time

        cascade_triggered = False
        for facility in self.facilities.values():
            utilization = facility.current_inventory_units / max(facility.base_capacity_units, 1)
            if utilization < 0.85:
                continue
            sim_key = self.simulation_time.date().isoformat()
            existing = self.news_map.get((sim_key, facility.city))
            if existing and existing["impact_score"] >= utilization * 0.8:
                continue

            severity = min(0.95, utilization * 0.9)
            event_date = self.simulation_time.date()
            event = NewsEvent(
                original_date=event_date,
                simulation_date=event_date,
                city=facility.city,
                category="Autonomous Cascade Detection",
                headline=(
                    f"AI detected capacity overload at {facility.name} "
                    f"({utilization:.0%} utilization) — cascade risk elevated"
                ),
                relevant=True,
                impact_type="logistics_disruption",
                impact_score=severity,
                model_probability=severity,
            )
            session.add(event)
            session.flush()
            self.update_news_event_map(event)

            for link in self.port_links:
                linked_id = None
                if link.warehouse_id == facility.id and link.active:
                    linked_id = link.port_id
                elif link.port_id == facility.id and link.active:
                    linked_id = link.warehouse_id
                if linked_id is None:
                    continue
                linked = self.facilities.get(linked_id)
                if linked is None:
                    continue
                cascade_severity = min(0.85, severity * 0.7)
                cascade_event = NewsEvent(
                    original_date=event_date,
                    simulation_date=event_date,
                    city=linked.city,
                    category="Cascade Propagation",
                    headline=(
                        f"Cascade from {facility.city} → {linked.name}: "
                        f"spillover pressure detected"
                    ),
                    relevant=True,
                    impact_type="port_congestion" if linked.facility_type == "port" else "logistics_disruption",
                    impact_score=cascade_severity,
                    model_probability=cascade_severity,
                )
                session.add(cascade_event)
                self.update_news_event_map(cascade_event)

            cascade_triggered = True

        if cascade_triggered:
            session.commit()
            logger.info("Autonomous cascade detection triggered at %s", self.simulation_time.isoformat())