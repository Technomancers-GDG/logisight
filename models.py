from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Facility(Base):
    __tablename__ = "facilities"
    __table_args__ = (
        UniqueConstraint("name", "client_id", name="uq_facility_name_per_client"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    client_id: Mapped[Optional[int]] = mapped_column(ForeignKey("integration_clients.id"), nullable=True, index=True)
    city: Mapped[str] = mapped_column(String(80), index=True)
    facility_type: Mapped[str] = mapped_column(String(40), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    base_capacity_units: Mapped[int] = mapped_column(Integer)
    current_inventory_units: Mapped[int] = mapped_column(Integer, default=0)
    initial_inventory_units: Mapped[int] = mapped_column(Integer, default=0)
    queue_capacity_units: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )


class PortLink(Base):
    __tablename__ = "port_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    port_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    reserved_capacity_units: Mapped[int] = mapped_column(Integer, default=0)
    spillover_threshold_pct: Mapped[float] = mapped_column(Float, default=80.0)
    max_spillover_units: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    warehouse: Mapped[Facility] = relationship(
        "Facility", foreign_keys=[warehouse_id], lazy="joined"
    )
    port: Mapped[Facility] = relationship("Facility", foreign_keys=[port_id], lazy="joined")


class DriverProfile(Base):
    __tablename__ = "driver_profiles"
    __table_args__ = (
        UniqueConstraint("name", "client_id", name="uq_driver_name_per_client"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    client_id: Mapped[Optional[int]] = mapped_column(ForeignKey("integration_clients.id"), nullable=True, index=True)
    override_rating: Mapped[float] = mapped_column(Float, default=1.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    accept_recommendation_bias: Mapped[float] = mapped_column(Float, default=0.5)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint("identifier", "client_id", name="uq_vehicle_identifier_per_client"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identifier: Mapped[str] = mapped_column(String(80), index=True)
    client_id: Mapped[Optional[int]] = mapped_column(ForeignKey("integration_clients.id"), nullable=True, index=True)
    vehicle_type: Mapped[str] = mapped_column(String(40), default="truck")
    payload_capacity_units: Mapped[int] = mapped_column(Integer)
    home_facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    current_facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=True
    )
    driver_profile_id: Mapped[int] = mapped_column(ForeignKey("driver_profiles.id"))
    default_objective_id: Mapped[int] = mapped_column(
        ForeignKey("objectives.id"), nullable=True
    )
    average_speed_kmph: Mapped[float] = mapped_column(Float, default=48.0)
    emission_kg_per_km: Mapped[float] = mapped_column(Float, default=1.6)
    rest_every_hours: Mapped[float] = mapped_column(Float, default=8.0)
    rest_duration_minutes: Mapped[int] = mapped_column(Integer, default=45)
    status: Mapped[str] = mapped_column(String(40), default="idle")
    available_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )

    home_facility: Mapped[Facility] = relationship("Facility", foreign_keys=[home_facility_id])
    current_facility: Mapped[Facility] = relationship("Facility", foreign_keys=[current_facility_id])
    driver_profile: Mapped[DriverProfile] = relationship("DriverProfile", lazy="joined")
    dynamic_state: Mapped[Optional[VehicleDynamicState]] = relationship(
        "VehicleDynamicState", back_populates="vehicle", uselist=False, cascade="all, delete-orphan"
    )


class VehicleDynamicState(Base):
    """Dynamic runtime state of a vehicle, separated from static configuration.

    This table receives writes during simulation ticks (status, lat/lng,
    available_at) while the parent ``vehicles`` table keeps static info
    (identifier, capacity, driver, etc.).  The split lets the static schema
    remain stable while the dynamic rows can be rotated, archived, or
    replicated at high frequency without schema locks.
    """

    __tablename__ = "vehicle_dynamic_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(40), default="idle")
    current_facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=True
    )
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    available_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )

    vehicle: Mapped[Vehicle] = relationship("Vehicle", back_populates="dynamic_state")


class Objective(Base):
    __tablename__ = "objectives"
    __table_args__ = (
        UniqueConstraint("name", "client_id", name="uq_objective_name_per_client"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    client_id: Mapped[Optional[int]] = mapped_column(ForeignKey("integration_clients.id"), nullable=True, index=True)
    commodity: Mapped[str] = mapped_column(String(80))
    origin_facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    destination_facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    dispatch_interval_minutes: Mapped[int] = mapped_column(Integer, default=120)
    loading_duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    unloading_duration_minutes: Mapped[int] = mapped_column(Integer, default=35)
    sla_minutes: Mapped[int] = mapped_column(Integer, default=720)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    assigned_vehicle_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    fallback_facility_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )

    origin_facility: Mapped[Facility] = relationship(
        "Facility", foreign_keys=[origin_facility_id], lazy="joined"
    )
    destination_facility: Mapped[Facility] = relationship(
        "Facility", foreign_keys=[destination_facility_id], lazy="joined"
    )


class RouteTemplate(Base):
    __tablename__ = "route_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    route_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    origin_facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    destination_facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    distance_km: Mapped[float] = mapped_column(Float)
    duration_minutes: Mapped[float] = mapped_column(Float)
    encoded_polyline: Mapped[str] = mapped_column(Text, default="")
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(40), default="estimated")
    refreshed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class ScenarioPreset(Base):
    __tablename__ = "scenario_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(140), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    event_city: Mapped[str] = mapped_column(String(80), index=True)
    event_type: Mapped[str] = mapped_column(String(80), default="disruption")
    severity: Mapped[float] = mapped_column(Float, default=0.6)
    eta_multiplier: Mapped[float] = mapped_column(Float, default=1.2)
    inventory_pressure_pct: Mapped[float] = mapped_column(Float, default=12.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class NewsEvent(Base):
    __tablename__ = "news_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_date: Mapped[Date] = mapped_column(Date, index=True)
    simulation_date: Mapped[Date] = mapped_column(Date, index=True)
    city: Mapped[str] = mapped_column(String(80), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    headline: Mapped[str] = mapped_column(Text)
    relevant: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    impact_type: Mapped[str] = mapped_column(String(80), default="none")
    impact_score: Mapped[float] = mapped_column(Float, default=0.0)
    model_probability: Mapped[float] = mapped_column(Float, default=0.0)


class WeatherEvent(Base):
    __tablename__ = "weather_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_date: Mapped[Date] = mapped_column(Date, index=True)
    simulation_date: Mapped[Date] = mapped_column(Date, index=True)
    city: Mapped[str] = mapped_column(String(80), index=True)
    max_temp_c: Mapped[float] = mapped_column(Float)
    min_temp_c: Mapped[float] = mapped_column(Float)
    precipitation_mm: Mapped[float] = mapped_column(Float, default=0.0)
    closure_risk: Mapped[float] = mapped_column(Float, default=0.0)
    eta_multiplier: Mapped[float] = mapped_column(Float, default=1.0)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)
    simulation_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    objective_id: Mapped[int] = mapped_column(ForeignKey("objectives.id"), index=True)
    current_facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=True
    )
    original_destination_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    recommended_destination_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80), index=True)
    explanation: Mapped[str] = mapped_column(Text)
    structured_explanation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    counterfactual: Mapped[str] = mapped_column(Text, default="")
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    baseline_cost: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_cost: Mapped[float] = mapped_column(Float, default=0.0)
    financial_impact_usd: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(40), default="suggested")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)


class DriverDecision(Base):
    __tablename__ = "driver_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendations.id"))
    driver_profile_id: Mapped[int] = mapped_column(ForeignKey("driver_profiles.id"))
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    decision: Mapped[str] = mapped_column(String(40), index=True)
    actual_trip_cost: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_trip_cost: Mapped[float] = mapped_column(Float, default=0.0)
    rating_delta: Mapped[float] = mapped_column(Float, default=0.0)
    note: Mapped[str] = mapped_column(Text, default="")


class DriverIncident(Base):
    __tablename__ = "driver_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reported_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)
    driver_profile_id: Mapped[int] = mapped_column(ForeignKey("driver_profiles.id"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=True, index=True)
    city: Mapped[str] = mapped_column(String(80), index=True)
    incident_type: Mapped[str] = mapped_column(String(80), index=True)
    severity: Mapped[float] = mapped_column(Float, default=0.6)
    note: Mapped[str] = mapped_column(Text, default="")
    linked_news_event_id: Mapped[int] = mapped_column(ForeignKey("news_events.id"), nullable=True)


class DriverMetric(Base):
    __tablename__ = "driver_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("driver_profiles.id"), unique=True, index=True)
    efficiency_score: Mapped[float] = mapped_column(Float, default=0.75)
    reliability_score: Mapped[float] = mapped_column(Float, default=0.75, index=True)
    route_adherence_score: Mapped[float] = mapped_column(Float, default=0.75)
    idle_time_score: Mapped[float] = mapped_column(Float, default=0.75)
    risk_score: Mapped[float] = mapped_column(Float, default=0.25)
    classification_label: Mapped[str] = mapped_column(String(20), default="medium", index=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    scoring_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )


class SimEvent(Base):
    __tablename__ = "sim_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scheduled_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    processed_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    objective_id: Mapped[int] = mapped_column(ForeignKey("objectives.id"), nullable=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), nullable=True)
    client_id: Mapped[Optional[int]] = mapped_column(ForeignKey("integration_clients.id"), nullable=True, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class MetricsSnapshot(Base):
    __tablename__ = "metrics_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)
    co2_saved_kg: Mapped[float] = mapped_column(Float, default=0.0)
    idle_minutes_prevented: Mapped[float] = mapped_column(Float, default=0.0)
    on_time_delivery_pct: Mapped[float] = mapped_column(Float, default=100.0)
    warehouse_utilization_pct: Mapped[float] = mapped_column(Float, default=0.0)
    reroute_count: Mapped[int] = mapped_column(Integer, default=0)
    active_trucks: Mapped[int] = mapped_column(Integer, default=0)
    queued_trucks: Mapped[int] = mapped_column(Integer, default=0)
    financial_costs_saved_usd: Mapped[float] = mapped_column(Float, default=0.0)
    financial_costs_incurred_usd: Mapped[float] = mapped_column(Float, default=0.0)


class LogisticsNode(Base):
    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    node_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    node_type: Mapped[str] = mapped_column(String(40), index=True)
    city: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    capacity_units: Mapped[int] = mapped_column(Integer, nullable=True)
    node_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )


class LogisticsEdge(Base):
    __tablename__ = "edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    edge_key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    from_node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"), index=True)
    to_node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"), index=True)
    transport_mode: Mapped[str] = mapped_column(String(30), index=True)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    time_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    risk: Mapped[float] = mapped_column(Float, default=0.0)
    distance_km: Mapped[float] = mapped_column(Float, nullable=True)
    capacity_units: Mapped[int] = mapped_column(Integer, nullable=True)
    bidirectional: Mapped[bool] = mapped_column(Boolean, default=True)
    constraints: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    edge_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )

    from_node: Mapped[LogisticsNode] = relationship("LogisticsNode", foreign_keys=[from_node_id], lazy="joined")
    to_node: Mapped[LogisticsNode] = relationship("LogisticsNode", foreign_keys=[to_node_id], lazy="joined")


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    shipment_reference: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    client_id: Mapped[Optional[int]] = mapped_column(ForeignKey("integration_clients.id"), nullable=True, index=True)
    origin_node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"), nullable=True, index=True)
    destination_node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"), nullable=True, index=True)
    origin_node_key: Mapped[str] = mapped_column(String(120), index=True)
    destination_node_key: Mapped[str] = mapped_column(String(120), index=True)
    current_location_node_key: Mapped[str] = mapped_column(String(120), nullable=True, index=True)
    cargo_type: Mapped[str] = mapped_column(String(100), default="general")
    quantity_units: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="created", index=True)
    assigned_driver_id: Mapped[int] = mapped_column(ForeignKey("driver_profiles.id"), nullable=True, index=True)
    assigned_vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=True, index=True)
    current_route_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    shipment_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )


class LogisticsRoute(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    route_key: Mapped[str] = mapped_column(String(180), index=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), nullable=True, index=True)
    origin_node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"), nullable=True, index=True)
    destination_node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"), nullable=True, index=True)
    origin_node_key: Mapped[str] = mapped_column(String(120), index=True)
    destination_node_key: Mapped[str] = mapped_column(String(120), index=True)
    node_sequence: Mapped[list[str]] = mapped_column(JSON, default=list)
    edge_sequence: Mapped[list[str]] = mapped_column(JSON, default=list)
    transport_modes: Mapped[list[str]] = mapped_column(JSON, default=list)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    total_time: Mapped[float] = mapped_column(Float, default=0.0)
    total_risk: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(40), default="planned", index=True)
    assigned_driver_id: Mapped[int] = mapped_column(ForeignKey("driver_profiles.id"), nullable=True, index=True)
    assigned_vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=True, index=True)
    route_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )


class IntegrationClient(Base):
    __tablename__ = "integration_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    firebase_uid: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True, index=True)
    api_key_hash: Mapped[str] = mapped_column(String(128))
    api_key_prefix: Mapped[str] = mapped_column(String(16), index=True)
    contact_email: Mapped[str] = mapped_column(String(255), default="")
    allowed_ips: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=1000)
    monthly_api_calls: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("integration_clients.id"), index=True)
    callback_url: Mapped[str] = mapped_column(String(500))
    events: Mapped[str] = mapped_column(String(500))
    secret: Mapped[str] = mapped_column(String(128), default="")
    retry_count: Mapped[int] = mapped_column(Integer, default=3)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=10)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("webhook_subscriptions.id"), index=True)
    client_id: Mapped[Optional[int]] = mapped_column(ForeignKey("integration_clients.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[str] = mapped_column(Text)
    response_status: Mapped[int] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    next_retry_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), nullable=True, index=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), nullable=True, index=True)
    prediction_type: Mapped[str] = mapped_column(String(60), index=True)
    target_key: Mapped[str] = mapped_column(String(160), index=True)
    value: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False, index=True)


class ClientSimulation(Base):
    __tablename__ = "client_simulations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("integration_clients.id"), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="idle", index=True)
    simulation_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    speed_multiplier: Mapped[float] = mapped_column(Float, default=120.0)
    total_ticks: Mapped[int] = mapped_column(Integer, default=0)
    last_save_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    event_queue_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    live_states_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )
