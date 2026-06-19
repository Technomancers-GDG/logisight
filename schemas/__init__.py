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
    RecommendationDecisionRequest, SpotlightRequest,
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
from schemas.client import (
    DashboardResponse, UploadResult,
)
from schemas.integration import (
    BatchResult, DecisionExport, DriverExport, DriverImport,
    DriverImportBatch, ErrorDetail, EventImport, EventImportBatch,
    FacilityExport, FacilityImport, FacilityImportBatch,
    IncidentExport, IncidentImport, IntegrationSnapshot,
    IntegrationStatus, InventoryUpdateBatch, MetricsExport,
    ObjectiveExport, ObjectiveImport, ObjectiveImportBatch,
    OptimizeDispatchRequest, ShipmentExport, ShipmentImport,
    ShipmentImportBatch, SimulationDecideRequest, SimulationDecideResponse,
    VehicleExport, VehicleImport, VehicleImportBatch,
    WebhookCreate, WebhookDeliveryExport, WebhookExport, WebhookUpdate,
)
from schemas.simulation import (
    SimulationControlRequest, SpeedChangeRequest, SimulationStatus,
    FleetScaleRequest, FleetScaleResult, MetricsSnapshotRead, MetricsSummary,
    DashboardSnapshot, ScenarioPresetRead, ScenarioComparisonMetrics,
    ScenarioComparisonRead, TriggerScenarioRequest,
)
from schemas.inventory import (
    RiskForecastRead, InventoryForecastRead, ProactiveDispatchRead,
)
from schemas.ai import (
    RLDecisionRequest, RLDecisionResponse,
    AIChatRequest, AIChatResponse,
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
    "RecommendationDecisionRequest", "SpotlightRequest",
    "VehicleBase", "VehicleCreate", "VehicleUpdate", "VehicleRead",
    "VehicleStateView",
    "ObjectiveBase", "ObjectiveCreate", "ObjectiveUpdate", "ObjectiveRead",
    "RouteTemplateRead",
    "RecommendationRead", "DriverDecisionRead",
    "NewsEventRead", "WeatherEventRead", "ImportSummary",
    "SimulationControlRequest", "SpeedChangeRequest", "SimulationStatus", "FleetScaleRequest",
    "FleetScaleResult", "MetricsSnapshotRead", "MetricsSummary",
    "DashboardSnapshot", "ScenarioPresetRead", "ScenarioComparisonMetrics",
    "ScenarioComparisonRead", "TriggerScenarioRequest",
    "RiskForecastRead", "InventoryForecastRead", "ProactiveDispatchRead",
    "RLDecisionRequest", "RLDecisionResponse",
    "AIChatRequest", "AIChatResponse",
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
    "DashboardResponse", "UploadResult",
    "BatchResult", "DecisionExport", "DriverExport", "DriverImport",
    "DriverImportBatch", "ErrorDetail", "EventImport", "EventImportBatch",
    "FacilityExport", "FacilityImport", "FacilityImportBatch",
    "IncidentExport", "IncidentImport", "IntegrationSnapshot",
    "IntegrationStatus", "InventoryUpdateBatch", "MetricsExport",
    "ObjectiveExport", "ObjectiveImport", "ObjectiveImportBatch",
    "OptimizeDispatchRequest", "ShipmentExport", "ShipmentImport",
    "ShipmentImportBatch", "SimulationDecideRequest", "SimulationDecideResponse",
    "VehicleExport", "VehicleImport", "VehicleImportBatch",
    "WebhookCreate", "WebhookDeliveryExport", "WebhookExport", "WebhookUpdate",
]