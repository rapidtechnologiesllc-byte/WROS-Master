import asyncio
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore

from app.core.logging import logger

# Initialize the scheduler
jobstores = {
    'default': MemoryJobStore()
}
scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")

def start_scheduler():
    """Start the APScheduler instance."""
    if not scheduler.running:
        scheduler.start()
        logger.info("[OK] APScheduler started")

def shutdown_scheduler():
    """Shutdown the APScheduler instance."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler shutdown completed")

def add_job(func, trigger, **kwargs):
    """Add a scheduled job."""
    return scheduler.add_job(func, trigger, **kwargs)

def remove_job(job_id: str):
    """Remove a scheduled job by its ID."""
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info(f"Removed scheduled job: {job_id}")
