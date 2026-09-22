# PRODUCTION-READY MINIMAL - 136 ENDPOINTS (Clean)

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import logging
import os
from pathlib import Path

from app.core.config import settings
from app.core.database import engine, SessionLocal
from app.core.logging import logger
from app.models.base import Base
from app.core import tenant_context as _tenant_context

# ESSENTIAL ENDPOINTS - VERIFIED WORKING
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users_access_control import router as users_access_control_router
from app.api.v1.endpoints.candidates.crud import router as candidates_crud_router
import importlib.util
from pathlib import Path
_candidates_py_path = Path(__file__).parent / "api" / "v1" / "endpoints" / "candidates.py"
_spec = importlib.util.spec_from_file_location("candidates_legacy", str(_candidates_py_path))
_candidates_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_candidates_legacy)
from app.api.v1.endpoints.config import router as config_router
from app.api.v1.endpoints.message_queue import router as message_queue_router
from app.api.v1.endpoints.business_units import router as business_units_router
from app.api.v1.endpoints.rbac import router as rbac_router
from app.api.v1.endpoints.career_portal import router as career_portal_router
from app.api.v1.endpoints.flash_queue_metrics import router as flash_router

# Import models for registration
try:
    from app import models as _all_models
except ImportError:
    pass

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

# Setup middleware
from app.middleware import setup_cors, RequestLoggingMiddleware
from app.middleware.auth_middleware import AuthenticationMiddleware

setup_cors(app)
app.add_middleware(AuthenticationMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# Register essential routers only
app.include_router(auth_router)
logger.info(f"[ROUTER] auth_router included")
app.include_router(users_access_control_router, prefix="/api/v1")
logger.info(f"[ROUTER] users_access_control_router included")
app.include_router(candidates_crud_router)
logger.info(f"[ROUTER] candidates_crud_router included with {len(candidates_crud_router.routes)} routes")
app.include_router(_candidates_legacy.router)
logger.info(f"[ROUTER] _candidates_legacy.router included with {len(_candidates_legacy.router.routes)} routes")
app.include_router(config_router, prefix="/api/v1")
logger.info(f"[ROUTER] config_router included")
app.include_router(message_queue_router, prefix="/api/v1")
logger.info(f"[ROUTER] message_queue_router included")
app.include_router(business_units_router, prefix="/api/v1")
logger.info(f"[ROUTER] business_units_router included")
app.include_router(rbac_router, prefix="/api/v1")
logger.info(f"[ROUTER] rbac_router included")
app.include_router(career_portal_router, prefix="/api/v1")
logger.info(f"[ROUTER] career_portal_router included")
app.include_router(flash_router, prefix="/api/v1")
logger.info(f"[ROUTER] flash_router included")

logger.info(f"[ROUTER] Total routes in app: {len(app.routes)}")

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "message": "Backend is running - 9 core endpoints active"
    }

@app.on_event("startup")
async def startup_event():
    logger.info("[STARTUP] DATABASE_URL=%s...", settings.DATABASE_URL[:50] if settings.DATABASE_URL else "NOT SET")
    
    try:
        from app.core.db_contract import initialize_database
        initialize_database()
        logger.info("[STARTUP] Database contract initialized successfully")
    except Exception as e:
        logger.error(f"[STARTUP ERROR] {e}", exc_info=True)
        raise RuntimeError(f"Database initialization failed: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
