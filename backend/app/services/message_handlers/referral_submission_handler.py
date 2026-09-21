"""Message Handler: Employee Referral Submission

Triggers: employee_referral_submitted message
Purpose: Process employee referral, link to candidate or create new
Output: Referral record created with status=PENDING
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class ReferralSubmissionHandler:
    """Process employee referral submission."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=30)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process employee referral.

        Create or link candidate, create Referral record.

        Args:
            message: ChannelQueueItem with payload containing:
                - referrer_user_id: Employee making referral
                - candidate_email: Candidate email
                - candidate_name: Candidate name
                - candidate_phone: Candidate phone (optional)
            db: Database session

        Returns:
            {
                'referral_id': str,
                'candidate_id': str,
                'is_new_candidate': bool,
                'status': 'PENDING'
            }

        Raises:
            ValueError: Invalid payload (non-retryable)
            RuntimeError: Database errors (retryable)
        """
        try:
            if not message.payload:
                raise ValueError(f"Message {message.id} has no payload")

            payload = message.payload
            referrer_user_id = payload.get('referrer_user_id')
            candidate_email = payload.get('candidate_email')
            candidate_name = payload.get('candidate_name')

            if not all([referrer_user_id, candidate_email, candidate_name]):
                raise ValueError("Missing required fields")

            logger.info(
                f"[ReferralSubmission] Processing referral: "
                f"referrer={referrer_user_id}, candidate={candidate_email}"
            )

            # PHASE 1: Queue and wait for candidate creation via unified queue
            from app.services.candidate_creation_sync_wait import queue_and_wait_for_candidate

            name_parts = candidate_name.split() if candidate_name else ['Unknown']
            first_name = name_parts[0] if len(name_parts) > 0 else 'Unknown'
            last_name = name_parts[-1] if len(name_parts) > 1 else ''

            try:
                candidate, message_id = queue_and_wait_for_candidate(
                    db=db,
                    email=candidate_email,
                    first_name=first_name,
                    last_name=last_name,
                    mobile=payload.get('candidate_phone'),
                    tenant_id=payload.get('tenant_id', 1),
                    source='employee_referral',
                    timeout_seconds=15,
                )

                if not candidate:
                    logger.error(f"[ReferralSubmission] Candidate creation timed out: {message_id}")
                    raise RuntimeError(f"Candidate creation failed or timed out")

                logger.info(f"[ReferralSubmission] Candidate created: {candidate.candidateID}")
            except Exception as e:
                logger.error(f"[ReferralSubmission] Failed to create candidate: {e}", exc_info=True)
                raise

            # PHASE 2: Create Referral record
            from app.models.referral import Referral

            referral = Referral(
                referrer_user_id=referrer_user_id,
                candidate_id=candidate.candidateID,
                status='PENDING',
                referral_date=datetime.utcnow(),
                created_at=datetime.utcnow(),
                tenant_id=payload.get('tenant_id')
            )

            db.add(referral)
            db.flush()
            referral_id = referral.id

            logger.info(f"[ReferralSubmission] Referral created: {referral_id}")

            # PHASE 3: Commit transaction
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(f"[ReferralSubmission] Commit failed: {commit_err}", exc_info=True)
                raise RuntimeError(f"Failed to create referral: {str(commit_err)}") from commit_err

            logger.info(f"[ReferralSubmission] ✅ Referral submitted successfully")

            return {
                'referral_id': str(referral_id),
                'candidate_id': str(candidate.candidateID),
                'status': 'PENDING'
            }

        except ValueError as ve:
            logger.error(f"[ReferralSubmission] Validation error: {ve}")
            raise

        except OperationalError as oe:
            logger.error(f"[ReferralSubmission] DB error: {oe}", exc_info=True)
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[ReferralSubmission] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that referral was created successfully."""
        from app.models.referral import Referral

        if not result or "referral_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        referral_id = result.get("referral_id")

        try:
            referral = db.query(Referral).filter(Referral.id == referral_id).first()
            if not referral:
                raise ValueError(f"Referral {referral_id} not found")

            if referral.status != 'PENDING':
                raise ValueError(f"Referral status is {referral.status}, expected PENDING")

            logger.info(f"✅ Referral creation validated: {referral_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[ReferralSubmission] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= ReferralSubmissionHandler.MAX_RETRIES:
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
                minutes=ReferralSubmissionHandler.RETRY_DELAY_MINUTES
            )
            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"[ReferralSubmission] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            ReferralSubmissionHandler.validate(message, result, db)

            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err

            logger.info(f"[ReferralSubmission] ✅ Message marked COMPLETED")

        except ValueError:
            db.rollback()
            raise

        except RuntimeError:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            logger.error(f"[ReferralSubmission] Unexpected error: {e}", exc_info=True)
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
            logger.error(f"[ReferralSubmission] Failed to mark FAILED: {e}", exc_info=True)
            raise
