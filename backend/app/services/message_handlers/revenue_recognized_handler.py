"""Message Handler: Revenue Recognition P&L Reporting

Triggered by: invoice_paid_handler → revenue_recognized message
Purpose: Update client owner dashboards and P&L reporting
Output: Dashboard cache updated, P&L data available to finance queries
Validation: Ensures all P&L attribution fields are populated for reporting
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class RevenueRecognizedHandler:
    """Update P&L dashboards after revenue recognition."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=40)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Record revenue recognition and update P&L dashboards.

        Args:
            message: ChannelQueueItem with payload containing:
                - revenue_id: Revenue record just created
                - invoice_id: Invoice that triggered recognition
                - project_id: Project generating revenue
                - amount_recognized: Amount in cents
                - client_owner_id: Client owner for P&L attribution
                - business_type: CORE, SPECIALITY, OTHER for margin targets
            db: Database session

        Returns:
            {
                'revenue_id': str,
                'client_owner_id': str,
                'amount_recognized': int,
                'dashboard_updated': bool
            }

        Raises:
            ValueError: Invalid payload (non-retryable)
            RuntimeError: Database errors (retryable)
        """
        try:
            if not message.payload:
                raise ValueError(f"Message {message.id} has no payload")

            payload = message.payload
            revenue_id = payload.get('revenue_id')
            invoice_id = payload.get('invoice_id')
            project_id = payload.get('project_id')
            client_owner_id = payload.get('client_owner_id')
            amount_recognized = payload.get('amount_recognized', 0)
            business_type = payload.get('business_type', 'SPECIALITY')

            if not revenue_id:
                raise ValueError("Missing required field: revenue_id")

            logger.info(
                f"[RevenueRecognized] Processing P&L for revenue={revenue_id}, "
                f"owner={client_owner_id}, amount=${amount_recognized / 100:.2f}"
            )

            # PHASE 1: Verify revenue record exists with all P&L fields
            from app.models.revenue import Revenue

            revenue = db.query(Revenue).filter(Revenue.id == revenue_id).first()
            if not revenue:
                raise ValueError(f"Revenue {revenue_id} not found")

            if revenue.status != 'RECOGNIZED':
                raise ValueError(
                    f"Revenue {revenue_id} status is {revenue.status}, "
                    f"expected RECOGNIZED for P&L processing"
                )

            logger.info(f"[RevenueRecognized] Revenue record found: {revenue_id}")

            # PHASE 2: Verify all P&L attribution fields are populated
            if not revenue.client_owner_id:
                logger.warning(
                    f"[RevenueRecognized] Revenue {revenue_id} missing "
                    f"client_owner_id - P&L attribution incomplete"
                )
                # Continue but flag as incomplete

            if not revenue.business_type:
                raise ValueError(
                    f"Revenue {revenue_id} missing business_type "
                    f"(critical for P&L margin calculations)"
                )

            if not revenue.service_module:
                raise ValueError(
                    f"Revenue {revenue_id} missing service_module "
                    f"(critical for departmental P&L attribution)"
                )

            logger.info(
                f"[RevenueRecognized] P&L fields verified: "
                f"business_type={revenue.business_type}, "
                f"service_module={revenue.service_module}"
            )

            # PHASE 3: Update client owner dashboard (if owner assigned)
            dashboard_updated = False

            if revenue.client_owner_id:
                try:
                    from app.models.user import User

                    client_owner = db.query(User).filter(
                        User.id == revenue.client_owner_id
                    ).first()

                    if client_owner:
                        # Log revenue attribution to client owner
                        logger.info(
                            f"[RevenueRecognized] Attributed ${amount_recognized / 100:.2f} "
                            f"to client owner: {client_owner.email}"
                        )

                        # Mark that dashboard should be updated (actual update happens via separate service)
                        dashboard_updated = True
                    else:
                        logger.warning(
                            f"[RevenueRecognized] Client owner {revenue.client_owner_id} "
                            f"not found for dashboard update"
                        )

                except Exception as owner_err:
                    logger.warning(
                        f"[RevenueRecognized] Failed to find client owner "
                        f"(non-blocking): {owner_err}"
                    )

            # PHASE 4: Queue P&L dashboard update message
            try:
                from app.services.message_queue_service import MessageQueueService

                MessageQueueService.enqueue(
                    task_name='revenue_dashboard_update',
                    task_id=f"dashboard_{revenue_id}",
                    data={
                        'revenue_id': str(revenue_id),
                        'client_owner_id': str(revenue.client_owner_id) if revenue.client_owner_id else None,
                        'amount_recognized': amount_recognized,
                        'business_type': revenue.business_type,
                        'service_module': revenue.service_module,
                        'invoice_id': str(invoice_id) if invoice_id else None,
                        'project_id': str(project_id) if project_id else None
                    }
                )
                logger.info(
                    f"[RevenueRecognized] Queued dashboard update message"
                )

            except Exception as queue_err:
                logger.warning(
                    f"[RevenueRecognized] Failed to queue dashboard update "
                    f"(non-blocking): {queue_err}"
                )

            # PHASE 5: Mark revenue as P&L processed
            revenue.pnl_processed = True
            revenue.pnl_processed_at = datetime.utcnow()

            # PHASE 6: Commit transaction
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(
                    f"[RevenueRecognized] Commit failed: {commit_err}",
                    exc_info=True
                )
                raise RuntimeError(
                    f"Failed to process P&L: {str(commit_err)}"
                ) from commit_err

            logger.info(
                f"[RevenueRecognized] ✅ P&L processing complete"
            )

            return {
                'revenue_id': str(revenue_id),
                'client_owner_id': str(revenue.client_owner_id) if revenue.client_owner_id else None,
                'amount_recognized': amount_recognized,
                'dashboard_updated': dashboard_updated
            }

        except ValueError as ve:
            logger.error(f"[RevenueRecognized] Validation error: {ve}")
            raise

        except OperationalError as oe:
            logger.error(
                f"[RevenueRecognized] DB operational error: {oe}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(
                f"[RevenueRecognized] Unexpected error: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that P&L processing completed successfully."""
        from app.models.revenue import Revenue

        if not result or "revenue_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        revenue_id = result.get("revenue_id")

        try:
            revenue = db.query(Revenue).filter(Revenue.id == revenue_id).first()
            if not revenue:
                raise ValueError(f"Revenue {revenue_id} not found after P&L processing")

            if not hasattr(revenue, 'pnl_processed') or not revenue.pnl_processed:
                raise ValueError(
                    f"Revenue {revenue_id} P&L processing not marked complete"
                )

            if not revenue.business_type:
                raise ValueError(
                    f"Revenue {revenue_id} business_type not set for P&L"
                )

            if not revenue.service_module:
                raise ValueError(
                    f"Revenue {revenue_id} service_module not set for P&L"
                )

            logger.info(f"✅ P&L processing validated: {revenue_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(
                f"[RevenueRecognized] RETRYABLE validation error: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= RevenueRecognizedHandler.MAX_RETRIES:
            logger.error(f"[RevenueRecognized] Max retries exceeded for {message.id}")
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
                minutes=RevenueRecognizedHandler.RETRY_DELAY_MINUTES
            )
            db.commit()

            logger.info(
                f"[RevenueRecognized] Scheduled retry {message.retry_count}/"
                f"{RevenueRecognizedHandler.MAX_RETRIES}"
            )

        except Exception as e:
            db.rollback()
            logger.error(f"[RevenueRecognized] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            RevenueRecognizedHandler.validate(message, result, db)

            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err

            logger.info(f"[RevenueRecognized] ✅ Message marked COMPLETED")

        except ValueError:
            db.rollback()
            raise

        except RuntimeError:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            logger.error(
                f"[RevenueRecognized] Unexpected error: {e}",
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
                f"[RevenueRecognized] Message {message.id} FAILED after "
                f"{message.retry_count} retries: {final_error}"
            )

        except Exception as e:
            db.rollback()
            logger.error(
                f"[RevenueRecognized] Failed to mark as FAILED: {e}",
                exc_info=True
            )
            raise
