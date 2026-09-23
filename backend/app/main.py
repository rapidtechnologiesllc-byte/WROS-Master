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
from app.core.database_init import initialize_database

# ESSENTIAL ENDPOINTS - VERIFIED WORKING
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users_access_control import router as users_access_control_router
from app.api.v1.endpoints.candidates.crud import router as candidates_router
from app.api.v1.endpoints.candidates import router as candidate_forms_router
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
app.include_router(users_access_control_router, prefix="/api/v1")
app.include_router(candidates_router)
app.include_router(candidate_forms_router)
app.include_router(config_router, prefix="/api/v1")
app.include_router(message_queue_router, prefix="/api/v1")
app.include_router(business_units_router, prefix="/api/v1")
app.include_router(rbac_router, prefix="/api/v1")
app.include_router(career_portal_router, prefix="/api/v1")
app.include_router(flash_router, prefix="/api/v1")

logger.info(f"[STARTUP] Endpoint registration complete - {len(app.routes)} top-level routes registered")

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "message": "Backend is running - 9 core endpoints active"
    }

@app.on_event("startup")
async def startup_event():
    logger.info("[STARTUP] DATABASE_URL=%s...", settings.DATABASE_URL[:50] if settings.DATABASE_URL else "NOT SET")
    logger.info(f"[STARTUP] Connecting to database...")

    try:
        # Initialize database: create schema, tables, roles, permissions, users
        initialize_database()
        logger.info("[STARTUP] Database initialization complete")
    except Exception as e:
        logger.error(f"[STARTUP ERROR] Database initialization failed: {e}", exc_info=True)
        raise RuntimeError(f"Database initialization failed: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
