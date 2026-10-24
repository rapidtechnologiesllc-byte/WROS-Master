# PRODUCTION-READY MINIMAL - 136 ENDPOINTS (Clean)

# Load .env file FIRST (before any other imports that use os.getenv)
from dotenv import load_dotenv
load_dotenv()

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
from app.core.db_contract import initialize_database

# COMPLETE API ROUTES - All production endpoints
from app.api.v1.routes import router as api_router

# Import models for registration
try:
    from app import models as _all_models
except ImportError:
    pass

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

# Setup middleware - CRITICAL: CORSMiddleware MUST run first (added last in FastAPI)
from app.middleware import setup_cors, RequestLoggingMiddleware
from app.middleware.auth_middleware import AuthenticationMiddleware

# Add in REVERSE order: CORS last (runs first), Logging first (runs last)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(AuthenticationMiddleware)
setup_cors(app)  # Add CORS LAST so it runs FIRST
# Compress JSON / text responses over GZIP_MIN_BYTES: list endpoints shrink ~5-10x on the wire.
# Outermost, so it sees the final body (CORS and logging headers included).
from starlette.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=settings.GZIP_MIN_BYTES)

# Register complete API router (all production endpoints)
app.include_router(api_router)

# Microsoft OAuth redirect URI registered in Azure is
# https://hrms-backend.blitzenx.com/msgraph/auth/callback -- that host proxies
# to this app without the /api/v1 prefix, so serve the callback (and the
# sign-in redirect the login page links to) at the bare paths too.
from app.api.v1.endpoints.msgraph import oauth_callback as _msgraph_oauth_callback, signin as _msgraph_signin
app.add_api_route("/msgraph/auth/callback", _msgraph_oauth_callback, methods=["GET"], include_in_schema=False)
app.add_api_route("/msgraph/auth/signin", _msgraph_signin, methods=["GET"], include_in_schema=False)

logger.info(f"[STARTUP] Endpoint registration complete - {len(app.routes)} top-level routes registered")

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "message": "Backend is running - 9 core endpoints active"
    }

@app.on_event("startup")
async def startup_event():
    from app.core.database import SAFE_DATABASE_URL
    logger.info("[STARTUP] DATABASE_URL=%s", SAFE_DATABASE_URL)
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
