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

    # Note: Additional handlers (interview, offer, job, etc.) will be registered
    # as they are created in Phase 2


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
