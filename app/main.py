# main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.core.config import settings
from app.core.database import engine
from app.core.logging import logger
from app.models.base import Base
from app.api.v1.routes import router
from app.middleware import setup_cors, RequestLoggingMiddleware


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="HRMS Onboarding and Authentication API",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Setup CORS middleware
setup_cors(app)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Optional: Add rate limiting middleware
# from app.middleware import RateLimitMiddleware
# app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)


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
            try:
                # checkfirst=True skips tables that already exist — much faster on restarts
                Base.metadata.create_all(bind=engine, checkfirst=True)
                logger.info("[OK] Database tables initialized")

                from app.core.database import SessionLocal
                from app.services.rbac_service import RBACService
                _db = SessionLocal()
                try:
                    RBACService.seed_roles_and_permissions(_db)
                finally:
                    _db.close()

                logger.info(f"[OK] {settings.APP_NAME} v{settings.APP_VERSION} started successfully")
                logger.info(f"[OK] Server running on http://{settings.HOST}:{settings.PORT}")
            except Exception as exc:
                logger.error(f"Background startup error: {exc}", exc_info=True)

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