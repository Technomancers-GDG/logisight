# Resilient Essential Goods Coordinator

![Python](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![React](https://img.shields.io/badge/React-18-61DAFB)
![License](https://img.shields.io/badge/license-MIT-green)
[![CI](https://github.com/Technomancers-GDG/logisight/actions/workflows/ci.yml/badge.svg)](https://github.com/Technomancers-GDG/logisight/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Technomancers-GDG/logisight/branch/main/graph/badge.svg)](https://codecov.io/gh/Technomancers-GDG/logisight)
![Google Cloud Run](https://img.shields.io/badge/GCP-Cloud_Run-4285F4)
![Deployed](https://img.shields.io/badge/status-deployed-success)

FastAPI + React application for disruption-aware essential-goods logistics simulation across India.

**Live demo:** [https://logisight.app](https://logisight.app) | **API docs:** [https://logisight.app/docs](https://logisight.app/docs)

---

## 🏆 Hackathon Submission — Round 2

Disruption-aware logistics coordination platform featuring AI/ML decision engines, real-time simulation, driver mobile loop, and Google Cloud integration.

**One-liner pitch:** *"A disruption-aware logistics brain for India. We simulate real supply chains, ingest weather/news data, and use an AI decision engine to reroute vehicles before stockouts happen — all visible on a live map with a driver mobile loop."*

---

## Why This Matters for India

India loses **4–8% of cereals and 5–15% of fruits & vegetables** between harvest and the consumer (NABCONS, 2022 study commissioned by the Ministry of Food Processing Industries). The FSSAI reports that **1/3 of all food produced in India spoils before it is eaten** — amounting to **~78.2 million tonnes** of food waste annually (UNEP Food Waste Index, 2024). That quantity could feed **377 million people**.

The primary cause is **supply chain disruption** — not scarcity. Inefficient routing, weather-related road closures (cyclones, monsoon flooding, fog), and lack of real-time rerouting lead to inventory piling up at origin facilities while destination warehouses stock out. The problem is accelerating: India experiences **5–6 cyclonic storms annually**, extreme weather events are increasing in frequency, and the logistics cold-chain market relies on temperature-sensitive transport that cannot tolerate delays.

**Logisight addresses this at the operational decision layer.** Rather than building new infrastructure, it optimises the existing fleet — detecting disruptions early, rerouting vehicles before stockouts occur, and providing a live operations dashboard + driver mobile loop for ground-level execution. The result: fewer stockouts, less spoilage, lower CO₂ emissions from empty return trips, and a logistics system that adapts in minutes, not days.

---

## ✨ Current Feature Set (Verified)

- **Network management:** facilities, ports, port links, vehicles, drivers, and objectives
- **Simulation controls:** start, pause, resume, reset, and speed multiplier (up to 5000x)
- **AI Decision Engine:** dispatch scoring, RL-based rerouting (DQN with PyTorch), NSGA-II multi-objective optimization
- **RL agent convergence:** DQN trained offline (500 epochs, loss 0.25 → 0.25, epsilon 0.15 → 0.05) — see [`docs/rl_training_curve.png`](docs/rl_training_curve.png)
- **Route planning:** OSRM first, automatic estimated-route fallback when OSRM is unavailable
- **Disruption management:** weather/news ingestion from workbooks + manual driver incident injection + auto-demo disruption
- **Scenario comparison:** baseline vs AI-optimized with trigger presets
- **Driver mobile loop:** pending instructions, accept/ignore decisions, incident reporting, AI chat assistant
- **SDG-style metrics:** stockouts prevented, critical deliveries saved, CO2 reduction
- **Real-time WebSocket stream** at `/ws/operations`
- **Multi-tenant architecture:** isolated simulation engines per client
- **Cryptographic audit trail:** tamper-evident SHA-256 hash-chain ledger
- **Bilingual UI:** English + Hindi (i18n)
- **PWA support** with offline caching

---

## 🚀 Deployment

| Endpoint | URL | Platform |
|---|---|---|
| **Admin Dashboard** | [https://logisight.app](https://logisight.app) | Cloud Run + Firebase Hosting |
| **API & WebSocket** | [https://api.logisight.app](https://api.logisight.app) | Google Cloud Run |
| **Driver Mobile App** | [https://driver.logisight.app](https://driver.logisight.app) | Firebase Hosting |
| **Swagger Docs** | [https://logisight.app/docs](https://logisight.app/docs) | Cloud Run |

<img src="images/dashboard-preview.png" alt="Logisight Dashboard Preview" width="800"/>

---

## 🧠 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Admin Dashboard (React/Vite)              │
│  Map · Live Ops · Scenarios · Events · Impact · Analytics    │
└─────────────────────────┬────────────────────────────────── ┘
                          │ HTTP / WS
┌─────────────────────────▼──────────────────────────────────┐
│                   FastAPI Backend (Python 3.11)              │
│  ┌─────────────┐ ┌──────────┐ ┌────────────────────────┐   │
│  │Simulation   │ │AI/ML     │ │Google Cloud Integration │   │
│  │Engine       │ │Engine    │ │Firebase · Pub/Sub       │   │
│  │(1905 lines) │ │DQN RL    │ │Vertex AI · BigQuery     │   │
│  │             │ │NSGA-II   │ │Cloud Messaging · CloudSQL│   │
│  └─────────────┘ └──────────┘ └────────────────────────┘   │
│  ┌─────────────┐ ┌──────────┐ ┌────────────────────────┐   │
 │  │Route Planner│ │Event     │ │Cryptographic Audit     │   │
 │  │OSRM + Fallb.│ │Ingestion │ │SHA-256 Hash-chain      │   │
│  └─────────────┘ └──────────┘ └────────────────────────┘   │
└─────────────────────────┬──────────────────────────────────┘
                          │ HTTP / WS
┌─────────────────────────▼──────────────────────────────────┐
│                  Driver Mobile App (React/PWA)               │
│  Instructions · Incident Report · AI Chat · Real-time Map    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11+, FastAPI 0.115, Uvicorn |
| **Database** | PostgreSQL (prod) / SQLite (dev), SQLAlchemy 2.0, Alembic |
| **Frontend** | React 18, Vite 6, React Router 7, Leaflet, Recharts, Framer Motion |
| **AI/ML** | PyTorch (DQN RL), scikit-learn, Google Gemini, Groq (LLM) |
| **Infrastructure** | Docker, Google Cloud Run, Firebase Hosting, Cloud SQL, Pub/Sub, Vertex AI, BigQuery |
| **Real-time** | WebSocket (FastAPI native) |
| **Mobile** | Driver PWA (React + Vite) |
| **i18n** | English, Hindi |

---

## 📊 Tests & CI

| Category | Status | Coverage |
|---|---|---|
| **Backend pytest** | ✅ 7 test suites | 20%+ target |
| **Frontend Vitest** | ✅ 3 test suites (formatters, validators, dashboard utils) | 30+ unit tests |
| **Driver App Vitest** | ✅ Real unit tests | Added |
| **CI Pipeline** | ✅ GitHub Actions (lint → test → build → Docker) | [View runs](https://github.com/Technomancers-GDG/logisight/actions) |
| **Code Coverage** | ✅ pytest-cov with `.coveragerc` | [View on Codecov](https://codecov.io/gh/Technomancers-GDG/logisight) |

```bash
# Run all backend tests
python -m pytest tests/ -v --cov=. --cov-report=term

# Run frontend tests
cd frontend && npx vitest run

# Run driver app tests
cd driver-app-main && npx vitest run
```

---

## 🗺️ Database Migrations

Migrations managed via **Alembic** (replaces legacy auto-ALTER TABLE):

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

The initial migration (`0001_initial_schema.py`) captures the full schema at project inception. All new columns should be added via Alembic revisions.

---

## 🏁 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL (optional, SQLite used by default)

### Backend

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev       # → http://localhost:5173
```

### Driver App

```bash
cd driver-app-main
npm install
npm run dev       # → http://localhost:5174
```

### Docker (Full Stack)

```bash
docker build -t logisight .
docker run -p 8000:8000 logisight
```

---

## ⚙️ Configuration

Key environment variables — see `config.py` for the full list.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/supply_chain` | Production database |
| `GCP_PROJECT_ID` | `logisight-prod` | Google Cloud project |
| `GCP_REGION` | `asia-south1` | GCP region (Mumbai) |
| `GEMINI_API_KEY` | — | Google Gemini for AI chat |
| `GROQ_API_KEY` | — | Groq fallback for AI chat |
| `FIREBASE_ENABLED` | `true` | Firebase Realtime DB + Auth |
| `PUBSUB_ENABLED` | `true` | Cloud Pub/Sub event streaming |
| `VERTEX_AI_ENABLED` | `true` | Vertex AI model hosting |
| `BIGQUERY_ENABLED` | `true` | BigQuery analytics |
| `FCM_ENABLED` | `true` | Firebase Cloud Messaging |
| `SIMULATION_SPEED` | `5000.0` | Default speed multiplier |
| `DEMO_MODE` | `true` | Auto-start + auto-disruptions |

---

## 📐 Project Layout

```
logisight/
├── main.py                        # FastAPI entry point
├── config.py                      # Settings with env validation
├── database.py                    # SQLAlchemy + Alembic migrations
├── models.py                      # ORM models (20+ tables)
├── requirements.txt               # Python dependencies
├── alembic.ini / alembic/         # Database migrations
├── .github/workflows/ci.yml       # CI/CD pipeline
├── .coveragerc                    # Code coverage config
├── firebase-service-account.json.template  # GCP credentials template
├── gcp_config.yaml.template       # GCP configuration template
├── Dockerfile                     # Multi-stage Docker build
├── render.yaml                    # Render Blueprint config
├── routes/                        # API route modules (12 files)
├── services/                      # Business logic services (25 modules)
│   ├── simulation/engine.py       # Core simulation engine (1905 lines)
│   ├── rl_decision_engine.py      # DQN-based RL agent
│   ├── multi_objective_optimizer.py  # NSGA-II optimizer
│   ├── blockchain_audit.py        # Tamper-evident SHA-256 hash-chain audit ledger
│   ├── google_cloud_integration.py  # GCP services (Firebase, Pub/Sub, Vertex AI, BigQuery, FCM)
│   └── ...
├── schemas/                       # Pydantic schemas (17 files)
├── middleware/                     # Auth middleware (API key, Firebase)
├── frontend/                      # Admin dashboard (React + Vite)
│   ├── src/components/views/      # 23 view components
│   └── src/i18n/                  # Bilingual translations
├── driver-app-main/               # Driver mobile app (React + Vite)
└── tests/                         # Backend tests (pytest)
```

---

## 📖 Documentation

- [Demo Script](./DEMO_GUIDE.md) — 5-7 minute walkthrough for judges
- [Deployment Guide](./DEPLOYMENT_GUIDE.md) — Nginx, Docker, Render + cron-job.org
- [GCP Free Tier Deploy](./DEPLOY_GCP_FREE.md) — Cloud Run + Firebase Hosting
- [Driver App Setup](./DRIVER_APP_SETUP.md) — Architecture and data flow
- [Frontend Quick Start](./FRONTEND_QUICK_START.md) — Development reference
