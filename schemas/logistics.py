from __future__ import annotations

from datetime import datetime, date
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from schemas.core import ORMModel

NodeType = Literal["warehouse", "port", "railhead", "mine"]
TransportMode = Literal["road", "rail", "water"]

class LogisticsNodeInput(BaseModel):
    id: str = Field(min_length=1)
    name: str
    node_type: NodeType
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    capacity_units: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    active: bool = True


class LogisticsEdgeInput(BaseModel):
    id: str | None = None
    from_node_id: str = Field(min_length=1)
    to_node_id: str = Field(min_length=1)
    transport_mode: TransportMode
    cost: float = Field(ge=0)
    time: float = Field(ge=0, description="Transit time in minutes")
    risk: float = Field(ge=0, le=1)
    capacity: float | None = Field(default=None, ge=0)
    time_window: tuple[float, float] | None = Field(
        default=None,
        description="Allowed traversal window in minutes from route start.",
    )
    mode_switch_penalty: float = Field(default=0.0, ge=0)
    distance_km: float | None = Field(default=None, ge=0)
    capacity_units: int | None = Field(default=None, ge=0)
    bidirectional: bool = True
    constraints: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    active: bool = True


class LogisticsGraph(BaseModel):
    nodes: list[LogisticsNodeInput] = Field(default_factory=list)
    edges: list[LogisticsEdgeInput] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)


class DataFusionRequest(LogisticsGraph):
    persist: bool = False


class DataFusionResponse(LogisticsGraph):
    node_count: int
    edge_count: int


class RouteWeights(BaseModel):
    w1: float = Field(default=1.0, ge=0, description="Cost weight")
    w2: float = Field(default=1.0, ge=0, description="Time weight")
    w3: float = Field(default=1.0, ge=0, description="Risk weight")


class RouteBusinessMetrics(BaseModel):
    cost: float
    time: float
    risk: float
    fuel_estimate: float
    co2_estimate: float
    cost_savings_vs_baseline: float
    time_saved_vs_baseline: float


class RouteSegmentRead(BaseModel):
    edge_id: str
    from_node_id: str
    to_node_id: str
    transport_mode: TransportMode
    cost: float
    time: float
    risk: float
    base_cost: float | None = None
    base_time: float | None = None
    base_risk: float | None = None
    predicted_delay: float = 0.0
    risk_penalty: float = 0.0
    mode_switch_penalty_applied: float = 0.0
    switching_delay_applied: float = 0.0
    time_window_violation_minutes: float = 0.0
    driver_penalty_applied: float = 0.0
    capacity: float | None = None
    time_window: tuple[float, float] | None = None
    distance_km: float | None = None
    reversed: bool = False


class RouteOptionRead(BaseModel):
    route_id: int | None = None
    node_sequence: list[str]
    edge_sequence: list[str]
    segments: list[RouteSegmentRead]
    transport_modes: list[TransportMode]
    total_cost: float
    total_time: float
    total_risk: float
    score: float
    summary: str
    business_metrics: RouteBusinessMetrics | None = None


class ComputeRoutesRequest(BaseModel):
    origin_node_id: str
    destination_node_id: str
    graph: LogisticsGraph | None = None
    weights: RouteWeights = Field(default_factory=RouteWeights)
    max_routes: int = Field(default=3, ge=1, le=8)
    persist_graph: bool = False
    driver_id: int | None = None
    driver_reliability_score: float | None = Field(default=None, ge=0, le=1)
    driver_penalty_factor: float = Field(default=100.0, ge=0)
    required_capacity: float = Field(default=0.0, ge=0)
    switching_delay: float = Field(default=0.0, ge=0)
    time_window_penalty: float = Field(default=10.0, ge=0)
    prediction_enabled: bool = True
    delay_penalty_per_minute: float = Field(default=1.0, ge=0)
    risk_penalty_factor: float = Field(default=500.0, ge=0)
    port_context: dict[str, Any] = Field(default_factory=dict)
    rail_context: dict[str, Any] = Field(default_factory=dict)
    weather_context: dict[str, Any] = Field(default_factory=dict)
    shipment_context: dict[str, Any] = Field(default_factory=dict)


class ComputeRoutesResponse(BaseModel):
    graph: LogisticsGraph
    adjusted_graph: LogisticsGraph | None = None
    shortest_path: RouteOptionRead
    alternatives: list[RouteOptionRead]
    constraints: dict[str, Any] = Field(default_factory=dict)
    predictions: PredictionResponse | None = None


class PortDelayPrediction(BaseModel):
    node_id: str
    delay_minutes: float
    confidence: float
    severity: str
    factors: list[str]


class RakeAvailabilityPrediction(BaseModel):
    node_id: str
    available_rakes: int
    wait_minutes: float
    confidence: float
    status: str


class RouteRiskPrediction(BaseModel):
    route_index: int
    route_signature: str
    risk: float
    predicted_delay_minutes: float
    confidence: float
    factors: list[str]


class PredictionRequest(BaseModel):
    graph: LogisticsGraph | None = None
    route_options: list[RouteOptionRead] = Field(default_factory=list)
    origin_node_id: str | None = None
    destination_node_id: str | None = None
    weights: RouteWeights = Field(default_factory=RouteWeights)
    max_routes: int = Field(default=3, ge=1, le=8)
    port_context: dict[str, Any] = Field(default_factory=dict)
    rail_context: dict[str, Any] = Field(default_factory=dict)
    weather_context: dict[str, Any] = Field(default_factory=dict)
    shipment_context: dict[str, Any] = Field(default_factory=dict)
    persist: bool = False


class PredictionResponse(BaseModel):
    generated_at: datetime
    port_delays: list[PortDelayPrediction]
    rake_availability: list[RakeAvailabilityPrediction]
    route_risks: list[RouteRiskPrediction]
    assumptions: list[str]


class DecisionRequest(BaseModel):
    route_options: list[RouteOptionRead] = Field(min_length=1)
    predictions: PredictionResponse
    delay_threshold_minutes: float = Field(default=120.0, ge=0)
    risk_threshold: float = Field(default=0.7, ge=0, le=1)


class DecisionResponse(BaseModel):
    recommended_route: RouteOptionRead
    alternatives: list[RouteOptionRead]
    reasoning: str
    switched: bool
    delay_exceeded: bool


class AssignRouteRequest(BaseModel):
    route: RouteOptionRead
    graph: LogisticsGraph | None = None
    shipment_id: int | None = None
    shipment_reference: str | None = None
    origin_node_id: str
    destination_node_id: str
    cargo_type: str = "general"
    quantity_units: int = Field(default=0, ge=0)
    driver_id: int | None = None
    vehicle_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssignmentResponse(BaseModel):
    shipment_id: int
    shipment_reference: str
    route_id: int
    status: str
    assigned_driver_id: int | None
    assigned_vehicle_id: int | None
    route: RouteOptionRead


class RerouteRequest(BaseModel):
    shipment_id: int
    current_location_node_id: str | None = None
    destination_node_id: str | None = None
    graph: LogisticsGraph | None = None
    route_options: list[RouteOptionRead] = Field(default_factory=list)
    predictions: PredictionResponse | None = None
    weights: RouteWeights = Field(default_factory=RouteWeights)
    max_routes: int = Field(default=3, ge=1, le=8)
    delay_threshold_minutes: float = Field(default=120.0, ge=0)
    improvement_threshold: float = Field(default=50.0, ge=0)
    required_capacity: float = Field(default=0.0, ge=0)
    switching_delay: float = Field(default=0.0, ge=0)


class RerouteResponse(BaseModel):
    shipment_id: int
    previous_route: RouteOptionRead | None
    new_route: RouteOptionRead
    decision: DecisionResponse
    status: str
    rerouted: bool = True
    improvement_score: float = 0.0


class TelemetrySimulationRequest(BaseModel):
    route: RouteOptionRead
    shipment_id: int | None = None
    route_id: int | None = None
    payload_tons: float = Field(default=20.0, ge=0)


class TelemetrySimulationResponse(BaseModel):
    shipment_id: int | None
    route_id: int | None
    fuel_usage_liters: float
    delay_minutes: float
    emissions_kg: float
    generated_at: datetime
    details: dict[str, Any]
