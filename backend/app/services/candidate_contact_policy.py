"""Single source of truth for 'may Thunder contact this candidate?'."""
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_rejection import CandidateRejection
from app.services.linkedin_pipeline_task_service import is_placeholder_email

logger = logging.getLogger(__name__)

NO_CONTACT_DAYS_AFTER_REJECTION = 90  # matches candidate_rejection_handler


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
    until = rejection_cooldown_until(db, candidate.candidateID)
    if until is not None:
        return False, f"no-contact period until {until.isoformat()}"
    return True, "ok"
