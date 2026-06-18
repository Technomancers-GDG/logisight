"""Schemas package - re-exports all Pydantic models for backward compatibility."""
from __future__ import annotations

from schemas.core import ORMModel
from schemas.facility import (
    FacilityBase, FacilityCreate, FacilityUpdate, FacilityRead,
    PortLinkBase, PortLinkCreate, PortLinkRead,
    FacilityLoadView,
)
from schemas.driver import (
    DriverProfileBase, DriverProfileCreate, DriverProfileRead,
    DriverInstructionRead, DriverResponseRequest, DriverIncidentCreate,
    DriverIncidentRead, DriverMobileSnapshot, DriverMetricsRead,
    RecommendationDecisionRequest,
)
from schemas.vehicle import (
    VehicleBase, VehicleCreate, VehicleUpdate, VehicleRead, VehicleStateView,
)
from schemas.objective import (
    ObjectiveBase, ObjectiveCreate, ObjectiveUpdate, ObjectiveRead,
    RouteTemplateRead,
)
from schemas.recommendation import (
    RecommendationRead, DriverDecisionRead,
)
from schemas.news import (
    NewsEventRead, WeatherEventRead, ImportSummary,
)
from schemas.simulation import (
    SimulationControlRequest, SpeedChangeRequest, SimulationStatus,
    FleetScaleRequest, FleetScaleResult, MetricsSnapshotRead, MetricsSummary,
    DashboardSnapshot, ScenarioPresetRead, ScenarioComparisonMetrics,
    ScenarioComparisonRead,
)
from schemas.inventory import (
    RiskForecastRead, InventoryForecastRead, ProactiveDispatchRead,
)
from schemas.ai import (
    RLDecisionRequest, RLDecisionResponse,
)
from schemas.blockchain import (
    BlockchainBlockRead, BlockchainVerifyRead,
)
from schemas.edge import (
    EdgeSyncStatusRead, CloudHealthRead,
)
from schemas.logistics import (
    NodeType, TransportMode,
    LogisticsNodeInput, LogisticsEdgeInput, LogisticsGraph,
    DataFusionRequest, DataFusionResponse,
    RouteWeights, RouteBusinessMetrics, RouteSegmentRead,
    RouteOptionRead, ComputeRoutesRequest, ComputeRoutesResponse,
    PortDelayPrediction, RakeAvailabilityPrediction, RouteRiskPrediction,
    PredictionRequest, PredictionResponse,
    DecisionRequest, DecisionResponse,
    AssignRouteRequest, AssignmentResponse,
    RerouteRequest, RerouteResponse,
    TelemetrySimulationRequest, TelemetrySimulationResponse,
)
from schemas.multi_objective import (
    ParetoFrontRead,
)

__all__ = [
    "ORMModel",
    "FacilityBase", "FacilityCreate", "FacilityUpdate", "FacilityRead",
    "PortLinkBase", "PortLinkCreate", "PortLinkRead",
    "FacilityLoadView",
    "DriverProfileBase", "DriverProfileCreate", "DriverProfileRead",
    "DriverInstructionRead", "DriverResponseRequest", "DriverIncidentCreate",
    "DriverIncidentRead", "DriverMobileSnapshot", "DriverMetricsRead",
    "RecommendationDecisionRequest",
    "VehicleBase", "VehicleCreate", "VehicleUpdate", "VehicleRead",
    "VehicleStateView",
    "ObjectiveBase", "ObjectiveCreate", "ObjectiveUpdate", "ObjectiveRead",
    "RouteTemplateRead",
    "RecommendationRead", "DriverDecisionRead",
    "NewsEventRead", "WeatherEventRead", "ImportSummary",
    "SimulationControlRequest", "SpeedChangeRequest", "SimulationStatus", "FleetScaleRequest",
    "FleetScaleResult", "MetricsSnapshotRead", "MetricsSummary",
    "DashboardSnapshot", "ScenarioPresetRead", "ScenarioComparisonMetrics",
    "ScenarioComparisonRead",
    "RiskForecastRead", "InventoryForecastRead", "ProactiveDispatchRead",
    "RLDecisionRequest", "RLDecisionResponse",
    "BlockchainBlockRead", "BlockchainVerifyRead",
    "EdgeSyncStatusRead", "CloudHealthRead",
    "NodeType", "TransportMode",
    "LogisticsNodeInput", "LogisticsEdgeInput", "LogisticsGraph",
    "DataFusionRequest", "DataFusionResponse",
    "RouteWeights", "RouteBusinessMetrics", "RouteSegmentRead",
    "RouteOptionRead", "ComputeRoutesRequest", "ComputeRoutesResponse",
    "PortDelayPrediction", "RakeAvailabilityPrediction",
    "RouteRiskPrediction", "PredictionRequest", "PredictionResponse",
    "DecisionRequest", "DecisionResponse",
    "AssignRouteRequest", "AssignmentResponse",
    "RerouteRequest", "RerouteResponse",
    "TelemetrySimulationRequest", "TelemetrySimulationResponse",
    "ParetoFrontRead",
]