"""Message Handler: S316 Milestone Completion

S316 = Service-based invoicing with project milestones (not timesheet-based)
Triggers: s316_milestone_completed message
Purpose: Mark milestone complete, auto-generate invoice if all milestones done
Output: Milestone record updated, invoice created (if applicable)
Validation: Ensures all milestones complete, triggers invoice generation
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class S316MilestoneCompletionHandler:
    """Handle S316 project milestone completion and invoice generation."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=40)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Mark S316 milestone complete and auto-generate invoice if all done.

        Args:
            message: ChannelQueueItem with payload containing:
                - project_id: S316 project
                - milestone_id: Milestone being completed
                - milestone_name: Name of milestone (documentation)
                - completion_date: When milestone was completed (YYYY-MM-DD)
            db: Database session

        Returns:
            {
                'milestone_id': str,
                'project_id': str,
                'status': 'COMPLETED',
                'invoice_generated': bool,
                'invoice_id': str or None
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
            milestone_id = payload.get('milestone_id')
            completion_date = payload.get('completion_date')

            if not all([project_id, milestone_id, completion_date]):
                raise ValueError(
                    "Missing required fields: project_id, milestone_id, completion_date"
                )

            logger.info(
                f"[S316Milestone] Completing milestone={milestone_id}, "
                f"project={project_id}, date={completion_date}"
            )

            # PHASE 1: Verify project exists (S316 project)
            from app.models.project import Project

            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")

            if not hasattr(project, 'is_s316') or not project.is_s316:
                raise ValueError(f"Project {project_id} is not S316 (milestone-based)")

            logger.info(f"[S316Milestone] Project found: {project.name} (S316)")

            # PHASE 2: Verify milestone exists and update status
            from app.models.project import Milestone

            milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
            if not milestone:
                raise ValueError(f"Milestone {milestone_id} not found")

            if milestone.status == 'COMPLETED':
                logger.info(
                    f"[S316Milestone] Milestone {milestone_id} already completed, "
                    f"idempotent return"
                )
                # Return as if newly completed (idempotent)
            else:
                milestone.status = 'COMPLETED'
                milestone.completed_at = datetime.strptime(completion_date, '%Y-%m-%d')
                logger.info(f"[S316Milestone] Milestone status updated to COMPLETED")

            # PHASE 3: Check if all project milestones are now complete
            from sqlalchemy import func

            all_milestones_count = db.query(func.count(Milestone.id)).filter(
                Milestone.project_id == project_id
            ).scalar()

            completed_milestones_count = db.query(func.count(Milestone.id)).filter(
                Milestone.project_id == project_id,
                Milestone.status == 'COMPLETED'
            ).scalar()

            all_complete = (completed_milestones_count == all_milestones_count)

            logger.info(
                f"[S316Milestone] Milestones status: {completed_milestones_count}/"
                f"{all_milestones_count} complete"
            )

            # PHASE 4: If all milestones complete, queue invoice generation
            invoice_generated = False
            invoice_id = None

            if all_complete:
                try:
                    from app.services.message_queue_service import MessageQueueService

                    MessageQueueService.enqueue(
                        task_name='s316_invoice_generation',
                        task_id=f"s316_invoice_{project_id}",
                        data={
                            'project_id': str(project_id),
                            'milestone_ids': [],  # All completed
                            'triggered_by': 'milestone_completion'
                        }
                    )
                    logger.info(
                        f"[S316Milestone] All milestones complete - "
                        f"queued invoice generation"
                    )
                    invoice_generated = True

                except Exception as queue_err:
                    logger.warning(
                        f"[S316Milestone] Failed to queue invoice generation "
                        f"(non-blocking): {queue_err}"
                    )

            # PHASE 5: Commit transaction
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(
                    f"[S316Milestone] Commit failed: {commit_err}",
                    exc_info=True
                )
                raise RuntimeError(
                    f"Failed to complete milestone: {str(commit_err)}"
                ) from commit_err

            logger.info(
                f"[S316Milestone] ✅ Milestone completion processed"
            )

            return {
                'milestone_id': str(milestone_id),
                'project_id': str(project_id),
                'status': 'COMPLETED',
                'invoice_generated': invoice_generated,
                'invoice_id': str(invoice_id) if invoice_id else None
            }

        except ValueError as ve:
            logger.error(f"[S316Milestone] Validation error: {ve}")
            raise

        except OperationalError as oe:
            logger.error(
                f"[S316Milestone] DB operational error: {oe}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[S316Milestone] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that milestone completion processed successfully."""
        from app.models.project import Milestone

        if not result or "milestone_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        milestone_id = result.get("milestone_id")

        try:
            milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
            if not milestone:
                raise ValueError(f"Milestone {milestone_id} not found")

            if milestone.status != 'COMPLETED':
                raise ValueError(
                    f"Milestone {milestone_id} status is {milestone.status}, "
                    f"expected COMPLETED"
                )

            logger.info(f"✅ Milestone completion validated: {milestone_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(
                f"[S316Milestone] RETRYABLE validation error: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= S316MilestoneCompletionHandler.MAX_RETRIES:
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
                minutes=S316MilestoneCompletionHandler.RETRY_DELAY_MINUTES
            )
            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"[S316Milestone] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            S316MilestoneCompletionHandler.validate(message, result, db)

            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err

            logger.info(f"[S316Milestone] ✅ Message marked COMPLETED")

        except ValueError:
            db.rollback()
            raise

        except RuntimeError:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            logger.error(f"[S316Milestone] Unexpected error: {e}", exc_info=True)
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
            logger.error(f"[S316Milestone] Failed to mark as FAILED: {e}", exc_info=True)
            raise
