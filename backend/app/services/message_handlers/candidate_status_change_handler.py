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

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=15)
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

            # PHASE 2: Handle status-specific actions
            actions_taken = []

            if new_status == "INTERVIEW":
                if candidate.thunder_enabled:
                    candidate.thunder_enabled = False
                    actions_taken.append("paused_thunder_for_interview")
                    logger.info(f"[CandidateStatusChange] Thunder paused: interview scheduled")

            elif new_status == "OFFER":
                candidate.thunder_enabled = False
                actions_taken.append("paused_thunder_for_offer")
                logger.info(f"[CandidateStatusChange] Thunder paused: offer generated")

            elif new_status == "JOINED":
                candidate.thunder_enabled = False
                actions_taken.append("marked_joined_success")
                logger.info(f"[CandidateStatusChange] Candidate journey complete")

            elif new_status == "REJECTED":
                candidate.thunder_enabled = False
                actions_taken.append("paused_thunder_for_rejection")
                logger.info(f"[CandidateStatusChange] Thunder paused: rejected")

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

            # PHASE 5: Send status change notification via Email (Microsoft Graph)
            delivery_id = None
            delivery_channel = None
            try:
                if new_status in ["INTERVIEW", "OFFER", "JOINED"]:
                    from app.services.email_service import EmailService

                    candidate_name = getattr(candidate, 'candidateFirstName', 'Candidate')
                    candidate_email = getattr(candidate, 'candidateEmail', None)

                    # Email templates
                    status_email_subjects = {
                        "INTERVIEW": "Interview Scheduled - Your Next Step",
                        "OFFER": "Job Offer Extended",
                        "JOINED": "Welcome to the Team!"
                    }
                    status_email_bodies = {
                        "INTERVIEW": f"""Hi {candidate_name},

Great news! You have been selected to interview with our team.

We are impressed with your background and would like to learn more about your qualifications and interest in the position.

Our team will be in touch shortly with interview details.

Best regards,
Recruiting Team
""",
                        "OFFER": f"""Hi {candidate_name},

Congratulations! We are pleased to extend a job offer for the position.

Please check your email for the complete offer letter and next steps.

Thank you for your interest in joining our team!

Best regards,
Recruiting Team
""",
                        "JOINED": f"""Hi {candidate_name},

Welcome to the team! We are excited to have you on board.

Please prepare for your first day and look out for additional onboarding instructions coming soon.

If you have any questions, please don't hesitate to reach out.

Best regards,
HR Team
"""
                    }
                    email_subject = status_email_subjects.get(new_status, f"Application Status Update: {new_status}")
                    email_body = status_email_bodies.get(new_status, f"Your status has been updated to: {new_status}")

                    # Send Email via Microsoft Graph
                    if candidate_email:
                        try:
                            email_result = EmailService.send_email(
                                to_email=candidate_email,
                                subject=email_subject,
                                body_content=email_body,
                                is_html=True
                            )

                            if email_result.get('status') == 'skipped':
                                logger.warning(f"[CandidateStatusChange] Email skipped to {candidate_email}: {email_result.get('reason')}")
                            elif email_result.get('status') != 'success':
                                logger.warning(f"[CandidateStatusChange] Email delivery failed: {email_result}")
                            else:
                                delivery_id = "msgraph_" + str(hash(candidate_email))
                                delivery_channel = 'email'
                                logger.info(f"[CandidateStatusChange] Status update sent via Email to {candidate_email}, delivery_id={delivery_id}")
                        except Exception as email_err:
                            logger.warning(f"[CandidateStatusChange] Email send error: {email_err}")
                    else:
                        logger.warning(f"[CandidateStatusChange] No email available for candidate {candidate_id}")
            except Exception as delivery_err:
                logger.warning(f"[CandidateStatusChange] Delivery service error (non-blocking): {delivery_err}")

            logger.info(f"[CandidateStatusChange] ✅ Status change processed")

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
            logger.info(f"[CandidateStatusChange] ✅ Message marked COMPLETED")
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
