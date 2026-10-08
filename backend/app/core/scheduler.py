from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.logging import logger

# Kept only for add_job/remove_job callers (interviews feedback reminders, newsletters).
# It is never started in production, so those jobs do not run either; they need to
# move to SCHEDULED queue messages.
jobstores = {
    'default': MemoryJobStore()
}
scheduler = BackgroundScheduler(jobstores=jobstores, timezone="UTC")

def start_scheduler():
    """Retired. Production never started this in-process scheduler, so none of
    its jobs ever ran; background jobs now run from app.workers.scheduled_jobs_worker
    (cron, registry in app/core/scheduled_jobs.py, enabled via SCHEDULED_JOBS_ENABLED)."""
    raise RuntimeError(
        "start_scheduler() is retired: use app.workers.scheduled_jobs_worker "
        "(see app/core/scheduled_jobs.py)"
    )

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

