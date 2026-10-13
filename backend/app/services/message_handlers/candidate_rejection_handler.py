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

from app.core.config import settings
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


def _send_rejection_email(db: Session, candidate: Any, rejection: Any):
    """Neutral status-update email; marks the rejection email_sent so it goes out once."""
    from app.services.email_service import EmailService

    candidate_email = getattr(candidate, 'candidateEmail', None)
    if not candidate_email:
        return None
    from app.services.linkedin_pipeline_task_service import is_placeholder_email
    if is_placeholder_email(candidate_email):
        return None
    name = getattr(candidate, 'candidateFirstName', None) or 'there'
    result = EmailService.send_email(
        to_email=candidate_email,
        subject="Your application",
        body_content=(f"<p>Dear {name},</p><p>Thank you for your interest and for the time you gave us. "
                      "We have decided not to move forward with your application at this time.</p>"
                      "<p>We wish you every success.</p><p>Recruiting Team</p>"),
        is_html=True,
    )
    if result.get('status') != 'success':
        logger.warning(f"[CandidateRejection] Rejection email not sent to {candidate_email}: {result}")
        return None
    rejection.email_sent = True
    rejection.email_sent_at = datetime.utcnow()
    db.commit()
    return f"msgraph:{rejection.id}"


class CandidateRejectionHandler:
    """Record candidate rejection and archive engagement."""

    TIMEOUT_SECONDS = 15
    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
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

            # PHASE 2: Record the rejection through the one shared path (idempotent):
            # candidate_rejections row (starts the 90-day no-contact period), Thunder off,
            # candidate_rejection EventLog entry.
            from app.services.candidate_contact_policy import NO_CONTACT_DAYS_AFTER_REJECTION, record_rejection

            rejection = record_rejection(
                db, candidate, reason,
                rejected_by_user_id=payload.get('rejected_by_user_id'),
                job_id=payload.get('job_id'),
            )
            no_contact_until = rejection.rejected_at + timedelta(days=NO_CONTACT_DAYS_AFTER_REJECTION)
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(f"[CandidateRejection] Commit failed: {commit_err}", exc_info=True)
                raise RuntimeError(f"Failed to record rejection: {str(commit_err)}") from commit_err

            # PHASE 3: Candidate notification. Off until the CEO decides the rejection-email UX
            # (OPEN_ITEMS decision 5): REJECTION_EMAIL_ENABLED=true turns it on. The internal
            # reason (e.g. an interview verdict) is never sent to the candidate.
            email_delivery_id = None
            if settings.REJECTION_EMAIL_ENABLED and not rejection.email_sent:
                email_delivery_id = _send_rejection_email(db, candidate, rejection)

            logger.info(f"[CandidateRejection] ✅ Rejection recorded for {candidate_id}")

            return {
                'candidate_id': str(candidate_id),
                'rejection_reason': reason,
                'no_contact_until': no_contact_until.isoformat(),
                'status': 'rejected',
                'email_delivery_id': email_delivery_id
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
            logger.info("[CandidateRejection] ✅ Message marked COMPLETED")
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
