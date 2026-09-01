# main.py - HRMS FastAPI Backend
# Refactored for non-blocking startup: HTTP server starts immediately,
# all database/role operations deferred to first request (lazy init)

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pathlib import Path
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging import logger
from app.middleware import setup_cors, RequestLoggingMiddleware

# Global flag for initialization state
_INITIALIZED = False
_INIT_ERROR = None


async def _lazy_init():
    """Initialize database, routes, and RBAC on first request (lazy)."""
    global _INITIALIZED, _INIT_ERROR

    if _INITIALIZED:
        return

    try:
        logger.info("[Startup] Lazy initialization starting...")

        # Step 1: Import database (creates connection pool, doesn't execute queries)
        logger.info("[Init] Importing database engine...")
        from app.core.database import engine

        # Step 2: Import all models to register with SQLAlchemy
        logger.info("[Init] Registering models...")
        from app.models.base import Base
        import app.models.user  # noqa: F401
        import app.models.candidate  # noqa: F401
        import app.models.business_unit  # noqa: F401
        import app.models.role_template  # noqa: F401
        import app.models.permission  # noqa: F401
        import app.models.message_queue  # noqa: F401
        from app.models import agent_state_target  # noqa: F401
        from app.models import agent_phalanx  # noqa: F401
        from app.models import referral  # noqa: F401

        # Step 3: Create all tables (first real DB operation)
        logger.info("[Init] Creating database tables...")
        Base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("[Init] Database tables created/verified")

        # Step 4: Initialize org structure (positions, etc)
        logger.info("[Init] Initializing organizational structure...")
        from app.core.database import SessionLocal
        from app.services.org_structure_service import init_default_positions
        db = SessionLocal()
        try:
            result = init_default_positions(db)
            logger.info(f"[Init] Org positions: created={result['created']}, updated={result['updated']}")
        finally:
            db.close()

        # Step 5: Register tenant context listener
        logger.info("[Init] Registering tenant context...")
        from app.core import tenant_context  # noqa: F401

        _INITIALIZED = True
        logger.info("[OK] Lazy initialization complete - database ready")

    except Exception as e:
        _INIT_ERROR = str(e)
        logger.error(f"[Init] CRITICAL: Lazy initialization failed: {e}", exc_info=True)
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context - runs after server starts."""
    # Server is now running, do database initialization
    try:
        logger.info("[Lifespan] Starting lazy initialization...")
        await _lazy_init()

        # Include routes after models are registered
        logger.info("[Lifespan] Including API routes...")
        try:
            from app.api.v1.routes import router
            app.include_router(router, prefix="/api/v1")
            logger.info("[OK] Routes included successfully")
        except Exception as route_err:
            logger.error(f"[Routes] Failed to include routes: {route_err}", exc_info=True)
            raise

    except Exception as e:
        logger.error(f"[Lifespan] Initialization failed: {e}", exc_info=True)
        raise

    yield  # Server runs here

    # Shutdown - cleanup resources
    logger.info("Shutting down...")


# Create FastAPI app with lifespan
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="HRMS Onboarding and Authentication API",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Setup CORS middleware (fast, no DB needed)
setup_cors(app)

# Add authentication middleware
from app.middleware.auth_middleware import AuthenticationMiddleware
app.add_middleware(AuthenticationMiddleware)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)


@app.exception_handler(Exception)
async def log_unhandled_exception(request: Request, exc: Exception):
    """Global exception handler - logs to DB if available."""
    try:
        from app.core.database import SessionLocal
        from app.services.error_log_service import log_error
        db = SessionLocal()
        log_error(
            db, error_type=type(exc).__name__, severity="CRITICAL",
            message=str(exc)[:2000], exc=exc,
            request_context={"method": request.method, "path": request.url.path},
        )
        db.close()
    except Exception as logging_exc:
        logger.error(f"[ErrorLog] Could not log to DB: {logging_exc}")

    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    response = JSONResponse(status_code=500, content={"detail": "Internal server error."})
    origin = request.headers.get("origin", "http://localhost:3000")
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions (401, 403, 404, etc)."""
    response = JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    origin = request.headers.get("origin", "http://localhost:3000")
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


@app.get("/")
def home():
    """Root endpoint - API health check."""
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "initialized": _INITIALIZED,
        "docs": "/docs" if settings.DEBUG else "N/A",
    }


@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    if _INIT_ERROR:
        return JSONResponse(
            status_code=503,
            content={"status": "initializing", "error": _INIT_ERROR}
        )

    return {
        "status": "healthy" if _INITIALIZED else "initializing",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# Routes will be included after app starts (in lifespan)

# Mount static files if available
static_dir = Path("static")
if static_dir.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("[OK] Static files mounted at /static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level="info"
    )
