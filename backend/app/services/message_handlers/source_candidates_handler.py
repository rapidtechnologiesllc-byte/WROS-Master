"""Source Candidates Handler - Rank the job's candidate pool and report the best matches.

Ranking is job_candidate_ranking_service.rank_candidates_for_job: the job's tenant only, the
5-year floor and the job's own minimum, normalised skills.

Spartan Pattern: Reports cascade detection to Flash (Alpha Wolf).
- Health metric: "Can I source viable candidates for this job?"
- Cascade trigger: If best_match < 60%, escalate to Flash
- Formation role: Position 3 (depends on Thunder quality + Flash job specs)
"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.models.user import Jobs
from app.services.job_candidate_ranking_service import candidate_pool, rank_candidates_for_job
from app.services.message_queue_service import MessageQueueService
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)

TOP_MATCHES_REPORTED = 3


class SourceCandidatesHandler:
    """Source candidates for job - rank by skill recency, report cascade status to Flash"""
    # Enforced by queue_processor_service (its default for this task type) and by time_bound
    TIMEOUT_SECONDS = 30

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
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

            # PHASE 3: GET CANDIDATE POOL (the job's tenant, active, in the area)
            candidates_available = candidate_pool(db, job).count()
            logger.info(f"[SourceCandidates] {candidates_available} candidates in the pool for {job_id}")

            # PHASE 4: RANK (experience gates + skill match; only qualifying candidates come back)
            ranked = rank_candidates_for_job(db, job, limit=TOP_MATCHES_REPORTED)

            # PHASE 5: CASCADE DETECTION - Check if best match viable
            formation_integrity = ranked[0].score if ranked else 0
            if not ranked:
                cascade_status = "ESCALATE"
                formation_feedback = (f"ALERT: no candidate meets the {settings.FLASH_MATCH_MIN_SCORE}% skill match "
                                      f"and experience rules")
                logger.error(f"[SourceCandidates] {job_id}: Cascade alert - {formation_feedback}")
            else:
                cascade_status = "VIABLE"
                formation_feedback = f"OK: Best candidate match {formation_integrity}% - sourcing can proceed"
                logger.info(f"[SourceCandidates] {job_id}: Formation health {formation_integrity}% OK")

            # PHASE 6: TOP MATCHES FOR RECRUITER (the shape handle_sourcing_complete reads)
            top_matches = [{"candidate_id": r.candidate_id, "recency_score": r.score, "can_proceed": True,
                            "matched_skills": r.matched, "experience_months": r.experience_months}
                           for r in ranked]

            # PHASE 7: REPORT TO FLASH (Alpha Wolf)
            flash_report = {
                "job_id": job_id,
                "job_title": job.jobTitle,
                "sourcing_status": cascade_status,
                "formation_integrity": formation_integrity,
                "formation_feedback": formation_feedback,
                "candidates_available": candidates_available,
                "top_matches": top_matches,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Queue report to Flash for decision
            msg_id = MessageQueueService.enqueue(
                task_name="candidate_sourcing_complete",
                task_id=f"sourcing_complete:{job_id}:{uuid.uuid4().hex[:12]}",  # one per sourcing run
                data=flash_report,
                tenant_id=job.tenant_id,
            )

            logger.info(f"[SourceCandidates] Queued report to Flash: {msg_id}")

            result = {
                "status": "candidates_sourced",
                "job_id": job_id,
                "candidates_found": candidates_available,
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
        except Exception:
            db.rollback()
            raise


def handle_source_candidates_for_job(message: Any, db: Session) -> Dict[str, Any]:
    """Handle source_candidates message - entry point for job sourcing."""
    return SourceCandidatesHandler.process(message, db)
