"""Source Candidates Handler - Rank and queue candidates by skill recency for job.

Spartan Pattern: Reports cascade detection to Flash (Alpha Wolf).
- Health metric: "Can I source viable candidates for this job?"
- Cascade trigger: If best_match < 60%, escalate to Flash
- Formation role: Position 3 (depends on Thunder quality + Flash job specs)
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.user import Jobs
from app.services.skill_matching_service import SkillMatchingService
from app.services.message_queue_service import MessageQueueService
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)

VIABLE_MATCH_THRESHOLD = 60  # Formation integrity threshold
PHALANX_HEALTH_CRITICAL = 40  # Escalate if below this


class SourceCandidatesHandler:
    """Source candidates for job - rank by skill recency, report cascade status to Flash"""

    @staticmethod
    @time_bound(timeout_seconds=15)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process: Source candidates for job and report cascade status to Flash.

        Args:
            message: ChannelQueueItem with type='source_candidates'
            db: SQLAlchemy session

        Returns:
            {
                'status': 'candidates_sourced',
                'job_id': str,
                'candidates_found': int,
                'top_matches_count': int,
                'formation_integrity': float,
                'cascade_status': 'VIABLE' | 'ESCALATE',
                'message': str
            }

        Raises:
            ValueError: Invalid payload (400 client error)
            RuntimeError: DB operation failures (500 internal, retry eligible)
        """
        try:
            payload = message.payload or {}
            job_id = payload.get('job_id')

            # PHASE 1: VALIDATION
            if not job_id:
                raise ValueError("job_id required in payload")

            # PHASE 2: RETRIEVE JOB FROM DATABASE
            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")

            logger.info(f"[SourceCandidates] Starting sourcing for {job_id} ({job.jobTitle})")

            # PHASE 3: GET CANDIDATE POOL (location-based, active status)
            candidates = db.query(Candidate).filter(
                Candidate.status.in_(['active', 'offer_extended']),
                Candidate.current_location == job.jobLocation or Candidate.current_location.ilike(f"%{job.jobLocation}%")
            ).all()

            if not candidates:
                logger.warning(f"[SourceCandidates] No candidates found for {job_id}")
                candidate_ids = []
            else:
                candidate_ids = [c.candidate_id for c in candidates]
                logger.info(f"[SourceCandidates] Found {len(candidate_ids)} candidates in location")

            # PHASE 4: RANK BY SKILL RECENCY (SkillMatchingService handles Spartan patterns)
            matches = SkillMatchingService.get_best_matches_by_recency(
                job_id=job_id,
                candidate_ids=candidate_ids,
                db=db
            )

            # PHASE 5: CASCADE DETECTION - Check if best match viable
            best_match = matches[0] if matches else None
            formation_integrity = best_match.get("recency_score", 0) if best_match else 0

            if formation_integrity < VIABLE_MATCH_THRESHOLD:
                cascade_status = "ESCALATE"
                formation_feedback = f"ALERT: Best candidate match {formation_integrity}% < {VIABLE_MATCH_THRESHOLD}% threshold"
                logger.error(f"[SourceCandidates] {job_id}: Cascade alert - {formation_feedback}")
            else:
                cascade_status = "VIABLE"
                formation_feedback = f"OK: Best candidate match {formation_integrity}% - sourcing can proceed"
                logger.info(f"[SourceCandidates] {job_id}: Formation health {formation_integrity}% OK")

            # PHASE 6: GET TOP 3 MATCHES FOR RECRUITER
            top_matches = matches[:3] if matches else []

            # PHASE 7: REPORT TO FLASH (Alpha Wolf)
            flash_report = {
                "job_id": job_id,
                "job_title": job.jobTitle,
                "sourcing_status": cascade_status,
                "formation_integrity": formation_integrity,
                "formation_feedback": formation_feedback,
                "candidates_available": len(candidate_ids),
                "top_matches": top_matches,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Queue report to Flash for decision
            msg_id = MessageQueueService.enqueue(
                task_name="candidate_sourcing_complete",
                task_id=job_id,
                data=flash_report
            )

            logger.info(f"[SourceCandidates] Queued report to Flash: {msg_id}")

            result = {
                "status": "candidates_sourced",
                "job_id": job_id,
                "candidates_found": len(candidate_ids),
                "top_matches_count": len(top_matches),
                "formation_integrity": formation_integrity,
                "cascade_status": cascade_status,
                "message": formation_feedback
            }

            logger.info(f"[SourceCandidates] ✅ Completed: {job_id}")
            return result

        except ValueError as ve:
            logger.error(f"[SourceCandidates] Validation error: {ve}")
            raise  # NOT RETRYABLE - client error

        except RuntimeError as re:
            logger.error(f"[SourceCandidates] Runtime error (retryable): {re}")
            raise  # RETRYABLE - infrastructure error

        except OperationalError as oe:
            logger.error(f"[SourceCandidates] DB operational error: {oe}", exc_info=True)
            raise RuntimeError(f"DB unavailable: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[SourceCandidates] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that candidates were sourced successfully."""
        if not result or "job_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        job_id = result.get("job_id")
        logger.info(f"✅ Candidates sourced validated for job {job_id}")

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        MAX_RETRIES = 3
        RETRY_DELAY_MINUTES = 15

        if message.retry_count >= MAX_RETRIES:
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
            message.error = error[:1000]
            message.next_retry_at = datetime.utcnow() + timedelta(minutes=15)
            db.commit()
        except Exception as e:
            db.rollback()
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Mark message as COMPLETED after validation."""
        try:
            SourceCandidatesHandler.validate(message, result, db)

            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit COMPLETED status: {str(commit_err)}") from commit_err

            return {'is_valid': True, 'job_id': result.get("job_id")}

        except ValueError:
            db.rollback()
            raise

        except RuntimeError:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def on_failed(message: Any, final_error: str, db: Session) -> None:
        """Mark message as FAILED after all retries."""
        try:
            db.rollback()
            message.status = "FAILED"
            message.error = final_error[:1000]
            message.completed_at = datetime.utcnow()
            db.commit()
        except Exception as e:
            db.rollback()
            raise


def handle_source_candidates_for_job(message: Any, db: Session) -> Dict[str, Any]:
    """Handle source_candidates message - entry point for job sourcing."""
    return SourceCandidatesHandler.process(message, db)
