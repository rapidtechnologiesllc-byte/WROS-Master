"""
System Diagnostics API - Operational monitoring endpoints.

Provides visibility into system health: database pool, permission service,
circuit breaker status, cache performance.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db, engine
from app.services.database_pool_monitor import get_pool_monitor
from app.services.permission_circuit_breaker import get_permission_breaker
from app.services.permission_cache import get_permission_cache
from app.core.dependencies import require_role_template_permission

router = APIRouter(prefix="/system", tags=["system-diagnostics"])


@router.get(
    "/health/database-pool",
    dependencies=[Depends(require_role_template_permission("system-health", "view"))]
)
def get_database_pool_health(db: Session = Depends(get_db)):
    """Get database connection pool health metrics"""
    monitor = get_pool_monitor(engine)
    if monitor is None:
        return {"status": "UNKNOWN", "error": "Monitor not initialized"}

    health = monitor.check_pool_health()
    trend = monitor.get_trend()

    return {
        **health,
        "trend": trend["trend"] if trend else []
    }


@router.get(
    "/health/permission-circuit",
    dependencies=[Depends(require_role_template_permission("system-health", "view"))]
)
def get_permission_circuit_status():
    """Get permission service circuit breaker status"""
    breaker = get_permission_breaker()
    return {
        "service": "permission",
        "circuit_state": breaker.get_state()
    }


@router.get(
    "/health/permission-cache",
    dependencies=[Depends(require_role_template_permission("system-health", "view"))]
)
def get_permission_cache_stats():
    """Get permission cache statistics"""
    cache = get_permission_cache()
    return {
        "service": "permission_cache",
        "cache_stats": cache.get_stats()
    }


@router.get(
    "/health/summary",
    dependencies=[Depends(require_role_template_permission("system-health", "view"))]
)
def get_system_health_summary(db: Session = Depends(get_db)):
    """Get overall system health summary"""
    pool_monitor = get_pool_monitor(engine)
    breaker = get_permission_breaker()
    cache = get_permission_cache()

    pool_health = pool_monitor.check_pool_health() if pool_monitor else {}
    breaker_state = breaker.get_state()
    cache_stats = cache.get_stats()

    overall_status = "HEALTHY"
    issues = []

    if pool_health.get("status") == "CRITICAL":
        overall_status = "CRITICAL"
        issues.append(f"Database pool at {pool_health.get('utilization_percent', 0):.0f}%")

    if breaker_state.get("state") == "OPEN":
        overall_status = "WARNING" if overall_status == "HEALTHY" else "CRITICAL"
        issues.append(f"Permission service circuit OPEN ({breaker_state.get('failure_count')} failures)")

    return {
        "status": overall_status,
        "timestamp": pool_health.get("timestamp"),
        "issues": issues,
        "components": {
            "database_pool": pool_health,
            "permission_circuit": breaker_state,
            "permission_cache": cache_stats
        }
    }


@router.post(
    "/health/cache-invalidate",
    dependencies=[Depends(require_role_template_permission("system-health", "edit"))]
)
def invalidate_permission_cache(user_id: str = None):
    """
    Invalidate permission cache.

    Args:
        user_id: If provided, invalidate only this user's permissions.
                 If omitted, clears entire cache.
    """
    cache = get_permission_cache()

    if user_id:
        cache.invalidate(f"{user_id}:1")
        return {"message": f"Invalidated cache for user {user_id}"}
    else:
        cache.invalidate()
        return {"message": "Cleared entire permission cache"}
