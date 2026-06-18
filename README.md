# Resilient Essential Goods Coordinator

FastAPI + React application for disruption-aware essential-goods logistics simulation across India.

This repository currently includes:
- A FastAPI backend with simulation, routing, event ingestion, and impact metrics.
- A Vite + React frontend control center with map-driven operations and live updates.
- SQLite persistence by default, with configurable database and routing providers.

## Current Feature Set (Verified)

- Network management: facilities, ports, port links, vehicles, drivers, and objectives.
- Simulation controls: start, pause, resume, reset, and speed multiplier.
- Decision engine actions: continue, reroute to warehouse or port, wait, and defer dispatch.
- Route planning with OSRM first, automatic estimated-route fallback when OSRM is unavailable.
- Disruption ingestion from weather/news workbooks plus manual driver incident injection.
- Scenario presets with trigger and baseline-vs-AI comparison.
- Driver mobile loop: pending instructions, accept or ignore decisions, and incident reporting.
- SDG-style operations metrics including stockouts prevented and critical deliveries saved.
- Real-time operations stream over WebSocket at `/ws/operations`.

## Frontend Views Available Now

The current App shell exposes 8 tabs:
- Map View
- Network
- Objectives
- Live Ops
- Scenarios
- Driver Mobile
- Events
- Impact

## Architecture

- Backend: FastAPI + SQLAlchemy in [main.py](main.py) and [services/](services/).
- Database: SQLite by default (`supply_chain.db`) via [database.py](database.py).
- Frontend: React + Vite in [frontend/](frontend/), with Leaflet map rendering.
- Static serving: when [frontend/dist](frontend/dist) exists, FastAPI serves it at `/`.

## Quick Start

### 1. Backend setup (PowerShell)

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Backend URLs:
- API root: `http://127.0.0.1:8000/api/health`
- Swagger UI: `http://127.0.0.1:8000/docs`

### 2. Frontend development server

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:
- Vite app: `http://localhost:5173`

The Vite config proxies `/api` and `/ws` to `http://127.0.0.1:8000`.

## Build Frontend For FastAPI Serving

```bash
cd frontend
npm run build
cd ..
python -m uvicorn main:app --reload
```

After build, open `http://127.0.0.1:8000` to use the bundled frontend served by FastAPI.

## Configuration

Environment variables are defined in [config.py](config.py):

| Variable | Default | Purpose |
|---|---|---|
| `APP_NAME` | `Resilient Essential Goods Coordinator` | FastAPI app title |
| `DATABASE_URL` | `sqlite:///./supply_chain.db` | SQLAlchemy database URL |
| `OSRM_BASE_URL` | `https://router.project-osrm.org` | Routing provider base URL |
| `SIMULATION_START_DATE` | `2026-01-01` | Initial simulation date |
| `SIMULATION_SPEED` | `120.0` | Default speed multiplier |
| `NEWS_DATASET_PATH` | `All_Cities_News_v2.xlsx` | News workbook path |
| `WEATHER_DATASET_PATH` | `Historical_Weather_Data_2024_2026.xlsx` | Weather workbook path |
| `ALLOW_DEMO_SEED` | `true` | Loaded in settings (currently not enforced in startup flow) |

## Seed Data and Event Import Behavior

On startup:
- Tables are created automatically.
- If the `facilities` table is empty, demo data is seeded from [seed_data.py](seed_data.py).
- If weather/news tables are empty and workbook files exist, startup imports weather + sampled news.

Current demo seed contents:
- 86 facilities (warehouses and ports)
- 6 drivers
- 12 vehicles
- 44 objectives
- 10 port links
- 3 scenario presets

Manual import endpoint:
- `POST /api/events/import?full_news_import=false|true`

## API Surface (High-Level)

Main endpoint groups in [main.py](main.py):
- Health: `/api/health`
- Core entities: `/api/facilities`, `/api/port-links`, `/api/drivers`, `/api/vehicles`, `/api/objectives`
- Routes/events: `/api/routes`, `/api/events/news`, `/api/events/weather`, `/api/events/import`
- Simulation: `/api/simulation/start|pause|resume|reset|status`
- Dashboard/metrics: `/api/dashboard`, `/api/metrics/sdg`
- Recommendations and driver loop: `/api/recommendations`, `/api/driver-decisions`, `/api/driver/{driver_id}/mobile`, `/api/driver/decision`, `/api/driver/incidents`
- Scenarios: `/api/scenarios`, `/api/scenarios/{scenario_key}/trigger`, `/api/scenarios/{scenario_key}/compare`
- Demo scaling: `/api/demo/scale-fleet`
- Realtime stream: `/ws/operations`

## Tests

Backend tests:

```bash
python -m pytest tests/test_simulation.py -q
```

Notes about frontend tests:
- Test files exist in [frontend/tests/](frontend/tests/).
- `frontend/package.json` does not currently define a `test` script or include Vitest dependency.

## Project Layout

- [main.py](main.py): FastAPI app and API routes.
- [services/simulation.py](services/simulation.py): simulation and decision engines.
- [services/route_planner.py](services/route_planner.py): OSRM + fallback route templates.
- [services/event_ingestion.py](services/event_ingestion.py): weather/news workbook import pipeline.
- [seed_data.py](seed_data.py): initial network, fleet, objectives, and scenarios.
- [frontend/src/App.jsx](frontend/src/App.jsx): current main frontend shell.
- [frontend/src/components/views/MapView.jsx](frontend/src/components/views/MapView.jsx): map and route visualization.
