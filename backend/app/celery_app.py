"""
Celery application instance for async task processing.
Redis-backed task queue for Thunder autonomous agent, candidate processing, and background jobs.
"""
import os
from celery import Celery
from kombu import Queue, Exchange
from app.core.config import settings

# Configuration constants
TASK_HARD_TIMEOUT_SECONDS = 30 * 60
TASK_SOFT_TIMEOUT_SECONDS = 25 * 60
RESULT_EXPIRES_SECONDS = 3600
WORKER_MAX_TASKS = 100
REDIS_CONNECT_TIMEOUT_SECONDS = 5
REDIS_SOCKET_TIMEOUT_SECONDS = 5

# Create Celery app instance
redis_url = getattr(settings, 'REDIS_URL', None) or 'redis://localhost:6379/0'
app = Celery(
    'wros_backend',
    broker=redis_url,
    backend=redis_url.replace('/0', '/1') if redis_url else 'redis://localhost:6379/1',
    include=['app.tasks.candidate_tasks', 'app.tasks.notification_tasks']
)

# Configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=TASK_HARD_TIMEOUT_SECONDS,
    task_soft_time_limit=TASK_SOFT_TIMEOUT_SECONDS,
    result_expires=RESULT_EXPIRES_SECONDS,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=WORKER_MAX_TASKS,
    # Connection timeouts (fail fast if Redis unavailable)
    broker_connection_retry_on_startup=False,
    broker_connection_retry=False,
    broker_connection_max_retries=0,
    redis_socket_connect_timeout=REDIS_CONNECT_TIMEOUT_SECONDS,
    redis_socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
    # Celery Beat periodic task schedule
    beat_scheduler='celery.beat:PersistentScheduler',
    beat_schedule={
        'process-candidates-every-30-seconds': {
            'task': 'process_candidates_batch',
            'schedule': 30.0,  # Run every 30 seconds
            'options': {'queue': 'celery', 'priority': 10}
        },
    },
)

# Define queues
default_exchange = Exchange('celery', type='direct')
app.conf.task_queues = (
    Queue('default', exchange=default_exchange, routing_key='default'),
    Queue('thunder', exchange=default_exchange, routing_key='thunder'),
    Queue('email', exchange=default_exchange, routing_key='email'),
    Queue('sms', exchange=default_exchange, routing_key='sms'),
    Queue('whatsapp', exchange=default_exchange, routing_key='whatsapp'),
    Queue('slack', exchange=default_exchange, routing_key='slack'),
)

def check_redis_connection() -> bool:
    """Check if Redis broker is available. Fails fast if not."""
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Try to connect to Redis via Celery
        with app.connection() as conn:
            conn.connect()
        logger.info("✅ Redis broker connection verified")
        return True
    except Exception as error:
        logger.error(
            f"❌ CRITICAL: Redis broker unavailable: {error}\n"
            f"Redis must be running on {redis_url} for candidate creation and background tasks.\n"
            f"Please start Redis: redis-server --port 6379",
            exc_info=True
        )
        return False


if __name__ == '__main__':
    app.start()
