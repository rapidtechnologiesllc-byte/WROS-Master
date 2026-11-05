"""Who a submitted candidate belongs to (CEO 2026-11-05: "Recruiter details and business unit is not being assigned",
"for all existing and new candidates"). Submitting a candidate to a job sets, only where nobody has set them:
the recruiter (the job's recruiter, else whoever submitted) and the business unit (the job's). This shows the BU on the
candidate; it does not take the candidate out of the org pool, which still happens when an offer is released.
"""
import logging
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate, CandidateJobApplication
from app.models.candidate_history import CandidateHistory
from app.models.user import Jobs, Users

logger = logging.getLogger(__name__)


def assign_from_job(db: Session, candidate: Candidate, job: Jobs, submitted_by: Optional[str]) -> bool:
    """Fill the candidate's blank recruiter and business unit from the job. True when something changed. Flushes."""
    changed = False
    if not candidate.assigned_recruiter_id:
        recruiter = next((u for u in (db.get(Users, i) for i in (job.recuriterID, submitted_by) if i)
                          if u is not None and u.terminated_at is None), None)
        if recruiter is not None:
            candidate.assigned_recruiter_id = recruiter.UserID
            candidate.assigned_recruiter_changed_at = datetime.utcnow()
            candidate.assigned_recruiter_changed_by = submitted_by or "SYSTEM"
            changed = True
    if job.business_unit_id and not candidate.submission_bu_id:
        candidate.submission_bu_id = job.business_unit_id
        changed = True
    if job.business_unit_id and not candidate.associated_bu_id:
        candidate.associated_bu_id = job.business_unit_id
        changed = True
    if changed:
        db.flush()
    return changed


def run_submitted_candidates_backfill(db: Session) -> Dict:
    """Candidates already on a job with a blank recruiter or business unit. The submitter is whoever recorded the
    submission, else whoever created the candidate. Idempotent; commits."""
    rows = (db.query(CandidateJobApplication, Candidate, Jobs)
            .join(Candidate, Candidate.candidateID == CandidateJobApplication.candidate_id)
            .join(Jobs, Jobs.jobID == CandidateJobApplication.job_id)
            .filter((Candidate.assigned_recruiter_id.is_(None)) | (Candidate.submission_bu_id.is_(None)))
            .order_by(CandidateJobApplication.applied_at).all())
    updated = 0
    for application, candidate, job in rows:
        logged = (db.query(CandidateHistory.performed_by_id)
                  .filter(CandidateHistory.candidateID == candidate.candidateID, CandidateHistory.job_id == job.jobID,
                          CandidateHistory.performed_by_id.isnot(None))
                  .order_by(CandidateHistory.event_at).first())
        submitter = logged[0] if logged else candidate.created_by_user_id
        updated += assign_from_job(db, candidate, job, submitter)
    db.commit()
    if updated:
        logger.info(f"[CandidateAssignment] {updated} submitted candidate(s) filled in")
    return {"updated": updated}
