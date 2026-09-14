"""Message Handler: S316 Invoice Generation

S316 = Service-based invoicing (milestone-based, not timesheet-based)
Triggers: s316_invoice_ready message (from s316_milestone_completion_handler)
Purpose: Generate DRAFT invoice from completed milestones with fixed prices
Output: Invoice record with line items, ready for Finance approval
Validation: Ensures all required milestones, prices sum correctly
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class S316InvoiceHandler:
    """Generate S316 invoice from completed project milestones."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=50)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Generate S316 invoice from completed milestones.

        S316 invoices are milestone-based (not timesheet-based):
        - Each milestone has fixed price
        - Can have payment schedule splits (30-30-40, etc)
        - Line items = completed milestones with their prices

        Args:
            message: ChannelQueueItem with payload containing:
                - project_id: S316 project
                - milestone_ids: List of completed milestones (optional, uses all if not specified)
                - triggered_by: 'milestone_completion' or 'manual_trigger'
            db: Database session

        Returns:
            {
                'invoice_id': str,
                'project_id': str,
                'milestone_count': int,
                'total_usd_cents': int,
                'status': 'DRAFT'
            }

        Raises:
            ValueError: Invalid payload (non-retryable)
            RuntimeError: Database errors (retryable)
        """
        try:
            if not message.payload:
                raise ValueError(f"Message {message.id} has no payload")

            payload = message.payload
            project_id = payload.get('project_id')

            if not project_id:
                raise ValueError("Missing required field: project_id")

            logger.info(
                f"[S316Invoice] Generating S316 invoice for project={project_id}"
            )

            # PHASE 1: Verify S316 project exists
            from app.models.project import Project

            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")

            if not hasattr(project, 'is_s316') or not project.is_s316:
                raise ValueError(f"Project {project_id} is not S316")

            logger.info(f"[S316Invoice] Project found: {project.name}")

            # PHASE 2: Get all completed milestones
            from app.models.project import Milestone

            completed_milestones = db.query(Milestone).filter(
                Milestone.project_id == project_id,
                Milestone.status == 'COMPLETED'
            ).all()

            if not completed_milestones:
                raise ValueError(
                    f"Project {project_id} has no completed milestones for invoicing"
                )

            logger.info(
                f"[S316Invoice] Found {len(completed_milestones)} completed milestones"
            )

            # PHASE 3: Calculate invoice total from milestone prices
            total_usd_cents = 0

            for milestone in completed_milestones:
                # Get milestone price (should be set on milestone model)
                milestone_price_usd = getattr(milestone, 'price_usd', 0)
                milestone_price_cents = int(milestone_price_usd * 100)
                total_usd_cents += milestone_price_cents

                logger.debug(
                    f"[S316Invoice] Milestone {milestone.name}: "
                    f"${milestone_price_usd:.2f}"
                )

            if total_usd_cents <= 0:
                raise ValueError(
                    f"Project {project_id} milestones total ${total_usd_cents / 100:.2f} "
                    f"(must be > $0)"
                )

            logger.info(
                f"[S316Invoice] Total invoice amount: "
                f"${total_usd_cents / 100:.2f}"
            )

            # PHASE 4: Create Invoice record (DRAFT status)
            from app.models.invoice import Invoice, InvoiceLineItem

            invoice = Invoice(
                project_id=project_id,
                status='DRAFT',
                invoice_type='S316',  # Mark as S316 invoice
                billing_period_start=datetime.utcnow().date(),
                billing_period_end=datetime.utcnow().date(),
                total_usd_cents=0,  # Will be updated after line items
                created_at=datetime.utcnow(),
                created_by=payload.get('created_by', 'system'),
                tenant_id=project.tenant_id
            )

            db.add(invoice)
            db.flush()
            invoice_id = invoice.id

            logger.info(f"[S316Invoice] Invoice record created: {invoice_id}")

            # PHASE 5: Create line items from milestones
            total_usd_cents = 0

            for milestone in completed_milestones:
                milestone_price_usd = getattr(milestone, 'price_usd', 0)
                milestone_price_cents = int(milestone_price_usd * 100)

                line_item = InvoiceLineItem(
                    invoice_id=invoice_id,
                    description=f"Milestone: {milestone.name}",
                    quantity=1,
                    unit_price_usd_cents=milestone_price_cents,
                    total_usd_cents=milestone_price_cents,
                    milestone_id=milestone.id,
                    created_at=datetime.utcnow()
                )

                db.add(line_item)
                total_usd_cents += milestone_price_cents

            # Update invoice total
            invoice.total_usd_cents = total_usd_cents

            logger.info(
                f"[S316Invoice] Created {len(completed_milestones)} line items"
            )

            # PHASE 6: Commit transaction
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(
                    f"[S316Invoice] Commit failed: {commit_err}",
                    exc_info=True
                )
                raise RuntimeError(
                    f"Failed to create S316 invoice: {str(commit_err)}"
                ) from commit_err

            logger.info(
                f"[S316Invoice] ✅ S316 invoice generated successfully"
            )

            return {
                'invoice_id': str(invoice_id),
                'project_id': str(project_id),
                'milestone_count': len(completed_milestones),
                'total_usd_cents': total_usd_cents,
                'status': 'DRAFT'
            }

        except ValueError as ve:
            logger.error(f"[S316Invoice] Validation error: {ve}")
            raise

        except OperationalError as oe:
            logger.error(
                f"[S316Invoice] DB operational error: {oe}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[S316Invoice] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that S316 invoice generation completed successfully."""
        from app.models.invoice import Invoice

        if not result or "invoice_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        invoice_id = result.get("invoice_id")

        try:
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                raise ValueError(f"Invoice {invoice_id} not found")

            if invoice.status != 'DRAFT':
                raise ValueError(
                    f"Invoice {invoice_id} status is {invoice.status}, expected DRAFT"
                )

            if not hasattr(invoice, 'invoice_type') or invoice.invoice_type != 'S316':
                raise ValueError(f"Invoice {invoice_id} is not S316 type")

            if invoice.total_usd_cents <= 0:
                raise ValueError(
                    f"Invoice {invoice_id} total is ${invoice.total_usd_cents / 100:.2f} "
                    f"(must be > $0)"
                )

            logger.info(f"✅ S316 invoice validation passed: {invoice_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(
                f"[S316Invoice] RETRYABLE validation error: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= S316InvoiceHandler.MAX_RETRIES:
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
                minutes=S316InvoiceHandler.RETRY_DELAY_MINUTES
            )
            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"[S316Invoice] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            S316InvoiceHandler.validate(message, result, db)

            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err

            logger.info(f"[S316Invoice] ✅ Message marked COMPLETED")

        except ValueError:
            db.rollback()
            raise

        except RuntimeError:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            logger.error(f"[S316Invoice] Unexpected error: {e}", exc_info=True)
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
            logger.error(f"[S316Invoice] Failed to mark as FAILED: {e}", exc_info=True)
            raise
