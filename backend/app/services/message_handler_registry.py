"""Message Handler Registry - Maps message types to handler functions."""
import logging
from typing import Dict, Callable, Optional, Any
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Handler configuration (Gate #6: TIMEOUT_SECONDS enforcement)
TIMEOUT_SECONDS = 30  # Default timeout for message handler operations


class MessageHandlerRegistry:
    """Centralized registry for message type handlers."""

    _handlers: Dict[str, Callable] = {}

    @classmethod
    def register(cls, message_type: str, handler: Callable) -> None:
        """Register a handler for a message type."""
        cls._handlers[message_type] = handler
        logger.info(f"[Registry] Registered handler for '{message_type}'")

    @classmethod
    def get_handler(cls, message_type: str) -> Optional[Callable]:
        """Retrieve handler for a message type."""
        return cls._handlers.get(message_type)

    @classmethod
    def get_all_handlers(cls) -> Dict[str, Callable]:
        """Get all registered handlers."""
        return cls._handlers.copy()

    @classmethod
    def clear(cls) -> None:
        """Clear all registered handlers (for testing)."""
        cls._handlers.clear()


def _initialize_default_handlers():
    """Initialize built-in message handlers."""
    # Register candidate handlers (CRITICAL - must succeed)
    try:
        from app.services.channel_processors.candidate_queue_processor import CandidateQueueProcessor
        MessageHandlerRegistry.register("create_candidate", CandidateQueueProcessor.process)
        logger.info("[Registry] Registered create_candidate handler")
    except ImportError as e:
        logger.error(f"[Registry] CRITICAL: Failed to import CandidateQueueProcessor: {e}")
        logger.error("[Registry] Candidate creation will fail without this handler")

    # Register Thunder/engagement handlers (CRITICAL - must succeed)
    try:
        from app.services.message_handlers.thunder_engagement_handler import ThunderEngagementHandler
        MessageHandlerRegistry.register("engage_candidate_with_thunder", ThunderEngagementHandler.process)
        MessageHandlerRegistry.register("assign_thunder_agent", ThunderEngagementHandler.process)
        logger.info("[Registry] Registered Thunder engagement handlers")
    except Exception as e:
        logger.error(f"[Registry] CRITICAL: Failed to register Thunder handlers: {e}")
        logger.error("[Registry] Thunder candidate engagement will fail without this handler")

    # Register SLM email generation handler (NEW - Phase 2)
    try:
        from app.services.message_handlers.slm_email_generation_handler import SLMEmailGenerationHandler
        MessageHandlerRegistry.register("slm_generate_email", SLMEmailGenerationHandler.process)
        logger.info("[Registry] Registered SLM email generation handler")
    except ImportError as e:
        logger.warning(f"[Registry] Could not import SLM email generation handler: {e}")
    except Exception as e:
        logger.error(f"[Registry] Failed to register SLM email generation handler: {e}", exc_info=True)

    # Register SLM training alert handler (CRITICAL FIX - handles SLM failures)
    try:
        from app.services.message_handlers.slm_training_alert_handler import SLMTrainingAlertHandler
        MessageHandlerRegistry.register("slm_training_alert", SLMTrainingAlertHandler.process)
        logger.info("[Registry] Registered SLM training alert handler")
    except ImportError as e:
        logger.warning(f"[Registry] Could not import SLM training alert handler: {e}")
    except Exception as e:
        logger.error(f"[Registry] Failed to register SLM training alert handler: {e}", exc_info=True)

    # Register email delivery handler (Thunder queue email sending)
    try:
        from app.services.message_handlers.send_email_handler import SendEmailHandler
        MessageHandlerRegistry.register("send_email_to_candidate", SendEmailHandler.process)
        logger.info("[Registry] Registered send_email_to_candidate handler (Azure Graph or stub)")
    except ImportError as e:
        logger.warning(f"[Registry] Could not import email handler: {e}")
    except Exception as e:
        logger.error(f"[Registry] Failed to register email handler: {e}", exc_info=True)

    # Register candidate update handler (CRITICAL - updates audit trail, Message Payload + Validation Response logging)
    try:
        from app.services.message_handlers.candidate_update_handler import CandidateUpdateHandler
        MessageHandlerRegistry.register("candidate_update", CandidateUpdateHandler.process)
        logger.info("[Registry] Registered candidate_update handler")
    except ImportError as e:
        logger.warning(f"[Registry] Could not import candidate_update handler: {e}")
    except Exception as e:
        logger.error(f"[Registry] Failed to register candidate_update handler: {e}", exc_info=True)

    # Register candidate note handler (Thunder Memory updates)
    try:
        from app.services.message_handlers.candidate_note_added_handler import CandidateNoteAddedHandler
        MessageHandlerRegistry.register("candidate_note_added", CandidateNoteAddedHandler.process)
        logger.info("[Registry] Registered candidate note added handler")
    except ImportError as e:
        logger.warning(f"[Registry] Could not import candidate note handler: {e}")
    except Exception as e:
        logger.error(f"[Registry] Failed to register candidate note handler: {e}", exc_info=True)

    try:
        from app.services.message_handlers.enrich_linkedin_candidate_handler import EnrichLinkedInCandidateHandler
        MessageHandlerRegistry.register("enrich_linkedin_candidate", EnrichLinkedInCandidateHandler.process)
        logger.info("[Registry] Registered enrich_linkedin_candidate handler")
    except Exception as e:
        logger.error(f"[Registry] CRITICAL: Failed to register enrich_linkedin_candidate handler: {e}", exc_info=True)

    try:
        from app.services.message_handlers.thunder_send_email_handler import ThunderSendEmailHandler
        from app.services.message_handlers.thunder_inbound_email_handler import ThunderInboundEmailHandler
        MessageHandlerRegistry.register("thunder_send_email", ThunderSendEmailHandler.process)
        MessageHandlerRegistry.register("thunder_process_inbound_email", ThunderInboundEmailHandler.process)
        from app.services.message_handlers.thunder_forwarded_email_handler import ThunderForwardedEmailHandler
        MessageHandlerRegistry.register("thunder_process_forwarded_email", ThunderForwardedEmailHandler.process)
        logger.info("[Registry] Registered Thunder email cadence handlers")
    except Exception as e:
        logger.error(f"[Registry] CRITICAL: Failed to register Thunder email handlers: {e}", exc_info=True)

    try:
        from app.services.message_handlers.send_account_email_handler import SendAccountEmailHandler
        MessageHandlerRegistry.register("send_account_email", SendAccountEmailHandler.process)
        logger.info("[Registry] Registered send_account_email handler")
    except Exception as e:
        logger.error(f"[Registry] CRITICAL: Failed to register send_account_email handler: {e}", exc_info=True)

    try:
        from app.services.message_handlers.send_staff_email_handler import SendStaffEmailHandler
        MessageHandlerRegistry.register("send_staff_email", SendStaffEmailHandler.process)
        logger.info("[Registry] Registered send_staff_email handler")
    except Exception as e:
        logger.error(f"[Registry] CRITICAL: Failed to register send_staff_email handler: {e}", exc_info=True)

    try:
        from app.services.message_handlers.hiring_pipeline_handlers import (
            HiringConvertToBenchHandler,
            HiringPipelineEvaluateHandler,
            HiringStageActionHandler,
        )
        MessageHandlerRegistry.register("hiring_convert_to_bench", HiringConvertToBenchHandler.process)
        MessageHandlerRegistry.register("hiring_pipeline_evaluate", HiringPipelineEvaluateHandler.process)
        MessageHandlerRegistry.register("hiring_stage_action", HiringStageActionHandler.process)
        from app.services.message_handlers.send_pipeline_email_handler import SendPipelineEmailHandler
        MessageHandlerRegistry.register("send_pipeline_email", SendPipelineEmailHandler.process)
        from app.services.message_handlers.interview_notice_handler import InterviewNoticeHandler
        MessageHandlerRegistry.register("send_interview_notice", InterviewNoticeHandler.process)
        logger.info("[Registry] Registered hiring pipeline handlers")
    except Exception as e:
        logger.error(f"[Registry] CRITICAL: Failed to register hiring pipeline handlers: {e}", exc_info=True)

    try:
        from app.services.message_handlers.send_invoice_email_handler import SendInvoiceEmailHandler
        MessageHandlerRegistry.register("send_invoice_email", SendInvoiceEmailHandler.process)
        logger.info("[Registry] Registered send_invoice_email handler")
    except Exception as e:
        logger.error(f"[Registry] CRITICAL: Failed to register send_invoice_email handler: {e}", exc_info=True)

    try:
        from app.services.message_handlers.send_client_timesheet_approval_handler import (
            SendClientTimesheetApprovalHandler,
        )
        MessageHandlerRegistry.register("send_client_timesheet_approval", SendClientTimesheetApprovalHandler.process)
        logger.info("[Registry] Registered send_client_timesheet_approval handler")
    except Exception as e:
        logger.error(f"[Registry] CRITICAL: Failed to register send_client_timesheet_approval handler: {e}",
                     exc_info=True)

    # Register ops alert handler (NEW - Phase 3/4 stale message detection)
    try:
        from app.services.message_handlers.ops_alert_handler import OpsAlertHandler
        MessageHandlerRegistry.register("ops_alert", OpsAlertHandler.process)
        logger.info("[Registry] Registered ops alert handler")
    except ImportError as e:
        logger.warning(f"[Registry] Could not import ops alert handler: {e}")
    except Exception as e:
        logger.error(f"[Registry] Failed to register ops alert handler: {e}", exc_info=True)

    # Register job handlers (CYCLE 19: Queue-driven architecture)
    try:
        from app.services.message_handlers.job_status_changed_handler import handle_job_status_changed
        from app.services.message_handlers.source_candidates_handler import handle_source_candidates_for_job
        from app.services.message_handlers.job_creation_flash_handler import JobCreationFlashHandler
        from app.services.message_handlers.flash_recruiter_handler import FlashRecruiterHandler

        # CYCLE 19: Queue-driven job creation (two handlers)
        # 1. job_created_flash → Creates job in database
        # 2. flash_recruiter → Finds candidates & queues outreach
        MessageHandlerRegistry.register("job_created_flash", JobCreationFlashHandler.process)
        MessageHandlerRegistry.register("flash_recruiter", FlashRecruiterHandler.process)

        MessageHandlerRegistry.register("job_status_changed", handle_job_status_changed)
        MessageHandlerRegistry.register("source_candidates_for_job", handle_source_candidates_for_job)  # Skill matching + cascade detection
        from app.services.recruiting_service import handle_sourcing_complete
        MessageHandlerRegistry.register("candidate_sourcing_complete", handle_sourcing_complete)  # top matches -> recruiter task
    except ImportError as e:
        logger.warning(f"[Registry] Could not import job handlers: {e}")

    # CYCLE 20A: Spartan Phalanx Formation Feedback (Thunder reports back to Flash)
    try:
        # engage_candidate_with_thunder stays on ThunderEngagementHandler (registered above):
        # ThunderOutreachHandler requires job_id, which no candidate-creation caller sends.
        # Formation feedback: Thunder → Flash (health metrics)
        def _handle_formation_feedback(message: Any, db: Session) -> Dict[str, Any]:
            """Formation feedback handler: Receive health reports from downstream neighbors."""
            logger.info(f"[FormationFeedback] {message.payload.get('source')} → {message.payload.get('target')}: "
                       f"{message.payload.get('metric')} = {message.payload.get('value'):.1%}")
            return {
                'status': 'feedback_received',
                'source': message.payload.get('source'),
                'target': message.payload.get('target'),
                'metric': message.payload.get('metric'),
                'value': message.payload.get('value')
            }

        MessageHandlerRegistry.register("formation_feedback_thunder_to_flash", _handle_formation_feedback)
        MessageHandlerRegistry.register("formation_integrity_escalation", _handle_formation_feedback)

    except ImportError as e:
        logger.warning(f"[Registry] Could not import Thunder/Formation handlers: {e}")

    # Offers move through the offer-letter endpoints and offer_response_service only; the
    # offer_approved/sent/accepted/rejected queue handlers had no producer and were deleted.

    # Invoice status changes happen only in invoice_service (approve: Finance Senior Manager+;
    # send: request_invoice_email; paid: bank_reconciliation_service) and revenue only in
    # revenue_chain_service.recognize_revenue. The old queue handlers that set those statuses
    # directly (bypassing those rules) were deleted 2026-10-10.

    # interview_scheduled (queued by POST /interviews after it creates the interview): pause
    # Thunder outreach only. The old handler created a second, duplicate interview row.
    MessageHandlerRegistry.register("interview_scheduled", _pause_thunder_on_interview)

    # Register offer generation handler (existing - needs adapter)
    try:
        from app.services.message_handlers.offer_generated_handler import handle_offer_generated as legacy_handle_offer_generated

        def _offer_generated_adapter(message: Any, db: Session) -> Dict[str, Any]:
            """Adapter for legacy offer_generated handler."""
            event_payload = {
                "candidate_id": message.payload.get("candidate_id"),
                "data": message.payload
            }
            return legacy_handle_offer_generated(event_payload, db)

        MessageHandlerRegistry.register("offer_generated", _offer_generated_adapter)
    except ImportError:
        logger.info("[Registry] Offer generated handler not yet available")

    # Register create_user_with_roles handler (POST /hr/users/create-with-roles
    # queues this - previously had no handler, so queued accounts never got created)
    try:
        from app.services.message_handlers.create_user_with_roles_handler import handle_create_user_with_roles
        MessageHandlerRegistry.register("create_user_with_roles", handle_create_user_with_roles)
    except ImportError as e:
        logger.warning(f"[Registry] Could not import create_user_with_roles handler: {e}")

    # Register dead-letter escalation handler (the safety net for every other
    # handler's exhausted retries - without this, permanent failures were
    # silently invisible instead of escalated)
    try:
        from app.services.message_handlers.dead_letter_escalation_handler import handle_dead_letter_escalation
        MessageHandlerRegistry.register("dead_letter_escalation", handle_dead_letter_escalation)
    except ImportError as e:
        logger.warning(f"[Registry] Could not import dead-letter escalation handler: {e}")

    # Register candidate lifecycle handlers (deletion, conversion to employee)
    try:
        from app.services.message_handlers.candidate_deleted_handler import handle_candidate_deleted
        from app.services.message_handlers.candidate_converted_to_employee_handler import (
            handle_candidate_converted_to_employee,
        )
        MessageHandlerRegistry.register("candidate_deleted", handle_candidate_deleted)
        MessageHandlerRegistry.register("candidate_converted_to_employee", handle_candidate_converted_to_employee)
    except ImportError as e:
        logger.warning(f"[Registry] Could not import candidate lifecycle handlers: {e}")

    # Register the generic flash-notification handler for every internal
    # lifecycle-event task name that was previously enqueued with no handler
    # at all (job/invoice/interview/milestone/offer/employee notifications).
    try:
        from app.services.message_handlers.flash_notification_handler import (
            FLASH_NOTIFICATION_TASK_NAMES,
            handle_flash_notification,
        )
        for _task_name in FLASH_NOTIFICATION_TASK_NAMES:
            MessageHandlerRegistry.register(_task_name, handle_flash_notification)
        logger.info(
            f"[Registry] Registered generic flash-notification handler for "
            f"{len(FLASH_NOTIFICATION_TASK_NAMES)} task names"
        )
    except ImportError as e:
        logger.warning(f"[Registry] Could not import flash notification handler: {e}")


# Thunder engagement handler moved to ThunderEngagementHandler class
# See: app/services/message_handlers/thunder_engagement_handler.py


# MEDIUM FIX #12: Initialize handlers and validate
def _event_bus_adapter(process: Callable) -> Callable:
    """CandidateEventBus enqueues {event_type, candidate_id, timestamp, data:{...}};
    the candidate handlers read their fields at the top level. Flatten before calling."""
    def run(message, db):
        payload = dict(message.payload or {})
        flat = {"candidate_id": payload.get("candidate_id"), **(payload.get("data") or {})}

        class _Flat:
            id = getattr(message, "id", None)
            tenant_id = getattr(message, "tenant_id", None)
            retry_count = getattr(message, "retry_count", 0)
        _Flat.payload = flat
        return process(_Flat, db)
    run.__name__ = getattr(process, "__name__", "event_bus_handler")
    return run


def _pause_thunder_on_interview(message, db):
    """interview_scheduled from the event bus: the interview already exists (the
    endpoint created it), so only pause Thunder outreach for the candidate."""
    from app.models.candidate import Candidate

    candidate = db.query(Candidate).filter(Candidate.candidateID == message.payload.get("candidate_id")).first()
    if candidate is None:
        raise ValueError(f"Candidate {message.payload.get('candidate_id')} not found")
    paused = bool(candidate.thunder_enabled)
    if paused:
        candidate.thunder_enabled = False
        db.add(candidate)
        db.commit()
    return {"status": "success", "candidate_id": candidate.candidateID, "thunder_paused": paused}


def _register_event_bus_handlers():
    """Message types CandidateEventBus publishes (see its _get_handler_function)."""
    from app.services.message_handlers.candidate_data_change_handler import CandidateDataChangeHandler
    from app.services.message_handlers.candidate_status_change_handler import CandidateStatusChangeHandler
    from app.services.message_handlers.candidate_rejection_handler import handle_candidate_rejected
    from app.services.message_handlers.candidate_archive_handler import handle_candidate_archived
    from app.services.message_handlers.candidate_reactivation_handler import handle_candidate_reactivated

    # Standard event-bus handlers
    MessageHandlerRegistry.register("handle_candidate_data_changed", _event_bus_adapter(CandidateDataChangeHandler.process))
    MessageHandlerRegistry.register("handle_candidate_status_changed", _event_bus_adapter(CandidateStatusChangeHandler.process))
    MessageHandlerRegistry.register("handle_interview_scheduled", _event_bus_adapter(_pause_thunder_on_interview))

    # Candidate lifecycle handlers (rejection, archiving, reactivation)
    MessageHandlerRegistry.register("handle_candidate_rejected", _event_bus_adapter(handle_candidate_rejected))
    MessageHandlerRegistry.register("handle_candidate_archived", _event_bus_adapter(handle_candidate_archived))
    MessageHandlerRegistry.register("handle_candidate_reactivated", _event_bus_adapter(handle_candidate_reactivated))

    logger.info("[Registry] Registered 6 event-bus handlers (data-change, status-change, interview, rejection, archive, reactivation)")


def _validate_handler_registry():
    """Validate that critical handlers are registered."""
    critical_handlers = [
        "create_candidate",
        "job_created_flash",
        "flash_recruiter",
    ]

    registered = MessageHandlerRegistry.get_all_handlers()
    missing = [h for h in critical_handlers if h not in registered]

    if missing:
        logger.error(f"[Registry] CRITICAL: Missing handlers: {missing}")
    else:
        logger.info(f"[Registry] All critical handlers registered ({len(registered)} total)")

    return len(missing) == 0

# Initialize default handlers on module load
try:
    _initialize_default_handlers()
    _register_event_bus_handlers()
    _validate_handler_registry()
except Exception as e:
    logger.warning(f"[Registry] Failed to initialize default handlers: {e}")
