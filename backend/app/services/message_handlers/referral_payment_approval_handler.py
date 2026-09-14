"""Message Handler: Referral Payment Approval

Triggers: referral_payment_approval message (from referral_hire_conversion_handler)
Purpose: Approve referral bonus payment, notify referrer and HR
Output: Payment record created, notifications sent
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class ReferralPaymentApprovalHandler:
    """Approve referral bonus payment and notify employee."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=30)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Approve referral bonus payment.

        Args:
            message: ChannelQueueItem with payload containing:
                - referral_id: Referral record
                - referrer_user_id: Employee receiving bonus
                - bonus_usd_cents: Bonus amount
                - employment_type: Full-Time or Contractor
            db: Database session

        Returns:
            {
                'referral_id': str,
                'payment_id': str,
                'bonus_usd_cents': int,
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
            referral_id = payload.get('referral_id')
            referrer_user_id = payload.get('referrer_user_id')
            bonus_usd_cents = payload.get('bonus_usd_cents', 0)

            if not all([referral_id, referrer_user_id, bonus_usd_cents]):
                raise ValueError("Missing required fields")

            logger.info(
                f"[ReferralPaymentApproval] Approving payment: "
                f"referral={referral_id}, bonus=${bonus_usd_cents / 100:.2f}"
            )

            # PHASE 1: Verify referral exists
            from app.models.referral import Referral

            referral = db.query(Referral).filter(Referral.id == referral_id).first()
            if not referral:
                raise ValueError(f"Referral {referral_id} not found")

            # PHASE 2: Create payment record
            from app.models.payment import Payment

            payment = Payment(
                referral_id=referral_id,
                payment_type='referral_bonus',
                amount_usd_cents=bonus_usd_cents,
                recipient_user_id=referrer_user_id,
                status='PENDING',
                created_at=datetime.utcnow(),
                created_by='system'
            )

            db.add(payment)
            db.flush()
            payment_id = payment.id

            logger.info(f"[ReferralPaymentApproval] Payment record created: {payment_id}")

            # PHASE 3: Send notification to referrer
            try:
                from app.models.user import User
                from app.services.delivery_factory import DeliveryFactory

                referrer = db.query(User).filter(User.id == referrer_user_id).first()
                if referrer and referrer.email:
                    delivery_service = DeliveryFactory.get_delivery_service()
                    if delivery_service:
                        delivery_service.send_email(
                            to=referrer.email,
                            subject="Your Referral Bonus has been Approved!",
                            body=f"""
Hi {referrer.firstName or 'Referrer'},

Congratulations! Your referral bonus of ${bonus_usd_cents / 100:.2f} has been approved.

Payment Details:
- Amount: ${bonus_usd_cents / 100:.2f}
- Expected in paycheck: Next available pay period
- Payment ID: {payment_id}

Thank you for helping us build a great team!

Best regards,
HR Team
                            """
                        )
                        logger.info(f"[ReferralPaymentApproval] Referrer notification sent")

            except Exception as email_err:
                logger.warning(
                    f"[ReferralPaymentApproval] Failed to send referrer email "
                    f"(non-blocking): {email_err}"
                )

            # PHASE 4: Commit transaction
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(f"[ReferralPaymentApproval] Commit failed: {commit_err}", exc_info=True)
                raise RuntimeError(f"Failed to approve payment: {str(commit_err)}") from commit_err

            logger.info(f"[ReferralPaymentApproval] ✅ Payment approved successfully")

            return {
                'referral_id': str(referral_id),
                'payment_id': str(payment_id),
                'bonus_usd_cents': bonus_usd_cents,
                'status': 'PENDING'
            }

        except ValueError as ve:
            logger.error(f"[ReferralPaymentApproval] Validation error: {ve}")
            raise

        except OperationalError as oe:
            logger.error(f"[ReferralPaymentApproval] DB error: {oe}", exc_info=True)
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[ReferralPaymentApproval] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that payment was approved."""
        from app.models.payment import Payment

        if not result or "payment_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        payment_id = result.get("payment_id")

        try:
            payment = db.query(Payment).filter(Payment.id == payment_id).first()
            if not payment:
                raise ValueError(f"Payment {payment_id} not found")

            if payment.status != 'PENDING':
                raise ValueError(f"Payment status is {payment.status}, expected PENDING")

            logger.info(f"✅ Payment approval validated: {payment_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[ReferralPaymentApproval] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= ReferralPaymentApprovalHandler.MAX_RETRIES:
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
                minutes=ReferralPaymentApprovalHandler.RETRY_DELAY_MINUTES
            )
            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"[ReferralPaymentApproval] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            ReferralPaymentApprovalHandler.validate(message, result, db)

            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err

            logger.info(f"[ReferralPaymentApproval] ✅ Message marked COMPLETED")

        except ValueError:
            db.rollback()
            raise

        except RuntimeError:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            logger.error(f"[ReferralPaymentApproval] Unexpected error: {e}", exc_info=True)
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
            logger.error(f"[ReferralPaymentApproval] Failed to mark FAILED: {e}", exc_info=True)
            raise
