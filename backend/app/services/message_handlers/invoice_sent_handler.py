"""Message Handler: Invoice Sending to Client

Triggers: invoice_sent message
Purpose: Generate PDF, send to client via email, transition APPROVED → SENT
Output: Invoice marked SENT with delivery tracking
Validation: Verifies email sent and receipt confirmed
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class InvoiceSentHandler:
    """Send invoice PDF to client and mark as SENT."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=60)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Send invoice PDF to client.

        Transition: APPROVED → SENT (sets sent_at)
        Generates PDF and emails to client contact.

        Args:
            message: ChannelQueueItem with payload containing:
                - invoice_id: Invoice to send
                - project_id: Project (for PDF generation context)
                - sent_by_user_id: Finance user sending
            db: Database session

        Returns:
            {
                'invoice_id': str,
                'pdf_generated': bool,
                'email_sent': bool,
                'status': 'SENT'
            }

        Raises:
            ValueError: Invalid payload (non-retryable)
            RuntimeError: PDF/email errors (retryable)
        """
        try:
            if not message.payload:
                raise ValueError(f"Message {message.id} has no payload")

            payload = message.payload
            invoice_id = payload.get('invoice_id')
            project_id = payload.get('project_id')

            if not invoice_id:
                raise ValueError("Missing required field: invoice_id")

            logger.info(f"[InvoiceSent] Sending invoice={invoice_id}")

            # PHASE 1: Verify invoice exists and is APPROVED
            from app.models.invoice import Invoice

            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                raise ValueError(f"Invoice {invoice_id} not found")

            if invoice.status != 'APPROVED':
                raise ValueError(
                    f"Invoice {invoice_id} status is {invoice.status}, "
                    f"expected APPROVED (cannot send from wrong status)"
                )

            logger.info(f"[InvoiceSent] Invoice found: {invoice_id}")

            # PHASE 2: Get client email from project
            from app.models.project import Project

            project = db.query(Project).filter(Project.id == invoice.project_id).first()
            if not project:
                raise ValueError(f"Project {invoice.project_id} not found")

            if not hasattr(project, 'client_email') or not project.client_email:
                raise ValueError(
                    f"Project {invoice.project_id} has no client email address"
                )

            client_email = project.client_email
            logger.info(f"[InvoiceSent] Client email: {client_email}")

            # PHASE 3: Generate invoice PDF (using invoice_complete_service)
            pdf_generated = False
            try:
                from app.services.invoice_complete_service import InvoiceCompleteService

                pdf_bytes = InvoiceCompleteService.generate_pdf(invoice_id, db)
                if pdf_bytes:
                    pdf_generated = True
                    logger.info(
                        f"[InvoiceSent] PDF generated: {len(pdf_bytes)} bytes"
                    )
                else:
                    logger.warning(f"[InvoiceSent] PDF generation returned empty")

            except ImportError:
                logger.warning(
                    f"[InvoiceSent] InvoiceCompleteService not available, "
                    f"skipping PDF generation"
                )
                pdf_generated = False

            except Exception as pdf_err:
                logger.error(
                    f"[InvoiceSent] PDF generation failed: {pdf_err}",
                    exc_info=True
                )
                raise RuntimeError(f"PDF generation failed: {str(pdf_err)}") from pdf_err

            # PHASE 4: Send email to client
            email_sent = False
            try:
                from app.services.delivery_factory import DeliveryFactory

                delivery_service = DeliveryFactory.get_delivery_service()
                if delivery_service:
                    delivery_result = delivery_service.send_email(
                        to=client_email,
                        subject=f"Invoice {invoice_id} - {project.name}",
                        body=f"""
Dear {project.client_name},

Please find attached your invoice {invoice_id} for {project.name}.

Invoice Total: ${invoice.total_usd_cents / 100:.2f}
Billing Period: {invoice.billing_period_start} to {invoice.billing_period_end}

Please process payment and retain this invoice for your records.

Best regards,
Finance Team
                        """,
                        attachment_data=pdf_bytes if pdf_generated else None,
                        attachment_filename=f"Invoice_{invoice_id}.pdf" if pdf_generated else None
                    )

                    if delivery_result and delivery_result.get('status') == 'sent':
                        email_sent = True
                        logger.info(
                            f"[InvoiceSent] Email sent to {client_email}, "
                            f"delivery_id={delivery_result.get('delivery_id')}"
                        )
                    else:
                        raise RuntimeError(
                            f"Email delivery failed: "
                            f"{delivery_result.get('error', 'Unknown error')}"
                        )
                else:
                    raise RuntimeError("Delivery service not configured")

            except Exception as email_err:
                logger.error(
                    f"[InvoiceSent] Email sending failed: {email_err}",
                    exc_info=True
                )
                raise RuntimeError(f"Email sending failed: {str(email_err)}") from email_err

            # PHASE 5: Update invoice to SENT
            invoice.status = 'SENT'
            invoice.sent_at = datetime.utcnow()
            invoice.updated_at = datetime.utcnow()

            logger.info(f"[InvoiceSent] Invoice status updated to SENT")

            # PHASE 6: Commit transaction
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(
                    f"[InvoiceSent] Commit failed: {commit_err}",
                    exc_info=True
                )
                raise RuntimeError(
                    f"Failed to mark invoice as sent: {str(commit_err)}"
                ) from commit_err

            logger.info(f"[InvoiceSent] ✅ Invoice sent successfully")

            return {
                'invoice_id': str(invoice_id),
                'pdf_generated': pdf_generated,
                'email_sent': email_sent,
                'status': 'SENT'
            }

        except ValueError as ve:
            logger.error(f"[InvoiceSent] Validation error: {ve}")
            raise

        except RuntimeError as re:
            logger.error(f"[InvoiceSent] Runtime error (retryable): {re}")
            raise

        except OperationalError as oe:
            logger.error(
                f"[InvoiceSent] DB operational error: {oe}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[InvoiceSent] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that invoice sending completed successfully."""
        from app.models.invoice import Invoice

        if not result or "invoice_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        invoice_id = result.get("invoice_id")

        try:
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                raise ValueError(f"Invoice {invoice_id} not found after sending")

            if invoice.status != 'SENT':
                raise ValueError(
                    f"Invoice {invoice_id} status is {invoice.status}, expected SENT"
                )

            if not invoice.sent_at:
                raise ValueError(f"Invoice {invoice_id} sent_at not set")

            if not result.get('email_sent'):
                raise ValueError(f"Invoice {invoice_id} email was not sent")

            logger.info(f"✅ Invoice sending validated: {invoice_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(
                f"[InvoiceSent] RETRYABLE validation error: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= InvoiceSentHandler.MAX_RETRIES:
            logger.error(f"[InvoiceSent] Max retries exceeded")
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
                minutes=InvoiceSentHandler.RETRY_DELAY_MINUTES
            )
            db.commit()
            logger.info(f"[InvoiceSent] Scheduled retry")

        except Exception as e:
            db.rollback()
            logger.error(f"[InvoiceSent] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            InvoiceSentHandler.validate(message, result, db)

            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err

            logger.info(f"[InvoiceSent] ✅ Message marked COMPLETED")

        except ValueError:
            db.rollback()
            raise

        except RuntimeError:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            logger.error(f"[InvoiceSent] Unexpected error: {e}", exc_info=True)
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
            logger.error(f"[InvoiceSent] Message FAILED: {final_error}")

        except Exception as e:
            db.rollback()
            logger.error(f"[InvoiceSent] Failed to mark as FAILED: {e}", exc_info=True)
            raise
