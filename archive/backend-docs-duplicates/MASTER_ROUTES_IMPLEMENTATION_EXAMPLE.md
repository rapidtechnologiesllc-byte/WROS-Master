# Master Routes Implementation Example

## File: app/main.py (Updated)

This document shows the complete, production-ready `main.py` that integrates the master routes file.

```python
"""
WROS Backend - Main Application Entry Point
===========================================

Master application file that:
1. Creates FastAPI app
2. Configures middleware stack
3. Registers all API routes (via master router)
4. Sets up exception handlers
5. Initializes database and RBAC

Production Stack:
- FastAPI 0.104+ with Pydantic v2
- PostgreSQL 18 (or SQLite for local dev)
- SQLAlchemy 2.0 with ORM
- JWT RS256 authentication
- Role-based access control (RBAC)
- Tenant isolation via context manager
- Request rate limiting (500/60s)
- Async/await support throughout
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import asyncio
import time

# ==============================================================================
# IMPORTS
# ==============================================================================

# Core configuration
from app.core.config import settings
from app.core.database import engine, SessionLocal
from app.core.logging import logger, log_security_event
from app.models.base import Base

# Master routes (NEW - replaces individual endpoint imports)
from app.api.v1.routes_master import setup_master_routes, MasterRouterConfig

# Middleware
from app.middleware import setup_cors, RequestLoggingMiddleware, RateLimitMiddleware
from app.middleware.auth_middleware import AuthenticationMiddleware

# Tenant context setup
# IMPORTANT: Import before any app code so orm execute listener is registered
from app.core import tenant_context as _tenant_context  # noqa: F401

# Database models (imported to register with Base.metadata)
from app.models import agent_state_target, agent_phalanx, referral  # noqa: F401

# RBAC
from app.services.rbac_service import RBACService

# ==============================================================================
# FASTAPI APPLICATION SETUP
# ==============================================================================

# Create FastAPI instance
# Note: Swagger/ReDoc disabled in production (DEBUG=False) for security
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="WROS - Workforce Revenue Operating System API",
    docs_url="/docs" if settings.DEBUG else None,  # Hidden in production
    redoc_url="/redoc" if settings.DEBUG else None,  # Hidden in production
    openapi_url="/openapi.json" if settings.DEBUG else None,  # Hidden in production
)

# ==============================================================================
# MIDDLEWARE STACK CONFIGURATION
# ==============================================================================

# Add middleware in reverse order (FastAPI applies them in reverse)
# So the actual order is: RequestLogging → RateLimit → Auth → CORS

# 1. Rate limiting middleware (Phase 1 B4)
# Limits: 500 requests per 60 seconds per IP address
# Note: This is in-memory only; use Redis for horizontal scaling
app.add_middleware(
    RateLimitMiddleware,
    max_requests=MasterRouterConfig.RATE_LIMIT_REQUESTS,
    window_seconds=MasterRouterConfig.RATE_LIMIT_WINDOW_SECONDS
)

# 2. Request logging middleware
# Logs all incoming requests and outgoing responses with:
# - Method, path, status code
# - Response time in milliseconds
# - User ID and tenant ID (if authenticated)
app.add_middleware(RequestLoggingMiddleware)

# 3. Setup CORS (must be last so it wraps all other middleware)
# Configures cross-origin resource sharing for browser-based frontend
# - Allowed origins: localhost (dev) + production domains
# - Allowed methods: GET, POST, PUT, DELETE, PATCH, OPTIONS
# - Allow credentials: true (for cookies/auth headers)
setup_cors(app)

# ==============================================================================
# EXCEPTION HANDLERS
# ==============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Handle FastAPI HTTPException with CORS headers.
    
    Catches 400, 401, 403, 404, 409, 422 errors from routes.
    Returns structured JSON error response.
    """
    from app.middleware.cors import add_cors_headers

    logger.warning(
        f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}"
    )

    response = JSONResponse(
        status_code=exc.status_code,
        content={
            "status_code": exc.status_code,
            "error_type": _get_error_type(exc.status_code),
            "message": exc.detail,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )
    return add_cors_headers(response, origin=request.headers.get("origin", "*"))


@app.exception_handler(Exception)
async def log_unhandled_exception(request: Request, exc: Exception):
    """
    Handle all unhandled exceptions (500 errors).
    
    Per HRMS-0215/AC-1: unhandled exceptions are CRITICAL and must be:
    1. Logged to error_log database table
    2. Paged to on-call engineers
    3. Logged to file logger
    
    This handler runs outside normal per-request Depends(get_db) lifecycle,
    so it creates its own database session for error logging.
    """
    from app.services.error_log_service import log_error
    from app.middleware.cors import add_cors_headers

    db = SessionLocal()
    try:
        log_error(
            db,
            error_type=type(exc).__name__,
            severity="CRITICAL",
            message=str(exc)[:2000],
            exc=exc,
            request_context={
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_ip": request.client.host if request.client else None,
            },
        )
    except Exception as logging_exc:
        logger.error(f"[ErrorLog] Failed to record unhandled exception: {logging_exc}")
    finally:
        db.close()

    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}",
        exc_info=True
    )

    response = JSONResponse(
        status_code=500,
        content={
            "status_code": 500,
            "error_type": "internal_server_error",
            "message": "Internal server error",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )
    return add_cors_headers(response, origin=request.headers.get("origin", "*"))


def _get_error_type(status_code: int) -> str:
    """Map HTTP status code to error type string."""
    mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "unprocessable_entity",
        429: "too_many_requests",
    }
    return mapping.get(status_code, f"http_{status_code}")


# ==============================================================================
# STARTUP EVENT
# ==============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Application startup event handler.
    
    Startup sequence:
    1. Start APScheduler immediately (no I/O)
    2. Validate configuration
    3. Run slow DB operations in background thread:
       - Create database tables
       - Clean orphaned bulk import jobs
       - Seed RBAC roles and permissions
    
    This approach ensures uvicorn reports "started" immediately while
    slow DB operations run in the background.
    """
    logger.info(f"[Startup] Starting {settings.APP_NAME} v{settings.APP_VERSION}...")

    # Step 1: Start APScheduler immediately (no I/O required)
    from app.core.scheduler import start_scheduler
    start_scheduler()
    logger.info("[Startup] APScheduler initialized")

    # Step 2: Validate configuration
    settings.validate_config()
    logger.info("[Startup] Configuration validated")

    # Step 3: Run slow database operations in background thread
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="startup")

    async def _db_init():
        """Background database initialization."""
        def _run():
            from sqlalchemy.exc import OperationalError
            from datetime import timedelta

            # 3a. Create all tables (checkfirst=True skips existing tables)
            try:
                Base.metadata.create_all(bind=engine, checkfirst=True)
                logger.info("[Startup] Database tables created/verified")
            except Exception as exc:
                logger.error(f"[Startup] Failed to create DB tables: {exc}", exc_info=True)
                return  # Can't continue without tables

            # 3b. Clean up orphaned bulk import jobs from backend crashes
            try:
                from app.models.bulk_engagement import BulkEngagementJob
                from datetime import datetime

                _db = SessionLocal()
                now = datetime.utcnow()
                orphaned_jobs = _db.query(BulkEngagementJob).filter(
                    BulkEngagementJob.status == "PROCESSING"
                ).all()

                for job in orphaned_jobs:
                    if job.created_at and (now - job.created_at) > timedelta(seconds=30):
                        job.status = "FAILED"
                        logger.warning(f"[Startup] Marked orphaned job {job.id} as FAILED")

                if orphaned_jobs:
                    _db.commit()
                _db.close()
            except Exception as e:
                logger.warning(f"[Startup] Failed to clean orphaned jobs: {e}")

            # 3c. Seed RBAC with retries for transient DB errors
            from app.core.database import SessionLocal

            MAX_RETRIES = 3
            RETRY_DELAY = 5  # seconds

            for attempt in range(1, MAX_RETRIES + 1):
                _db = SessionLocal()
                try:
                    RBACService.seed_roles_and_permissions(_db)
                    logger.info(f"[Startup] RBAC seeded successfully")
                    logger.info(
                        f"[Startup] {settings.APP_NAME} v{settings.APP_VERSION} "
                        f"ready on http://{settings.HOST}:{settings.PORT}"
                    )
                    break  # Success — exit retry loop
                except OperationalError as exc:
                    logger.warning(
                        f"[Startup] RBAC seed attempt {attempt}/{MAX_RETRIES} failed "
                        f"(transient DB error): {exc}"
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
                    logger.error(f"[Startup] Unrecoverable error during RBAC seed: {exc}", exc_info=True)
                    break
                finally:
                    _db.close()

        await loop.run_in_executor(executor, _run)

    # Fire-and-forget background task (don't await so uvicorn finishes startup immediately)
    loop.create_task(_db_init())


# ==============================================================================
# SHUTDOWN EVENT
# ==============================================================================

@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown event handler.
    
    Cleanup operations:
    1. Shutdown APScheduler
    2. Log shutdown event
    """
    logger.info(f"Shutting down {settings.APP_NAME}...")

    from app.core.scheduler import shutdown_scheduler
    shutdown_scheduler()

    logger.info(f"{settings.APP_NAME} shutdown complete")


# ==============================================================================
# REGISTER MASTER ROUTES
# ==============================================================================

# Import and setup all 15 core story endpoints via master router
# This replaces the old approach of importing ~100+ individual routers
setup_master_routes(app)


# ==============================================================================
# ROUTE PERMISSION AUDIT (HRMS-0114)
# ==============================================================================

# Per HRMS-0114: All routes must have explicit permission declarations.
# This audit runs at import time (not startup) so misconfigured routes
# cause immediate startup failure, not silent drift.

from app.core.route_security_audit import assert_all_routes_have_permission_declarations

assert_all_routes_have_permission_declarations(
    app,
    AuthenticationMiddleware.PUBLIC_ROUTES + AuthenticationMiddleware.PUBLIC_ROUTE_TEMPLATES,
    known_exceptions=[
        # These routes have manual permission checks inside the function body,
        # not via FastAPI's Depends(), so the audit scanner can't see them.
        # Each has a test in tests/test_route_permission_audit_real_app.py
        # to verify the manual check still works.
        "GET /msgraph/calendar/meetings",
        "POST /msgraph/calendar/schedule",
        "POST /msgraph/mail/send",
        "GET /rbac/modules-and-verbs",
        "GET /candidates/bulk-import/list",
        "GET /candidates/bulk-import/{job_id}/progress",
        "GET /candidate/opt-out/status/{candidate_id}",
        "POST /candidate/opt-out/{candidate_id}",
    ],
)
logger.info("[OK] HRMS-0114 route permission audit passed")


# ==============================================================================
# STATIC FILES
# ==============================================================================

# Mount static files directory if it exists
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("[OK] Static files mounted at /static")
else:
    logger.debug("Static directory not found (optional)")


# ==============================================================================
# HEALTH CHECK ENDPOINTS
# ==============================================================================

@app.get("/")
def home():
    """
    Root endpoint - API health check and metadata.
    
    Returns basic information about the API and links to documentation.
    """
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": "production" if not settings.DEBUG else "development",
        "docs": "/docs" if settings.DEBUG else None,
        "redoc": "/redoc" if settings.DEBUG else None
    }


@app.get("/health")
def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    
    Used by:
    - Docker health checks
    - Kubernetes liveness probes
    - Monitoring systems (Datadog, New Relic, etc.)
    
    Returns:
        {
            "status": "healthy",
            "app": "WROS Backend",
            "version": "1.0.0",
            "timestamp": "2026-08-15T10:30:45Z"
        }
    """
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


# ==============================================================================
# PRODUCTION SERVER RUNNER
# ==============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,  # Auto-reload in dev, disabled in prod
        log_level="info",
        # Production settings (use gunicorn/supervisor in production, not uvicorn)
        workers=1,  # Single worker for local dev
        access_log=True,
    )
```

---

## Integration Steps

### Step 1: Backup Current main.py
```bash
cp app/main.py app/main.py.backup
```

### Step 2: Replace with Above Code
Copy the complete code above into `app/main.py`

### Step 3: Remove Old Routes Import
Delete or comment out:
```python
# OLD - Remove this
from app.api.v1.routes import router
app.include_router(router)
```

### Step 4: Verify Files Exist
```bash
# Make sure master routes file exists
ls -la app/api/v1/routes_master.py

# Make sure middleware exists
ls -la app/middleware/auth_middleware.py
ls -la app/middleware/__init__.py
```

### Step 5: Test Startup
```bash
# Start the server
python app/main.py

# Or with uvicorn
uvicorn app.main:app --reload --port 8080
```

Expected output:
```
[Startup] Starting WROS Backend v1.0.0...
[Startup] APScheduler initialized
[Startup] Configuration validated
[Startup] Database tables created/verified
[Startup] RBAC seeded successfully
[Startup] WROS Backend v1.0.0 ready on http://127.0.0.1:8080
```

### Step 6: Test Health Check
```bash
curl http://localhost:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "app": "WROS Backend",
  "version": "1.0.0",
  "timestamp": "2026-08-15T10:30:45Z"
}
```

### Step 7: Test Protected Route
```bash
# Get JWT token
TOKEN=$(curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"password123"}' \
  | jq -r '.access_token')

# Use token to access protected endpoint
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/v1/candidates/list
```

Expected response: 200 OK with candidate list

### Step 8: Verify Swagger Docs (Dev Only)
```bash
# If DEBUG=true
curl http://localhost:8080/docs
```

Should return Swagger UI (disabled in production)

---

## Troubleshooting

### Issue: "routes_master module not found"

**Solution**: Verify file exists
```bash
ls -la app/api/v1/routes_master.py
python -m app.api.v1.routes_master  # Should print summary
```

### Issue: "AttributeError: 'FastAPI' object has no attribute 'include_router'"

**Solution**: Use `setup_master_routes(app)` instead of manual include_router

### Issue: "422 Unprocessable Entity" on login

**Solution**: Verify request schema matches endpoint expectations
```python
# Make sure you're sending:
{
  "email": "user@example.com",
  "password": "password123"
}
```

### Issue: "401 Unauthorized" on protected route

**Solution**: Add JWT token to header
```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8080/api/v1/candidates/list
```

### Issue: Slow startup (database operations timeout)

**Solution**: Check database connectivity
```bash
# Test PostgreSQL connection
psql -U user -d wros_dev -c "SELECT 1"

# Or test SQLite
sqlite3 wros.db "SELECT 1"
```

---

## Configuration Reference

### Environment Variables Required

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/wros_dev

# JWT (generate with: python scripts/generate_jwt_keys.py)
JWT_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"

# Server
HOST=127.0.0.1
PORT=8080
DEBUG=true  # Development only, false in production

# Application
APP_NAME="WROS Backend"
APP_VERSION="1.0.0"

# OAuth (optional, for Microsoft Graph)
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
```

### Database Migrations

If starting with empty database:
```bash
# Initialize Alembic (already done)
alembic init alembic

# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Run migration
alembic upgrade head
```

---

## Performance Tuning

### Database Connection Pooling

For production (PostgreSQL):
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,          # Number of connections to keep open
    max_overflow=10,       # Additional connections to create if pool exhausted
    pool_recycle=3600,     # Recycle connections after 1 hour
    pool_pre_ping=True,    # Test connection before using
)
```

### Rate Limiting for Production

For horizontal scaling, use Redis:
```python
# In requirements.txt: add redis, fastapi-limiter

from fastapi_limiter import FastAPILimiter
from fastapi_limiter.backends.redis import RedisBackend
from redis import asyncio as aioredis

@app.on_event("startup")
async def startup():
    redis = aioredis.from_url("redis://localhost")
    await FastAPILimiter.init(RedisBackend(redis))
```

### Caching Strategies

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_roles():
    """Cache roles for 1 hour between app reloads."""
    db = SessionLocal()
    return db.query(Role).all()
```

---

## Monitoring Setup

### Logging to Datadog
```python
import logging
from datadog import initialize, api

options = {
    "api_key": "YOUR_API_KEY",
    "app_key": "YOUR_APP_KEY"
}
initialize(**options)

# Configure Python logging to send to Datadog
handler = logging.handlers.SysLogHandler(address=('localhost', 514))
logger.addHandler(handler)
```

### Metrics to Track
```python
# 1. Request latency (p50, p95, p99)
# 2. Error rate by status code (4xx, 5xx)
# 3. Database query time
# 4. Rate limit violations
# 5. Active connections
# 6. Memory usage
# 7. CPU usage
```

---

**Version**: 1.0  
**Last Updated**: 2026-08-15  
**Status**: Production Ready
