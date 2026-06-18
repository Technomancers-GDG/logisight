from .crud import crud_router
from .simulation import simulation_router
from .driver import driver_router
from .ai import ai_router
from .logistics import logistics_router
from .rl import rl_router
from .comparison import router as comparison_router
from .integration import router as integration_router, management_router
from .client_auth import router as client_auth_router
from .client_upload import router as client_upload_router
from .client_dashboard import router as client_dashboard_router

__all__ = ["crud_router", "simulation_router", "driver_router", "ai_router", "logistics_router", "rl_router", "comparison_router", "integration_router", "management_router", "client_auth_router", "client_upload_router", "client_dashboard_router"]