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

        # ── Every 30 min: SLA_MONITORING_JOB (S-020/HRMS-0420) ──────────────
        try:
            from app.core.database import SessionLocal
            from app.services.sla_monitoring_service import detect_and_resolve_no_contact_breaches

            async def _run_sla_monitoring():
                db = SessionLocal()
                try:
                    result = detect_and_resolve_no_contact_breaches(db)
                    if result["created"] or result["resolved"]:
                        logger.info(f"[scheduler] SLA monitoring: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] SLA monitoring error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_sla_monitoring,
                trigger="interval",
                minutes=30,
                id="sla_monitoring_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled SLA monitoring job (every 30 min)")
        except Exception as exc:
            logger.warning(f"Could not register SLA monitoring scheduler: {exc}")

        # ── Every 15 min: FOLLOW_UP_EXECUTION_JOB (S-041/HRMS-0441) ─────────
        try:
            from app.core.database import SessionLocal
            from app.services.follow_up_scheduler_service import run_follow_up_execution_job

            async def _run_followup_execution():
                db = SessionLocal()
                try:
                    result = run_follow_up_execution_job(db)
                    if result["processed"]:
                        logger.info(f"[scheduler] Follow-up execution: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] Follow-up execution error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_followup_execution,
                trigger="interval",
                minutes=15,
                id="follow_up_execution_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled follow-up execution job (every 15 min)")
        except Exception as exc:
            logger.warning(f"Could not register follow-up execution scheduler: {exc}")

        # ── Every 30 min: NO_RESPONSE_DETECTION_JOB (S-042/HRMS-0442) ───────
        try:
            from app.core.database import SessionLocal
            from app.services.no_response_detection_service import run_no_response_detection_job

            async def _run_no_response_detection():
                db = SessionLocal()
                try:
                    result = run_no_response_detection_job(db)
                    if result["first_detected"] or result["post_third"]:
                        logger.info(f"[scheduler] No-response detection: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] No-response detection error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_no_response_detection,
                trigger="interval",
                minutes=30,
                id="no_response_detection_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled no-response detection job (every 30 min)")
        except Exception as exc:
            logger.warning(f"Could not register no-response detection scheduler: {exc}")

        # ── Every 30 min: GHOSTING_DETECTION_JOB (S-043/HRMS-0443) ──────────
        try:
            from app.core.database import SessionLocal
            from app.services.ghosting_detection_service import run_ghosting_detection_job

            async def _run_ghosting_detection():
                db = SessionLocal()
                try:
                    result = run_ghosting_detection_job(db)
                    if result["ghosted"]:
                        logger.info(f"[scheduler] Ghosting detection: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] Ghosting detection error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_ghosting_detection,
                trigger="interval",
                minutes=30,
                id="ghosting_detection_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled ghosting detection job (every 30 min)")
        except Exception as exc:
            logger.warning(f"Could not register ghosting detection scheduler: {exc}")

        # ── Every 15 min: CAMPAIGN_EXECUTION_JOB (S-044/HRMS-0444) ──────────
        try:
            from app.core.database import SessionLocal
            from app.services.outreach_campaign_service import run_campaign_execution_job

            async def _run_campaign_execution():
                db = SessionLocal()
                try:
                    result = run_campaign_execution_job(db)
                    if result["processed"]:
                        logger.info(f"[scheduler] Campaign execution: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] Campaign execution error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_campaign_execution,
                trigger="interval",
                minutes=15,
                id="campaign_execution_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled campaign execution job (every 15 min)")
        except Exception as exc:
            logger.warning(f"Could not register campaign execution scheduler: {exc}")

        # ── Every 30 min: REACTIVATION_JOB (S-045/HRMS-0445) ────────────────
        try:
            from app.core.database import SessionLocal
            from app.services.reactivation_campaign_service import run_reactivation_job

            async def _run_reactivation():
                db = SessionLocal()
                try:
                    result = run_reactivation_job(db)
                    if result["processed"]:
                        logger.info(f"[scheduler] Reactivation: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] Reactivation error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_reactivation,
                trigger="interval",
                minutes=30,
                id="reactivation_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled reactivation job (every 30 min)")
        except Exception as exc:
            logger.warning(f"Could not register reactivation scheduler: {exc}")

        # ── Daily: REACTIVATION_RESCHEDULE_JOB (S-045/HRMS-0445) ────────────
        # No archive/terminal state per Avinash's explicit override -- see
        # reactivation_campaign_service module docstring. This is the "keep
        # trying till I succeed" mechanism: a completed reactivation
        # campaign with no reply gets queued for another attempt, forever.
        try:
            from app.core.database import SessionLocal
            from app.services.reactivation_campaign_service import run_reactivation_reschedule_job

            async def _run_reactivation_reschedule():
                db = SessionLocal()
                try:
                    result = run_reactivation_reschedule_job(db)
                    if result["rescheduled"]:
                        logger.info(f"[scheduler] Reactivation reschedule: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] Reactivation reschedule error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_reactivation_reschedule,
                trigger="cron",
                hour=1,
                minute=0,
                id="reactivation_reschedule_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled reactivation reschedule job (01:00 UTC daily)")
        except Exception as exc:
            logger.warning(f"Could not register reactivation reschedule scheduler: {exc}")


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

