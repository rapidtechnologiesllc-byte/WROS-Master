"""Health Check Service - Monitor queue processor and database connection health

Phase 4: Monitoring & Alerting
Tracks queue health, database connection status, error rates.
"""
import os
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class HealthCheckService:
    """Monitor system health: queue processor, database, Redis."""

    @staticmethod
    def check_database_connection(db: Session) -> Dict[str, Any]:
        """
        Check database connection health.

        Returns:
            {
                'status': 'healthy' | 'unhealthy',
                'response_time_ms': float,
                'last_check': str (ISO format)
            }
        """
        try:
            start_time = datetime.utcnow()
            result = db.execute(text("SELECT 1"))
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            if response_time > 1000:  # > 1 second is slow
                logger.warning(f"[HealthCheck] Database slow: {response_time:.0f}ms")

            return {
                'status': 'healthy',
                'response_time_ms': response_time,
                'last_check': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"[HealthCheck] Database connection failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'last_check': datetime.utcnow().isoformat()
            }

    @staticmethod
    def check_queue_processor_health(db: Session) -> Dict[str, Any]:
        """
        Check queue processor health by analyzing recent message statuses.

        Returns:
            {
                'status': 'healthy' | 'degraded' | 'unhealthy',
                'recent_messages': int,
                'completed': int,
                'failed': int,
                'pending': int,
                'success_rate': float,
                'avg_processing_time_seconds': float
            }
        """
        try:
            from app.models.channel_queue import ChannelQueueItem

            # Last 100 messages or last 24 hours
            cutoff = datetime.utcnow() - timedelta(hours=24)
            recent = db.query(ChannelQueueItem).filter(
                ChannelQueueItem.created_at >= cutoff
            ).order_by(ChannelQueueItem.created_at.desc()).limit(100).all()

            if not recent:
                return {
                    'status': 'healthy',
                    'recent_messages': 0,
                    'message': 'No recent messages to analyze'
                }

            completed = sum(1 for m in recent if m.status == 'COMPLETED')
            failed = sum(1 for m in recent if m.status == 'FAILED')
            pending = sum(1 for m in recent if m.status in ['PENDING', 'IN_PROGRESS'])

            success_rate = completed / len(recent) if recent else 0
            status = 'healthy' if success_rate >= 0.95 else ('degraded' if success_rate >= 0.7 else 'unhealthy')

            # Calculate average processing time
            processing_times = []
            for msg in recent:
                if msg.completed_at and msg.created_at:
                    delta = (msg.completed_at - msg.created_at).total_seconds()
                    if 0 < delta < 3600:  # Sanity check: 0-1 hour
                        processing_times.append(delta)

            avg_time = sum(processing_times) / len(processing_times) if processing_times else 0

            result = {
                'status': status,
                'recent_messages': len(recent),
                'completed': completed,
                'failed': failed,
                'pending': pending,
                'success_rate': round(success_rate * 100, 1),
                'avg_processing_time_seconds': round(avg_time, 2)
            }

            if status != 'healthy':
                logger.warning(f"[HealthCheck] Queue processor degraded: {status} (success={success_rate*100:.1f}%)")

            return result

        except Exception as e:
            logger.error(f"[HealthCheck] Queue health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }

    @staticmethod
    def check_redis_connection() -> Dict[str, Any]:
        """
        Check Redis connection health (used by Celery).

        Returns:
            {
                'status': 'healthy' | 'unhealthy',
                'response_time_ms': float
            }
        """
        try:
            import redis
            from datetime import datetime

            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            r = redis.from_url(redis_url, decode_responses=True)

            start_time = datetime.utcnow()
            r.ping()
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return {
                'status': 'healthy',
                'response_time_ms': response_time
            }
        except Exception as e:
            logger.error(f"[HealthCheck] Redis connection failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }

    @staticmethod
    def get_full_health_report(db: Session) -> Dict[str, Any]:
        """Get comprehensive health report for all systems."""
        import os

        database_health = HealthCheckService.check_database_connection(db)
        queue_health = HealthCheckService.check_queue_processor_health(db)
        redis_health = HealthCheckService.check_redis_connection()

        # Aggregate component statuses
        component_statuses = [
            database_health.get('status'),
            queue_health.get('status'),
            redis_health.get('status')
        ]

        # Overall status: unhealthy if any component is unhealthy,
        # degraded if any component is degraded but none are unhealthy,
        # healthy if all components are healthy
        if 'unhealthy' in component_statuses:
            overall_status = 'unhealthy'
        elif 'degraded' in component_statuses:
            overall_status = 'degraded'
        else:
            overall_status = 'healthy'

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'database': database_health,
            'queue_processor': queue_health,
            'redis': redis_health,
            'overall_status': overall_status
        }

    @staticmethod
    def report_health_to_sentry(db: Session) -> None:
        """Send health report to Sentry if any component is unhealthy."""
        try:
            health = HealthCheckService.get_full_health_report(db)

            # Check for any unhealthy components
            unhealthy = [
                k for k, v in health.items()
                if isinstance(v, dict) and v.get('status') == 'unhealthy'
            ]

            if unhealthy:
                from app.services.sentry_integration import SentryIntegration

                SentryIntegration.capture_message(
                    f"System health degraded: {', '.join(unhealthy)}",
                    level="warning",
                    context=health
                )
                logger.warning(f"[HealthCheck] Sent health alert to Sentry: {unhealthy}")

        except Exception as e:
            logger.error(f"[HealthCheck] Failed to report health: {e}")
