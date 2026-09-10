"""Source Candidates Handler - Rank and queue candidates by skill recency for job.

Spartan Pattern: Reports cascade detection to Flash (Alpha Wolf).
- Health metric: "Can I source viable candidates for this job?"
- Cascade trigger: If best_match < 60%, escalate to Flash
- Formation role: Position 3 (depends on Thunder quality + Flash job specs)
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.user import Jobs
from app.services.skill_matching_service import SkillMatchingService
from app.services.message_queue_service import MessageQueueService

logger = logging.getLogger(__name__)

VIABLE_MATCH_THRESHOLD = 60  # Formation integrity threshold
PHALANX_HEALTH_CRITICAL = 40  # Escalate if below this


def handle_source_candidates_for_job(message: Any, db: Session) -> Dict[str, Any]:
    """
    Source candidates for job based on skill recency matching.

    Spartan Pattern: Cascade detection + formation health reporting to Flash
    """
    try:
        payload = message.payload or {}
        job_id = payload.get('job_id')

        if not job_id:
            raise ValueError("job_id required in payload")

        # Retrieve job
        job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        logger.info(f"[SourceCandidates] Starting sourcing for {job_id} ({job.jobTitle})")

        # Get candidate pool (location-based, active status)
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

        # Rank by skill recency (SkillMatchingService handles Spartan patterns)
        matches = SkillMatchingService.get_best_matches_by_recency(
            job_id=job_id,
            candidate_ids=candidate_ids,
            db=db
        )

        # Cascade detection: Check if best match viable
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

        # Get top 3 matches for recruiter
        top_matches = matches[:3] if matches else []

        # Report to Flash (Alpha Wolf)
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
        logger.error(f"[SourceCandidates] Validation error: {ve}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"[SourceCandidates] Failed: {str(e)}", exc_info=True)
        raise
