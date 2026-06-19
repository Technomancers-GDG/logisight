from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str
    database_url: str
    osrm_base_url: str
    simulation_start_date: date
    simulation_speed: float
    news_dataset_path: Path
    weather_dataset_path: Path
    allow_demo_seed: bool
    demo_mode: bool
    route_use_osrm: bool
    route_use_osmnx: bool
    osmnx_graph_path: str
    osmnx_graphs_dir: str
    news_model_artifact_path: Path
    demo_disruption_delay_seconds: int
    demo_disruption_city: str
    demo_disruption_severity: float
    # JWT
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_expiry_hours: int
    # RL & Optimization
    rl_model_path: str
    use_rl_engine: bool
    use_nsga2_optimizer: bool
    # Cryptographic Audit (SHA-256 hash-chain ledger)
    blockchain_ledger_path: str
    # Google Cloud
    gcp_project_id: str
    gcp_region: str
    firebase_enabled: bool
    pubsub_enabled: bool
    vertex_ai_enabled: bool
    bigquery_enabled: bool
    bigquery_dataset: str
    fcm_enabled: bool
    cost_point_to_inr: float
    # Gemini
    gemini_api_key: str
    # Groq (fallback)
    groq_api_key: str
    groq_models: list[str]
    # Redis (horizontal WebSocket scaling)
    use_redis: bool
    redis_url: str
    # Rate limiting
    ai_rate_limit_per_min: int


def _get_env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _get_bool_env(name: str, default: str) -> bool:
    return _get_env(name, default).lower() in {"1", "true", "yes"}


def _validate_settings(s: Settings) -> None:
    import logging
    logger = logging.getLogger(__name__)
    warnings: list[str] = []
    if not s.gemini_api_key and not s.groq_api_key:
        warnings.append("GEMINI_API_KEY and GROQ_API_KEY are both empty — AI chat will fall back to rule-based responses")
    if s.database_url.startswith("sqlite") and s.demo_mode is False:
        warnings.append("Using SQLite in non-demo mode — consider PostgreSQL for production")
    if not s.gcp_project_id:
        warnings.append("GCP_PROJECT_ID is not set — Google Cloud integrations will run in stub mode")
    if s.firebase_enabled and not s.gcp_project_id:
        warnings.append("FIREBASE_ENABLED=true but GCP_PROJECT_ID is empty")
    if s.vertex_ai_enabled and not s.gcp_project_id:
        warnings.append("VERTEX_AI_ENABLED=true but GCP_PROJECT_ID is empty")
    for w in warnings:
        logger.warning("Config: %s", w)


def load_settings() -> Settings:
    import secrets as _secrets
    s = Settings(
        app_name=_get_env("APP_NAME", "Resilient Essential Goods Coordinator"),
        database_url=_get_env("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/supply_chain"),
        osrm_base_url=_get_env("OSRM_BASE_URL", "https://router.project-osrm.org"),
        simulation_start_date=date.fromisoformat(
            _get_env("SIMULATION_START_DATE", "2026-01-01")
        ),
        simulation_speed=float(_get_env("SIMULATION_SPEED", "5000.0")),
        news_dataset_path=Path(_get_env("NEWS_DATASET_PATH", "All_Cities_News_v2.xlsx")),
        weather_dataset_path=Path(
            _get_env("WEATHER_DATASET_PATH", "Historical_Weather_Data_2024_2026.xlsx")
        ),
        allow_demo_seed=_get_bool_env("ALLOW_DEMO_SEED", "true"),
        demo_mode=_get_bool_env("DEMO_MODE", "true"),
        route_use_osrm=_get_bool_env("ROUTE_USE_OSRM", "true"),
        route_use_osmnx=_get_bool_env("ROUTE_USE_OSMNX", "false"),
        osmnx_graph_path=_get_env("OSMNX_GRAPH_PATH", "data/osmnx_graph.graphml"),
        osmnx_graphs_dir=_get_env("OSMNX_GRAPHS_DIR", "data/osmnx_graphs"),
        news_model_artifact_path=Path(_get_env("NEWS_MODEL_ARTIFACT_PATH", "news_model.pkl")),
        demo_disruption_delay_seconds=int(_get_env("DEMO_DISRUPTION_DELAY_SECONDS", "4")),
        demo_disruption_city=_get_env("DEMO_DISRUPTION_CITY", "Chennai"),
        demo_disruption_severity=float(_get_env("DEMO_DISRUPTION_SEVERITY", "0.82")),
        # JWT
        jwt_secret_key=_get_env("JWT_SECRET_KEY", _secrets.token_hex(32)),
        jwt_algorithm=_get_env("JWT_ALGORITHM", "HS256"),
        jwt_expiry_hours=int(_get_env("JWT_EXPIRY_HOURS", "24")),
        # RL & Optimization
        rl_model_path=_get_env("RL_MODEL_PATH", "data/rl_model.json"),
        use_rl_engine=_get_bool_env("USE_RL_ENGINE", "true"),
        use_nsga2_optimizer=_get_bool_env("USE_NSGA2_OPTIMIZER", "true"),
        # Cryptographic Audit trail
        blockchain_ledger_path=_get_env("BLOCKCHAIN_LEDGER_PATH", "data/blockchain_ledger.json"),
        # Google Cloud
        gcp_project_id=_get_env("GCP_PROJECT_ID", ""),
        gcp_region=_get_env("GCP_REGION", "asia-south1"),
        firebase_enabled=_get_bool_env("FIREBASE_ENABLED", "false"),
        pubsub_enabled=_get_bool_env("PUBSUB_ENABLED", "false"),
        vertex_ai_enabled=_get_bool_env("VERTEX_AI_ENABLED", "false"),
        bigquery_enabled=_get_bool_env("BIGQUERY_ENABLED", "false"),
        bigquery_dataset=_get_env("BIGQUERY_DATASET", "supply_chain"),
        fcm_enabled=_get_bool_env("FCM_ENABLED", "false"),
        # Financial calibration: 1 cost point = ₹15 INR (based on ~₹45/km Indian truck ops)
        cost_point_to_inr=float(_get_env("COST_POINT_TO_INR", "15.0")),
        # Gemini
        gemini_api_key=_get_env("GEMINI_API_KEY", ""),
        # Groq (fallback)
        groq_api_key=_get_env("GROQ_API_KEY", ""),
        groq_models=_get_env("GROQ_MODELS", "").split(",") if _get_env("GROQ_MODELS", "") else [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
            "llama-3.2-3b-preview",
        ],
        use_redis=_get_bool_env("USE_REDIS", "false"),
        redis_url=_get_env("REDIS_URL", ""),
        ai_rate_limit_per_min=int(_get_env("AI_RATE_LIMIT_PER_MIN", "10")),
    )
    _validate_settings(s)
    return s


settings = load_settings()

# Explicit demo flag for fast, deterministic startup
DEMO_MODE = settings.demo_mode
