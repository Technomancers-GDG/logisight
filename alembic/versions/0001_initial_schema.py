"""Initial schema — matches models.py at project inception.

Revision ID: 0001
Revises:
Create Date: 2026-01-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "integration_clients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_name", sa.String(length=255), nullable=False),
        sa.Column("contact_email", sa.String(length=255), nullable=False),
        sa.Column("api_key_prefix", sa.String(length=8), nullable=False),
        sa.Column("api_key_hash", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("password_hash", sa.String(length=128), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("firebase_uid", sa.String(length=128), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_name"),
    )
    op.create_table(
        "facilities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("capacity", sa.Float(), nullable=True),
        sa.Column("current_stock", sa.Float(), nullable=True, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("priority_tier", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["integration_clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "nodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "port_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("port_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("transit_days", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["port_id"], ["facilities.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["facilities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "driver_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'idle'")),
        sa.Column("current_vehicle_id", sa.Integer(), nullable=True),
        sa.Column("total_trips", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("rating", sa.Float(), nullable=True, server_default=sa.text("4.5")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["integration_clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("capacity_kg", sa.Float(), nullable=False),
        sa.Column("current_load_kg", sa.Float(), nullable=True, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'idle'")),
        sa.Column("current_facility_id", sa.Integer(), nullable=True),
        sa.Column("driver_id", sa.Integer(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_maintenance_date", sa.DateTime(), nullable=True),
        sa.Column("fuel_efficiency_kmpl", sa.Float(), nullable=True, server_default=sa.text("4.0")),
        sa.Column("co2_per_km_kg", sa.Float(), nullable=True, server_default=sa.text("0.8")),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["current_facility_id"], ["facilities.id"]),
        sa.ForeignKeyConstraint(["driver_id"], ["driver_profiles.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["integration_clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "objectives",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("origin_id", sa.Integer(), nullable=False),
        sa.Column("destination_id", sa.Integer(), nullable=False),
        sa.Column("cargo_kg", sa.Float(), nullable=False),
        sa.Column("deadline", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("priority", sa.Integer(), nullable=True, server_default=sa.text("1")),
        sa.Column("assigned_vehicle_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["assigned_vehicle_id"], ["vehicles.id"]),
        sa.ForeignKeyConstraint(["destination_id"], ["facilities.id"]),
        sa.ForeignKeyConstraint(["origin_id"], ["facilities.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["integration_clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "edges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("base_time_min", sa.Float(), nullable=False),
        sa.Column("mode", sa.String(length=50), nullable=True, server_default=sa.text("'truck'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.ForeignKeyConstraint(["source_id"], ["nodes.id"]),
        sa.ForeignKeyConstraint(["target_id"], ["nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "scenario_presets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "news_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("original_date", sa.DateTime(), nullable=False),
        sa.Column("simulation_date", sa.DateTime(), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("headline", sa.String(length=500), nullable=False),
        sa.Column("relevant", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("impact_type", sa.String(length=100), nullable=True),
        sa.Column("impact_score", sa.Float(), nullable=True),
        sa.Column("model_probability", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "weather_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("original_date", sa.DateTime(), nullable=False),
        sa.Column("simulation_date", sa.DateTime(), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "route_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("origin_id", sa.Integer(), nullable=False),
        sa.Column("destination_id", sa.Integer(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("duration_min", sa.Float(), nullable=True),
        sa.Column("geometry", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["destination_id"], ["nodes.id"]),
        sa.ForeignKeyConstraint(["origin_id"], ["nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "routes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column("origin_id", sa.Integer(), nullable=False),
        sa.Column("destination_id", sa.Integer(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("estimated_duration_min", sa.Float(), nullable=True),
        sa.Column("geometry", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["destination_id"], ["facilities.id"]),
        sa.ForeignKeyConstraint(["origin_id"], ["facilities.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("applied", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "driver_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("driver_id", sa.Integer(), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("decision", sa.String(length=50), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["driver_id"], ["driver_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "driver_incidents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("driver_id", sa.Integer(), nullable=False),
        sa.Column("incident_type", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.Float(), nullable=True),
        sa.Column("reported_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["driver_id"], ["driver_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "driver_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("driver_id", sa.Integer(), nullable=False),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["driver_id"], ["driver_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "sim_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("simulation_tick", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["integration_clients.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("secret", sa.String(length=255), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["integration_clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["integration_clients.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["webhook_subscriptions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "shipments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("objective_id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=True),
        sa.Column("origin_id", sa.Integer(), nullable=False),
        sa.Column("destination_id", sa.Integer(), nullable=False),
        sa.Column("cargo_kg", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("dispatched_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["integration_clients.id"]),
        sa.ForeignKeyConstraint(["destination_id"], ["facilities.id"]),
        sa.ForeignKeyConstraint(["objective_id"], ["objectives.id"]),
        sa.ForeignKeyConstraint(["origin_id"], ["facilities.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("prediction_type", sa.String(length=100), nullable=False),
        sa.Column("predicted_value", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "metrics_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_type", sa.String(length=100), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "client_simulations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("paused_at", sa.DateTime(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["integration_clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("client_simulations")
    op.drop_table("metrics_snapshots")
    op.drop_table("predictions")
    op.drop_table("shipments")
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_subscriptions")
    op.drop_table("sim_events")
    op.drop_table("driver_metrics")
    op.drop_table("driver_incidents")
    op.drop_table("driver_decisions")
    op.drop_table("recommendations")
    op.drop_table("routes")
    op.drop_table("route_templates")
    op.drop_table("weather_events")
    op.drop_table("news_events")
    op.drop_table("scenario_presets")
    op.drop_table("edges")
    op.drop_table("objectives")
    op.drop_table("vehicles")
    op.drop_table("driver_profiles")
    op.drop_table("port_links")
    op.drop_table("nodes")
    op.drop_table("facilities")
    op.drop_table("integration_clients")
