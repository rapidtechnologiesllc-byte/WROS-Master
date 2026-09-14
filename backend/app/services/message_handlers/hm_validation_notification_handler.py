"""Message Handler: HM Validation Questionnaire Notification

Triggers: hm_validation_notify message (from hm_validation_created_handler)
Purpose: Send validation questionnaire email to Hiring Manager
Output: Email sent, delivery logged, HM awaits response
Delivery: Email via SendGrid with validation portal link
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class HMValidationNotificationHandler:
    """Send HM validation questionnaire via email."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=45)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Send HM validation questionnaire email.

        Email contains:
        - Candidate profile summary
        - Job position details
        - Validation questions (4-6)
        - Link to validation portal
        - 24-hour deadline

        Args:
            message: ChannelQueueItem with payload containing:
                - validation_id: HM validation record
                - candidate_id: Candidate being validated
                - job_id: Job being validated for
                - hiring_manager_id: HM receiving email
            db: Database session

        Returns:
            {
                'validation_id': str,
                'email_sent': bool,
                'delivery_id': str or None,
                'hm_email': str
            }

        Raises:
            ValueError: Invalid payload (non-retryable)
            RuntimeError: Email/DB errors (retryable)
        """
        try:
            if not message.payload:
                raise ValueError(f"Message {message.id} has no payload")

            payload = message.payload
            validation_id = payload.get('validation_id')
            candidate_id = payload.get('candidate_id')
            job_id = payload.get('job_id')
            hiring_manager_id = payload.get('hiring_manager_id')

            if not all([validation_id, candidate_id, job_id, hiring_manager_id]):
                raise ValueError("Missing required fields in payload")

            logger.info(
                f"[HMValidationNotif] Sending notification: validation={validation_id}"
            )

            # PHASE 1: Verify validation exists
            from app.models.hiring import HiringManagerValidation

            validation = db.query(HiringManagerValidation).filter(
                HiringManagerValidation.id == validation_id
            ).first()

            if not validation:
                raise ValueError(f"HM validation {validation_id} not found")

            if validation.status != 'PENDING':
                raise ValueError(
                    f"Cannot notify on validation {validation_id} with status {validation.status}"
                )

            # PHASE 2: Get candidate and job details
            from app.models.candidate import Candidate
            from app.models.user import Jobs, User

            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()

            if not job:
                raise ValueError(f"Job {job_id} not found")

            hm = db.query(User).filter(User.id == hiring_manager_id).first()

            if not hm:
                raise ValueError(f"Hiring manager {hiring_manager_id} not found")

            hm_email = hm.email
            logger.info(f"[HMValidationNotif] HM email: {hm_email}")

            # PHASE 3: Compose validation questionnaire email
            email_subject = f"Action Required: Validate {candidate.candidateFirstName} for {job.jobTitle}"

            email_body = f"""
Hi {hm.firstName or 'Hiring Manager'},

A candidate has matched to your open position. Please review and provide your assessment within 24 hours.

**CANDIDATE PROFILE**
Name: {candidate.candidateFirstName} {candidate.candidateLast Name if hasattr(candidate, 'candidateLast Name') else ''}
Email: {candidate.candidateEmail}
Phone: {candidate.candidateMobile if hasattr(candidate, 'candidateMobile') else 'N/A'}
Experience: {candidate.candidateExperienceLevel if hasattr(candidate, 'candidateExperienceLevel') else 'N/A'} years

**POSITION**
Title: {job.jobTitle}
Department: {job.jobDepartment if hasattr(job, 'jobDepartment') else 'N/A'}
Level: {job.jobLevel if hasattr(job, 'jobLevel') else 'N/A'}

**VALIDATION QUESTIONS** (Please answer by {validation.due_at.strftime('%Y-%m-%d %H:%M UTC')})

Q1: Is the candidate's experience level appropriate for this role?
    ☐ Yes ☐ No ☐ Maybe

Q2: Do you have any red flags from the candidate profile?
    [Open response - describe any concerns]

Q3: Which specific skills are most critical for success in this role?
    [Open response]

Q4: Would you recommend proceeding with an interview?
    ☐ Yes ☐ No ☐ Need more information

**IMPORTANT:** Please complete this assessment within 24 hours to keep the hiring process on track.
If "Maybe" or "Need more info", provide context so we can discuss with your manager.

[Respond here: {payload.get('portal_link', f'/hr/hm-validations/{validation_id}')}]

Thank you,
AI Recruiting
"""

            logger.info(f"[HMValidationNotif] Email composed, sending to {hm_email}")

            # PHASE 4: Send email via delivery service
            from app.services.delivery_factory import DeliveryFactory

            delivery_service = DeliveryFactory.get_delivery_service()
            if not delivery_service:
                raise RuntimeError("Delivery service not configured")

            delivery_result = delivery_service.send_email(
                to=hm_email,
                subject=email_subject,
                body=email_body
            )

            if not delivery_result or delivery_result.get('status') != 'sent':
                raise RuntimeError(
                    f"Email delivery failed: {delivery_result.get('error', 'Unknown error')}"
                )

            delivery_id = delivery_result.get('delivery_id')
            logger.info(f"[HMValidationNotif] Email sent successfully: {delivery_id}")

            # PHASE 5: Log delivery to message_delivery table
            from app.models.message_delivery import MessageDelivery

            msg_delivery = MessageDelivery(
                validation_id=validation_id,
                delivery_type='email',
                recipient=hm_email,
                channel='email',
                status='sent',
                delivery_id=delivery_id,
                sent_at=datetime.utcnow(),
                created_at=datetime.utcnow()
            )

            db.add(msg_delivery)

            # PHASE 6: Update validation to mark notification sent
            validation.email_sent_at = datetime.utcnow()

            # PHASE 7: Commit transaction
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(f"[HMValidationNotif] Commit failed: {commit_err}", exc_info=True)
                raise RuntimeError(f"Failed to log delivery: {str(commit_err)}") from commit_err

            logger.info(f"[HMValidationNotif] ✅ Notification sent successfully")

            return {
                'validation_id': str(validation_id),
                'email_sent': True,
                'delivery_id': str(delivery_id) if delivery_id else None,
                'hm_email': hm_email
            }

        except ValueError as ve:
            logger.error(f"[HMValidationNotif] Validation error: {ve}")
            raise

        except RuntimeError as re:
            logger.error(f"[HMValidationNotif] Runtime error (retryable): {re}")
            raise

        except Exception as e:
            logger.error(f"[HMValidationNotif] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that notification was sent successfully."""
        if not result or "validation_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        if not result.get('email_sent'):
            raise ValueError("Email was not sent")

        validation_id = result.get('validation_id')

        try:
            from app.models.hiring import HiringManagerValidation

            validation = db.query(HiringManagerValidation).filter(
                HiringManagerValidation.id == validation_id
            ).first()

            if not validation:
                raise ValueError(f"Validation {validation_id} not found")

            if not validation.email_sent_at:
                raise ValueError(f"Validation {validation_id} email_sent_at not set")

            logger.info(f"✅ HM notification validated: {validation_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[HMValidationNotif] RETRYABLE validation error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= HMValidationNotificationHandler.MAX_RETRIES:
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
                minutes=HMValidationNotificationHandler.RETRY_DELAY_MINUTES
            )
            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"[HMValidationNotif] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            HMValidationNotificationHandler.validate(message, result, db)

            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err

            logger.info(f"[HMValidationNotif] ✅ Message marked COMPLETED")

        except ValueError:
            db.rollback()
            raise

        except RuntimeError:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            logger.error(f"[HMValidationNotif] Unexpected error: {e}", exc_info=True)
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
            logger.error(f"[HMValidationNotif] Failed to mark as FAILED: {e}", exc_info=True)
            raise
