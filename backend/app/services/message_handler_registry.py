"""Message Handler Registry - Maps message types to handler functions."""
import logging
from typing import Dict, Callable, Optional, Any
from app.core.database import SessionLocal
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
    except ImportError as e:
        logger.warning(f"[Registry] Could not import job handlers: {e}")

    # Register cascade failure signal handler (CRITICAL FIX #7)
    try:
        from app.services.message_handlers.cascade_failure_signal_handler import CascadeFailureSignalHandler
        MessageHandlerRegistry.register("cascade_failure_signal", CascadeFailureSignalHandler.process)
    except ImportError as e:
        logger.warning(f"[Registry] Could not import cascade failure signal handler: {e}")

    # Register offer handlers
    try:
        from app.services.message_handlers.offer_approved_handler import handle_offer_approved
        from app.services.message_handlers.offer_sent_handler import handle_offer_sent
        from app.services.message_handlers.offer_accepted_handler import handle_offer_accepted
        from app.services.message_handlers.offer_rejected_handler import handle_offer_rejected
        MessageHandlerRegistry.register("offer_approved", handle_offer_approved)
        MessageHandlerRegistry.register("offer_sent", handle_offer_sent)
        MessageHandlerRegistry.register("offer_accepted", handle_offer_accepted)
        MessageHandlerRegistry.register("offer_rejected", handle_offer_rejected)
    except ImportError as e:
        logger.warning(f"[Registry] Could not import offer handlers: {e}")

    # Register Phase 2: Revenue & Invoicing handlers (CRITICAL - ASC 606 compliance)
    try:
        from app.services.message_handlers.invoice_generation_handler import InvoiceGenerationHandler
        from app.services.message_handlers.invoice_approved_handler import InvoiceApprovedHandler
        from app.services.message_handlers.invoice_sent_handler import InvoiceSentHandler
        from app.services.message_handlers.invoice_paid_handler import InvoicePaidHandler
        from app.services.message_handlers.revenue_recognized_handler import RevenueRecognizedHandler
        from app.services.message_handlers.s316_milestone_completion_handler import S316MilestoneCompletionHandler
        from app.services.message_handlers.s316_invoice_handler import S316InvoiceHandler

        # Standard timesheet-based invoicing (5 handlers)
        MessageHandlerRegistry.register("invoice_generation", InvoiceGenerationHandler.process)
        MessageHandlerRegistry.register("invoice_approved", InvoiceApprovedHandler.process)
        MessageHandlerRegistry.register("invoice_sent", InvoiceSentHandler.process)
        MessageHandlerRegistry.register("invoice_paid", InvoicePaidHandler.process)
        MessageHandlerRegistry.register("revenue_recognized", RevenueRecognizedHandler.process)

        # S316 service-based invoicing (2 handlers)
        MessageHandlerRegistry.register("s316_milestone_completion", S316MilestoneCompletionHandler.process)
        MessageHandlerRegistry.register("s316_invoice_generation", S316InvoiceHandler.process)

        logger.info("[Registry] Registered Phase 2 invoice & revenue handlers (7 handlers total)")
    except ImportError as e:
        logger.warning(f"[Registry] Could not import invoice/revenue handlers: {e}")
    except Exception as e:
        logger.error(f"[Registry] Failed to register invoice/revenue handlers: {e}", exc_info=True)

    # Register Phase 3: Hiring Manager Validation handlers (CRITICAL - hiring workflow)
    try:
        from app.services.message_handlers.hm_validation_created_handler import HMValidationCreatedHandler
        from app.services.message_handlers.hm_validation_notification_handler import HMValidationNotificationHandler
        from app.services.message_handlers.hm_validation_response_handler import HMValidationResponseHandler
        from app.services.message_handlers.hm_validation_escalation_handler import HMValidationEscalationHandler

        MessageHandlerRegistry.register("hm_validation_created", HMValidationCreatedHandler.process)
        MessageHandlerRegistry.register("hm_validation_notify", HMValidationNotificationHandler.process)
        MessageHandlerRegistry.register("hm_validation_response_submitted", HMValidationResponseHandler.process)
        MessageHandlerRegistry.register("hm_validation_escalated", HMValidationEscalationHandler.process)
        logger.info("[Registry] Registered Phase 3 HM validation handlers (4 of 5 core)")

        from app.services.message_handlers.referral_submission_handler import ReferralSubmissionHandler
        from app.services.message_handlers.referral_hire_conversion_handler import ReferralHireConversionHandler
        from app.services.message_handlers.referral_payment_approval_handler import ReferralPaymentApprovalHandler

        MessageHandlerRegistry.register("employee_referral_submitted", ReferralSubmissionHandler.process)
        MessageHandlerRegistry.register("referral_hire_conversion", ReferralHireConversionHandler.process)
        MessageHandlerRegistry.register("referral_payment_approval", ReferralPaymentApprovalHandler.process)
        logger.info("[Registry] Registered Phase 3 referral handlers (3 handlers)")
    except ImportError as e:
        logger.warning(f"[Registry] Could not import HM validation handlers: {e}")
    except Exception as e:
        logger.error(f"[Registry] Failed to register HM validation handlers: {e}", exc_info=True)

    # Register interview handlers (legacy signature, needs adapter)
    try:
        from app.services.message_handlers.interview_scheduled_handler import handle_interview_scheduled as legacy_handle_interview_scheduled

        def _interview_scheduled_adapter(message: Any, db: Session) -> Dict[str, Any]:
            """Adapter for legacy interview_scheduled handler."""
            event_payload = {
                "candidate_id": message.payload.get("candidate_id"),
                "data": message.payload
            }
            return legacy_handle_interview_scheduled(event_payload, db)

        MessageHandlerRegistry.register("interview_scheduled", _interview_scheduled_adapter)
    except ImportError as e:
        logger.warning(f"[Registry] Could not import interview handlers: {e}")

    # Register project/milestone handlers
    try:
        from app.services.message_handlers.project_handlers import handle_project_created, handle_project_status_changed
        MessageHandlerRegistry.register("project_created", handle_project_created)
        MessageHandlerRegistry.register("project_status_changed", handle_project_status_changed)
    except ImportError:
        logger.info("[Registry] Project handlers not yet available")

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


# Thunder engagement handler moved to ThunderEngagementHandler class
# See: app/services/message_handlers/thunder_engagement_handler.py


# Initialize default handlers on module load
try:
    _initialize_default_handlers()
except Exception as e:
    logger.warning(f"[Registry] Failed to initialize default handlers: {e}")
