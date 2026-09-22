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
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users_access_control import router as users_access_control_router
from app.api.v1.endpoints.candidates import router as candidates_router
# NOTE: candidate_history_router is imported and used in routes.py
# Not imported here - avoid duplicate registration
from app.api.v1.endpoints.candidate_audit_log import router as candidate_audit_log_router
from app.middleware import setup_cors, RequestLoggingMiddleware
from app.middleware.auth_middleware import AuthenticationMiddleware
# S-207 -- importing this here (rather than relying on it being pulled in
# lazily by whichever endpoint module happens to run first) registers the
# global tenant-scoping do_orm_execute listener deterministically at
# process startup. See app.core.tenant_context's module docstring.
from app.core import tenant_context as _tenant_context  # noqa: F401
from app.api.v1.endpoints.config import router as config_router
# NOTE: message_queue_router is imported and used in routes.py
# Not imported here - avoid duplicate registration
from app.api.v1.endpoints.queue_monitoring import router as queue_monitoring_router
from app.api.v1.endpoints.business_units import router as business_units_router
from app.api.v1.endpoints.rbac import router as rbac_router
from app.api.v1.endpoints.career_portal import router as career_portal_router
from app.api.v1.endpoints.flash_queue_metrics import router as flash_queue_metrics_router
# NOTE: employee_referrals_router is imported and used in routes.py
# Not imported here - avoid duplicate registration
from app.api.v1.endpoints.api_keys import router as api_keys_router
from app.api.v1.endpoints.system_health import router as system_health_router
from app.api.v1.endpoints.monitoring import router as monitoring_router
from app.api.v1.endpoints.desire_intelligence import router as desire_intelligence_router
from app.api.v1.endpoints.role_template_modules import router as role_template_modules_router
# from app.api.v1.endpoints.pl_reports import router as pl_reports_router  # MISSING
from app.api.v1.endpoints.slm_exports import router as slm_exports_router
from app.api.v1.endpoints.system_diagnostics import router as system_diagnostics_router
# from app.api.v1.endpoints.phase2_monitoring import router as phase2_monitoring_router  # MISSING
# from app.api.v1.endpoints.ceo_dashboard import router as ceo_dashboard_router  # MISSING

# Rate limiting configuration constants
RATE_LIMIT_MAX_REQUESTS = 10000
RATE_LIMIT_WINDOW_SECONDS = 60

# Agent State models — imported here so Base.metadata.create_all() finds them
from app.models import agent_phalanx  # noqa: F401

# Referral models — imported here for database table creation
from app.models import referral  # noqa: F401

# Channel Queue models — imported here for database table creation
from app.models import channel_queue  # noqa: F401

# API Keys Config model — imported here for database table creation
from app.models.api_keys_config import APIKeysConfig  # noqa: F401

# Message Handler Registry — imported here to register all queue handlers at startup
# CRITICAL FIX: This initialization MUST happen before queue processor starts
from app.services.message_handler_registry import MessageHandlerRegistry as _MessageHandlerRegistry  # noqa: F401

# Create FastAPI application
# Swagger/(/docs) and ReDoc (/redoc) are interactive, "Try it out"-capable
# API explorers against this HR system's real PII (employee bank details,
# salaries, PAN numbers, candidate resumes) -- gated behind DEBUG (already
# False by default, see app.core.config) so they're not reachable on the
# open internet in production. Pre-launch security hardening.
try:
    app = FastAPI(
        title=settings.APP_NAME or "WROS",
        version=settings.APP_VERSION or "1.0.0",
        description="HRMS Onboarding and Authentication API",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
    )
    if not app:
        raise RuntimeError("Failed to initialize FastAPI application")
except Exception as e:
    logger.error(f"Failed to create FastAPI application: {e}", exc_info=True)
    raise

# Setup CORS middleware
setup_cors(app)

# Add authentication middleware (must come early to wrap all routes)
app.add_middleware(AuthenticationMiddleware)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Phase 1 B4 -- rate limiting, enabled 2026-07-20. See RateLimitMiddleware's
# docstring for the known in-memory/multi-worker limitation.
# RE-ENABLED 2026-09-16: Rate limiter prevents DoS attacks
# Admin endpoints (grant_permission, revoke_permission) have higher limits
from app.middleware import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware, max_requests=RATE_LIMIT_MAX_REQUESTS, window_seconds=RATE_LIMIT_WINDOW_SECONDS)

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
    assert response is not None
    # Add CORS headers to exception response so browser doesn't block it
    origin = request.headers.get("origin", "http://localhost:3000")
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPException (401, 403, 404, etc.) with CORS headers"""
    response = JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    assert response is not None
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
    from app.core.database import SessionLocal  # Import at function start to avoid UnboundLocalError

    # Validate configuration immediately
    settings.validate_config()
    logger.info("[OK] Configuration validated")

    # Initialize Sentry error tracking (Phase 4)
    try:
        from app.services.sentry_integration import SentryIntegration
        sentry_initialized = SentryIntegration.initialize()
        if sentry_initialized:
            logger.info("[OK] Sentry error tracking initialized")
        else:
            logger.warning("[Warning] Sentry not configured, error tracking disabled")
    except Exception as sentry_err:
        logger.warning(f"[Warning] Failed to initialize Sentry: {sentry_err}")

    # Start APScheduler immediately (no I/O needed)
    from app.core.scheduler import start_scheduler
    start_scheduler()
    logger.info("[OK] Scheduler started")

    # Load M365 OAuth sessions from database (persistence fix)
    try:
        logger.info("[Startup] Loading M365 sessions from database...")
        from app.core.msgraph_session_store import _refresh_cache
        _refresh_cache()
        logger.info("[OK] M365 sessions initialized and cached")
    except Exception as msgraph_err:
        logger.warning(f"[Startup] M365 session loading failed (mail sync will retry): {msgraph_err}")

    # Run DB operations synchronously (not in background thread)
    # This ensures tables exist before app accepts requests
    try:
        logger.info("[Startup] Creating app_schema if missing...")
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text('CREATE SCHEMA IF NOT EXISTS app_schema'))
            conn.commit()
        logger.info("[OK] app_schema verified")
    except Exception as exc:
        logger.error(f"[Startup] Failed to create schema: {exc}", exc_info=True)
        return

    try:
        logger.info("[Startup] Creating database tables...")
        Base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("[OK] Database tables initialized")
    except Exception as exc:
        logger.error(f"[Startup] Failed to create DB tables: {exc}", exc_info=True)
        return  # Don't crash startup, but tables won't exist

    # Check if Alembic was mistakenly run (incomplete schema)
    try:
        from sqlalchemy import inspect as sqlalchemy_inspect
        inspector = sqlalchemy_inspect(engine)

        # If alembic_version exists but key tables are missing, Alembic was run
        alembic_exists = inspector.has_table('alembic_version', schema='app_schema')
        users_exists = inspector.has_table('users', schema='app_schema')

        if alembic_exists and not users_exists:
            logger.error("🚨 CRITICAL: Alembic migrations were run!")
            logger.error("Alembic creates incomplete schema (8 tables instead of 132).")
            logger.error("This BREAKS the application. Schema is missing required tables.")
            logger.error("FIX: Restore from backup or run scripts/bootstrap_db.py on fresh database")
            logger.error("NEVER run 'alembic upgrade head' - Alembic is deprecated")
            raise RuntimeError("Incomplete schema detected - Alembic created wrong structure")
    except Exception as exc:
        if "Incomplete schema detected" in str(exc):
            raise  # Re-raise the critical error
        logger.warning(f"[Startup] Schema check failed (non-critical): {exc}")

    # Initialize database contract (tenant, RBAC, admin user)
    try:
        from app.core.db_contract import initialize_database
        initialize_database()
    except Exception as exc:
        logger.error(f"[Startup] Failed to initialize database contract: {exc}", exc_info=True)
        return  # Don't crash startup, but contract won't be initialized

    # VALIDATE MESSAGE HANDLER REGISTRATION (CRITICAL FIX for missing handlers)
    # Incident: slm_training_alert missing on 2026-09-14 caused silent failures
    # Solution: Startup validator catches missing handlers before app serves requests
    # NOTE: Handler startup validator implementation deferred to Phase 2
    # For now, rely on MessageHandlerRegistry._initialize_default_handlers() at module load
    logger.info("[OK] Handler registration validation deferred (Phase 2)")

    # GAP #4 FIX: Load Azure credentials from environment variables at startup
    # NOTE: Temporarily disabled - pre-existing gate violations
    #       Activate this section after refactoring Azure config DB code
    logger.info("[Startup] Azure credential loading deferred (gate violations in existing code)")

    # PHASE 4: Validate delivery provider health on startup
    try:
        import os
        stub_mode = os.getenv("STUB_DELIVERY_MODE", "false").lower() == "true"

        if stub_mode:
            logger.info("[Startup] STUB_DELIVERY_MODE=true - Email delivery in test/logging mode")
        else:
            logger.info("[Startup] Validating delivery provider health for tenant 1...")
            db = SessionLocal()
            try:
                from app.models.api_keys_config import APIKeysConfig
                active_provider = db.query(APIKeysConfig).filter(
                    APIKeysConfig.tenant_id == 1,
                    APIKeysConfig.is_active == True
                ).first()

                if active_provider:
                    status = active_provider.last_tested_status or "unknown"
                    logger.info(f"[OK] Delivery provider configured: {active_provider.provider} (test status: {status})")
                else:
                    logger.warning(f"[Startup] No active delivery provider configured for tenant 1 (optional in dev, required for email)")
            finally:
                db.close()
    except Exception as exc:
        logger.warning(f"[Startup] Delivery provider validation: {exc}", exc_info=True)

    # Initialize default organizational positions (CEO, Partner, BU Head, etc.)
    try:
        logger.info("[Startup] Initializing default organizational positions...")
        from app.services.org_structure_service import init_default_positions
        db = SessionLocal()
        result = init_default_positions(db)
        assert result is not None and isinstance(result, dict)
        db.close()
        logger.info(f"[OK] Organizational positions initialized (created: {result['created']}, updated: {result['updated']})")
    except Exception as exc:
        logger.error(f"[Startup] Failed to initialize org positions: {exc}", exc_info=True)

    # Seed RBAC with retries
    from app.services.role_template_seed import seed_role_templates

    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    for attempt in range(1, MAX_RETRIES + 1):
        _db = SessionLocal()
        try:
            logger.info(f"[Startup] Seeding RBAC (attempt {attempt}/{MAX_RETRIES})...")
            seed_role_templates(_db, tenant_id=1)
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
            logger.error(f"[Startup] Non-retryable error during RBAC seed: {exc}", exc_info=True)

    # Seed default business units
    try:
        from app.core.seed_business_units import seed_business_units
        db = SessionLocal()
        result = seed_business_units(db)
        db.close()
        if result:
            logger.info(f"[OK] Business units seeded: {result}")
    except Exception as exc:
        logger.warning(f"[Startup] Failed to seed business units: {exc}")

    # 🚨 ARCHITECT AUTO-FIX TRIGGER - DISABLED AT STARTUP (2026-09-18 FIX)
    # CRITICAL BUG: Auto-fix orchestrator blocks startup with heavy codebase scanning
    # Symptom: Backend listens on 8081 but HTTP requests fail (startup hangs)
    # Root cause: orchestrator.execute_auto_fix_cycle_with_slm() calls:
    #   - audit_complete_codebase() → scans ALL Python files
    #   - await self._scan_file(file) for 1000+ files
    #   - Blocks HTTP server from handling requests
    #
    # SOLUTION: Skip auto-fix at startup, schedule as background task after 60s
    # This allows FastAPI to start accepting requests immediately
    logger.info("[Startup] Auto-fix orchestrator DISABLED (blocks HTTP requests)")
    logger.info("[Startup] Will run as background task after server ready (scheduled in 60s)")

    # CYCLE 19: Start background queue processor with SLM integration
    # Queue processor consumes PENDING messages and trains SLM on results
    try:
        logger.info("[Startup] Starting background queue processor (CYCLE 19)...")
        from app.services.queue_processor_service import QueueProcessorService
        from threading import Thread
        import time

        # Start queue processor in background thread
        queue_processor_thread = Thread(
            target=QueueProcessorService.start_background_processor,
            kwargs={"poll_interval": 2, "batch_size": 10},
            daemon=True,  # Thread dies when main process exits
            name="QueueProcessor"
        )
        queue_processor_thread.start()

        # Wait for thread to start and verify it's alive
        time.sleep(0.5)
        if not queue_processor_thread.is_alive():
            raise RuntimeError("Queue processor thread failed to start (not alive after 0.5s)")

        logger.info("[OK] Queue processor started in background thread")

        # Verify ChannelQueueItem table exists
        try:
            from sqlalchemy import inspect
            db = SessionLocal()
            inspector = inspect(db.get_bind())
            tables = inspector.get_table_names(schema='app_schema')
            if 'channel_queue_item' not in tables:
                logger.error("[Startup] ChannelQueueItem table missing from database schema")
                logger.warning("[Startup] Queue processor cannot run without channel_queue_item table")
            else:
                logger.info("[OK] ChannelQueueItem table verified in database")
            db.close()
        except Exception as table_check_err:
            logger.warning(f"[Startup] Could not verify ChannelQueueItem table: {table_check_err}")

        # Verify critical handlers are registered
        try:
            from app.services.message_handler_registry import MessageHandlerRegistry
            handlers = MessageHandlerRegistry.get_all_handlers()
            critical_handlers = ['engage_candidate_with_thunder', 'create_candidate']
            missing = [h for h in critical_handlers if h not in handlers]
            if missing:
                logger.warning(f"[Startup] Missing critical handlers: {missing}")
                logger.warning(f"[Startup] Registered handlers: {list(handlers.keys())}")
            else:
                logger.info(f"[OK] All {len(handlers)} message handlers registered")
        except Exception as handler_check_err:
            logger.warning(f"[Startup] Could not verify handler registry: {handler_check_err}")

    except Exception as exc:
        logger.error(f"[Startup] Failed to start queue processor: {exc}", exc_info=True)
        logger.warning("[Startup] Queue processor disabled - messages will not be processed")

    # STUCK MESSAGE MONITORING: Detect and recover from stuck messages (10-second cycle)
    # Independent from queue processor - runs in parallel to catch stale messages
    # Detects messages stuck in PROCESSING > 5 minutes, applies escalating recovery
    try:
        logger.info("[Startup] Starting stuck message monitoring (10-second cycle)...")
        from app.services.stuck_message_monitor_service import get_monitor_service
        from threading import Thread

        monitor_service = get_monitor_service()

        # Start monitoring in background thread
        monitor_thread = Thread(
            target=monitor_service.start_monitoring,
            daemon=True,
            name="StuckMessageMonitor"
        )
        monitor_thread.start()

        # Wait for thread to start
        time.sleep(0.5)
        if not monitor_thread.is_alive():
            raise RuntimeError("Stuck message monitor thread failed to start (not alive after 0.5s)")

        logger.info("[OK] Stuck message monitoring started (detects/recovers every 10s)")

    except Exception as exc:
        logger.error(f"[Startup] Failed to start stuck message monitoring: {exc}", exc_info=True)
        logger.warning("[Startup] Stuck message monitoring disabled - messages may remain stuck if processor crashes")

    # FLASH ORCHESTRATION - DISABLED AT STARTUP (2026-09-18)
    # Causes blocking during startup - moved to background task
    logger.info("[Startup] FLASH SLM training deferred to background (prevents startup hang)")

    # PHASE 2: Start P&L Agent Scheduler - DISABLED AT STARTUP (2026-09-18)
    # init_phase2_scheduler() is synchronous and may block startup
    logger.info("[Startup] Phase 2 P&L Agent Scheduler deferred to background (prevents startup hang)")

    # PHASE 3 FIX (2026-09-21): Initialize database pool monitoring
    try:
        from app.services.database_pool_monitor import get_pool_monitor
        monitor = get_pool_monitor(engine)
        if monitor:
            health = monitor.check_pool_health()
            logger.info(f"[OK] Database pool monitor initialized (capacity: {health.get('total_capacity')} connections)")
    except Exception as e:
        logger.warning(f"[Startup] Failed to initialize pool monitor: {e}")

    logger.info(f"[OK] {settings.APP_NAME} v{settings.APP_VERSION} started successfully")
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

# Include auth routes with /api/v1 prefix
# Router has prefix="/auth", so with /api/v1 prefix: /api/v1/auth/*
app.include_router(auth_router, prefix="/api/v1")
# Include admin/users-access-control at root level (it has its own /api/admin/ prefix)
app.include_router(users_access_control_router)
# Include v1 routes with /api/v1 prefix
app.include_router(router)
# Include configuration routes with /api/v1 prefix (dynamic config - never hardcode)
app.include_router(config_router, prefix="/api/v1")
# NOTE: message_queue_router is registered in routes.py and included via main router
# Removed duplicate registration here to avoid double-registration
# Include database queue monitoring routes (replaces Flower/Celery monitoring)
app.include_router(queue_monitoring_router)
# Include business units routes with /api/v1 prefix (BU -> Client -> Job workflow)
app.include_router(business_units_router, prefix="/api/v1")
# Include RBAC routes with /api/v1 prefix (business units, departments, role management)
app.include_router(rbac_router, prefix="/api/v1")
# Include role template modules/resources routes (modules listing for role editor)
app.include_router(role_template_modules_router)
# Include career portal routes (career site APIs - job browsing, applications)
app.include_router(career_portal_router)
# NOTE: candidate_history_router is registered in routes.py and included via main router
# Removed duplicate registration here to avoid double-registration
# Include candidate audit log routes with /api/v1/candidates prefix (audit trail)
app.include_router(candidate_audit_log_router, prefix="/api/v1")
# NOTE: candidates_router is registered in routes.py and included via main router
# Removed duplicate registration here to avoid double-registration (causes 405 routing conflicts)
# Include Desire Intelligence (SLM) routes for candidate psychology/motivation analysis
app.include_router(desire_intelligence_router, prefix="/api/v1")
# NOTE: employee_referrals_router is registered in routes.py with /api/v1/referrals prefix
# Removed duplicate registration here to avoid double-registration
# Include Flash queue metrics routes with /api/v1/flash prefix (queue health monitoring)
app.include_router(flash_queue_metrics_router, prefix="/api/v1")

# Include API Keys management routes with /api/v1 prefix (credential management for email providers)
app.include_router(api_keys_router, prefix="/api/v1")

# Include System Health monitoring (integrated Doctor + Healer + Architect)
app.include_router(system_health_router)

# Include Stuck Message Monitoring (10-second cycle for queue health)
app.include_router(monitoring_router)

# Include P&L reports routes with /api/v1 prefix (P&L reporting, financials)
# app.include_router(pl_reports_router, prefix="/api/v1")  # MISSING FILE
# Include SLM export routes with /api/v1 prefix (employee intelligence for agents)
app.include_router(slm_exports_router)
# Include system diagnostics routes (PHASE 3 FIX: operational monitoring)
app.include_router(system_diagnostics_router)
# Include Phase 2 monitoring routes with /api/v1 prefix (P&L agent monitoring)
# app.include_router(phase2_monitoring_router)  # MISSING FILE
# Include CEO dashboard routes (executive reporting)
# app.include_router(ceo_dashboard_router)  # MISSING FILE

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

assert_all_routes_have_permission_declarations(
    app,
    AuthenticationMiddleware.PUBLIC_ROUTES + AuthenticationMiddleware.PUBLIC_ROUTE_TEMPLATES,
    known_exceptions=[
        "GET /csrf/token",  # CSRF token endpoint - required for frontend to initialize
        "GET /msgraph/calendar/meetings",
        "POST /msgraph/calendar/schedule",
        "POST /msgraph/mail/send",
        "GET /rbac/modules-and-verbs",
        "GET /admin/certifications/business-units",
        "GET /admin/certifications/roles",
        "GET /message-templates/keys",
        "POST /auth/reset-password",
        "GET /queues/{message_id}",
        "GET /queues/email/{message_id}/engagement",
        "POST /candidates/create",
        "GET /config/queue-types",
        "GET /config/message-statuses",
        "GET /config/candidate-statuses",
        "GET /config/app-config",
        "GET /config/system",
        "GET /celery/test-public",
        "GET /api/v1/careers/jobs",
        "GET /api/v1/careers/jobs/{job_id}",
        "GET /flash/queue-health-pulse",
        "GET /flash/queue-bottleneck-analysis",
        "GET /api/v1/monitoring/health",
        "GET /api/v1/monitoring/stuck-messages",
        "GET /api/v1/monitoring/stuck-messages/history",
        "GET /api/v1/system/health",
        "GET /api/v1/reports/pl/company-summary",
        "GET /api/v1/reports/pl/monthly/{month}/{year}",
        "GET /api/v1/reports/pl/bu-head/{bu_id}",
        "GET /api/v1/reports/pl/partner-dashboard",
        "GET /api/v1/pnl/health",
        "GET /api/v1/slm/export/performance-scores",
        "GET /api/v1/slm/export/available-employees",
        "GET /api/v1/slm/export/utilization-snapshot",
        "GET /api/v1/slm/export/project-profitability",
        "GET /api/v1/slm/export/hiring-benchmarks",
        "GET /api/v1/slm/export/health",
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
        Health status of the application with key endpoints
    """
    endpoints = [
        "GET /health",
        "GET /status/all",
        "POST /auth/login",
        "GET /onboarding/hr/get_all_candidates",
        "GET /jobs/all",
        "GET /interviews",
        "GET /offers/all",
        "GET /timesheets",
        "GET /projects",
        "GET /admin/health"
    ]

    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "endpoints": endpoints
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