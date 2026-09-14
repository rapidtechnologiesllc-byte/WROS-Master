"""Message Handler: Invoice Approval Transition

Triggers: invoice_approved message
Purpose: Record Finance approval, transition DRAFT → APPROVED
Output: Invoice updated with approval metadata
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class InvoiceApprovedHandler:
    """Record invoice approval and transition to APPROVED status."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=30)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Record Finance approval of invoice.

        Transition: DRAFT → APPROVED (sets approved_by, approved_at)

        Args:
            message: ChannelQueueItem with payload containing:
                - invoice_id: Invoice to approve
                - approved_by_user_id: Finance user approving
                - approval_notes: Optional approval notes
            db: Database session

        Returns:
            {
                'invoice_id': str,
                'status': 'APPROVED',
                'approved_at': ISO8601 timestamp
            }

        Raises:
            ValueError: Invalid payload (non-retryable)
            RuntimeError: Database errors (retryable)
        """
        try:
            if not message.payload:
                raise ValueError(f"Message {message.id} has no payload")

            payload = message.payload
            invoice_id = payload.get('invoice_id')
            approved_by_user_id = payload.get('approved_by_user_id')

            if not invoice_id:
                raise ValueError("Missing required field: invoice_id")

            logger.info(
                f"[InvoiceApproved] Approving invoice={invoice_id}, "
                f"by={approved_by_user_id}"
            )

            # PHASE 1: Verify invoice exists and is DRAFT
            from app.models.invoice import Invoice

            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                raise ValueError(f"Invoice {invoice_id} not found")

            if invoice.status != 'DRAFT':
                raise ValueError(
                    f"Invoice {invoice_id} status is {invoice.status}, "
                    f"expected DRAFT (cannot approve from wrong status)"
                )

            logger.info(f"[InvoiceApproved] Invoice found: {invoice_id}")

            # PHASE 2: Update invoice to APPROVED
            invoice.status = 'APPROVED'
            invoice.approved_by_user_id = approved_by_user_id
            invoice.approved_at = datetime.utcnow()
            invoice.approval_notes = payload.get('approval_notes', '')
            invoice.updated_at = datetime.utcnow()

            logger.info(f"[InvoiceApproved] Invoice status updated to APPROVED")

            # PHASE 3: Queue next message (invoice_ready_for_send)
            try:
                from app.services.message_queue_service import MessageQueueService

                MessageQueueService.enqueue(
                    task_name='invoice_sent',
                    task_id=f"invoice_send_{invoice_id}",
                    data={
                        'invoice_id': str(invoice_id),
                        'project_id': str(invoice.project_id),
                        'sent_by_user_id': approved_by_user_id
                    }
                )
                logger.info(f"[InvoiceApproved] Queued invoice_sent message")

            except Exception as queue_err:
                logger.warning(
                    f"[InvoiceApproved] Failed to queue next message "
                    f"(non-blocking): {queue_err}"
                )

            # PHASE 4: Commit transaction
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(
                    f"[InvoiceApproved] Commit failed: {commit_err}",
                    exc_info=True
                )
                raise RuntimeError(
                    f"Failed to approve invoice: {str(commit_err)}"
                ) from commit_err

            logger.info(f"[InvoiceApproved] ✅ Invoice approved successfully")

            return {
                'invoice_id': str(invoice_id),
                'status': 'APPROVED',
                'approved_at': invoice.approved_at.isoformat()
            }

        except ValueError as ve:
            logger.error(f"[InvoiceApproved] Validation error: {ve}")
            raise

        except OperationalError as oe:
            logger.error(
                f"[InvoiceApproved] DB operational error: {oe}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[InvoiceApproved] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that invoice approval completed successfully."""
        from app.models.invoice import Invoice

        if not result or "invoice_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        invoice_id = result.get("invoice_id")

        try:
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                raise ValueError(f"Invoice {invoice_id} not found after approval")

            if invoice.status != 'APPROVED':
                raise ValueError(
                    f"Invoice {invoice_id} status is {invoice.status}, expected APPROVED"
                )

            if not invoice.approved_at:
                raise ValueError(f"Invoice {invoice_id} approved_at not set")

            logger.info(f"✅ Invoice approval validated: {invoice_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(
                f"[InvoiceApproved] RETRYABLE validation error: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= InvoiceApprovedHandler.MAX_RETRIES:
            logger.error(f"[InvoiceApproved] Max retries exceeded")
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
                minutes=InvoiceApprovedHandler.RETRY_DELAY_MINUTES
            )
            db.commit()
            logger.info(f"[InvoiceApproved] Scheduled retry")

        except Exception as e:
            db.rollback()
            logger.error(f"[InvoiceApproved] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            InvoiceApprovedHandler.validate(message, result, db)

            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err

            logger.info(f"[InvoiceApproved] ✅ Message marked COMPLETED")

        except ValueError:
            db.rollback()
            raise

        except RuntimeError:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            logger.error(f"[InvoiceApproved] Unexpected error: {e}", exc_info=True)
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
            logger.error(f"[InvoiceApproved] Message FAILED: {final_error}")

        except Exception as e:
            db.rollback()
            logger.error(f"[InvoiceApproved] Failed to mark as FAILED: {e}", exc_info=True)
            raise
