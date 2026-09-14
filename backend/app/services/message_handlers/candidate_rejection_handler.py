"""Message Handler: Candidate Rejection

Triggers: candidate_rejection message (manual or system rejection)
Purpose: Archive candidate, set 90-day no-contact flag, record rejection
Output: Rejection recorded, candidate archived
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class CandidateRejectionHandler:
    """Record candidate rejection and archive engagement."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=15)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Record candidate rejection.

        Args:
            message: ChannelQueueItem with payload containing:
                - candidate_id: Rejected candidate
                - rejection_reason: Reason for rejection
            db: Database session

        Returns:
            {
                'candidate_id': str,
                'rejection_reason': str,
                'no_contact_until': str,
                'status': 'rejected'
            }

        Raises:
            ValueError: Invalid payload (non-retryable)
            RuntimeError: Database errors (retryable)
        """
        try:
            if not message.payload:
                raise ValueError(f"Message {message.id} has no payload")

            payload = message.payload
            candidate_id = payload.get('candidate_id')
            reason = payload.get('rejection_reason', 'Candidate rejected')

            if not candidate_id:
                raise ValueError("Missing required field: candidate_id")

            logger.info(f"[CandidateRejection] Recording rejection for {candidate_id}: {reason}")

            # PHASE 1: Fetch candidate
            from app.models.candidate import Candidate

            candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            # PHASE 2: Archive candidate (disable Thunder)
            candidate.thunder_enabled = False

            # PHASE 3: Calculate 90-day no-contact expiry
            no_contact_until = datetime.utcnow() + timedelta(days=90)

            logger.info(
                f"[CandidateRejection] No-contact period: {no_contact_until.isoformat()}"
            )

            # PHASE 4: Record rejection event
            from app.models.event_log import EventLog

            rejection_event = EventLog(
                event_type="candidate_rejection",
                entity_id=str(candidate_id),
                entity_type="candidate",
                data={"reason": reason, "no_contact_until": no_contact_until.isoformat()},
                created_at=datetime.utcnow()
            )
            db.add(rejection_event)

            # PHASE 5: Commit transaction
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(f"[CandidateRejection] Commit failed: {commit_err}", exc_info=True)
                raise RuntimeError(f"Failed to record rejection: {str(commit_err)}") from commit_err

            logger.info(f"[CandidateRejection] ✅ Rejection recorded")

            return {
                'candidate_id': str(candidate_id),
                'rejection_reason': reason,
                'no_contact_until': no_contact_until.isoformat(),
                'status': 'rejected'
            }

        except ValueError as ve:
            logger.error(f"[CandidateRejection] Validation error: {ve}")
            raise

        except OperationalError as oe:
            logger.error(f"[CandidateRejection] DB error: {oe}", exc_info=True)
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[CandidateRejection] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that rejection was recorded."""
        from app.services.message_handlers.validate_handlers_factory import ValidateHandlersFactory
        return ValidateHandlersFactory.validate_candidate_rejection_recorded(result, db, "candidate_rejection")

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= CandidateRejectionHandler.MAX_RETRIES:
            return False
        if hasattr(message, 'next_retry_at') and message.next_retry_at:
            if datetime.utcnow() < message.next_retry_at:
                return False
        return True

    @staticmethod
    def on_retry(message: Any, error: str, db: Session) -> None:
        """Schedule message for retry."""
        try:
            db.rollback()
            message.retry_count += 1
            message.error = error[:1000] if error else "Unknown error"
            message.next_retry_at = datetime.utcnow() + timedelta(
                minutes=CandidateRejectionHandler.RETRY_DELAY_MINUTES
            )
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"[CandidateRejection] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            CandidateRejectionHandler.validate(message, result, db)
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err
            logger.info(f"[CandidateRejection] ✅ Message marked COMPLETED")
        except ValueError:
            db.rollback()
            raise
        except RuntimeError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"[CandidateRejection] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def on_failed(message: Any, final_error: str, db: Session) -> None:
        """Mark message as FAILED after all retries."""
        try:
            db.rollback()
            message.status = "FAILED"
            message.error = final_error[:1000] if final_error else "Unknown error"
            message.completed_at = datetime.utcnow()
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"[CandidateRejection] Failed to mark FAILED: {e}", exc_info=True)
            raise


def handle_candidate_rejected(event_payload: Dict[str, Any], db: Session = None) -> Dict[str, Any]:
    """Legacy adapter for old event payload format."""
    from app.core.database import SessionLocal

    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False

    try:
        class LegacyMessage:
            def __init__(self, payload):
                self.id = "legacy"
                self.payload = payload

        message = LegacyMessage(event_payload)
        result = CandidateRejectionHandler.process(message, db)
        return result
    finally:
        if should_close:
            db.close()
