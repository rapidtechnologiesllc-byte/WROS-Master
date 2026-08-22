"""
Celery Configuration
====================

Async task queue for background jobs:
- Bulk candidate imports
- Resume parsing
- Email sending
- Thunder autonomous cycles
- Report generation

Uses Redis as message broker (free, no extra setup needed).
Tasks are logged to message queue dashboard via admin_queue endpoints.
"""

from celery import Celery
import os
from app.core.config import settings

# Initialize Celery
celery_app = Celery(
    "hrms",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
)

# Celery Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes hard limit
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
    worker_prefetch_multiplier=1,  # One task at a time (don't queue up)
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
)

# Auto-discover tasks from all apps
celery_app.autodiscover_tasks(["app.tasks"])
