# Driver App Setup Guide

## Overview

The **Driver App** is a separate React + Vite application that runs alongside the main admin dashboard. It provides a mobile-friendly interface for drivers to:

- Review rerouting requests
- Respond to instructions
- Report incidents on the road

## Architecture

| Service            | Port | Description                      |
|--------------------|------|----------------------------------|
| Backend API        | 8000 | FastAPI server (main backend)    |
| Admin Dashboard    | 5173 | Main frontend (Vite + React)     |
| Driver App         | 5174 | Driver mobile app (Vite + React) |

The Driver App proxies all `/api/*` and `/ws/*` requests to the backend server running on `localhost:8000` via Vite's dev server proxy.

## Prerequisites

- **Node.js** (v18+ recommended) with npm
- **Python** 3.10+ with the backend dependencies installed
- Backend dependencies: `pip install -r requirements.txt`

## Quick Start

### Option 1: Run Everything from One Terminal

1. **Start the Backend** (in one terminal):
   ```bat
   start-backend.bat
   ```

2. **Start the Driver App** (in a second terminal):
   ```bat
   start-driver-app.bat
   ```

3. **(Optional) Start the Admin Dashboard** (in a third terminal):
   ```bat
   start-admin-frontend.bat
   ```

### Option 2: Manual Commands

**Backend:**
```bat
cd "modern ui"
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

**Driver App:**
```bat
cd "modern ui\driver-app-main"
npm run dev
```

**Admin Frontend:**
```bat
cd "modern ui\frontend"
npm run dev
```

## Environment Variables

The Driver App uses `.env` variables (defined in `driver-app-main/.env`):

| Variable                 | Default               | Description                                |
|--------------------------|-----------------------|--------------------------------------------|
| `VITE_API_BASE_URL`      | *(empty)*             | Leave empty to use Vite proxy              |
| `VITE_WS_BASE_URL`       | `ws://localhost:8000` | WebSocket base URL                         |
| `VITE_POLLING_INTERVAL_MS`| `12000`              | How often to refresh driver data (ms)      |

> **Note:** `VITE_API_BASE_URL` is intentionally left empty so the Vite dev server proxy handles `/api` → `http://localhost:8000` automatically. This avoids CORS issues during development.

## API Endpoints Used

The Driver App calls these backend endpoints:

- `GET /api/drivers` — List all drivers
- `GET /api/vehicles` — List all vehicles
- `GET /api/recommendations` — List recommendations
- `GET /api/facilities` — List facilities
- `GET /api/driver/{id}/mobile` — Get driver mobile snapshot (pending instructions, recent incidents)
- `POST /api/driver/decision` — Submit accept/reject decision
- `POST /api/driver/incidents` — Report a new incident

## Data Flow

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Driver App     │      │  Vite Dev Server│      │  FastAPI        │
│  (localhost:5174)│◄────►│  (port 5174)    │◊────►│  (localhost:8000)│
│                 │      │  Proxy /api/*   │      │                 │
└─────────────────┘      └─────────────────┘      └─────────────────┘
                                │
                                │  Admin Dashboard
                                ▼
                         ┌─────────────────┐
                         │  localhost:5173 │
                         └─────────────────┘
```

## Troubleshooting

### Driver app won't start
- Make sure you ran `npm install` in the `driver-app-main` folder
- Check that port 5174 is not already in use

### "Failed to fetch" / API errors
- Ensure the backend is running on `localhost:8000`
- Check the backend health endpoint: `http://localhost:8000/api/health`
- Verify the proxy is working by checking the Vite dev server logs

### Backend won't start
- Make sure Python dependencies are installed: `pip install -r requirements.txt`
- Check that port 8000 is not already in use
- The backend uses SQLite (`supply_chain.db`) which is created automatically on first run

## File Structure

```
driver-app-main/
├── .env              ← Environment config (already set up)
├── index.html        ← Entry HTML
├── package.json      ← Dependencies (React + Vite)
├── vite.config.js    ← Dev server config (port 5174 + proxy)
└── src/
    ├── main.jsx      ← React root
    ├── App.jsx       ← Main app component
    ├── styles.css    ← App styles
    └── components/
        └── common/
            └── UiPrimitives.jsx  ← Reusable UI components
```

## Next Steps

1. Start the backend: `start-backend.bat`
2. Start the driver app: `start-driver-app.bat`
3. Open `http://localhost:5174` in your browser
4. Select a driver to see their dashboard, pending instructions, and incident reporting form
