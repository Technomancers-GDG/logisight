"""Multi-tenant simulation manager — manages per-client SimulationEngine instances."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import SessionLocal
from models import ClientSimulation

logger = logging.getLogger(__name__)


class SimulationManager:
    def __init__(self) -> None:
        self._engines: dict[int | None, Any] = {}
        self._lock = asyncio.Lock()
        self._save_task: asyncio.Task[None] | None = None

    def get_engine(self, client_id: int | None) -> Any | None:
        engine = self._engines.get(client_id)
        if engine is not None:
            logger.info("[DIAG] get_engine(client_id=%s) -> found, status=%s", client_id, engine.status)
        else:
            logger.info("[DIAG] get_engine(client_id=%s) -> NOT FOUND. Active engines: %s",
                        client_id, list(self._engines.keys()))
        return engine

    def list_engines(self) -> list[dict[str, Any]]:
        """Diagnostic: list all active engines with their status."""
        return [
            {"client_id": cid, "status": e.status, "channel": e._channel,
             "vehicle_count": len(e.live_vehicle_states), "tick": e._tick_counter}
            for cid, e in self._engines.items()
        ]

    def register_engine(self, client_id: int | None, engine: Any) -> None:
        self._engines[client_id] = engine

    def remove_engine(self, client_id: int) -> None:
        self._engines.pop(client_id, None)

    async def start_client(self, client_id: int, session: Session) -> Any:
        from app_state import route_planner
        from services.simulation import SimulationEngine

        logger.info("[DIAG] start_client called for client_id=%s", client_id)
        async with self._lock:
            if client_id in self._engines:
                engine = self._engines[client_id]
                logger.info("[DIAG] Engine already exists for client_id=%s status=%s", client_id, engine.status)
                if engine.status not in ("running",):
                    logger.info("[DIAG] Restarting non-running engine for client_id=%s", client_id)
                    await engine.start()
                return engine

            logger.info("[DIAG] Creating new engine for client_id=%s channel=client_%s", client_id, client_id)
            try:
                engine = SimulationEngine(route_planner, client_id=client_id, channel=f"client_{client_id}")
                self._engines[client_id] = engine
                
                from sqlalchemy import select
                from models import ClientSimulation
                row = session.scalar(select(ClientSimulation).where(ClientSimulation.client_id == client_id))
                speed = row.speed_multiplier if row else 1000.0
                
                await engine.start(speed_multiplier=speed)
                logger.info("[DIAG] Engine started successfully for client_id=%s status=%s", client_id, engine.status)
            except Exception as exc:
                self._engines.pop(client_id, None)
                logger.error("[DIAG] Engine start FAILED for client_id=%s: %s", client_id, exc)
                raise
            return engine

    async def stop_client(self, client_id: int) -> None:
        async with self._lock:
            engine = self._engines.get(client_id)
            if engine is not None:
                await engine.stop()
                with SessionLocal() as session:
                    engine.save_state(session)
                self._engines.pop(client_id, None)

    async def stop_all(self) -> None:
        async with self._lock:
            for engine in list(self._engines.values()):
                try:
                    await engine.stop()
                except Exception as exc:
                    logger.error("Error stopping engine: %s", exc)
            self._engines.clear()

    async def save_all(self, session: Session) -> None:
        async with self._lock:
            for engine in list(self._engines.values()):
                try:
                    engine.save_state(session)
                except Exception as exc:
                    logger.error("Error saving engine state: %s", exc)

    async def start_all(self, session: Session) -> None:
        """Restore all previously running engines on server boot.

        Restores engines with status 'running', 'paused', or 'error'.
        'error' engines are retried since the crash may have been caused by
        a transient issue (e.g. database lock) that has since been resolved.
        """
        rows = session.scalars(
            select(ClientSimulation).where(ClientSimulation.status.in_(["running", "paused", "error"]))
        ).all()

        logger.info("[DIAG] start_all: found %s engine(s) to restore: %s",
                    len(rows), [{"client_id": r.client_id, "status": r.status} for r in rows])

        for row in rows:
            try:
                from app_state import route_planner
                from services.simulation import SimulationEngine

                engine = SimulationEngine(route_planner, client_id=row.client_id, channel=f"client_{row.client_id}")
                engine.load_state(session)
                engine.restore_state(row)
                self._engines[row.client_id] = engine

                if row.status == "running":
                    engine._task = asyncio.create_task(engine._run_loop())
                    engine.status = "running"
                else:
                    engine.status = "paused"

                logger.info("Restored engine for client %s (status=%s)", row.client_id, row.status)
            except Exception as exc:
                logger.error("Failed to restore engine for client %s: %s", row.client_id, exc)


simulation_manager = SimulationManager()
