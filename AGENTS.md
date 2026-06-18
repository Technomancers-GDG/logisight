# AGENTS.md — Resilient Essential Goods Coordinator

## Project structure

- **Root**: FastAPI backend (Python 3.11, SQLAlchemy, SQLite)
- `frontend/`: Admin dashboard — React 18 + Vite (port 5173)
- `driver-app-main/`: Driver mobile app — React 18 + Vite (port 5174)
- `services/`, `routes/`, `schemas/`, `models.py` — backend layers
- `main.py:34-51` — lifespan startup seeds DB + starts simulation if `DEMO_MODE=true`
- `config.py:13-47` — all env vars with defaults (via `python-dotenv`)
- `database.py:54-57` — `init_db()` creates tables; `get_session()` yields `SessionLocal`

## Development commands

```powershell
# Backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn main:app --reload  # http://localhost:8000

# Admin frontend (separate terminal)
cd frontend; npm install --legacy-peer-deps; npm run dev  # http://localhost:5173

# Driver app (separate terminal)
cd driver-app-main; npm install --legacy-peer-deps; npm run dev  # http://localhost:5174
```

Use `start-backend.bat`, `start-admin-frontend.bat`, `start-driver-app.bat` for one-click starts.

## Testing

```powershell
# Backend (all)
python -m pytest tests/ -v

# Backend (single file)
python -m pytest tests/test_simulation.py -v

# Frontend
cd frontend; npm test

# CI runs: backend tests (with coverage) → frontend tests → frontend + driver builds
```

## Vite proxy (both frontends)

`/api` → `https://sim-backend-...run.app` and `/ws` → `wss://sim-backend-...run.app`.
To proxy local backend instead, change `target` in each `vite.config.js` to `http://127.0.0.1:8000`.

## Static serving (production)

FastAPI serves `frontend/dist/` at `/` and `driver-app-main/dist/` at `/driver` when those dirs exist (see `main.py:178-193`). Build with `cd frontend; npm run build` then open `http://localhost:8000`.

## GSD workflow system

Do not touch `get-shit-done/`, `agents/`, `.planning/`, or `.clinerules` unless the user explicitly invokes a `/gsd-*` command. The `.clinerules` file governs those interactions.

## Key quirks

- `npm install` requires `--legacy-peer-deps` (see `build.sh:34,41`)
- Backend auto-seeds facilities, drivers, vehicles, objectives on startup when `ALLOW_DEMO_SEED=true` and DB is empty
- Session-based DB access via `get_session()` generator (no `Depends` pattern)
- Route modules registered in `main.py:88-93` — crud, simulation, driver, ai, logistics, rl
- `render.yaml` and `Dockerfile` define the deployed runtime; `build.sh` is the CI/CD pipeline
