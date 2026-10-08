"""Put existing candidates into the Thunder email cadence.

Eligible: contactable (real email, Thunder on, no rejection no-contact
period), email consent not revoked, not already in a cadence, not an
employee, and not archived/hired/rejected in candidate_status. Starts are
staggered by the hourly send cap, so the 15-minute cadence sweep queues them
gradually instead of all at once. dry_run reports the same numbers and writes
nothing.
"""
import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate import Candidate, CandidateStatus
from app.models.employee import Employee
from app.models.thunder_email import ThunderCadenceState
from app.services.candidate_contact_policy import is_contactable
from app.services.thunder_mail.cadence_service import email_consent_revoked, start_cadence

logger = logging.getLogger(__name__)

CLOSED_STATUSES = {"archived", "inactive", "hired", "rejected", "blacklisted", "do not contact", "converted"}


def _exclusion(db: Session, candidate: Candidate, employees: set, closed: set) -> Optional[str]:
    if candidate.candidateID in employees:
        return "already an employee"
    if candidate.candidateID in closed:
        return "closed in candidate_status"
    contactable, reason = is_contactable(db, candidate)
    if not contactable:
        return reason.split(" until ")[0]
    if email_consent_revoked(db, candidate.candidateID):
        return "email consent revoked"
    return None


def enroll_existing_candidates(db: Session, *, limit: int, dry_run: bool = True,
                               now: Optional[datetime] = None) -> Dict:
    now = now or datetime.utcnow()
    in_cadence = {row[0] for row in db.query(ThunderCadenceState.candidate_id).all()}
    employees = {row[0] for row in db.query(Employee.candidate_id).filter(Employee.candidate_id.isnot(None)).all()}
    closed = {cid for cid, status in db.query(CandidateStatus.candidateID, CandidateStatus.status).all()
              if (status or "").strip().lower() in CLOSED_STATUSES}

    gap = timedelta(seconds=max(1, 3600 // max(1, settings.THUNDER_MAX_SENDS_PER_HOUR)))
    excluded: Counter = Counter()
    enrolled, eligible = 0, 0
    for candidate in db.query(Candidate).order_by(Candidate.candidateID).all():
        if candidate.candidateID in in_cadence:
            excluded["already in cadence"] += 1
            continue
        reason = _exclusion(db, candidate, employees, closed)
        if reason:
            excluded[reason] += 1
            continue
        eligible += 1
        if dry_run or enrolled >= limit:
            continue
        start_cadence(db, candidate, now=now + gap * enrolled)
        enrolled += 1
    if not dry_run:
        db.commit()
    result = {
        "dry_run": dry_run, "eligible": eligible, "enrolled": enrolled,
        "left_for_later": max(0, eligible - enrolled) if not dry_run else eligible,
        "first_send_at": now.isoformat(),
        "last_start_at": (now + gap * max(0, enrolled - 1)).isoformat() if enrolled else None,
        "excluded": dict(excluded),
    }
    logger.info(f"[ThunderEnroll] {result}")
    return result
