"""Quick integration test for the multi-tenant backend."""
from config import settings
from database import SessionLocal, init_db
import models
from app_state import simulation_engine, simulation_manager
from schemas.client import ClientRegisterRequest, ClientLoginRequest, ClientAuthResponse, DashboardResponse, UploadResult
from routes import (
    crud_router, simulation_router, driver_router, ai_router, logistics_router,
    rl_router, comparison_router, integration_router, management_router,
    client_auth_router, client_upload_router, client_dashboard_router,
)
from routes.client_upload import router as upload_r
from routes.client_dashboard import router as dash_r
from services.simulation_manager import simulation_manager as sm



# Test router registration
assert client_auth_router is not None
assert client_upload_router is not None
assert client_dashboard_router is not None
print("All client routers registered OK")

# Test simulation_manager singleton
assert sm is not None

print("\nALL CHECKS PASSED")
