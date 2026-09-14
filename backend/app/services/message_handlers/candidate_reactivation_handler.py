"""Message Handler: Candidate Reactivation

Triggers: candidate_reactivation message (archive → active transition)
Purpose: Resume Thunder engagement, check 90-day rejection cooling period
Output: Candidate marked active, Thunder resumed/deprioritized
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class CandidateReactivationHandler:
    """Resume candidate engagement after reactivation."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=15)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Reactivate candidate engagement.

        Args:
            message: ChannelQueueItem with payload containing:
                - candidate_id: Candidate to reactivate
            db: Database session

        Returns:
            {
                'candidate_id': str,
                'can_resume_thunder': bool,
                'deprioritized': bool,
                'status': 'processed'
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

            if not candidate_id:
                raise ValueError("Missing required field: candidate_id")

            logger.info(f"[CandidateReactivation] Reactivating candidate: {candidate_id}")

            # PHASE 1: Fetch candidate
            from app.models.candidate import Candidate

            candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            # PHASE 2: Check 90-day rejection cooling period
            can_resume_thunder = True
            deprioritized = False

            if hasattr(candidate, 'previous_status') and candidate.previous_status == "REJECTED":
                if hasattr(candidate, 'status_changed_at') and candidate.status_changed_at:
                    days_since_rejection = (datetime.utcnow() - candidate.status_changed_at).days
                    if days_since_rejection < 90:
                        deprioritized = True
                        logger.warning(
                            f"[CandidateReactivation] Within 90-day cooling period: "
                            f"{days_since_rejection} days since rejection"
                        )

            # PHASE 3: Resume Thunder if cleared
            if can_resume_thunder:
                candidate.thunder_enabled = True
                logger.info(f"[CandidateReactivation] Thunder resumed for {candidate_id}")

            # PHASE 4: Commit transaction
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(f"[CandidateReactivation] Commit failed: {commit_err}", exc_info=True)
                raise RuntimeError(f"Failed to reactivate: {str(commit_err)}") from commit_err

            logger.info(f"[CandidateReactivation] ✅ Reactivation complete")

            return {
                'candidate_id': str(candidate_id),
                'can_resume_thunder': can_resume_thunder,
                'deprioritized': deprioritized,
                'status': 'processed'
            }

        except ValueError as ve:
            logger.error(f"[CandidateReactivation] Validation error: {ve}")
            raise

        except OperationalError as oe:
            logger.error(f"[CandidateReactivation] DB error: {oe}", exc_info=True)
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[CandidateReactivation] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that candidate was reactivated."""
        from app.services.message_handlers.validate_handlers_factory import ValidateHandlersFactory
        return ValidateHandlersFactory.validate_candidate_reactivation_timestamp(result, db, "candidate_reactivation")

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= CandidateReactivationHandler.MAX_RETRIES:
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
                minutes=CandidateReactivationHandler.RETRY_DELAY_MINUTES
            )
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"[CandidateReactivation] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            CandidateReactivationHandler.validate(message, result, db)
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err
            logger.info(f"[CandidateReactivation] ✅ Message marked COMPLETED")
        except ValueError:
            db.rollback()
            raise
        except RuntimeError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"[CandidateReactivation] Unexpected error: {e}", exc_info=True)
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
            logger.error(f"[CandidateReactivation] Failed to mark FAILED: {e}", exc_info=True)
            raise


def handle_candidate_reactivated(event_payload: Dict[str, Any], db: Session = None) -> Dict[str, Any]:
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
        result = CandidateReactivationHandler.process(message, db)
        return result
    finally:
        if should_close:
            db.close()
