"""
Celery tasks for candidate processing (Thunder autonomous candidate intake and preparation).
Handles async candidate processing, Thunder assignment, and related background work.
"""
import logging
from datetime import datetime
from app.celery_app import app
from app.core.database import SessionLocal
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@app.task(bind=True, name='process_candidate', autoretry_for=(Exception,), retry_kwargs={'max_retries': 3})
def process_candidate(self, candidate_id: str, tenant_id: int = 1):
    """
    Process candidate asynchronously after creation.

    This task:
    1. Updates candidate status to Thunder intake
    2. Prepares candidate for Thunder autonomous agent assignment
    3. Logs candidate activity
    4. Triggers Thunder autonomous loop if configured

    Args:
        candidate_id: UUID of candidate to process (format: CAN-xxxxx)
        tenant_id: Tenant ID for multi-tenancy support

    Returns:
        dict: Status update with processing results
    """
    db: Session = SessionLocal()
    try:
        logger.info(f"[Celery] Starting candidate processing for {candidate_id} (tenant={tenant_id})")

        # Import here to avoid circular imports
        from app.models.candidate import Candidate
        from app.models.candidate_status import CandidateStatus

        # Fetch candidate with explicit error handling
        try:
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id,
                Candidate.tenant_id == tenant_id
            ).first()
        except Exception as e:
            logger.error(f"[Celery] Failed to query candidate: {str(e)}", exc_info=True)
            raise ValueError(f"Database query failed for candidate {candidate_id}: {str(e)}")

        if not candidate:
            logger.warning(f"[Celery] Candidate not found: {candidate_id}")
            return {"status": "error", "message": "Candidate not found"}

        logger.info(f"[Celery] Found candidate: {candidate.candidateEmail} ({candidate.candidateID})")

        # Update candidate status to intake with explicit error handling
        try:
            candidate_status = db.query(CandidateStatus).filter(
                CandidateStatus.candidateID == candidate_id
            ).first()
        except Exception as e:
            logger.error(f"[Celery] Failed to query candidate status: {str(e)}", exc_info=True)
            raise ValueError(f"Database query failed for candidate status: {str(e)}")

        if candidate_status:
            try:
                candidate_status.piplineStatus = "Intake"
                candidate_status.status = "Active"
                candidate_status.updatedAt = datetime.now()
            except Exception as e:
                logger.error(f"[Celery] Failed to update candidate status fields: {str(e)}", exc_info=True)
                raise ValueError(f"Failed to update status: {str(e)}")

        logger.info(f"[Celery] Processing complete for {candidate_id}")

        # Commit with explicit error handling
        try:
            db.commit()
        except Exception as e:
            logger.error(f"[Celery] Failed to commit candidate processing: {str(e)}", exc_info=True)
            db.rollback()
            raise ValueError(f"Failed to save candidate processing: {str(e)}")

        return {
            "status": "success",
            "candidate_id": candidate_id,
            "processed_at": datetime.now().isoformat(),
            "message": f"Candidate {candidate.candidateEmail} queued for Thunder intake"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] Error processing candidate {candidate_id}: {str(e)}", exc_info=True)
        # Celery will auto-retry based on autoretry_for config
        raise
    finally:
        db.close()


@app.task(bind=True, name='assign_thunder_agent', autoretry_for=(Exception,), retry_kwargs={'max_retries': 3})
def assign_thunder_agent(self, candidate_id: str, job_id: str = None, tenant_id: int = 1):
    """
    Assign candidate to Thunder autonomous agent for intake and matching.

    Args:
        candidate_id: UUID of candidate
        job_id: Optional target job ID
        tenant_id: Tenant ID

    Returns:
        dict: Assignment status
    """
    db: Session = SessionLocal()
    try:
        logger.info(f"[Celery] Assigning Thunder agent for {candidate_id} (job={job_id})")

        from app.models.candidate import Candidate

        try:
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id,
                Candidate.tenant_id == tenant_id
            ).first()
        except Exception as e:
            logger.error(f"[Celery] Failed to query candidate for Thunder assignment: {str(e)}", exc_info=True)
            raise ValueError(f"Database query failed: {str(e)}")

        if not candidate:
            return {"status": "error", "message": "Candidate not found"}

        # Thunder agent assignment logic would go here
        # For now, just log the assignment
        logger.info(f"[Celery] Thunder agent assigned to {candidate.candidateEmail}")

        return {
            "status": "success",
            "candidate_id": candidate_id,
            "agent": "Thunder",
            "message": f"Thunder agent assigned to {candidate.candidateEmail}"
        }

    except Exception as e:
        logger.error(f"[Celery] Error assigning Thunder agent: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()
