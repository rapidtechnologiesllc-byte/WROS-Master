"""
Handler for candidate profile updates queued from REST endpoint.
Processes updates asynchronously to provide audit trail and failure visibility.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_history import CandidateHistory
from app.core.database import SessionLocal
from app.services.candidate_activity_service import EVENT_CANDIDATE_EDITED
from .base_message_handler import BaseMessageHandler

logger = logging.getLogger(__name__)

class CandidateUpdateHandler(BaseMessageHandler):
    """
    Asynchronous handler for candidate profile updates.

    Processes updates with full audit trail including:
    - Field-level change tracking
    - History entry creation with performer attribution
    - Event bus notifications
    - SLM feedback recording
    """

    HANDLER_NAME = "candidate_update"
    TIMEOUT_SECONDS = 30

    @staticmethod
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """Queue entry point (registry calls process(message, db)). Fails the
        message, with the handler's own reason, when the update didn't apply."""
        payload = message.payload if hasattr(message, "payload") else message
        handler = CandidateUpdateHandler()
        if not handler.validate_message(payload):
            raise ValueError(f"candidate_update payload missing required fields: {sorted(payload or {})}")
        result = handler.execute(payload)
        if result.get("status") == "failed":
            raise RuntimeError(result.get("error") or "candidate_update failed")
        return result

    def validate_message(self, message: Dict[str, Any]) -> bool:
        """Validate update message has required fields."""
        required_fields = ['candidate_id', 'updates', 'performer_id', 'performer_name']
        return all(field in message for field in required_fields)

    def execute(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process candidate update asynchronously.

        Args:
            message: {
                'candidate_id': str,
                'updates': dict of field_name -> new_value,
                'performer_id': str,
                'performer_name': str
            }

        Returns:
            {'status': 'success', 'candidate_id': str, 'fields_updated': int, ...}
            or {'status': 'failed', 'error': str}
        """
        candidate_id = message.get('candidate_id')
        updates = message.get('updates', {})
        performer_id = message.get('performer_id')
        performer_name = message.get('performer_name')

        # Log complete message payload for visibility
        logger.info(f"[CandidateUpdate] Message Payload: {message}")

        logger.info(f"[CandidateUpdate] Processing update for {candidate_id} "
                   f"({len(updates)} fields) by {performer_name}")

        db = SessionLocal()
        try:
            # Fetch candidate
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                error_msg = f"Candidate {candidate_id} not found"
                logger.error(f"[CandidateUpdate] {error_msg}")
                validation_response = {
                    'status': 'failed',
                    'error': error_msg,
                    'candidate_id': candidate_id
                }
                logger.error(f"[CandidateUpdate] Validation Response: {validation_response}")
                return {'status': 'failed', 'error': error_msg, 'validation_response': validation_response}

            # Track corrections for audit trail
            corrections = {}

            # Apply updates to candidate object
            for field_name, new_value in updates.items():
                old_value = getattr(candidate, field_name, None)
                if old_value != new_value:
                    setattr(candidate, field_name, new_value)
                    corrections[field_name] = (old_value, new_value)
                    logger.debug(f"[CandidateUpdate] {field_name}: {old_value} → {new_value}")

            if not corrections:
                logger.info(f"[CandidateUpdate] No changes detected for {candidate_id}")
                validation_response = {
                    'status': 'success',
                    'candidate_id': candidate_id,
                    'fields_updated': 0,
                    'note': 'No changes detected'
                }
                logger.info(f"[CandidateUpdate] Validation Response: {validation_response}")
                return {
                    'status': 'success',
                    'candidate_id': candidate_id,
                    'fields_updated': 0,
                    'note': 'No changes detected',
                    'validation_response': validation_response
                }

            # Commit changes to database
            try:
                db.commit()
                db.refresh(candidate)
                logger.info(f"[CandidateUpdate] Database commit successful for {candidate_id}")
            except Exception as e:
                db.rollback()
                error_msg = f"Database commit failed: {str(e)}"
                logger.error(f"[CandidateUpdate] {error_msg}", exc_info=True)
                validation_response = {
                    'status': 'failed',
                    'error': error_msg,
                    'candidate_id': candidate_id,
                    'phase': 'database_commit'
                }
                logger.error(f"[CandidateUpdate] Validation Response: {validation_response}")
                return {'status': 'failed', 'error': error_msg, 'validation_response': validation_response}

            # Create history entry with audit trail
            try:
                change_summary = []
                for field_name, (old_val, new_val) in corrections.items():
                    field_label = field_name.replace('_', ' ').title()
                    change_summary.append(f"{field_label}: {old_val} → {new_val}")

                note = " | ".join(change_summary) if change_summary else "Fields updated"

                history_entry = CandidateHistory(
                    candidateID=candidate_id,
                    event_type=EVENT_CANDIDATE_EDITED,
                    note=note,
                    performed_by_id=performer_id,
                    performed_by_name=performer_name,
                    event_at=datetime.utcnow(),
                )
                db.add(history_entry)
                db.commit()

                logger.info(f"[CandidateUpdate] History entry created for {candidate_id} "
                           f"({len(corrections)} fields changed)")
            except Exception as e:
                logger.error(
                    f"[CandidateUpdate] Failed to create history for {candidate_id}: {str(e)}",
                    exc_info=True
                )
                # Don't fail the update if history creation fails

            # Emit event bus notification
            try:
                from app.services.candidate_event_bus import CandidateEventBus
                CandidateEventBus.publish_data_changed(
                    candidate_id=candidate_id,
                    changed_fields=list(corrections.keys()),
                    **{field: corrections[field][1] for field in corrections}
                )
                logger.info(f"[CandidateUpdate] Event published for {candidate_id}")
            except Exception as e:
                logger.error(f"[CandidateUpdate] Failed to publish event: {e}")
                # Don't fail on event emission failure

            # Record SLM feedback
            try:
                from app.services.slm_feedback_engine import SLMFeedbackEngine
                for field_name, (old_val, new_val) in corrections.items():
                    SLMFeedbackEngine.record_correction(
                        db=db,
                        candidate_id=candidate_id,
                        field_name=field_name,
                        parsed_value=str(old_val) if old_val is not None else "",
                        corrected_value=str(new_val) if new_val is not None else "",
                        confidence_score=0.5  # User correction
                    )
                logger.info(f"[CandidateUpdate] SLM feedback recorded for {candidate_id}")
            except Exception as e:
                logger.error(f"[CandidateUpdate] Failed to record SLM feedback: {e}")
                # Don't fail on SLM feedback failure

            validation_response = {
                'status': 'success',
                'candidate_id': candidate_id,
                'fields_updated': len(corrections),
                'fields': list(corrections.keys()),
                'performer': performer_name,
                'timestamp': datetime.utcnow().isoformat()
            }
            logger.info(f"[CandidateUpdate] Validation Response: {validation_response}")
            return {
                'status': 'success',
                'candidate_id': candidate_id,
                'fields_updated': len(corrections),
                'fields': list(corrections.keys()),
                'performer': performer_name,
                'validation_response': validation_response
            }

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"[CandidateUpdate] {error_msg}", exc_info=True)
            validation_response = {
                'status': 'failed',
                'error': error_msg,
                'candidate_id': candidate_id,
                'phase': 'execution'
            }
            logger.error(f"[CandidateUpdate] Validation Response: {validation_response}")
            return {'status': 'failed', 'error': error_msg, 'validation_response': validation_response}
        finally:
            db.close()
