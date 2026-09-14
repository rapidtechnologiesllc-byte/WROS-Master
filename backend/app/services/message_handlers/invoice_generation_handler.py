"""Message Handler: Invoice Generation from Project Timesheets

Triggers: monthly_period_close message
Purpose: Generate DRAFT invoices for all projects in billing period
Output: Invoice record with line items, ready for Finance approval
Validation: Ensures no open disputes, timesheets complete, amounts accurate
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound
from app.services.message_handlers.validate_handlers_factory import ValidateHandlersFactory

logger = logging.getLogger(__name__)


class InvoiceGenerationHandler:
    """Generate DRAFT invoices for project timesheets in billing period."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=60)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Generate DRAFT invoice for project + billing period.

        Args:
            message: ChannelQueueItem with payload containing:
                - project_id: Project to invoice
                - billing_period_start: Start date (YYYY-MM-DD)
                - billing_period_end: End date (YYYY-MM-DD)
            db: Database session

        Returns:
            {
                'invoice_id': str,
                'project_id': str,
                'line_item_count': int,
                'total_usd_cents': int,
                'status': 'DRAFT'
            }

        Raises:
            ValueError: Invalid payload or preconditions (non-retryable)
            RuntimeError: Database errors (retryable)
        """
        try:
            if not message.payload:
                raise ValueError(f"Message {message.id} has no payload")

            payload = message.payload
            project_id = payload.get('project_id')
            billing_period_start = payload.get('billing_period_start')
            billing_period_end = payload.get('billing_period_end')

            # Validate required fields
            if not all([project_id, billing_period_start, billing_period_end]):
                raise ValueError(
                    "Missing required fields: project_id, billing_period_start, billing_period_end"
                )

            logger.info(
                f"[InvoiceGeneration] Generating invoice for project={project_id}, "
                f"period={billing_period_start} to {billing_period_end}"
            )

            # PHASE 1: Verify project exists
            from app.models.project import Project

            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")

            logger.info(f"[InvoiceGeneration] Project found: {project.name}")

            # PHASE 2: Verify no open timesheet disputes in period
            from app.models.timesheet import Timesheet, TimesheetStatus

            disputed_timesheets = db.query(Timesheet).filter(
                Timesheet.project_id == project_id,
                Timesheet.status == TimesheetStatus.DISPUTED,
                Timesheet.week_ending >= billing_period_start,
                Timesheet.week_ending <= billing_period_end
            ).all()

            if disputed_timesheets:
                raise ValueError(
                    f"Cannot generate invoice: {len(disputed_timesheets)} "
                    f"timesheet disputes in period. Resolve before invoicing."
                )

            # PHASE 3: Get all approved timesheets in period
            approved_timesheets = db.query(Timesheet).filter(
                Timesheet.project_id == project_id,
                Timesheet.status == TimesheetStatus.APPROVED,
                Timesheet.week_ending >= billing_period_start,
                Timesheet.week_ending <= billing_period_end
            ).all()

            if not approved_timesheets:
                raise ValueError(
                    f"No approved timesheets found for project {project_id} "
                    f"in period {billing_period_start} to {billing_period_end}"
                )

            logger.info(
                f"[InvoiceGeneration] Found {len(approved_timesheets)} "
                f"approved timesheets for invoicing"
            )

            # PHASE 4: Create Invoice record (DRAFT status)
            from app.models.invoice import Invoice

            invoice = Invoice(
                project_id=project_id,
                status='DRAFT',
                billing_period_start=datetime.strptime(billing_period_start, '%Y-%m-%d').date(),
                billing_period_end=datetime.strptime(billing_period_end, '%Y-%m-%d').date(),
                total_usd_cents=0,  # Will be calculated from line items
                created_at=datetime.utcnow(),
                created_by=payload.get('created_by', 'system'),
                tenant_id=project.tenant_id
            )

            db.add(invoice)
            db.flush()
            invoice_id = invoice.id

            logger.info(f"[InvoiceGeneration] Invoice record created: {invoice_id}")

            # PHASE 5: Create line items from timesheets
            from app.models.invoice import InvoiceLineItem

            total_usd_cents = 0
            line_item_count = 0

            for timesheet in approved_timesheets:
                # Get hourly rate from timesheet (or project default)
                hourly_rate_cents = int(
                    timesheet.hourly_rate_usd * 100
                    if hasattr(timesheet, 'hourly_rate_usd')
                    else project.hourly_rate_usd * 100
                )

                # Calculate line item amount: hours * rate
                hours_worked = timesheet.total_hours or 0
                line_item_amount_cents = int(hours_worked * hourly_rate_cents / 100)

                line_item = InvoiceLineItem(
                    invoice_id=invoice_id,
                    description=f"Timesheet {timesheet.week_ending}",
                    hours=hours_worked,
                    hourly_rate_usd_cents=hourly_rate_cents,
                    total_usd_cents=line_item_amount_cents,
                    timesheet_id=timesheet.id,
                    created_at=datetime.utcnow()
                )

                db.add(line_item)
                total_usd_cents += line_item_amount_cents
                line_item_count += 1

            # Update invoice total
            invoice.total_usd_cents = total_usd_cents

            logger.info(
                f"[InvoiceGeneration] Created {line_item_count} line items, "
                f"total: ${total_usd_cents / 100:.2f}"
            )

            # PHASE 6: Commit transaction
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(
                    f"[InvoiceGeneration] Commit failed: {commit_err}",
                    exc_info=True
                )
                raise RuntimeError(f"Failed to commit invoice: {str(commit_err)}") from commit_err

            logger.info(
                f"[InvoiceGeneration] ✅ Invoice generated successfully: {invoice_id}"
            )

            return {
                'invoice_id': str(invoice_id),
                'project_id': str(project_id),
                'line_item_count': line_item_count,
                'total_usd_cents': total_usd_cents,
                'status': 'DRAFT'
            }

        except ValueError as ve:
            logger.error(f"[InvoiceGeneration] Validation error: {ve}")
            raise

        except OperationalError as oe:
            logger.error(
                f"[InvoiceGeneration] DB operational error: {oe}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(
                f"[InvoiceGeneration] Unexpected error: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that invoice generation completed successfully."""
        from app.models.invoice import Invoice

        if not result or "invoice_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        invoice_id = result.get("invoice_id")

        try:
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                raise ValueError(f"Invoice {invoice_id} not found after generation")

            if invoice.status != 'DRAFT':
                raise ValueError(
                    f"Invoice {invoice_id} status is {invoice.status}, expected DRAFT"
                )

            if invoice.total_usd_cents <= 0:
                raise ValueError(
                    f"Invoice {invoice_id} total is invalid: ${invoice.total_usd_cents / 100:.2f}"
                )

            # Verify line items exist
            line_item_count = result.get('line_item_count', 0)
            if line_item_count <= 0:
                raise ValueError(
                    f"Invoice {invoice_id} has no line items"
                )

            logger.info(f"✅ Invoice generation validated: {invoice_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(
                f"[InvoiceGeneration] RETRYABLE validation error: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= InvoiceGenerationHandler.MAX_RETRIES:
            logger.error(
                f"[InvoiceGeneration] Max retries exceeded for {message.id}"
            )
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
                minutes=InvoiceGenerationHandler.RETRY_DELAY_MINUTES
            )
            db.commit()

            logger.info(
                f"[InvoiceGeneration] Scheduled retry {message.retry_count}/"
                f"{InvoiceGenerationHandler.MAX_RETRIES}"
            )

        except Exception as e:
            db.rollback()
            logger.error(f"[InvoiceGeneration] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            InvoiceGenerationHandler.validate(message, result, db)

            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err

            logger.info(f"[InvoiceGeneration] ✅ Message marked COMPLETED")

        except ValueError:
            db.rollback()
            raise

        except RuntimeError:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            logger.error(
                f"[InvoiceGeneration] Unexpected error: {e}",
                exc_info=True
            )
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
                f"[InvoiceGeneration] Message {message.id} FAILED after "
                f"{message.retry_count} retries: {final_error}"
            )

        except Exception as e:
            db.rollback()
            logger.error(
                f"[InvoiceGeneration] Failed to mark as FAILED: {e}",
                exc_info=True
            )
            raise
