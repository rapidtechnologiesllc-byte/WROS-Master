"""Message Handler: Candidate Status Change

Triggers: candidate_status_change message (Applied→Interview→Offer→Joined→Rejected)
Purpose: Handle status transitions, pause Thunder when appropriate
Output: Status updated, Thunder engagement adjusted per status
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class CandidateStatusChangeHandler:
    """Handle candidate status transitions and update engagement."""

    TIMEOUT_SECONDS = 30
    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process candidate status changes.

        Args:
            message: ChannelQueueItem with payload containing:
                - candidate_id: Candidate changing status
                - old_status: Previous status
                - new_status: New status
                - status_change_reason: Reason for change
            db: Database session

        Returns:
            {
                'candidate_id': str,
                'old_status': str,
                'new_status': str,
                'actions_taken': list,
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
            old_status = payload.get('old_status')
            new_status = payload.get('new_status')
            reason = payload.get('status_change_reason', 'Status changed')

            if not candidate_id or not new_status:
                raise ValueError("Missing required fields: candidate_id, new_status")

            logger.info(
                f"[CandidateStatusChange] Processing: {candidate_id} "
                f"{old_status} → {new_status}"
            )

            # PHASE 1: Fetch candidate
            from app.models.candidate import Candidate

            candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            # PHASE 2: Thunder's nurture outreach stops once the candidate is in the process
            from app.services.candidate_status_notifications import THUNDER_OFF_STATUSES, send_status_email
            actions_taken = []
            if new_status in THUNDER_OFF_STATUSES and candidate.thunder_enabled:
                candidate.thunder_enabled = False
                actions_taken.append("paused_thunder")

            # PHASE 2b: a referred candidate's referral follows their pipeline (My Referrals,
            # and the pending bonus for Finance on hire)
            from app.services.employee_referral_service import EmployeeReferralService
            referral_status = EmployeeReferralService.sync_with_pipeline_status(db, candidate, new_status)
            if referral_status:
                actions_taken.append(f"referral:{referral_status}")

            # PHASE 3: Update status tracking
            candidate.previous_status = old_status
            candidate.status_changed_at = datetime.utcnow()
            if hasattr(candidate, 'status_change_reason'):
                candidate.status_change_reason = reason

            # PHASE 4: Commit transaction
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(f"[CandidateStatusChange] Commit failed: {commit_err}", exc_info=True)
                raise RuntimeError(f"Failed to update status: {str(commit_err)}") from commit_err

            # PHASE 5: Tell the candidate (every status; wording = the stage's message template),
            # queued through Thunder's guardrails (candidate_notices). A failure to queue raises.
            email = send_status_email(db, candidate, new_status)
            if email.get("queued"):
                actions_taken.append(f"email_queued:{email['template']}")
            delivery_channel = "email" if email.get("queued") else None
            delivery_id = email.get("email_id")

            logger.info("[CandidateStatusChange] ✅ Status change processed")

            return {
                'candidate_id': str(candidate_id),
                'old_status': old_status,
                'new_status': new_status,
                'actions_taken': actions_taken,
                'delivery_id': delivery_id,
                'delivery_channel': delivery_channel,
                'status': 'processed'
            }

        except ValueError as ve:
            logger.error(f"[CandidateStatusChange] Validation error: {ve}")
            raise

        except OperationalError as oe:
            logger.error(f"[CandidateStatusChange] DB error: {oe}", exc_info=True)
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[CandidateStatusChange] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that status was changed."""
        from app.services.message_handlers.validate_handlers_factory import ValidateHandlersFactory
        return ValidateHandlersFactory.validate_candidate_status_matches(
            result, db, "candidate_status_change", result.get('new_status')
        )

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= CandidateStatusChangeHandler.MAX_RETRIES:
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
                minutes=CandidateStatusChangeHandler.RETRY_DELAY_MINUTES
            )
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"[CandidateStatusChange] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            CandidateStatusChangeHandler.validate(message, result, db)
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err
            logger.info("[CandidateStatusChange] ✅ Message marked COMPLETED")
        except ValueError:
            db.rollback()
            raise
        except RuntimeError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"[CandidateStatusChange] Unexpected error: {e}", exc_info=True)
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
            logger.error(f"[CandidateStatusChange] Failed to mark FAILED: {e}", exc_info=True)
            raise


def handle_candidate_status_changed(event_payload: Dict[str, Any], db: Session = None) -> Dict[str, Any]:
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
        result = CandidateStatusChangeHandler.process(message, db)
        return result
    finally:
        if should_close:
            db.close()
