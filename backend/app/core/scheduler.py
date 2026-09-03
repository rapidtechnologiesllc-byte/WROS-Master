import asyncio
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from apscheduler.schedulers.background import BackgroundScheduler
import logging
from apscheduler.jobstores.memory import MemoryJobStore

from app.core.logging import logger

# Initialize the scheduler
jobstores = {
    'default': MemoryJobStore()
}
scheduler = BackgroundScheduler(jobstores=jobstores, timezone="UTC")

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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
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
                    logger.error(f"Error: {str(exc)}", exc_info=True)
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
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register pause expiry scheduler: {exc}")

        # ── Every 15 min: SUPERVISOR_AGENT_JOB (S-066/HRMS-0466) ────────────
        try:
            from app.core.database import SessionLocal
            from app.services.supervisor_agent_service import run_supervisor_cycle

            async def _run_supervisor_cycle():
                db = SessionLocal()
                try:
                    result = run_supervisor_cycle(db)
                    if result["tenants_processed"]:
                        logger.info(f"[scheduler] Supervisor cycle: {result}")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] Supervisor cycle error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_supervisor_cycle,
                trigger="interval",
                minutes=15,
                id="supervisor_agent_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled supervisor agent job (every 15 min)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register supervisor agent scheduler: {exc}")

        # ── Every 6 hours: ONBOARDING_TOUCHPOINT_JOB (S-067/HRMS-0467) ──────
        try:
            from app.core.database import SessionLocal
            from app.services.onboarding_agent_service import run_onboarding_touchpoint_job

            async def _run_onboarding_touchpoint():
                db = SessionLocal()
                try:
                    result = run_onboarding_touchpoint_job(db)
                    if result["processed"] or result["completions_detected"]:
                        logger.info(f"[scheduler] Onboarding touchpoint job: {result}")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] Onboarding touchpoint job error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_onboarding_touchpoint,
                trigger="interval",
                hours=6,
                id="onboarding_touchpoint_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled onboarding touchpoint job (every 6 hours)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register onboarding touchpoint scheduler: {exc}")

        # ── Every hour: TASK_ESCALATION_JOB (S-434) ─────────────────────────
        try:
            from app.core.database import SessionLocal
            from app.services.task_escalation_service import escalate_overdue_tasks

            async def _run_task_escalation():
                db = SessionLocal()
                try:
                    escalated = escalate_overdue_tasks(db)
                    if escalated:
                        logger.info(f"[scheduler] Task escalation: {len(escalated)} task(s) escalated")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] Task escalation job error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_task_escalation,
                trigger="interval",
                hours=1,
                id="task_escalation_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled task escalation job (every 1 hour)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register task escalation scheduler: {exc}")

        # ── Daily: BIRTHDAY_DRAFTS_JOB (Executive Signal & Culture Agent) ───
        try:
            from app.core.database import SessionLocal
            from app.services.culture_agent_service import generate_birthday_drafts

            async def _run_birthday_drafts():
                db = SessionLocal()
                try:
                    drafts = generate_birthday_drafts(db)
                    if drafts:
                        logger.info(f"[scheduler] Birthday drafts: {len(drafts)} drafted for review")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] Birthday drafts job error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_birthday_drafts,
                trigger="interval",
                hours=24,
                id="birthday_drafts_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled birthday drafts job (every 24 hours)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register birthday drafts scheduler: {exc}")

        # ── Daily: MELLOW_KEEPWARM_JOB (outreach cadence-by-stage) ──────────
        try:
            from app.core.database import SessionLocal
            from app.services.mellow_keepwarm_service import run_mellow_keepwarm_job

            async def _run_mellow_keepwarm():
                db = SessionLocal()
                try:
                    result = run_mellow_keepwarm_job(db)
                    if result["nudged"]:
                        logger.info(f"[scheduler] Mellow keep-warm: {result}")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] Mellow keep-warm job error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_mellow_keepwarm,
                trigger="interval",
                hours=24,
                id="mellow_keepwarm_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled mellow keep-warm job (every 24 hours)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register mellow keep-warm scheduler: {exc}")

        # ── Every 30 min: S-347 Desire Signal Processing Job ────────────────
        try:
            from app.core.database import SessionLocal
            from app.services.desire_signal_service import process_unprocessed_signals

            async def _run_desire_signal_processing():
                db = SessionLocal()
                try:
                    result = process_unprocessed_signals(db)
                    if result["batch_size"]:
                        logger.info(f"[scheduler] Desire signal processing: {result}")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] Desire signal processing error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_desire_signal_processing,
                trigger="interval",
                minutes=30,
                id="desire_signal_processing_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled desire signal processing job (every 30 minutes)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register desire signal processing scheduler: {exc}")

        # ── Every 4 hours: S-348 Desire Profile Update Job ──────────────────
        try:
            from app.core.database import SessionLocal
            from app.services.desire_profile_service import run_desire_profile_update_job

            async def _run_desire_profile_update():
                db = SessionLocal()
                try:
                    result = run_desire_profile_update_job(db)
                    if result["candidates_due"]:
                        logger.info(f"[scheduler] Desire profile update: {result}")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] Desire profile update error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_desire_profile_update,
                trigger="interval",
                hours=4,
                id="desire_profile_update_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled desire profile update job (every 4 hours)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register desire profile update scheduler: {exc}")

        # ── Every 30 min: S-349 ScheduledMotivationJob ──────────────────────
        try:
            from app.core.database import SessionLocal
            from app.services.motivation_engine_service import run_motivation_job

            async def _run_motivation_job():
                db = SessionLocal()
                try:
                    result = run_motivation_job(db)
                    if result["sent"]:
                        logger.info(f"[scheduler] Motivation job: {result}")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] Motivation job error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_motivation_job,
                trigger="interval",
                minutes=30,
                id="proactive_motivation_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled proactive motivation job (every 30 minutes)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register proactive motivation scheduler: {exc}")

        # ── Every 30 min: EPIC-14/S-435 M365 mail sync (lifecycle linking) ──
        try:
            from app.core.database import SessionLocal
            from app.services.msgraph_mail_sync_service import run_msgraph_mail_sync_job

            async def _run_msgraph_mail_sync():
                db = SessionLocal()
                try:
                    result = run_msgraph_mail_sync_job(db)
                    if result["total_linked"]:
                        logger.info(f"[scheduler] M365 mail sync: {result}")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] M365 mail sync error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_msgraph_mail_sync,
                trigger="interval",
                minutes=30,
                id="msgraph_mail_sync_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled M365 mail sync job (every 30 minutes)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register M365 mail sync scheduler: {exc}")

        # ── Daily: TIMESHEET_NAG_JOB (EPIC-16) ───────────────────────────────
        # 2026-08-06 -- built 2026-08-05 with the logic fully tested but never
        # actually registered here; Avinash caught the resulting gap live
        # ("Is my timesheet pending for this week to employee") and it's the
        # proof point behind this codebase's standing Task-Driven Workflow
        # Coverage rule (see CLAUDE.md). Daily, not weekly -- escalation to
        # the reporting manager depends on days-since-last-nag, so this needs
        # to check in more than once a week to fire on time.
        try:
            from app.core.database import SessionLocal
            from app.services.timesheet_nag_service import run_timesheet_nag_job

            async def _run_timesheet_nag():
                db = SessionLocal()
                try:
                    result = run_timesheet_nag_job(db)
                    if result["processed"]:
                        logger.info(f"[scheduler] Timesheet nag: {result}")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] Timesheet nag job error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_timesheet_nag,
                trigger="cron",
                hour=9,
                minute=0,
                id="timesheet_nag_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled timesheet nag job (09:00 UTC daily)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register timesheet nag scheduler: {exc}")

        # ── Daily: AR_FOLLOW_UP_JOB (EPIC-16) ────────────────────────────────
        # 2026-08-06 -- same gap as timesheet nag above, same fix.
        try:
            from app.core.database import SessionLocal
            from app.services.ar_followup_service import run_ar_follow_up_job

            async def _run_ar_follow_up():
                db = SessionLocal()
                try:
                    result = run_ar_follow_up_job(db)
                    if result["processed"]:
                        logger.info(f"[scheduler] AR follow-up: {result}")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] AR follow-up job error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_ar_follow_up,
                trigger="cron",
                hour=9,
                minute=30,
                id="ar_follow_up_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled AR follow-up job (09:30 UTC daily)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register AR follow-up scheduler: {exc}")

        # ── Weekly (Monday 00:00 UTC): TIMESHEET_DRAFT_CREATION_JOB (EPIC-05) ─
        # Auto-creates weekly timesheet drafts for all active employees every
        # Monday at midnight UTC. Employees can also trigger on-demand via
        # GET /my/timesheet/current which creates if not found for current week.
        try:
            from app.core.database import SessionLocal
            from app.services.timesheet_service import create_weekly_draft_batch

            async def _run_weekly_draft_creation():
                db = SessionLocal()
                try:
                    result = create_weekly_draft_batch(db)
                    logger.info(f"[scheduler] Weekly timesheet draft creation: {result}")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] Weekly timesheet draft creation error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_weekly_draft_creation,
                trigger="cron",
                day_of_week=0,
                hour=0,
                minute=0,
                id="weekly_timesheet_draft_creation_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled weekly timesheet draft creation job (Monday 00:00 UTC)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register weekly timesheet draft creation scheduler: {exc}")

        # ── Daily: AGENT_DAILY_STANDUP_JOB (8:00 AM EST) ─────────────────────
        # Sequential agent reporting with validation. Each agent reports
        # yesterday's metrics in priority order. System validates each update.
        # 8:00 AM EST = 13:00 UTC (EST is UTC-5)
        try:
            from app.core.database import SessionLocal
            from app.services.agent_daily_standup_service import AgentDailyStandup

            async def _run_agent_standup():
                db = SessionLocal()
                try:
                    result = await AgentDailyStandup.generate_standup_report(
                        tenant_id="default",  # Will be called per-tenant in production
                        db=db
                    )
                    if result.get("agent_reports"):
                        logger.info(f"[scheduler] Agent daily standup: {len(result['agent_reports'])} agents reported, {len(result.get('validation_issues', []))} issues flagged")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] Agent daily standup error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_agent_standup,
                trigger="cron",
                hour=13,  # 8 AM EST = 13:00 UTC
                minute=0,
                id="agent_daily_standup_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled agent daily standup job (8:00 AM EST / 13:00 UTC)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register agent daily standup scheduler: {exc}")

        # ── Daily: AGENT_SCRUM_OF_SCRUMS_JOB (8:30 AM EST) ──────────────────
        # Flash + CEO + Feedback + Partners (Troy, Curtis) sync.
        # 8:30 AM EST = 13:30 UTC
        try:
            from app.core.database import SessionLocal
            from app.services.agent_daily_standup_service import AgentDailyStandup

            async def _run_scrum_of_scrums():
                db = SessionLocal()
                try:
                    result = await AgentDailyStandup.scrum_of_scrums(
                        tenant_id="default",  # Will be called per-tenant in production
                        db=db
                    )
                    critical_count = len(result.get("ceo_directives", []))
                    if critical_count > 0:
                        logger.info(f"[scheduler] Scrum of Scrums: {critical_count} CEO directives issued")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] Scrum of Scrums error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_scrum_of_scrums,
                trigger="cron",
                hour=13,  # 8:30 AM EST = 13:30 UTC
                minute=30,
                id="agent_scrum_of_scrums_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled agent scrum of scrums job (8:30 AM EST / 13:30 UTC)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register agent scrum of scrums scheduler: {exc}")

        # ── Daily: HTD_PIPELINE_ACCOUNTABILITY_JOB (8:05 AM EST) ─────────────────
        # SPECIALTY→CORE conversion pipeline health for each partner/BU.
        # Runs daily so Flash sees where CORE talent is being developed.
        # Triggers HTD hiring recommendations if internal development too slow.
        # 8:05 AM EST = 13:05 UTC
        try:
            from app.core.database import SessionLocal
            from app.services.htd_pipeline_accountability_agent import HTDPipelineAccountabilityAgent
            from app.models.business_unit import BusinessUnit

            async def _run_htd_pipeline_tracking():
                db = SessionLocal()
                try:
                    result = await HTDPipelineAccountabilityAgent.partners_conversion_health(
                        tenant_id="default",
                        db=db
                    )
                    critical = len(result.get("critical_alerts", []))
                    at_risk = len(result.get("at_risk_units", []))
                    if critical > 0 or at_risk > 0:
                        logger.info(f"[scheduler] HTD Pipeline: {critical} critical (no dev pipeline), {at_risk} at-risk (< 50% CORE)")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] HTD pipeline tracking error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_htd_pipeline_tracking,
                trigger="cron",
                hour=13,  # 8:05 AM EST = 13:05 UTC
                minute=5,
                id="htd_pipeline_accountability_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled HTD pipeline accountability job (8:05 AM EST / 13:05 UTC)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register HTD pipeline accountability scheduler: {exc}")

        # ── Daily: FLASH_DAILY_COORDINATION_JOB (8:15 AM EST) ──────────────────
        # Flash orchestration engine: analyze all agent data and issue directives.
        # Runs after HTD Pipeline (8:05) so has all pipeline data ready.
        # Issues directives to partners on what to do TODAY.
        # Escalates to CEO if critical issues found.
        # 8:15 AM EST = 13:15 UTC
        try:
            from app.core.database import SessionLocal
            from app.services.flash_orchestration_engine import FlashOrchestrationEngine

            async def _run_flash_coordination():
                db = SessionLocal()
                try:
                    result = await FlashOrchestrationEngine.daily_flash_coordination(
                        tenant_id="default",
                        db=db
                    )
                    partners_with_action = len(result.get("partner_directives", []))
                    critical = result.get("summary", {}).get("critical_alerts", 0)
                    high = result.get("summary", {}).get("high_alerts", 0)
                    logger.info(f"[scheduler] Flash Coordination: {partners_with_action} partners have directives, {critical} critical, {high} high alerts")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] Flash coordination error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_flash_coordination,
                trigger="cron",
                hour=13,  # 8:15 AM EST = 13:15 UTC
                minute=15,
                id="flash_daily_coordination_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled Flash daily coordination job (8:15 AM EST / 13:15 UTC)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register Flash coordination scheduler: {exc}")

        # ── Weekly (Thursday): PARTNER_SUCCESS_AGENT_JOB ────────────────────
        # Thursday morning before CEO call: Partners get final validation check
        # "Here's your week. Here's what you'll tell the CEO."
        # Not daily nagging - just once-per-week reality check with action items
        try:
            from app.core.database import SessionLocal
            from app.services.partner_success_agent_service import PartnerSuccessAgent

            async def _run_partner_success_check():
                db = SessionLocal()
                try:
                    # Check all partners: Troy, Curtis, Avinash
                    for partner_key in ["troy", "curtis", "avinash"]:
                        result = await PartnerSuccessAgent.thursday_ceo_prep(
                            tenant_id="default",
                            partner_key=partner_key,
                            db=db
                        )
                        if result.get("action_items"):
                            logger.info(f"[scheduler] Partner Success ({partner_key}): {len(result['action_items'])} items, {result['this_week']['revenue_closed_usd']:,.0f} closed this week")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] Partner success check error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_partner_success_check,
                trigger="cron",
                day_of_week=3,  # Thursday (0=Monday, 3=Thursday)
                hour=7,         # 7 AM EST = 12:00 UTC (before CEO weekly call)
                minute=0,
                id="partner_success_thursday_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled partner success check (Thursday 7 AM EST / 12:00 UTC - before CEO call)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register partner success scheduler: {exc}")

        # ── Daily (02:00 UTC): REVENUE_AUTONOMOUS_SCANNING_JOB (PRIORITY-2) ───
        # Proactively scan all active projects for revenue leakage daily.
        # Stores results in cache (RevenueLeakageFlag table).
        # API endpoint returns cached results by default (no manual UUID needed).
        try:
            from app.core.database import SessionLocal
            from app.services.revenue_scanning_service import run_daily_revenue_scan_job

            async def _run_revenue_scan():
                db = SessionLocal()
                try:
                    result = run_daily_revenue_scan_job(db)
                    if result["leakage_detected"]:
                        logger.info(f"[scheduler] Revenue scan: {result}")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] Revenue scan error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_revenue_scan,
                trigger="cron",
                hour=2,
                minute=0,
                id="daily_revenue_scan_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled daily revenue autonomous scanning job (02:00 UTC)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register revenue scanning scheduler: {exc}")

        # ── Every 2 min: MESSAGE_QUEUE_PROCESSING_JOB ───────────────────────
        # CRITICAL: Process pending messages BEFORE Thunder runs so queue is ready
        try:
            from app.core.database import SessionLocal
            from app.services.message_queue_coordinator import MessageQueueCoordinator

            def _run_message_queue_processing():
                db = SessionLocal()
                try:
                    # Step 1: Convert PENDING messages to CHANNEL_QUEUED (routes via SLM orchestration)
                    pending_result = MessageQueueCoordinator.process_pending_messages(limit=100, db=db)
                    if pending_result.get("messages_processed", 0) > 0 or pending_result.get("errors", 0) > 0:
                        logger.info(f"[scheduler] Message queue processing (pending): {pending_result}")

                    # Step 2: Process THUNDER_QUEUE messages specifically
                    thunder_result = MessageQueueCoordinator.process_channel_messages(
                        queue_type="THUNDER_QUEUE", limit=50, db=db
                    )
                    if thunder_result.get("channels_processed", 0) > 0 or thunder_result.get("channels_failed", 0) > 0:
                        logger.info(f"[scheduler] Message queue processing (THUNDER): {thunder_result}")

                    # Step 3: Mark fully-completed messages as COMPLETED
                    complete_result = MessageQueueCoordinator.complete_messages(db=db)
                    if complete_result.get("messages_completed", 0) > 0:
                        logger.info(f"[scheduler] Message completion check: {complete_result}")

                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] Message queue processing error: {exc}", exc_info=True)
                finally:
                    db.close()

            scheduler.add_job(
                _run_message_queue_processing,
                trigger="interval",
                minutes=2,
                id="message_queue_processing_job",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled message queue processing (every 2 min)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register message queue processing scheduler: {exc}")

        # ── Every 5 min: THUNDER_AUTONOMOUS_LOOP (Candidate Outreach) ────────
        try:
            from app.core.database import SessionLocal
            from app.services.thunder_autonomous_loop import run_thunder_autonomous_cycle

            def _run_thunder_autonomous():
                db = SessionLocal()
                try:
                    result = run_thunder_autonomous_cycle(db)
                    if result.get("status") == "success":
                        if result.get("candidates_contacted") or result.get("sequences_advanced"):
                            logger.info(f"[scheduler] Thunder autonomous: {result}")
                    elif result.get("status") == "paused":
                        logger.debug("[scheduler] Thunder paused (kill switch active)")
                    else:
                        logger.error(f"[scheduler] Thunder autonomous error: {result.get('error')}")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] Thunder autonomous error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_thunder_autonomous,
                trigger="interval",
                minutes=5,
                id="thunder_autonomous_loop",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled Thunder autonomous loop (every 5 min)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register Thunder autonomous loop scheduler: {exc}")

        # ── Every 30 min: SLM_IMPROVEMENT_CYCLE (Self-Learning Model) ───────
        try:
            from app.core.database import SessionLocal
            from app.services.slm_daily_improvement import SLMImprovementScheduler

            def _run_slm_improvement():
                db = SessionLocal()
                try:
                    result = SLMImprovementScheduler.run_and_report(db)
                    if result.get("corrections_processed") > 0 or result.get("outcomes_processed") > 0:
                        logger.info(f"[scheduler] SLM improvement: {result}")
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[scheduler] SLM improvement error: {exc}")
                finally:
                    db.close()

            scheduler.add_job(
                _run_slm_improvement,
                trigger="interval",
                minutes=30,
                id="slm_improvement_30min",
                replace_existing=True,
            )
            logger.info("[OK] Scheduled SLM improvement cycle (every 30 min)")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not register SLM improvement scheduler: {exc}")


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

