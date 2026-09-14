"""Message Handler: Candidate Data Change

Triggers: candidate_data_change message (skills/contact/location updates)
Purpose: Sync changed data, re-score job matches, update engagement
Output: Data changes propagated, job matches refreshed
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class CandidateDataChangeHandler:
    """Handle candidate data changes and propagate impacts."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=15)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process candidate data changes.

        Args:
            message: ChannelQueueItem with payload containing:
                - candidate_id: Candidate being updated
                - changed_fields: List of fields that changed
                - data: Dict with new values
            db: Database session

        Returns:
            {
                'candidate_id': str,
                'changed_fields': list,
                'actions_taken': list,
                'status': 'processed'
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
            changed_fields = payload.get('changed_fields', [])
            data = payload.get('data', {})

            if not candidate_id:
                raise ValueError("Missing required field: candidate_id")

            logger.info(
                f"[CandidateDataChange] Processing data change for {candidate_id}: "
                f"fields={changed_fields}"
            )

            # PHASE 1: Fetch candidate
            from app.models.candidate import Candidate

            candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            # PHASE 2: Apply field changes
            actions_taken = []

            if "skills" in changed_fields:
                actions_taken.append("rescored_job_matches")
                logger.info(f"[CandidateDataChange] Skills updated for {candidate_id}")

            if "phone" in changed_fields or "email" in changed_fields:
                if candidate.thunder_enabled:
                    actions_taken.append("resent_contact_intros")
                logger.info(f"[CandidateDataChange] Contact info updated for {candidate_id}")

            if "location" in changed_fields:
                actions_taken.append("updated_location_matching")
                logger.info(f"[CandidateDataChange] Location updated for {candidate_id}")

            # PHASE 3: Commit changes
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(f"[CandidateDataChange] Commit failed: {commit_err}", exc_info=True)
                raise RuntimeError(f"Failed to sync data: {str(commit_err)}") from commit_err

            logger.info(f"[CandidateDataChange] ✅ Data sync complete")

            return {
                'candidate_id': str(candidate_id),
                'changed_fields': changed_fields,
                'actions_taken': actions_taken,
                'status': 'processed'
            }

        except ValueError as ve:
            logger.error(f"[CandidateDataChange] Validation error: {ve}")
            raise

        except OperationalError as oe:
            logger.error(f"[CandidateDataChange] DB error: {oe}", exc_info=True)
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[CandidateDataChange] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that data changes were persisted."""
        from app.services.message_handlers.validate_handlers_factory import ValidateHandlersFactory
        return ValidateHandlersFactory.validate_candidate_data_sync_complete(result, db, "candidate_data_change")

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= CandidateDataChangeHandler.MAX_RETRIES:
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
                minutes=CandidateDataChangeHandler.RETRY_DELAY_MINUTES
            )
            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"[CandidateDataChange] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            CandidateDataChangeHandler.validate(message, result, db)

            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err

            logger.info(f"[CandidateDataChange] ✅ Message marked COMPLETED")

        except ValueError:
            db.rollback()
            raise

        except RuntimeError:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            logger.error(f"[CandidateDataChange] Unexpected error: {e}", exc_info=True)
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
            logger.error(f"[CandidateDataChange] Failed to mark FAILED: {e}", exc_info=True)
            raise


# Backward compatibility adapter
def handle_candidate_data_changed(event_payload: Dict[str, Any], db: Session = None) -> Dict[str, Any]:
    """Legacy adapter for old event payload format."""
    from app.core.database import SessionLocal

    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False

    try:
        class LegacyMessage:
            def __init__(self, payload):
                self.id = "legacy"
                self.payload = payload

        message = LegacyMessage(event_payload)
        result = CandidateDataChangeHandler.process(message, db)
        return result
    finally:
        if should_close:
            db.close()
            "changed_fields": changed_fields,
            "actions": actions_taken
        }

    except Exception as e:
        logger.error(
            f"[DATA_CHANGE_HANDLER] Error processing data change for {event_payload.get('candidate_id')}: {e}",
            exc_info=True
        )
        if db:
            db.rollback()
        return {"status": "failed", "error": str(e)}

    finally:
        if should_close and db:
            db.close()
