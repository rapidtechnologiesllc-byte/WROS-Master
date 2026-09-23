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

# COMPLETE API ROUTES - All production endpoints
from app.api.v1.routes import router as api_router

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

# Register complete API router (all production endpoints)
app.include_router(api_router)

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
