# main.py  # 2026-08-17 - Force reload for bug fixes
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import logging
from pathlib import Path

from app.core.config import settings
from app.core.database import engine, SessionLocal
from app.core.logging import logger
from app.models.base import Base
from app.api.v1.routes import router
from app.middleware import setup_cors, RequestLoggingMiddleware
# S-207 -- importing this here (rather than relying on it being pulled in
# lazily by whichever endpoint module happens to run first) registers the
# global tenant-scoping do_orm_execute listener deterministically at
# process startup. See app.core.tenant_context's module docstring.
from app.core import tenant_context as _tenant_context  # noqa: F401

# Agent State models — imported here so Base.metadata.create_all() finds them
from app.models import agent_phalanx  # noqa: F401

# Referral models — imported here for database table creation
from app.models import referral  # noqa: F401

# Create FastAPI application
# Swagger/(/docs) and ReDoc (/redoc) are interactive, "Try it out"-capable
# API explorers against this HR system's real PII (employee bank details,
# salaries, PAN numbers, candidate resumes) -- gated behind DEBUG (already
# False by default, see app.core.config) so they're not reachable on the
# open internet in production. Pre-launch security hardening.
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="HRMS Onboarding and Authentication API",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# Setup CORS middleware
setup_cors(app)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Phase 1 B4 -- rate limiting, enabled 2026-07-20. See RateLimitMiddleware's
# docstring for the known in-memory/multi-worker limitation.
# DISABLED: Rate limiter was blocking role template permission updates
# from app.middleware import RateLimitMiddleware
# app.add_middleware(RateLimitMiddleware, max_requests=10000, window_seconds=60)

# S-215/HRMS-0117 Step 3/AC-1 -- an unhandled exception is, by
# definition, the CRITICAL case (nothing in the request path expected
# or handled it) -- logged to the real error_log table and pages
# on-call synchronously, additive to the existing file logger. Uses
# its own fresh DB session (exception handlers run outside the normal
# per-request Depends(get_db) lifecycle).
@app.exception_handler(Exception)
async def log_unhandled_exception(request: Request, exc: Exception):
    from app.core.database import SessionLocal
    from app.services.error_log_service import log_error

    db = SessionLocal()
    try:
        log_error(
            db, error_type=type(exc).__name__, severity="CRITICAL", message=str(exc)[:2000], exc=exc,
            request_context={"method": request.method, "path": request.url.path},
        )
    except Exception as logging_exc:
        logger.error(f"[ErrorLog] Failed to record unhandled exception: {logging_exc}")
    finally:
        db.close()

    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    response = JSONResponse(status_code=500, content={"detail": "Internal server error."})
    # Add CORS headers to exception response so browser doesn't block it
    origin = request.headers.get("origin", "http://localhost:3000")
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPException (401, 403, 404, etc.) with CORS headers"""
    response = JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    # Add CORS headers so browser doesn't block 401, 403, 404, etc responses
    origin = request.headers.get("origin", "http://localhost:3000")
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

@app.on_event("startup")
async def startup_event():
    """
    Application startup event.
    Creates tables and seeds RBAC data.
    """
    import asyncio
    import time
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy.exc import OperationalError

    # Validate configuration immediately
    settings.validate_config()
    logger.info("[OK] Configuration validated")

    # Start APScheduler immediately (no I/O needed)
    from app.core.scheduler import start_scheduler
    start_scheduler()
    logger.info("[OK] Scheduler started")

    # Run DB operations synchronously (not in background thread)
    # This ensures tables exist before app accepts requests
    try:
        logger.info("[Startup] Creating database tables...")
        Base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("[OK] Database tables initialized")
    except Exception as exc:
        logger.error(f"[Startup] Failed to create DB tables: {exc}", exc_info=True)
        return  # Don't crash startup, but tables won't exist

    # Initialize database contract (tenant, RBAC, admin user)
    try:
        from app.core.db_contract import initialize_database
        initialize_database()
    except Exception as exc:
        logger.error(f"[Startup] Failed to initialize database contract: {exc}", exc_info=True)
        return  # Don't crash startup, but contract won't be initialized

    # Initialize default organizational positions (CEO, Partner, BU Head, etc.)
    try:
        logger.info("[Startup] Initializing default organizational positions...")
        from app.services.org_structure_service import init_default_positions
        db = SessionLocal()
        result = init_default_positions(db)
        db.close()
        logger.info(f"[OK] Organizational positions initialized (created: {result['created']}, updated: {result['updated']})")
    except Exception as exc:
        logger.error(f"[Startup] Failed to initialize org positions: {exc}", exc_info=True)

    # Seed RBAC with retries
    # DISABLED: Starting with clean database for RBAC testing
    # from app.core.database import SessionLocal
    # from app.services.role_template_seed import seed_role_templates

    # MAX_RETRIES = 3
    # RETRY_DELAY = 2  # seconds

    # for attempt in range(1, MAX_RETRIES + 1):
    #     _db = SessionLocal()
    #     try:
    #         logger.info(f"[Startup] Seeding RBAC (attempt {attempt}/{MAX_RETRIES})...")
    #         seed_role_templates(_db, tenant_id=1)
    #         logger.info(f"[OK] {settings.APP_NAME} v{settings.APP_VERSION} started successfully")
    #         logger.info(f"[OK] Server running on http://{settings.HOST}:{settings.PORT}")
    #         break  # Success — exit retry loop
    #     except OperationalError as exc:
    #         logger.warning(
    #             f"[Startup] RBAC seed attempt {attempt}/{MAX_RETRIES} failed "
    #             f"(DB connectivity issue): {exc}"
    #         )
    #         if attempt < MAX_RETRIES:
    #             logger.info(f"[Startup] Retrying RBAC seed in {RETRY_DELAY}s...")
    #             time.sleep(RETRY_DELAY)
    #         else:
    #             logger.error(
    #                 "[Startup] RBAC seed failed after all retries. "
    #                 "The app will run but role/permission data may be incomplete."
    #             )
    #     except Exception as exc:
    #         logger.error(f"[Startup] Non-retryable error during RBAC seed: {exc}", exc_info=True)

    logger.info(f"[OK] {settings.APP_NAME} v{settings.APP_VERSION} started successfully (no seed data)")
    logger.info(f"[OK] Server running on http://{settings.HOST}:{settings.PORT}")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown event.
    Cleanup resources and log shutdown.
    """
    logger.info(f"Shutting down {settings.APP_NAME}...")
    
    # Shutdown APScheduler
    from app.core.scheduler import shutdown_scheduler
    shutdown_scheduler()

# Include API routes
app.include_router(router)

# HRMS-0114 -- fail startup if any route has no explicit identity/
# permission declaration at all. Runs synchronously at import time
# (not inside the async startup event) so an offending route fails the
# app immediately and loudly, the same moment `app` becomes importable,
# rather than only surfacing once uvicorn's startup event fires.
#
# known_exceptions: the msgraph mail/calendar routes check a session
# cookie inside their function body (_require_account in msgraph.py),
# not via FastAPI's Depends() -- real protection this scanner
# structurally can't see. Each is guarded by
# tests/test_route_permission_audit_real_app.py::test_msgraph_manual_exception_guard_still_has_real_protection
# so this exception list can't silently go stale if that function is
# ever removed. See docs/build-package/HRMS-0114-route-gap.md for the
# full history of how every other route reached 0 unexplained gaps.
from app.core.route_security_audit import assert_all_routes_have_permission_declarations
from app.middleware.auth_middleware import AuthenticationMiddleware

assert_all_routes_have_permission_declarations(
    app,
    AuthenticationMiddleware.PUBLIC_ROUTES + AuthenticationMiddleware.PUBLIC_ROUTE_TEMPLATES,
    known_exceptions=[
        "GET /msgraph/calendar/meetings",
        "POST /msgraph/calendar/schedule",
        "POST /msgraph/mail/send",
        "GET /rbac/modules-and-verbs",
        "GET /admin/certifications/business-units",
        "GET /admin/certifications/roles",
    ],
)
logger.info("[OK] HRMS-0114 route permission audit passed")

# Mount static files directory
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("[OK] Static files mounted at /static")
else:
    logger.warning("Static directory not found. Skipping static file mounting.")

@app.get("/")
def home():
    """
    Root endpoint - API health check and information.
    
    Returns:
        API status and basic information
    """
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health")
def health_check():
    """
    Health check endpoint for monitoring.
    
    Returns:
        Health status of the application
    """
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }

if __name__ == "__main__":
    import uvicorn
    
    # Run the application
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,#settings.DEBUG,
        log_level="info"
    )