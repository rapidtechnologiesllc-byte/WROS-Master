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
    from app.services.channel_processors.candidate_queue_processor import CandidateQueueProcessor

    # Register candidate handlers
    MessageHandlerRegistry.register("create_candidate", CandidateQueueProcessor.process)

    # Register Thunder/engagement handlers
    MessageHandlerRegistry.register("engage_candidate_with_thunder", _handle_thunder_engagement)
    MessageHandlerRegistry.register("assign_thunder_agent", _handle_thunder_engagement)

    # Register job handlers
    try:
        from app.services.message_handlers.job_created_handler import handle_job_created
        from app.services.message_handlers.job_status_changed_handler import handle_job_status_changed
        MessageHandlerRegistry.register("job_created", handle_job_created)
        MessageHandlerRegistry.register("job_status_changed", handle_job_status_changed)
    except ImportError as e:
        logger.warning(f"[Registry] Could not import job handlers: {e}")

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
    """Handle Thunder engagement messages."""
    from app.models.candidate import Candidate
    from app.models.candidate_ai import CandidateConversation
    from app.services.thunder_service import send_thunder_message, has_active_consent

    candidate_id = message.payload.get('candidate_id')

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
        if has_active_consent(db, candidate_id):
            try:
                initial_message = f"Hi {candidate.candidateFirstName}, thanks for your interest! Let's explore this opportunity."
                send_thunder_message(
                    db=db,
                    conversation=conversation,
                    candidate=candidate,
                    message_body=initial_message,
                    sender_type="ai_agent",
                    channel="whatsapp"
                )
                db.commit()
                logger.info(f"[Thunder] Sent initial message to {candidate_id}")
            except Exception as msg_err:
                logger.warning(f"[Thunder] Could not send message (no consent?): {msg_err}, marking candidate as engaged anyway")
                db.commit()
        else:
            logger.info(f"[Thunder] No consent for {candidate_id}, conversation created but no message sent")
            db.commit()

        return {
            "status": "thunder_engaged_and_messaged",
            "candidate_id": candidate_id,
            "conversation_created": True,
            "message_sent": has_active_consent(db, candidate_id)
        }

    except Exception as e:
        logger.error(f"[Thunder] Failed to engage candidate {candidate_id}: {e}", exc_info=True)
        raise


# Initialize default handlers on module load
try:
    _initialize_default_handlers()
except Exception as e:
    logger.warning(f"[Registry] Failed to initialize default handlers: {e}")
