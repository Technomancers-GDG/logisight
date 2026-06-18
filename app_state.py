"""Centralized service instances shared across route modules."""
from __future__ import annotations

from config import settings
from services.driver_performance import DriverPerformanceService
from services.event_ingestion import EventIngestionService
from services.inventory_optimizer import InventoryOptimizer
from services.logistics_data_fusion import DataFusionService
from services.logistics_decision_engine import LogisticsDecisionEngine
from services.logistics_execution import LogisticsExecutionService
from services.logistics_prediction import LogisticsPredictionEngine
from services.logistics_telemetry import TelemetrySimulationService
from services.multi_objective_optimizer import NSGA2Optimizer
from services.multimodal_graph_engine import MultimodalGraphEngine
from services.news_relevance import NewsRelevanceService
from services.predictive_forecast import PredictiveForecastService
from services.rl_decision_engine import get_rl_engine
from services.route_planner import RoutePlanner
from services.simulation import SimulationEngine
from services.simulation_manager import simulation_manager

class LazyService:
    def __init__(self, factory):
        self._factory = factory
        self._instance = None
    
    def __getattr__(self, name):
        if self._instance is None:
            self._instance = self._factory()
        return getattr(self._instance, name)

news_model = LazyService(lambda: NewsRelevanceService())
route_planner = LazyService(lambda: RoutePlanner())
event_ingestion_service = LazyService(lambda: EventIngestionService(news_model))

# Demo/general engine (client_id=None, channel="global")
simulation_engine = SimulationEngine(route_planner, client_id=None, channel="global")
simulation_manager.register_engine(None, simulation_engine)

forecast_service = LazyService(lambda: PredictiveForecastService())
inventory_optimizer = LazyService(lambda: InventoryOptimizer())
data_fusion_service = LazyService(lambda: DataFusionService())
multimodal_graph_engine = LazyService(lambda: MultimodalGraphEngine())
logistics_prediction_engine = LazyService(lambda: LogisticsPredictionEngine())
logistics_decision_engine = LazyService(lambda: LogisticsDecisionEngine())
logistics_execution_service = LazyService(lambda: LogisticsExecutionService())
telemetry_simulation_service = LazyService(lambda: TelemetrySimulationService())
driver_performance_service = LazyService(lambda: DriverPerformanceService(telemetry_simulation_service))
multi_objective_optimizer = LazyService(lambda: NSGA2Optimizer())
