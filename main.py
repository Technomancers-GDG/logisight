"""Resilient Essential Goods Coordinator — FastAPI application entry point."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import select

logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from limiter import limiter


try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth, credentials
    _firebase_available = True
except Exception:
    _firebase_available = False
    firebase_auth = None

from config import settings
from database import SessionLocal, init_db
from seed_data import seed_demo_data

from app_state import simulation_engine
from services.rl_decision_engine import get_rl_engine
from services.simulation_manager import simulation_manager
from routes import crud_router, simulation_router, driver_router, ai_router, logistics_router, rl_router, comparison_router, integration_router, management_router, client_auth_router, client_upload_router, client_dashboard_router

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    global demo_disruption_task
    init_db()
    with SessionLocal() as session:
        if settings.allow_demo_seed:
            seed_demo_data(session)
        # Restore all previously running client engines
        await simulation_manager.start_all(session)

    # Seed RL engine with pre-trained weights at startup
    get_rl_engine()

    if settings.demo_mode:
        await simulation_engine.start(speed_multiplier=settings.simulation_speed)
        if demo_disruption_task is None or demo_disruption_task.done():
            demo_disruption_task = asyncio.create_task(_trigger_demo_disruption())
        _rl_background_train = asyncio.create_task(_run_rl_background_training())
        _periodic_disruption = asyncio.create_task(_run_periodic_disruption_scheduler())
    else:
        _rl_background_train = None
        _periodic_disruption = None
    yield
    for task_name, task in [("demo_disruption", demo_disruption_task),
                            ("rl_background_train", _rl_background_train),
                            ("periodic_disruption", _periodic_disruption)]:
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    demo_disruption_task = None
    # Graceful shutdown: save all engines
    with SessionLocal() as session:
        await simulation_manager.save_all(session)
    await simulation_manager.stop_all()

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

cors_origins_env = os.getenv("CORS_ORIGINS", "")
if cors_origins_env:
    origins = [o.strip() for o in cors_origins_env.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

demo_disruption_task: asyncio.Task | None = None

app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(Exception)
async def cors_aware_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    origin = request.headers.get("origin", "")
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers={"Access-Control-Allow-Origin": origin or "*"},
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers={"Access-Control-Allow-Origin": origin or "*"},
    )


# --- Router registration ---
app.include_router(crud_router)
app.include_router(simulation_router)
app.include_router(driver_router)
app.include_router(ai_router)
app.include_router(logistics_router)
app.include_router(rl_router)
app.include_router(comparison_router)
app.include_router(integration_router)
app.include_router(management_router)
app.include_router(client_auth_router)
app.include_router(client_upload_router)
app.include_router(client_dashboard_router)


# --- Auth ---
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name}


@app.get("/api/auth/me")
def auth_me(request: Request) -> dict:
    user = _verify_firebase_token(request)
    if user is None:
        return {"authenticated": False, "message": "No valid Firebase token provided. Demo mode active."}
    return {"authenticated": True, "uid": user.get("uid"), "email": user.get("email"), "name": user.get("name")}


def _init_firebase() -> None:
    if not _firebase_available:
        return
    try:
        firebase_admin.get_app()
    except ValueError:
        try:
            firebase_admin.initialize_app(credentials.Certificate("firebase-service-account.json"))
        except Exception:
            firebase_admin.initialize_app()


def _verify_firebase_token(request: Request) -> dict | None:
    if not _firebase_available:
        return None
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        _init_firebase()
        return firebase_auth.verify_id_token(auth_header.replace("Bearer ", ""), clock_skew_seconds=60)
    except Exception:
        return None


# --- Demo disruption task ---
async def _trigger_demo_disruption() -> None:
    try:
        await asyncio.sleep(max(1, settings.demo_disruption_delay_seconds))
        if simulation_engine.status != "running":
            return
        severity = min(0.99, max(0.0, settings.demo_disruption_severity))
        event_date = simulation_engine.simulation_time.date()
        from models import NewsEvent
        for attempt in range(3):
            try:
                with SessionLocal() as session:
                    event = NewsEvent(
                        original_date=event_date, simulation_date=event_date, city=settings.demo_disruption_city,
                        category="Demo Disruption", headline=f"Automatic disruption: flood pressure in {settings.demo_disruption_city}",
                        relevant=True, impact_type="weather_disruption", impact_score=severity, model_probability=severity,
                    )
                    session.add(event)
                    session.commit()
                    session.refresh(event)
                    simulation_engine.update_news_event_map(event)
                break
            except Exception:
                if attempt < 2:
                    await asyncio.sleep(1)
                else:
                    raise
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error("Demo disruption task failed: %s", exc)


# --- Background RL training ---
async def _run_rl_background_training() -> None:
    """Periodically run mini-batch RL training steps during simulation."""
    try:
        rl = get_rl_engine()
        while True:
            await asyncio.sleep(3.0)
            if simulation_engine.status != "running":
                continue
            for _ in range(3):
                result = rl.train_step_update()
                if result is None:
                    break
            if rl.train_step > 0 and rl.train_step % 20 == 0:
                rl.save_weights()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error("RL background training failed: %s", exc)


# --- Periodic disruption scheduler ---
async def _run_periodic_disruption_scheduler() -> None:
    """Inject random simulated disruptions every 10-20 simulated days
    to give the illusion of a live API feed."""
    import random as _random
    from models import WeatherEvent, Facility

    CITIES = ["Chennai", "Mumbai", "Bengaluru", "Delhi", "Kolkata", "Hyderabad", "Pune", "Ahmedabad"]
    TYPES = ["heavy_rainfall", "flood", "cyclone", "heatwave", "fog", "landslide", "thunderstorm"]

    try:
        while True:
            sim_days_interval = _random.randint(10, 20)
            real_seconds = sim_days_interval / max(settings.simulation_speed, 1)
            await asyncio.sleep(real_seconds)

            if simulation_engine.status != "running":
                continue

            city = _random.choice(CITIES)
            event_type = _random.choice(TYPES)
            severity = round(_random.uniform(0.3, 0.85), 2)
            event_date = simulation_engine.simulation_time.date()

            with SessionLocal() as session:
                existing = session.query(WeatherEvent).filter(
                    WeatherEvent.city == city,
                    WeatherEvent.event_type == event_type,
                    WeatherEvent.original_date == event_date,
                ).first()
                if existing:
                    continue

                event = WeatherEvent(
                    original_date=event_date,
                    simulation_date=event_date,
                    city=city,
                    event_type=event_type,
                    severity=severity,
                    description=f"Scheduled disruption: {event_type} in {city} (severity={severity})",
                )
                session.add(event)
                session.commit()
                session.refresh(event)
                simulation_engine.update_weather_event_map(event)
                logger.info(
                    "Periodic disruption injected: %s in %s (severity=%.2f)",
                    event_type, city, severity,
                )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error("Periodic disruption scheduler failed: %s", exc)
# --- Diagnostic ---
@app.get("/api/diag/engines")
async def diag_engines():
    """Diagnostic: list all simulation engines and their status."""
    return {
        "global_engine": {
            "status": simulation_engine.status,
            "client_id": simulation_engine.client_id,
            "vehicle_count": len(simulation_engine.live_vehicle_states),
            "tick": simulation_engine._tick_counter,
            "speed": simulation_engine.speed_multiplier,
        },
        "client_engines": simulation_manager.list_engines(),
    }


# --- WebSocket ---
@app.websocket("/ws/operations")
async def operations_socket(websocket: WebSocket) -> None:
    await simulation_engine.connection_manager.connect(websocket)
    try:
        from starlette.concurrency import run_in_threadpool
        def get_snapshot():
            with SessionLocal() as session:
                return simulation_engine.dashboard_snapshot(session).model_dump(mode="json")
        
        snapshot = await run_in_threadpool(get_snapshot)
        await websocket.send_json(
            {"type": "simulation_snapshot", "payload": snapshot}
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        simulation_engine.connection_manager.disconnect(websocket)


@app.websocket("/ws/client")
async def client_socket(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token or token == "undefined":
        logger.info("[DIAG] /ws/client: missing token, closing 4001")
        await websocket.close(code=4001, reason="Missing token")
        return

    logger.info("[DIAG] /ws/client: token received, verifying...")
    client_id = None

    with SessionLocal() as session:
        from models import IntegrationClient

        if token.startswith("regc_"):
            from middleware.api_key_auth import _hash_api_key
            import hmac
            prefix = token[:8]
            client = session.scalar(
                select(IntegrationClient).where(
                    IntegrationClient.api_key_prefix == prefix,
                    IntegrationClient.enabled.is_(True),
                )
            )
            if client is not None and hmac.compare_digest(client.api_key_hash, _hash_api_key(token)):
                client_id = client.id
                logger.info("[DIAG] /ws/client: API key verified, client_id=%s", client_id)
        else:
            from middleware.firebase_client import _decode_unverified_firebase_token as _decode_fb
            if settings.firebase_enabled:
                try:
                    _init_firebase()
                    decoded = firebase_auth.verify_id_token(token, clock_skew_seconds=60)
                except Exception as exc:
                    logger.warning("[DIAG] /ws/client: token verification failed: %s", exc)
                    await websocket.close(code=4001, reason="Invalid token")
                    return
            else:
                decoded = _decode_fb(token)
                if decoded is None:
                    logger.warning("[DIAG] /ws/client: mock token decode failed")
                    await websocket.close(code=4001, reason="Invalid token")
                    return
            
            firebase_uid = decoded.get("uid")
            client = session.scalar(
                select(IntegrationClient).where(IntegrationClient.firebase_uid == firebase_uid)
            )
            if client is not None and client.enabled:
                client_id = client.id
                logger.info("[DIAG] /ws/client: Firebase token verified, client_id=%s", client_id)

        if client_id is None:
            logger.warning("[DIAG] /ws/client: client not found or disabled")
            await websocket.close(code=4003, reason="Unauthorized")
            return
        logger.info("[DIAG] /ws/client: client found, client_id=%s", client_id)

    channel = f"client_{client_id}"
    engine = simulation_manager.get_engine(client_id)
    if engine is None:
        logger.info("[DIAG] /ws/client: no engine for client_id=%s, attempting lazy start", client_id)
        with SessionLocal() as session:
            try:
                engine = await simulation_manager.start_client(client_id, session)
            except Exception as exc:
                logger.warning("[DIAG] /ws/client: lazy start failed for client_id=%s: %s", client_id, exc)
        if engine is None:
            await websocket.close(code=4004, reason="No active engine for client")
            return

    logger.info("[DIAG] /ws/client: engine found for client_id=%s, status=%s, vehicles=%s",
                client_id, engine.status, len(engine.live_vehicle_states))
    await engine.connection_manager.connect(websocket, channel=channel)
    logger.info("[DIAG] /ws/client: websocket connected for client_id=%s", client_id)
    try:
        from starlette.concurrency import run_in_threadpool
        def get_client_snapshot():
            with SessionLocal() as session:
                snap = engine.dashboard_snapshot(session)
                return snap.model_dump(mode="json"), len(snap.vehicles)
                
        try:
            payload, vehicles_len = await run_in_threadpool(get_client_snapshot)
            await websocket.send_json(
                {"type": "simulation_snapshot", "payload": payload}
            )
            logger.info("[DIAG] /ws/client: initial snapshot sent for client_id=%s, vehicles=%s",
                        client_id, vehicles_len)
        except Exception as exc:
            logger.error("[DIAG] /ws/client: snapshot failed for client_id=%s: %s", client_id, exc)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("[DIAG] /ws/client: disconnect for client_id=%s", client_id)
        engine.connection_manager.disconnect(websocket, channel=channel)


# --- Static file serving ---
FRONTEND_DIST = Path("frontend/dist")
DRIVER_DIST = Path("driver-app-main/dist")

# Mount static assets first (order-independent)
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

if DRIVER_DIST.exists():
    app.mount("/driver-assets", StaticFiles(directory=DRIVER_DIST), name="driver_assets")

# Specific SPA routes (must be registered before the catch-all)
if DRIVER_DIST.exists():
    @app.get("/driver", include_in_schema=False)
    async def driver_index() -> FileResponse:
        return FileResponse(DRIVER_DIST / "index.html")

if FRONTEND_DIST.exists():
    @app.get("/", include_in_schema=False)
    async def frontend_index() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def frontend_catch_all(full_path: str) -> FileResponse:
        """Serve index.html for all client-side routes (SPA)."""
        path = full_path.rstrip("/")
        if path.startswith("api/") or path.startswith("ws/") or path.startswith("driver"):
            raise HTTPException(status_code=404)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    async def placeholder_index() -> HTMLResponse:
        return HTMLResponse("""
            <html>
            <head><title>Resilient Essential Goods Coordinator</title></head>
            <body style="font-family:Segoe UI, sans-serif;padding:32px;background:#101622;color:#f4f7fb;">
            <h1>Resilient Essential Goods Coordinator API</h1>
            <p>The FastAPI backend is running. Build the React admin panel in <code>frontend/</code> to serve it here.</p>
            <p>Core endpoints are available under <code>/api/*</code> and the live stream is at <code>/ws/operations</code>.</p>
            </body>
            </html>
        """)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
# Reload 2
