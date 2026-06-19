from __future__ import annotations

import os
from datetime import date

import pytest

from config import load_settings, Settings


class TestSettings:
    def test_default_settings_loaded(self):
        s = load_settings()
        assert isinstance(s, Settings)
        assert s.app_name == "Resilient Essential Goods Coordinator"
        assert s.simulation_speed > 0
        assert s.gcp_region == "asia-south1"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("APP_NAME", "Test App")
        monkeypatch.setenv("SIMULATION_SPEED", "100")
        monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
        s = load_settings()
        assert s.app_name == "Test App"
        assert s.simulation_speed == 100.0
        assert s.gcp_project_id == "test-project"

    def test_bool_env_parsing(self, monkeypatch):
        for true_val in ("1", "true", "True", "yes", "YES"):
            monkeypatch.setenv("DEMO_MODE", true_val)
            assert load_settings().demo_mode is True

        for false_val in ("0", "false", "no", ""):
            monkeypatch.setenv("DEMO_MODE", false_val)
            assert load_settings().demo_mode is False

    def test_groq_models_default(self, monkeypatch):
        monkeypatch.delenv("GROQ_MODELS", raising=False)
        s = load_settings()
        assert len(s.groq_models) >= 3
        assert "llama-3.3-70b-versatile" in s.groq_models

    def test_groq_models_override(self, monkeypatch):
        monkeypatch.setenv("GROQ_MODELS", "model-a,model-b")
        s = load_settings()
        assert s.groq_models == ["model-a", "model-b"]

    def test_simulation_start_date(self):
        s = load_settings()
        assert isinstance(s.simulation_start_date, date)

    def test_jwt_secret_auto_generated(self):
        s1 = load_settings()
        s2 = load_settings()
        assert s1.jwt_secret_key != ""
        # Different calls should generate different keys (token_hex)
        assert s1.jwt_secret_key != s2.jwt_secret_key


class TestSettingsDefaults:
    """Verify defaults match expected production-safe values."""

    def test_default_database_is_postgres(self):
        s = load_settings()
        assert s.database_url.startswith("postgresql")

    def test_default_region_is_india(self):
        s = load_settings()
        assert s.gcp_region == "asia-south1"

    def test_default_ai_models_loaded(self):
        s = load_settings()
        assert len(s.groq_models) > 0

    def test_rl_and_nsga2_enabled_by_default(self):
        s = load_settings()
        assert s.use_rl_engine is True
        assert s.use_nsga2_optimizer is True

    def test_demo_disruption_defaults(self):
        s = load_settings()
        assert s.demo_disruption_city == "Chennai"
        assert 0 < s.demo_disruption_severity <= 1
        assert s.demo_disruption_delay_seconds >= 1


class TestSettingsValidation:
    def test_config_loads_without_crash(self):
        s = load_settings()
        assert s is not None

    def test_empty_gcp_project_id_is_handled(self, monkeypatch):
        monkeypatch.setenv("GCP_PROJECT_ID", "")
        s = load_settings()
        assert s.gcp_project_id == ""
        assert s.firebase_enabled is False

    def test_firebase_enabled_no_project_id(self, monkeypatch):
        monkeypatch.setenv("FIREBASE_ENABLED", "true")
        monkeypatch.setenv("GCP_PROJECT_ID", "")
        s = load_settings()
        assert s.firebase_enabled is True
        assert s.gcp_project_id == ""
