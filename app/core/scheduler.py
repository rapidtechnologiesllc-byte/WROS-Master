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

        # ── Every 6 hours: ABANDONMENT_SCORING_JOB (S-046/HRMS-0446) ────────
        try:
            from app.core.database import SessionLocal
            from app.services.abandonment_scoring_service import run_abandonment_scoring_job

            async def _run_abandonment_scoring():
                db = SessionLocal()
                try:
                    result = run_abandonment_scoring_job(db)
                    if result["scored"]:
                        logger.info(f"[scheduler] Abandonment scoring: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] Abandonment scoring error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_abandonment_scoring,
                trigger="interval",
                hours=6,
                id="abandonment_scoring_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled abandonment scoring job (every 6 hours)")
        except Exception as exc:
            logger.warning(f"Could not register abandonment scoring scheduler: {exc}")

        # ── Every 10 min: REMINDER_EXECUTION_JOB (S-050/HRMS-0450) ──────────
        try:
            from app.core.database import SessionLocal
            from app.services.interview_reminder_service import run_reminder_execution_job

            async def _run_reminder_execution():
                db = SessionLocal()
                try:
                    result = run_reminder_execution_job(db)
                    if result["processed"]:
                        logger.info(f"[scheduler] Interview reminder execution: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] Interview reminder execution error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_reminder_execution,
                trigger="interval",
                minutes=10,
                id="interview_reminder_execution_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled interview reminder execution job (every 10 min)")
        except Exception as exc:
            logger.warning(f"Could not register interview reminder execution scheduler: {exc}")

        # ── Every 5 min: NO_SHOW_DETECTION_JOB (S-052/HRMS-0452) ────────────
        try:
            from app.core.database import SessionLocal
            from app.services.interview_no_show_service import run_no_show_detection_job

            async def _run_no_show_detection():
                db = SessionLocal()
                try:
                    result = run_no_show_detection_job(db)
                    if result["processed"]:
                        logger.info(f"[scheduler] No-show detection: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] No-show detection error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_no_show_detection,
                trigger="interval",
                minutes=5,
                id="no_show_detection_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled no-show detection job (every 5 min)")
        except Exception as exc:
            logger.warning(f"Could not register no-show detection scheduler: {exc}")

        # ── Every 6 hours: DOCUMENT_REMINDER_JOB (S-057/HRMS-0457) ──────────
        try:
            from app.core.database import SessionLocal
            from app.services.document_collection_service import run_document_reminder_job

            async def _run_document_reminder():
                db = SessionLocal()
                try:
                    result = run_document_reminder_job(db)
                    if result["processed"]:
                        logger.info(f"[scheduler] Document reminder: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] Document reminder error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_document_reminder,
                trigger="interval",
                hours=6,
                id="document_reminder_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled document reminder job (every 6 hours)")
        except Exception as exc:
            logger.warning(f"Could not register document reminder scheduler: {exc}")

        # ── Every 6 hours: JOINING_READINESS_JOB (S-058/HRMS-0458) ──────────
        try:
            from app.core.database import SessionLocal
            from app.services.joining_readiness_service import run_joining_readiness_job

            async def _run_joining_readiness():
                db = SessionLocal()
                try:
                    result = run_joining_readiness_job(db)
                    if result["processed"]:
                        logger.info(f"[scheduler] Joining readiness: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] Joining readiness error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_joining_readiness,
                trigger="interval",
                hours=6,
                id="joining_readiness_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled joining readiness job (every 6 hours)")
        except Exception as exc:
            logger.warning(f"Could not register joining readiness scheduler: {exc}")

        # ── Every 30 min: DAILY_DIGEST_JOB (S-065/HRMS-0465) ────────────────
        try:
            from app.core.database import SessionLocal
            from app.services.daily_digest_service import run_daily_digest_job

            async def _run_daily_digest():
                db = SessionLocal()
                try:
                    result = run_daily_digest_job(db)
                    if result["sent"]:
                        logger.info(f"[scheduler] Daily digest: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] Daily digest error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_daily_digest,
                trigger="interval",
                minutes=30,
                id="daily_digest_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled daily digest job (every 30 minutes, checks each recruiter's local 8 AM)")
        except Exception as exc:
            logger.warning(f"Could not register daily digest scheduler: {exc}")

        # ── Every 4 hours: ENGAGEMENT_METRICS_JOB (S-070/HRMS-0470) ─────────
        try:
            from app.core.database import SessionLocal
            from app.services.engagement_metrics_service import run_engagement_metrics_job

            async def _run_engagement_metrics():
                db = SessionLocal()
                try:
                    result = run_engagement_metrics_job(db)
                    if result["processed"]:
                        logger.info(f"[scheduler] Engagement metrics: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] Engagement metrics error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_engagement_metrics,
                trigger="interval",
                hours=4,
                id="engagement_metrics_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled engagement metrics job (every 4 hours)")
        except Exception as exc:
            logger.warning(f"Could not register engagement metrics scheduler: {exc}")

        # ── Every 4 hours: DROP_RISK_SCORING_JOB (S-060/HRMS-0460) ──────────
        try:
            from app.core.database import SessionLocal
            from app.services.drop_risk_service import run_drop_risk_scoring_job

            async def _run_drop_risk_scoring():
                db = SessionLocal()
                try:
                    result = run_drop_risk_scoring_job(db)
                    if result["processed"]:
                        logger.info(f"[scheduler] Drop risk scoring: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] Drop risk scoring error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_drop_risk_scoring,
                trigger="interval",
                hours=4,
                id="drop_risk_scoring_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled drop risk scoring job (every 4 hours)")
        except Exception as exc:
            logger.warning(f"Could not register drop risk scoring scheduler: {exc}")

        # ── Every 15 min: NO_SHOW_FOLLOWUP_JOB (S-052/HRMS-0452) ────────────
        try:
            from app.core.database import SessionLocal
            from app.services.interview_no_show_service import run_no_show_followup_job

            async def _run_no_show_followup():
                db = SessionLocal()
                try:
                    result = run_no_show_followup_job(db)
                    if result["processed"]:
                        logger.info(f"[scheduler] No-show follow-up: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] No-show follow-up error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_no_show_followup,
                trigger="interval",
                minutes=15,
                id="no_show_followup_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled no-show follow-up job (every 15 min)")
        except Exception as exc:
            logger.warning(f"Could not register no-show follow-up scheduler: {exc}")

        # ── Every 15 min: PAUSE_EXPIRY_JOB (S-075/HRMS-0475) ────────────────
        try:
            from app.core.database import SessionLocal
            from app.services.thunder_pause_service import run_pause_expiry_job

            async def _run_pause_expiry():
                db = SessionLocal()
                try:
                    result = run_pause_expiry_job(db)
                    if result["resumed"]:
                        logger.info(f"[scheduler] Pause expiry: {result}")
                except Exception as exc:
                    logger.error(f"[scheduler] Pause expiry error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_pause_expiry,
                trigger="interval",
                minutes=15,
                id="pause_expiry_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled pause expiry job (every 15 min)")
        except Exception as exc:
            logger.warning(f"Could not register pause expiry scheduler: {exc}")


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

