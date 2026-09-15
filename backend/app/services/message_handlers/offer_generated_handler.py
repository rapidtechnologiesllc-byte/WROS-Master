"""Handler: Offer Generated Events."""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from app.models.candidate import Candidate
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class OfferGeneratedHandler:
    """Handles offer generated events."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=8)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """Process offer generated events.

        When offer is created for candidate:
        - Archive active conversations (don't message during offer discussion)
        - Switch to onboarding Thunder flow
        - Set offer acceptance deadline

        Args:
            message: ChannelQueueItem with type='offer_generated'
            db: SQLAlchemy session

        Returns:
            Handler result: {"status": "processed", "offer_id": "...", "actions": [...]}
        """
        try:
            payload = message.payload or {}
            candidate_id = payload.get("candidate_id")
            data = payload.get("data", {})
            offer_id = data.get("offer_id")
            offer_acceptance_deadline = data.get("offer_acceptance_deadline")

            # Fetch candidate
            candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            actions_taken = []

            # Archive active conversations
            if candidate.thunder_enabled:
                candidate.thunder_enabled = False
                actions_taken.append("archived_active_conversations")
                logger.info(f"[OfferGenerated] Archived conversations for candidate {candidate_id}: offer generated")

            # Log offer details
            logger.info(f"[OfferGenerated] Offer {offer_id} generated for candidate {candidate_id}")
            logger.info(f"  Acceptance deadline: {offer_acceptance_deadline}")
            actions_taken.append("switched_to_onboarding_flow")

            db.commit()

            return {
                "status": "processed",
                "candidate_id": candidate_id,
                "offer_id": offer_id,
                "offer_acceptance_deadline": offer_acceptance_deadline,
                "actions": actions_taken
            }

        except ValueError as ve:
            logger.error(f"[OfferGenerated] Validation error: {ve}")
            raise
        except OperationalError as oe:
            logger.error(f"[OfferGenerated] DB error: {oe}", exc_info=True)
            raise RuntimeError(f"Database error: {str(oe)}") from oe
        except Exception as e:
            logger.error(f"[OfferGenerated] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that candidate was archived successfully."""
        from app.services.message_handlers.validate_handlers_factory import ValidateHandlersFactory
        return ValidateHandlersFactory.validate_candidate_archived(result, db, "offer_generated")

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        return message.retry_count < OfferGeneratedHandler.MAX_RETRIES

    @staticmethod
    def on_retry(message: Any, error: str, db: Session) -> None:
        """Schedule message for retry."""
        db.rollback()
        message.retry_count += 1
        message.error = error[:1000]
        message.next_retry_at = datetime.utcnow() + timedelta(minutes=OfferGeneratedHandler.RETRY_DELAY_MINUTES)
        db.commit()

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation passes."""
        OfferGeneratedHandler.validate(message, result, db)
        message.status = "COMPLETED"
        message.completed_at = datetime.utcnow()
        db.commit()

    @staticmethod
    def on_failed(message: Any, final_error: str, db: Session) -> None:
        """Mark message as FAILED after all retries exhausted."""
        db.rollback()
        message.status = "FAILED"
        message.error = final_error[:1000]
        message.completed_at = datetime.utcnow()
        db.commit()


def handle_offer_generated(message: Any, db: Session) -> Dict[str, Any]:
    """Handle offer_generated message."""
    return OfferGeneratedHandler.process(message, db)
