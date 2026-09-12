"""Message Handler Registry - Maps message types to handler functions."""
import logging
from typing import Dict, Callable, Optional, Any
from app.core.database import SessionLocal
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


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
        MessageHandlerRegistry.register("engage_candidate_with_thunder", _handle_thunder_engagement)
        MessageHandlerRegistry.register("assign_thunder_agent", _handle_thunder_engagement)
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


def _handle_thunder_engagement(message: Any, db: Session) -> Dict[str, Any]:
    """Handle Thunder engagement messages with timeout protection."""
    import threading
    import time
    from app.models.candidate import Candidate
    from app.models.candidate_ai import CandidateConversation
    from app.services.thunder_service import send_thunder_message, has_active_consent

    candidate_id = message.payload.get('candidate_id')
    SEND_MESSAGE_TIMEOUT = 10  # 10 second max for sending message

    try:
        # 1. Get candidate
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            raise ValueError(f"Candidate {candidate_id} not found")

        # 2. Create/fetch conversation
        conversation = db.query(CandidateConversation).filter(
            CandidateConversation.candidate_id == candidate_id
        ).first()

        if not conversation:
            conversation = CandidateConversation(
                candidate_id=candidate_id,
                owner_type="Thunder",
                owner_id="Thunder_Autonomous",
                status="ACTIVE",
            )
            db.add(conversation)
            db.flush()
            logger.info(f"[Thunder] Created conversation for {candidate_id}")

        # 3. Check consent & send initial message
        message_sent = False
        if has_active_consent(db, candidate_id):
            try:
                # Phase 2: Check if SLM generated email content (from READY_TO_SEND state)
                initial_message = message.payload.get('slm_generated_email_body') if message else None

                # Fallback: Use generic message if SLM didn't generate one
                if not initial_message:
                    initial_message = f"Hi {candidate.candidateFirstName}, thanks for your interest! Let's explore this opportunity."
                    logger.debug(f"[Thunder] No SLM-generated email for {candidate_id}, using fallback message")
                else:
                    logger.info(f"[Thunder] Using SLM-generated email for {candidate_id} ({len(initial_message)} chars)")

                # TIMEOUT PROTECTION: Send message in thread with timeout
                send_result = {'success': False, 'exception': None}

                def _send_with_timeout():
                    try:
                        send_thunder_message(
                            db=db,
                            conversation=conversation,
                            candidate=candidate,
                            message_body=initial_message,
                            sender_type="ai_agent",
                            channel="whatsapp"
                        )
                        send_result['success'] = True
                    except Exception as e:
                        send_result['exception'] = e

                send_thread = threading.Thread(target=_send_with_timeout, daemon=True)
                send_thread.start()
                send_thread.join(timeout=SEND_MESSAGE_TIMEOUT)

                if send_thread.is_alive():
                    raise RuntimeError(f"Thunder message send timed out after {SEND_MESSAGE_TIMEOUT}s for {candidate_id}")

                if send_result['exception']:
                    raise send_result['exception']

                db.commit()
                logger.info(f"[Thunder] Sent initial message to {candidate_id}")
                message_sent = True
            except Exception as msg_err:
                logger.error(f"[Thunder] Failed to send message to {candidate_id}: {msg_err}", exc_info=True)
                # RE-RAISE so queue processor retries on delivery failure (not just missing consent)
                raise
        else:
            logger.info(f"[Thunder] No consent for {candidate_id}, conversation created but no message sent")
            db.commit()

        return {
            "status": "thunder_engaged_and_messaged",
            "candidate_id": candidate_id,
            "conversation_created": True,
            "message_sent": message_sent,
            "delivery_confirmed": message_sent
        }

    except Exception as e:
        logger.error(f"[Thunder] Failed to engage candidate {candidate_id}: {e}", exc_info=True)
        raise


# Initialize default handlers on module load
try:
    _initialize_default_handlers()
except Exception as e:
    logger.warning(f"[Registry] Failed to initialize default handlers: {e}")
