"""
Handler: Interview Scheduled Events

Triggers when interview created for candidate

Actions:
- Create interview record
- Notify Thunder: Candidate advanced, pause other outreach
- Sync interview context to Thunder conversation (date, time, panel)
- Add briefing notes for panel (from Thunder analysis)
- Set interview reminder

Note: Pausing other outreach prevents candidate from getting multiple offers.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.channel_queue import ChannelQueueItem
from app.services.message_handlers.base_message_handler import time_bound
from app.services.candidate_activity_service import log_thunder_operation

logger = logging.getLogger(__name__)


def handle_interview_scheduled(event_payload: dict, db: Session) -> Dict[str, Any]:
    """
    Wrapper function for legacy handler interface.

    Args:
        event_payload: {'candidate_id': str, 'data': dict}
        db: Database session

    Returns:
        {'status': str, 'interview_id': str, ...}
    """
    # Convert legacy format to ChannelQueueItem format
    from app.models.channel_queue import ChannelQueueItem

    mock_message = ChannelQueueItem(
        id="legacy_interview_scheduled",
        task_name="interview_scheduled",
        status="PROCESSING",
        payload=event_payload.get('data', event_payload)
    )

    return InterviewScheduledHandler.process(mock_message, db)


class InterviewScheduledHandler:
    """Handles interview scheduled messages with validation and timeout."""

    MAX_RETRIES = 5
    RETRY_DELAY_MINUTES = 30

    @staticmethod
    @time_bound(timeout_seconds=15)
    def process(message: ChannelQueueItem, db: Session) -> Dict[str, Any]:
        """
        Process interview scheduled message - creates interview record and pauses Thunder.

        Args:
            message: ChannelQueueItem with interview scheduling data
            db: Database session

        Returns:
            {'status': 'success', 'interview_id': str, 'candidate_id': str}

        Raises:
            ValueError: Invalid payload (non-retryable)
            RuntimeError: DB write failures (retryable)
        """
        if not message.payload:
            raise ValueError(f"Message {message.id} has no payload")

        payload = message.payload
        candidate_id = payload.get("candidate_id")
        logger.info(f"[InterviewHandler] Processing interview for candidate {candidate_id}")

        try:
            from app.models.candidate import Candidate
            from app.models.user import Interview
            from app.services.slm_service import SLMService
            from app.services.message_queue_service import MessageQueueService

            # ===== VALIDATION: Check required fields =====
            required_fields = ['candidate_id', 'interview_date']
            for field in required_fields:
                if not payload.get(field):
                    raise ValueError(f"Missing required field: {field}")

            # ===== PHASE 0: SLM Pre-flight analysis (optional, non-blocking) =====
            message_id = str(message.id) if hasattr(message, 'id') else "unknown"
            interview_date = payload.get("interview_date")
            interview_panel = payload.get("interview_panel", [])

            try:
                slm_analysis = SLMService.analyze_before_handler(
                    message_id=message_id,
                    message_type='interview_scheduled',
                    payload=payload,
                    context={
                        'business_goal': f'Schedule interview for candidate {candidate_id}',
                        'risk_level': 'MEDIUM',
                        'candidate_id': candidate_id,
                        'interview_date': interview_date,
                        'panel_size': len(interview_panel)
                    },
                    db=db
                )
                if not slm_analysis.get('should_proceed'):
                    logger.warning(f"[InterviewHandler] SLM escalation: {slm_analysis.get('reasoning')}")
                    raise ValueError(f"SLM escalation: {slm_analysis.get('reasoning')}")
            except Exception as slm_err:
                logger.warning(f"[InterviewHandler] SLM pre-flight failed (non-blocking): {slm_err}")
                # Continue - don't block interview on SLM failure

            # ===== PHASE 1: Fetch and validate candidate =====
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            logger.info(f"[InterviewHandler] ✅ Candidate found: {candidate_id}")

            # ===== PHASE 2: Create interview record =====
            start_time = payload.get("start_time")
            end_time = payload.get("end_time")
            meeting_link = payload.get("meeting_link")
            panel_id = payload.get("panel_id")

            interview = Interview(
                candidate_id=candidate_id,
                panel_id=panel_id,
                start_time=start_time,
                end_time=end_time,
                meeting_link=meeting_link,
                status="Scheduled",
                feedback_status="Pending"
            )

            db.add(interview)

            try:
                db.flush()  # Get interview.id before commit
                db.refresh(interview)
            except Exception as flush_err:
                db.rollback()
                logger.error(f"[InterviewHandler] Flush failed: {flush_err}", exc_info=True)
                raise RuntimeError(f"Failed to create interview: {str(flush_err)}") from flush_err

            interview_id = interview.id
            logger.info(f"[InterviewHandler] ✅ Interview record created: {interview_id}")

            # ===== PHASE 3: Pause Thunder outreach =====
            if hasattr(candidate, 'thunder_enabled') and candidate.thunder_enabled:
                candidate.thunder_enabled = False
                logger.info(f"[InterviewHandler] Paused Thunder for candidate {candidate_id}")

            # ===== PHASE 4: Queue Thunder pause notification =====
            try:
                MessageQueueService.enqueue(
                    task_name='interview_scheduled_pause_thunder',
                    task_id=f"interview_pause_{interview_id}",
                    data={
                        'candidate_id': candidate_id,
                        'interview_id': interview_id,
                        'reason': f'Interview scheduled for {interview_date}',
                        'pause_until': interview_date
                    }
                )
                logger.info(f"[InterviewHandler] ✅ Thunder pause notification queued")
            except Exception as queue_err:
                logger.warning(f"[InterviewHandler] Thunder queue failed (non-blocking): {queue_err}")

            # ===== PHASE 5: Commit transaction =====
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(f"[InterviewHandler] Commit failed: {commit_err}", exc_info=True)
                raise RuntimeError(f"Failed to commit interview: {str(commit_err)}") from commit_err

            # LOG ACTIVITY - Phase 2.4: Interview scheduling logging
            # Wrap in try/except so logging failure doesn't block interview creation
            try:
                log_thunder_operation(
                    db,
                    candidate_id=candidate_id,
                    operation="INTERVIEW_SCHEDULED",
                    metadata={
                        "interview_id": str(interview_id),
                        "interview_date": str(interview_date),
                        "start_time": str(start_time) if start_time else None,
                        "end_time": str(end_time) if end_time else None,
                        "panel_id": str(panel_id) if panel_id else None,
                        "meeting_link": meeting_link
                    }
                )
                db.commit()
                logger.info(f"[InterviewHandler] Logged interview scheduled for candidate {candidate_id}, interview {interview_id}")
            except Exception as log_err:
                logger.warning(f"[InterviewHandler] Failed to log interview: {log_err}, but interview created successfully")

            # ===== PHASE 6: SLM post-flight outcome recording =====
            try:
                SLMService.record_outcome(
                    slm_analysis=slm_analysis if 'slm_analysis' in locals() else None,
                    message_id=message_id,
                    handler_name='interview_scheduled_handler',
                    handler_result={
                        'interview_id': interview_id,
                        'candidate_id': candidate_id,
                        'interview_date': interview_date,
                        'status': 'created'
                    },
                    business_impact={
                        'candidate_affected': True,
                        'candidate_id': candidate_id,
                        'interview_id': interview_id,
                        'interview_date': interview_date,
                        'position_id': getattr(candidate, 'position_id', None),
                        'expected_outcome': 'schedule_confirmed',
                        'validation_method': 'Check if interview actually occurs on scheduled date',
                        '90_day_plan': 'Monitor interview completion rate and hiring velocity',
                        'can_be_reversed': False,
                    },
                    db=db
                )
                logger.info(f"[InterviewHandler] ✅ SLM outcome recorded")
            except Exception as slm_record_err:
                logger.warning(f"[InterviewHandler] SLM outcome recording failed (non-blocking): {slm_record_err}")

            return {
                'status': 'success',
                'interview_id': interview_id,
                'candidate_id': candidate_id,
                'interview_date': interview_date
            }

        except ValueError as ve:
            logger.error(f"[InterviewHandler] Validation error: {ve}")
            raise  # NOT RETRYABLE

        except Exception as e:
            db.rollback()
            logger.error(f"[InterviewHandler] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def should_retry(message: ChannelQueueItem) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= InterviewScheduledHandler.MAX_RETRIES:
            logger.error(f"[InterviewHandler] Max retries exceeded for {message.id}")
            return False

        if hasattr(message, 'next_retry_at') and message.next_retry_at:
            if datetime.utcnow() < message.next_retry_at:
                return False

        return True

    @staticmethod
    def on_retry(message: ChannelQueueItem, error: str, db: Session) -> None:
        """Schedule message for retry after failed attempt."""
        try:
            db.rollback()

            message.retry_count += 1
            message.error = error[:1000] if error else "Unknown error"
            message.next_retry_at = datetime.utcnow() + timedelta(
                minutes=InterviewScheduledHandler.RETRY_DELAY_MINUTES
            )

            db.commit()
            logger.info(
                f"[InterviewHandler] Scheduled retry for {message.id}: "
                f"retry_count={message.retry_count}/{InterviewScheduledHandler.MAX_RETRIES}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[InterviewHandler] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: ChannelQueueItem, result: Dict[str, Any], db: Session) -> None:
        """Handle successful message processing with validation before marking COMPLETED."""
        try:
            # ===== VALIDATION STEP 1: Check result structure =====
            if not isinstance(result, dict):
                raise ValueError(f"Handler returned invalid type: {type(result)}")

            required_fields = ['interview_id', 'candidate_id', 'status']
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Handler result missing required field: {field}")
                if not result[field]:
                    raise ValueError(f"Handler result has empty field: {field}")

            interview_id = result['interview_id']
            candidate_id = result['candidate_id']
            logger.info(f"[Handler] ✅ Step 1: Result structure valid (interview_id={interview_id})")

            # ===== VALIDATION STEP 2: Database verification =====
            from app.models.user import Interview

            interview = db.query(Interview).filter(Interview.id == interview_id).first()

            if not interview:
                raise RuntimeError(
                    f"Interview {interview_id} not found in database after handler completed. "
                    f"Handler returned ID but record was not persisted."
                )

            logger.info(f"[Handler] ✅ Step 2: Database verification passed, interview exists")

            # ===== VALIDATION STEP 3: Related records consistency =====
            # Verify interview status is correct
            if interview.status != "Scheduled":
                raise RuntimeError(
                    f"Interview {interview_id} status is '{interview.status}', "
                    f"expected 'Scheduled'. Interview state incorrect."
                )

            logger.info(f"[Handler] ✅ Step 3: Related records valid, interview status correct")

            # ===== VALIDATION STEP 4: Data integrity =====
            # Verify candidate matches
            if interview.candidate_id != candidate_id:
                raise RuntimeError(
                    f"Candidate mismatch: interview has '{interview.candidate_id}' "
                    f"but result specified '{candidate_id}'. "
                    f"Data corruption detected."
                )

            logger.info(f"[Handler] ✅ Step 4: Data integrity verified, candidate matches")

            # ===== FINAL: Mark COMPLETED after all validations pass =====
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit success status: {str(commit_err)}") from commit_err

            logger.info(f"[Handler] ✅✅✅ ALL VALIDATIONS PASSED - Message marked COMPLETED")

        except ValueError as e:
            # Non-retryable error
            db.rollback()
            logger.error(f"[Handler] ❌ NON-RETRYABLE validation failure: {e}")
            raise

        except RuntimeError as e:
            # Retryable error
            db.rollback()
            logger.error(f"[Handler] ❌ RETRYABLE validation failure: {e}")
            raise

        except Exception as e:
            # Unexpected error
            db.rollback()
            logger.error(f"[Handler] ❌ Unexpected validation error: {e}", exc_info=True)
            raise RuntimeError(f"Validation error: {str(e)}") from e

    @staticmethod
    def on_failed(message: ChannelQueueItem, final_error: str, db: Session) -> None:
        """Mark message as FAILED after all retries exhausted."""
        try:
            db.rollback()

            message.status = "FAILED"
            message.error = final_error[:1000] if final_error else "Unknown error"
            message.completed_at = datetime.utcnow()

            db.commit()
            logger.error(
                f"[InterviewHandler] Message {message.id} FAILED after "
                f"{message.retry_count} retries: {final_error}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[InterviewHandler] Failed to mark as FAILED: {e}", exc_info=True)
            raise
