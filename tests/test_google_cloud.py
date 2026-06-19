from __future__ import annotations

import pytest

from services.google_cloud_integration import (
    GoogleCloudIntegration,
    FirebaseRealtimeDB,
    CloudPubSub,
    VertexAIClient,
    BigQueryClient,
    CloudMessaging,
    get_gcp_integration,
)


class TestFirebaseRealtimeDB:
    def test_push_driver_state_buffered(self, monkeypatch):
        monkeypatch.setenv("FIREBASE_ENABLED", "false")
        monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
        from config import load_settings
        monkeypatch.setattr("services.google_cloud_integration.settings", load_settings())

        db = FirebaseRealtimeDB()
        result = db.push_driver_state(1, {"lat": 28.6, "lon": 77.2})
        assert result["status"] == "buffered"
        assert result["driver_id"] == 1
        assert result["buffer_size"] >= 1

    def test_get_driver_state_returns_stub(self):
        db = FirebaseRealtimeDB()
        result = db.get_driver_state(1)
        assert result["driver_id"] == 1
        assert result["status"] == "stub"


class TestCloudPubSub:
    def test_publish_queues_locally_when_disabled(self, monkeypatch):
        monkeypatch.setenv("PUBSUB_ENABLED", "false")
        from config import load_settings
        monkeypatch.setattr("services.google_cloud_integration.settings", load_settings())

        ps = CloudPubSub()
        result = ps.publish("disruptions", {"city": "Chennai", "severity": 0.8})
        assert result["status"] == "queued"
        assert result["queue_depth"] >= 1

    def test_subscribe_returns_stub(self, monkeypatch):
        monkeypatch.setenv("PUBSUB_ENABLED", "false")
        from config import load_settings
        monkeypatch.setattr("services.google_cloud_integration.settings", load_settings())

        ps = CloudPubSub()
        result = ps.subscribe("disruptions", lambda x: x)
        assert result["status"] == "stub"


class TestVertexAIClient:
    def test_predict_returns_stub_when_disabled(self, monkeypatch):
        monkeypatch.setenv("VERTEX_AI_ENABLED", "false")
        from config import load_settings
        monkeypatch.setattr("services.google_cloud_integration.settings", load_settings())

        va = VertexAIClient()
        result = va.predict("endpoint-1", [{"input": "test"}])
        assert result["status"] == "stub"
        assert len(result["predictions"]) == 1

    def test_deploy_model_returns_stub(self, monkeypatch):
        monkeypatch.setattr("services.google_cloud_integration.settings.vertex_ai_enabled", False)

        va = VertexAIClient()
        result = va.deploy_model("reroute-v1", "gs://models/reroute-v1")
        assert result["status"] == "stub_deploy"


class TestBigQueryClient:
    def test_query_metrics_stub(self, monkeypatch):
        monkeypatch.setenv("BIGQUERY_ENABLED", "false")
        from config import load_settings
        monkeypatch.setattr("services.google_cloud_integration.settings", load_settings())

        bq = BigQueryClient()
        result = bq.query_metrics("SELECT * FROM metrics")
        assert result["status"] == "stub"

    def test_stream_metrics_stub(self, monkeypatch):
        monkeypatch.setattr("services.google_cloud_integration.settings.bigquery_enabled", False)

        bq = BigQueryClient()
        result = bq.stream_metrics("driver_metrics", [{"driver_id": 1}])
        assert result["status"] == "stub"


class TestCloudMessaging:
    def test_send_to_driver_stub(self, monkeypatch):
        monkeypatch.setattr("services.google_cloud_integration.settings.fcm_enabled", False)

        fcm = CloudMessaging()
        result = fcm.send_to_driver(1, "Alert", "Disruption detected")
        assert result["status"] == "stub"
        assert result["driver_id"] == 1

    def test_send_to_topic_stub(self, monkeypatch):
        monkeypatch.setattr("services.google_cloud_integration.settings.fcm_enabled", False)

        fcm = CloudMessaging()
        result = fcm.send_to_topic("all_drivers", "Alert", "Test")
        assert result["status"] == "stub"


class TestGoogleCloudIntegration:
    def test_health_check_stub_mode(self, monkeypatch):
        monkeypatch.setenv("FIREBASE_ENABLED", "false")
        monkeypatch.setenv("PUBSUB_ENABLED", "false")
        monkeypatch.setenv("VERTEX_AI_ENABLED", "false")
        monkeypatch.setenv("BIGQUERY_ENABLED", "false")
        monkeypatch.setenv("FCM_ENABLED", "false")
        from config import load_settings
        monkeypatch.setattr("services.google_cloud_integration.settings", load_settings())

        gcp = GoogleCloudIntegration()
        health = gcp.health_check()
        assert health["overall"] == "stub_mode"

    def test_health_check_healthy(self, monkeypatch):
        monkeypatch.setenv("FIREBASE_ENABLED", "true")
        monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
        monkeypatch.setenv("PUBSUB_ENABLED", "false")
        monkeypatch.setenv("VERTEX_AI_ENABLED", "false")
        monkeypatch.setenv("BIGQUERY_ENABLED", "false")
        monkeypatch.setenv("FCM_ENABLED", "false")
        from config import load_settings
        monkeypatch.setattr("services.google_cloud_integration.settings", load_settings())

        gcp = GoogleCloudIntegration()
        health = gcp.health_check()
        assert health["overall"] == "healthy"
        assert health["firebase_rtdb"]["enabled"] is True

    def test_get_gcp_integration_singleton(self, monkeypatch):
        monkeypatch.setattr("services.google_cloud_integration.settings.gcp_project_id", "test")

        inst1 = get_gcp_integration()
        inst2 = get_gcp_integration()
        assert inst1 is inst2
