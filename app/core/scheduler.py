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

        # ── Daily job: expire 90-day BU ownerships ────────────────────────────
        try:
            from app.core.database import SessionLocal
            from app.services.candidate_pool_service import expire_bu_ownerships

            async def _run_expiry():
                db = SessionLocal()
                try:
                    count = expire_bu_ownerships(db)
                    if count:
                        logger.info(f"[scheduler] Expired {count} BU ownership lock(s)")
                except Exception as exc:
                    logger.error(f"[scheduler] BU ownership expiry error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_expiry,
                trigger="cron",
                hour=0,
                minute=0,
                id="expire_bu_ownerships",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled daily BU ownership expiry job (00:00 UTC)")
        except Exception as exc:
            logger.warning(f"Could not register BU ownership expiry scheduler: {exc}")

        # ── Every 15 min: poll for candidate email replies ─────────────────
        # HRMS-0401/0409 bug fix -- a candidate's reply to the AI recruiter's
        # missing-fields email was never actually processed by anything;
        # see app.services.ai_conversation_service.poll_all_awaiting_candidates()
        # for the full explanation.
        try:
            from app.core.database import SessionLocal
            from app.services.ai_conversation_service import poll_all_awaiting_candidates

            async def _run_reply_poll():
                db = SessionLocal()
                try:
                    result = poll_all_awaiting_candidates(db)
                    if result["checked"]:
                        logger.info(f"[scheduler] Candidate reply poll: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] Candidate reply poll error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_reply_poll,
                trigger="interval",
                minutes=15,
                id="poll_candidate_replies",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled candidate reply poll job (every 15 min)")
        except Exception as exc:
            logger.warning(f"Could not register candidate reply poll scheduler: {exc}")


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

