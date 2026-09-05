"""
Celery application instance for async task processing.
Redis-backed task queue for Thunder autonomous agent, candidate processing, and background jobs.
"""
import os
from celery import Celery
from app.core.config import settings

# Configuration constants
TASK_HARD_TIMEOUT_SECONDS = 30 * 60
TASK_SOFT_TIMEOUT_SECONDS = 25 * 60
RESULT_EXPIRES_SECONDS = 3600
WORKER_MAX_TASKS = 100

# Create Celery app instance
app = Celery(
    'wros_backend',
    broker=settings.REDIS_URL or 'redis://localhost:6379/0',
    backend=settings.REDIS_URL or 'redis://localhost:6379/1',
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
)

if __name__ == '__main__':
    app.start()
