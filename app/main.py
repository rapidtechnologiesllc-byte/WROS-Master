# main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.core.config import settings
from app.core.database import engine
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
from app.models import agent_state_target  # noqa: F401
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

# Phase 1 B4 -- rate limiting, enabled 2026-07-20. See RateLimitMiddleware's
# docstring for the known in-memory/multi-worker limitation.
# Note: Increased to 500 req/60s for development dashboard (which loads 20+ widgets in parallel)
from app.middleware import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware, max_requests=500, window_seconds=60)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Setup CORS middleware LAST so it wraps all other middleware
# (FastAPI applies middleware in reverse order of addition)
setup_cors(app)


# Handle HTTPException (401, 403, etc.) with CORS headers
from fastapi import HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPException and add CORS headers to the response"""
    from app.middleware.cors import add_cors_headers

    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
    return add_cors_headers(response, origin=request.headers.get("origin", "*"))


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
    from app.middleware.cors import add_cors_headers

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
    return add_cors_headers(response, origin=request.headers.get("origin", "*"))


@app.on_event("startup")
async def startup_event():
    """
    Application startup event.
    Fast path: start scheduler immediately.
    Slow DB work (create_all + RBAC seed) runs in a background thread.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    # Start APScheduler immediately (no I/O needed)
    from app.core.scheduler import start_scheduler
    start_scheduler()

    # Validate configuration
    settings.validate_config()
    logger.info("[OK] Configuration validated")

    # Run slow DB operations in a thread so uvicorn reports "started" right away
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="startup")

    async def _db_init():
        def _run():
            import time
            from sqlalchemy.exc import OperationalError
            from datetime import datetime, timedelta

            try:
                # checkfirst=True skips tables that already exist — much faster on restarts
                Base.metadata.create_all(bind=engine, checkfirst=True)
                logger.info("[OK] Database tables initialized")
            except Exception as exc:
                logger.error(f"[Startup] Failed to create DB tables: {exc}", exc_info=True)
                return  # Can't continue without tables

            # Clean up orphaned PROCESSING import jobs from backend crashes
            try:
                from app.core.database import SessionLocal
                from app.models.bulk_engagement import BulkEngagementJob

                _db = SessionLocal()
                now = datetime.utcnow()
                orphaned_jobs = _db.query(BulkEngagementJob).filter(
                    BulkEngagementJob.status == "PROCESSING"
                ).all()

                for job in orphaned_jobs:
                    # If job has been PROCESSING for more than 30 seconds and has no updated timestamp, it's orphaned
                    if job.created_at and (now - job.created_at) > timedelta(seconds=30):
                        job.status = "FAILED"
                        logger.warning(f"[Startup] Marked orphaned import job {job.id} as FAILED (no progress since {job.created_at})")

                if orphaned_jobs:
                    _db.commit()
                _db.close()
            except Exception as e:
                logger.warning(f"[Startup] Failed to clean orphaned jobs: {e}")

            # Seed RBAC with retries — transient network blips (08S01) are common on cold start
            from app.core.database import SessionLocal
            from app.services.rbac_service import RBACService

            MAX_RETRIES = 3
            RETRY_DELAY = 5  # seconds

            for attempt in range(1, MAX_RETRIES + 1):
                _db = SessionLocal()
                try:
                    RBACService.seed_roles_and_permissions(_db)
                    logger.info(f"[OK] {settings.APP_NAME} v{settings.APP_VERSION} started successfully")
                    logger.info(f"[OK] Server running on http://{settings.HOST}:{settings.PORT}")
                    break  # Success — exit retry loop
                except OperationalError as exc:
                    logger.warning(
                        f"[Startup] RBAC seed attempt {attempt}/{MAX_RETRIES} failed "
                        f"(DB connectivity issue): {exc}"
                    )
                    if attempt < MAX_RETRIES:
                        logger.info(f"[Startup] Retrying RBAC seed in {RETRY_DELAY}s...")
                        time.sleep(RETRY_DELAY)
                    else:
                        logger.error(
                            "[Startup] RBAC seed failed after all retries. "
                            "The app will run but role/permission data may be incomplete."
                        )
                except Exception as exc:
                    logger.error(f"Background startup error: {exc}", exc_info=True)
                    break  # Non-retryable error
                finally:
                    _db.close()

        await loop.run_in_executor(executor, _run)

    # Fire-and-forget — don't await so uvicorn finishes startup immediately
    loop.create_task(_db_init())


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
        "GET /candidates/bulk-import/list",
        "GET /candidates/bulk-import/{job_id}/progress",
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