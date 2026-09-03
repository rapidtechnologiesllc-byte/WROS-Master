"""
Autonomous Job Closure Service
===============================
import logging
Automatically closes jobs when all positions are filled and notifies remaining candidates.

Triggered by:
1. When a candidate's status is changed to "Hired"
2. When an offer letter is accepted
3. Periodically as a background task to catch edge cases

Workflow:
1. Check if job's hired count >= no_of_positions
2. If yes, close the job (status = "closed")
3. Find all candidates for that job NOT hired
4. Send rejection notification to those candidates
5. Log the closure action
"""

from datetime import datetime
from typing import Optional, Dict
from sqlalchemy.orm import Session
from app.core.logging import logger
from app.models.user import Jobs, Users
from app.models.candidate import Candidate, CandidateStatus


def check_and_close_job_if_filled(db: Session, job_id: str) -> Optional[Dict]:
    """
    Check if a job is filled (all positions hired) and close it if so.
    Returns closure details if job was closed, None otherwise.
    """
    try:
        job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
        if not job:
            return None

        # Already closed
        if job.jobStatus and job.jobStatus.lower() == "closed":
            return None

        # Get count of hired candidates for this job
        hired_count = (
            db.query(CandidateStatus)
            .join(Candidate, CandidateStatus.candidateID == Candidate.candidateID)
            .filter(
                Candidate.job_id == job_id,
                CandidateStatus.piplineStatus.ilike("hired")
            )
            .count()
        )

        # Check if positions are filled
        positions_needed = job.noOfPositions or 0
        if positions_needed <= 0 or hired_count < positions_needed:
            return None

        # Close the job
        job.jobStatus = "closed"
        job.endDate = datetime.utcnow().date()
        db.commit()

        # Notify remaining candidates (not hired)
        _notify_remaining_candidates(db, job_id)

        logger.info(f"[Autonomous] Job {job_id} closed: {hired_count} hired out of {positions_needed} positions")

        return {
            "job_id": job_id,
            "closed_at": datetime.utcnow().isoformat(),
            "positions": positions_needed,
            "hired": hired_count,
            "action": "job_closed"
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"[Autonomous] Error closing job {job_id}: {e}")
        db.rollback()
        raise ValueError("Operation failed")


def _notify_remaining_candidates(db: Session, job_id: str) -> None:
    """Send rejection notifications to candidates not hired for this job."""
    try:
        # Find all candidates for this job
        all_candidates = (
            db.query(Candidate)
            .filter(Candidate.job_id == job_id)
            .all()
        )

        if not all_candidates:
            return

        # Get hired candidates
        hired_candidate_ids = (
            db.query(CandidateStatus.candidateID)
            .filter(
                CandidateStatus.candidateID.in_([c.candidateID for c in all_candidates]),
                CandidateStatus.piplineStatus.ilike("hired")
            )
            .all()
        )
        hired_ids = {h[0] for h in hired_candidate_ids}

        # Mark remaining candidates as rejected
        for candidate in all_candidates:
            if candidate.candidateID not in hired_ids:
                # Get candidate status
                status = (
                    db.query(CandidateStatus)
                    .filter(CandidateStatus.candidateID == candidate.candidateID)
                    .order_by(CandidateStatus.updatedAt.desc())
                    .first()
                )

                # Only mark as rejected if not already rejected or hired
                if status and status.piplineStatus and status.piplineStatus.lower() not in ("hired", "rejected"):
                    status.piplineStatus = "Rejected"
                    status.updatedAt = datetime.utcnow()
                    db.commit()

                    logger.info(
                        f"[Autonomous] Candidate {candidate.candidateID} "
                        f"rejected for job {job_id} (position filled)"
                    )

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"[Autonomous] Error notifying candidates for job {job_id}: {e}")
        db.rollback()


def get_job_closure_status(db: Session, job_id: str) -> Dict:
    """
    Get the closure status of a job.
    Returns dict with positions needed, hired count, and closure eligibility.
    """
    try:
        job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
        if not job:
            return {"error": "Job not found"}

        positions_needed = job.noOfPositions or 0
        hired_count = (
            db.query(CandidateStatus)
            .join(Candidate, CandidateStatus.candidateID == Candidate.candidateID)
            .filter(
                Candidate.job_id == job_id,
                CandidateStatus.status.ilike("hired")
            )
            .count()
        )

        is_closed = job.jobStatus and job.jobStatus.lower() == "closed"
        is_eligible_for_closure = (
            not is_closed and positions_needed > 0 and hired_count >= positions_needed
        )

        return {
            "job_id": job_id,
            "job_status": job.jobStatus,
            "positions_needed": positions_needed,
            "hired_count": hired_count,
            "remaining_positions": max(0, positions_needed - hired_count),
            "is_closed": is_closed,
            "eligible_for_closure": is_eligible_for_closure,
            "fill_percentage": round((hired_count / positions_needed * 100) if positions_needed > 0 else 0)
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"[Autonomous] Error getting closure status for job {job_id}: {e}")
        return {"error": str(e)}
