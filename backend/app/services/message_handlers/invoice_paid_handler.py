"""Message Handler: Invoice Payment Recording & Revenue Recognition

CRITICAL: This handler triggers ASC 606 revenue recognition.
Revenue is recognized ONLY when invoice status transitions to PAID.

Triggers: invoice_paid message
Purpose: Record payment, create revenue record, attribute to P&L
Output: Revenue record with full P&L attribution (client owner, business type, partner share)
Validation: CRITICAL - must verify revenue record created with correct amounts
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class InvoicePaidHandler:
    """Record invoice payment and recognize revenue per ASC 606."""

    MAX_RETRIES = 5
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=45)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Record invoice payment and recognize revenue.

        CRITICAL: Revenue recognition happens at this point (ASC 606).
        Invoice must transition from SENT to PAID.

        Args:
            message: ChannelQueueItem with payload containing:
                - invoice_id: Invoice being marked paid
                - payment_date: When payment received (YYYY-MM-DD)
                - paid_by_user_id: User who recorded payment
            db: Database session

        Returns:
            {
                'invoice_id': str,
                'revenue_id': str,
                'amount_recognized': int,  # In cents
                'status': 'PAID'
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
            payment_date = payload.get('payment_date')

            if not all([invoice_id, payment_date]):
                raise ValueError("Missing required fields: invoice_id, payment_date")

            logger.info(
                f"[InvoicePaid] Recording payment for invoice={invoice_id}, "
                f"payment_date={payment_date}"
            )

            # PHASE 1: Verify invoice exists and is SENT (not already paid)
            from app.models.invoice import Invoice

            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                raise ValueError(f"Invoice {invoice_id} not found")

            if invoice.status != 'SENT':
                raise ValueError(
                    f"Invoice {invoice_id} status is {invoice.status}, "
                    f"expected SENT (cannot re-pay or pay from wrong status)"
                )

            logger.info(f"[InvoicePaid] Invoice found: status={invoice.status}")

            # PHASE 2: Update invoice to PAID status
            payment_datetime = datetime.strptime(payment_date, '%Y-%m-%d')
            invoice.status = 'PAID'
            invoice.paid_at = payment_datetime
            invoice.updated_at = datetime.utcnow()

            logger.info(f"[InvoicePaid] Invoice status updated to PAID")

            # PHASE 3: Get invoice line items and project for P&L attribution
            from app.models.project import Project

            project = db.query(Project).filter(Project.id == invoice.project_id).first()
            if not project:
                raise RuntimeError(
                    f"Project {invoice.project_id} not found for invoice {invoice_id}"
                )

            # PHASE 4: Create Revenue record (ASC 606 recognition happens here)
            from app.models.revenue import Revenue

            revenue = Revenue(
                invoice_id=invoice_id,
                project_id=invoice.project_id,
                client_id=project.client_id,
                amount_usd_cents=invoice.total_usd_cents,
                revenue_date=payment_datetime.date(),  # CRITICAL: Date is when payment received
                status='RECOGNIZED',
                business_type=project.business_type if hasattr(project, 'business_type') else 'SPECIALITY',
                service_module=project.service_module if hasattr(project, 'service_module') else 'recruiting',
                created_at=datetime.utcnow(),
                created_by=payload.get('paid_by_user_id', 'system'),
                tenant_id=invoice.tenant_id
            )

            # P&L Attribution (CRITICAL for financial reporting)
            revenue.client_owner_id = project.owner_id if hasattr(project, 'owner_id') else None

            # Partner revenue share calculation (if CORE business type)
            if hasattr(project, 'business_type') and project.business_type == 'CORE':
                partner_revenue_share_pct = payload.get('partner_revenue_share_pct', 0)
                if partner_revenue_share_pct > 0:
                    revenue.partner_revenue_share_usd_cents = int(
                        invoice.total_usd_cents * (partner_revenue_share_pct / 100)
                    )
                    revenue.partner_revenue_share_pct = partner_revenue_share_pct

            db.add(revenue)
            db.flush()
            revenue_id = revenue.id

            logger.info(
                f"[InvoicePaid] ✅ Revenue recognized: {revenue_id}, "
                f"amount=${invoice.total_usd_cents / 100:.2f}, "
                f"date={payment_date}"
            )

            # PHASE 5: Queue message for dashboard update and P&L reporting
            try:
                from app.services.message_queue_service import MessageQueueService

                MessageQueueService.enqueue(
                    task_name='revenue_recognized',
                    task_id=f"revenue_{revenue_id}",
                    data={
                        'revenue_id': str(revenue_id),
                        'invoice_id': str(invoice_id),
                        'project_id': str(invoice.project_id),
                        'amount_recognized': invoice.total_usd_cents,
                        'client_owner_id': str(revenue.client_owner_id) if revenue.client_owner_id else None,
                        'business_type': revenue.business_type
                    }
                )
                logger.info(f"[InvoicePaid] Queued revenue_recognized message")

            except Exception as queue_err:
                logger.warning(
                    f"[InvoicePaid] Failed to queue revenue message (non-blocking): {queue_err}"
                )

            # PHASE 6: Commit transaction
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(
                    f"[InvoicePaid] Commit failed: {commit_err}",
                    exc_info=True
                )
                raise RuntimeError(f"Failed to commit payment: {str(commit_err)}") from commit_err

            logger.info(
                f"[InvoicePaid] ✅ Invoice payment recorded and revenue recognized"
            )

            return {
                'invoice_id': str(invoice_id),
                'revenue_id': str(revenue_id),
                'amount_recognized': invoice.total_usd_cents,
                'status': 'PAID'
            }

        except ValueError as ve:
            logger.error(f"[InvoicePaid] Validation error: {ve}")
            raise

        except OperationalError as oe:
            logger.error(
                f"[InvoicePaid] DB operational error: {oe}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(
                f"[InvoicePaid] Unexpected error: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """
        CRITICAL VALIDATION: Verify revenue record was created correctly.

        This is the most important validation - revenue recognition is irreversible.
        Must verify: invoice paid, revenue record exists, amounts match, P&L fields set.
        """
        from app.models.invoice import Invoice
        from app.models.revenue import Revenue

        if not result or "invoice_id" not in result or "revenue_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        invoice_id = result.get("invoice_id")
        revenue_id = result.get("revenue_id")
        expected_amount = result.get("amount_recognized", 0)

        try:
            # Verify invoice is PAID
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                raise ValueError(f"Invoice {invoice_id} not found after payment")

            if invoice.status != 'PAID':
                raise ValueError(
                    f"Invoice {invoice_id} status is {invoice.status}, expected PAID"
                )

            if not invoice.paid_at:
                raise ValueError(f"Invoice {invoice_id} paid_at is not set")

            logger.info(f"[InvoicePaid] ✅ Invoice payment verified: {invoice_id}")

            # Verify revenue record exists
            revenue = db.query(Revenue).filter(Revenue.id == revenue_id).first()
            if not revenue:
                raise ValueError(f"Revenue {revenue_id} not found after recognition")

            if revenue.status != 'RECOGNIZED':
                raise ValueError(
                    f"Revenue {revenue_id} status is {revenue.status}, expected RECOGNIZED"
                )

            logger.info(f"[InvoicePaid] ✅ Revenue record verified: {revenue_id}")

            # Verify amount matches
            if revenue.amount_usd_cents != expected_amount:
                raise ValueError(
                    f"Revenue amount mismatch: invoice has ${expected_amount / 100:.2f}, "
                    f"revenue has ${revenue.amount_usd_cents / 100:.2f}"
                )

            # Verify P&L fields are populated
            if not revenue.client_owner_id:
                logger.warning(
                    f"[InvoicePaid] Revenue {revenue_id} missing client_owner_id "
                    f"(P&L attribution incomplete)"
                )

            if not revenue.business_type:
                raise ValueError(
                    f"Revenue {revenue_id} missing business_type (critical for P&L)"
                )

            if not revenue.service_module:
                raise ValueError(
                    f"Revenue {revenue_id} missing service_module (critical for P&L)"
                )

            logger.info(f"✅ Invoice payment and revenue validation complete: {invoice_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(
                f"[InvoicePaid] RETRYABLE validation error: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= InvoicePaidHandler.MAX_RETRIES:
            logger.error(f"[InvoicePaid] Max retries exceeded for {message.id}")
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
                minutes=InvoicePaidHandler.RETRY_DELAY_MINUTES
            )
            db.commit()

            logger.info(
                f"[InvoicePaid] Scheduled retry {message.retry_count}/"
                f"{InvoicePaidHandler.MAX_RETRIES}"
            )

        except Exception as e:
            db.rollback()
            logger.error(f"[InvoicePaid] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after CRITICAL validation."""
        try:
            # CRITICAL: Validate before marking complete
            InvoicePaidHandler.validate(message, result, db)

            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err

            logger.info(f"[InvoicePaid] ✅✅✅ Message marked COMPLETED (revenue recognized)")

        except ValueError:
            db.rollback()
            raise

        except RuntimeError:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            logger.error(f"[InvoicePaid] Unexpected error: {e}", exc_info=True)
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

            logger.error(
                f"[InvoicePaid] ❌ Message {message.id} FAILED (revenue NOT recognized): "
                f"{final_error}"
            )

        except Exception as e:
            db.rollback()
            logger.error(f"[InvoicePaid] Failed to mark as FAILED: {e}", exc_info=True)
            raise
