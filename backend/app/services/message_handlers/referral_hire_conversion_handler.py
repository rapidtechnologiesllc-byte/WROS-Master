"""Message Handler: Referral Hire Conversion

Triggers: candidate_hired message (offer accepted + employee starts)
Purpose: Update Referral to HIRED, calculate bonus, queue payment
Output: Referral marked HIRED, bonus amount calculated
Reward: $5k full-time, $2k contractor (50% preboarding)
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class ReferralHireConversionHandler:
    """Convert referral to hire and calculate bonus."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    FULL_TIME_BONUS_CENTS = 500000  # $5k
    CONTRACTOR_BONUS_CENTS = 200000  # $2k

    @staticmethod
    @time_bound(timeout_seconds=30)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Record referral hire conversion.

        Args:
            message: ChannelQueueItem with payload containing:
                - candidate_id: Candidate being hired
                - offer_id: Offer accepted
                - hire_date: When employee starts (YYYY-MM-DD)
                - employment_type: 'Full-Time' or 'Contractor'
            db: Database session

        Returns:
            {
                'referral_id': str,
                'referral_bonus': int,  # in cents
                'employment_type': str,
                'hire_date': str
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
            employment_type = payload.get('employment_type', 'Full-Time')
            hire_date = payload.get('hire_date')

            if not candidate_id:
                raise ValueError("Missing required field: candidate_id")

            logger.info(
                f"[ReferralHireConversion] Converting referral: "
                f"candidate={candidate_id}, type={employment_type}"
            )

            # PHASE 1: Find referral for candidate
            from app.models.referral import Referral

            referral = db.query(Referral).filter(
                Referral.candidate_id == candidate_id,
                Referral.status == 'PENDING'
            ).first()

            if not referral:
                raise ValueError(f"No pending referral found for candidate {candidate_id}")

            # PHASE 2: Calculate bonus based on employment type
            if employment_type.lower() == 'full-time':
                referral_bonus = ReferralHireConversionHandler.FULL_TIME_BONUS_CENTS
            elif employment_type.lower() == 'contractor':
                referral_bonus = ReferralHireConversionHandler.CONTRACTOR_BONUS_CENTS
            else:
                referral_bonus = ReferralHireConversionHandler.FULL_TIME_BONUS_CENTS

            logger.info(
                f"[ReferralHireConversion] Bonus calculated: "
                f"${referral_bonus / 100:.2f}"
            )

            # PHASE 3: Update referral to HIRED
            referral.status = 'HIRED'
            referral.hire_date = datetime.strptime(hire_date, '%Y-%m-%d') if hire_date else datetime.utcnow()
            referral.bonus_usd_cents = referral_bonus
            referral.hired_at = datetime.utcnow()

            # PHASE 4: Queue payment approval message
            try:
                from app.services.message_queue_service import MessageQueueService

                MessageQueueService.enqueue(
                    task_name='referral_payment_approval',
                    task_id=f"referral_pay_{referral.id}",
                    data={
                        'referral_id': str(referral.id),
                        'referrer_user_id': str(referral.referrer_user_id),
                        'bonus_usd_cents': referral_bonus,
                        'employment_type': employment_type
                    }
                )
                logger.info(f"[ReferralHireConversion] Queued payment approval message")

            except Exception as queue_err:
                logger.warning(
                    f"[ReferralHireConversion] Failed to queue payment "
                    f"(non-blocking): {queue_err}"
                )

            # PHASE 5: Commit transaction
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(f"[ReferralHireConversion] Commit failed: {commit_err}", exc_info=True)
                raise RuntimeError(f"Failed to convert referral: {str(commit_err)}") from commit_err

            logger.info(f"[ReferralHireConversion] ✅ Referral converted to HIRED")

            return {
                'referral_id': str(referral.id),
                'referral_bonus': referral_bonus,
                'employment_type': employment_type,
                'hire_date': hire_date or datetime.utcnow().isoformat()
            }

        except ValueError as ve:
            logger.error(f"[ReferralHireConversion] Validation error: {ve}")
            raise

        except OperationalError as oe:
            logger.error(f"[ReferralHireConversion] DB error: {oe}", exc_info=True)
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[ReferralHireConversion] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that referral was converted to HIRED."""
        from app.models.referral import Referral

        if not result or "referral_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        referral_id = result.get("referral_id")

        try:
            referral = db.query(Referral).filter(Referral.id == referral_id).first()
            if not referral:
                raise ValueError(f"Referral {referral_id} not found")

            if referral.status != 'HIRED':
                raise ValueError(f"Referral status is {referral.status}, expected HIRED")

            if referral.bonus_usd_cents <= 0:
                raise ValueError(f"Bonus not set: ${referral.bonus_usd_cents / 100:.2f}")

            logger.info(f"✅ Referral hire conversion validated: {referral_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[ReferralHireConversion] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= ReferralHireConversionHandler.MAX_RETRIES:
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
                minutes=ReferralHireConversionHandler.RETRY_DELAY_MINUTES
            )
            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"[ReferralHireConversion] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            ReferralHireConversionHandler.validate(message, result, db)

            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err

            logger.info(f"[ReferralHireConversion] ✅ Message marked COMPLETED")

        except ValueError:
            db.rollback()
            raise

        except RuntimeError:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            logger.error(f"[ReferralHireConversion] Unexpected error: {e}", exc_info=True)
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
            logger.error(f"[ReferralHireConversion] Failed to mark FAILED: {e}", exc_info=True)
            raise
