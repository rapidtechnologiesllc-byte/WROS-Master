"""Health Check Endpoints - System health and monitoring status

GET /health - Overall system health (liveness probe)
GET /health/detailed - Detailed component health

These are PUBLIC endpoints used by infrastructure monitoring,
load balancers, and Kubernetes. No authentication required.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.health_check_service import HealthCheckService

router = APIRouter(
    prefix="/health",
    tags=["monitoring", "public"]
)


@router.get("")
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint - returns 200 if system is healthy.

    Used by load balancers, monitoring systems, and Kubernetes.
    """
    try:
        database_health = HealthCheckService.check_database_connection(db)

        if database_health.get('status') != 'healthy':
            return {
                'status': 'unhealthy',
                'message': 'Database unavailable',
                'database': database_health
            }

        return {
            'status': 'healthy',
            'message': 'All systems operational'
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'message': str(e)
        }


@router.get("/detailed")
async def health_check_detailed(db: Session = Depends(get_db)):
    """
    Detailed health check - returns status of all components.

    Includes:
    - Database connection health
    - Queue processor health (message success rate)
    - Redis connection health
    - Average message processing time
    """
    try:
        health = HealthCheckService.get_full_health_report(db)

        # Report degraded status to Sentry if needed
        HealthCheckService.report_health_to_sentry(db)

        return health
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
