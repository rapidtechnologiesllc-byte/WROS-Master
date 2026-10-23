"""Single source of truth for 'may Thunder contact this candidate?'."""
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_rejection import CandidateRejection
from app.services.linkedin_pipeline_task_service import is_placeholder_email

logger = logging.getLogger(__name__)

NO_CONTACT_DAYS_AFTER_REJECTION = 90
# A second rejection signal for the same candidate within this window is the same
# rejection (queue retry, manual + verdict paths both firing), not a new one.
SAME_REJECTION_WINDOW = timedelta(hours=24)


def rejection_cooldown_until(db: Session, candidate_id: str) -> Optional[datetime]:
    """End of an active post-rejection no-contact period (naive UTC), else None.

    Source of truth is candidate_rejections: EventLog has no entity/data
    columns, so rejection events were never actually stored there.
    """
    latest = db.query(CandidateRejection).filter(
        CandidateRejection.candidate_id == str(candidate_id),
        CandidateRejection.rejection_status == "ACTIVE",
    ).order_by(CandidateRejection.rejected_at.desc()).first()
    if latest is None or latest.rejected_at is None:
        return None
    until = latest.rejected_at + timedelta(days=NO_CONTACT_DAYS_AFTER_REJECTION)
    return until if datetime.utcnow() < until else None


def is_contactable(db: Session, candidate: Candidate) -> Tuple[bool, str]:
    if candidate is None:
        return False, "candidate not found"
    if not candidate.candidateEmail or is_placeholder_email(candidate.candidateEmail):
        return False, "no real contact email"
    if not candidate.thunder_enabled:
        return False, "thunder disabled for candidate"
    if is_archived(db, candidate.candidateID):
        return False, "candidate archived"
    until = rejection_cooldown_until(db, candidate.candidateID)
    if until is not None:
        return False, f"no-contact period until {until.isoformat()}"
    return True, "ok"


# Account status that means "archived" (Archive / Unarchive on the candidate screens)
ARCHIVED_STATUS = "Inactive"


def is_archived(db: Session, candidate_id: str) -> bool:
    """Archived candidates get no outreach; Unarchive brings them back."""
    from app.models.candidate import CandidateStatus
    status = db.query(CandidateStatus.status).filter(CandidateStatus.candidateID == str(candidate_id)).scalar()
    return status == ARCHIVED_STATUS


def can_receive_transactional(db: Session, candidate: Candidate) -> Tuple[bool, str]:
    """May the candidate be sent a message about a step they are already in (an interview
    invitation or reminder)? A real email and no post-rejection no-contact period. Unlike
    is_contactable it does not need thunder_enabled: scheduling an interview pauses Thunder's
    outreach, never the candidate's own interview mail (flash spec E24)."""
    if candidate is None:
        return False, "candidate not found"
    if not candidate.candidateEmail or is_placeholder_email(candidate.candidateEmail):
        return False, "no real contact email"
    until = rejection_cooldown_until(db, candidate.candidateID)
    if until is not None:
        return False, f"no-contact period until {until.isoformat()}"
    return True, "ok"


def record_rejection(db: Session, candidate: Candidate, reason: str, *,
                     rejected_by_user_id: Optional[str] = None, job_id: Optional[str] = None,
                     note: Optional[str] = None) -> CandidateRejection:
    """The one way a rejection is recorded, from every path (manual pipeline status,
    interview No Hire verdict, queued candidate_rejection events). Idempotent:

    - writes the candidate_rejections row that starts the 90-day no-contact period
      (rejection_cooldown_until / is_contactable read it),
    - switches Thunder off for the candidate,
    - records a candidate_rejection EventLog entry for the timeline.

    Adds to the session; the caller commits with its own change.
    """
    from app.models.event_log import EventLog

    if candidate is None:
        raise ValueError("Cannot record a rejection for a missing candidate")
    if not reason or not str(reason).strip():
        raise ValueError("A rejection needs a reason")
    now = datetime.utcnow()
    existing = db.query(CandidateRejection).filter(
        CandidateRejection.candidate_id == candidate.candidateID,
        CandidateRejection.rejection_status == "ACTIVE",
        CandidateRejection.rejected_at >= now - SAME_REJECTION_WINDOW,
    ).order_by(CandidateRejection.rejected_at.desc()).first()
    candidate.thunder_enabled = False
    if existing is not None:
        return existing
    if candidate.tenant_id is None:
        raise ValueError(f"Candidate {candidate.candidateID} has no tenant")
    rejection = CandidateRejection(
        candidate_id=candidate.candidateID, job_id=job_id, rejection_reason=str(reason)[:512],
        rejection_note=note, rejected_by_user_id=rejected_by_user_id, rejected_at=now,
        tenant_id=candidate.tenant_id,
    )
    db.add(rejection)
    db.add(EventLog(
        tenant_id=str(candidate.tenant_id), candidate_id=candidate.candidateID,
        event_type="candidate_rejection",
        payload={"reason": str(reason), "job_id": job_id, "rejected_by": rejected_by_user_id,
                 "no_contact_until": (now + timedelta(days=NO_CONTACT_DAYS_AFTER_REJECTION)).isoformat()},
    ))
    logger.info(f"[ContactPolicy] Rejection recorded for {candidate.candidateID}: {reason}")
    return rejection
