"""Thunder's check before every cold email (CEO 2026-11-03: "there should be validation before sending out
-> some if else conditions where thunder checks if this candidate has any previous data, if there was
any previous things"). A cold step is the first email, its follow-ups (2-4) or monthly nurture.

Everything already known about the candidate is read first, then plain rules decide (no model):

  1. They are already in conversation with our people -> WARM: no cold email; Thunder asks for what
     the profile is missing (DETAILS), or rests. Evidence: an interview (any status but cancelled), a
     reply from them, an email one of our people wrote them, a forwarded email about them, a note, a
     client submission, a hiring pipeline past "applied", or history logged by a person.
  2. One of our people added them in the last CREATED_GRACE (they usually log the call or notes right
     after) -> WAIT, then decide again.
  3. The first email has no role to talk about -> NEED_ROLE: ask whoever added them (once), wait.
  4. Otherwise -> SEND (the first email names the role).

The decision and its evidence go on the candidate's history, so anyone can see why Thunder wrote or not.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.thunder_email import ThunderEmailMessage

logger = logging.getLogger(__name__)

CREATED_GRACE = timedelta(hours=2)
SYSTEM_HISTORY_EVENTS = ("Candidate Added", "Thunder Message Sent", "Thunder Message Received", "Status Changed",
                         "Thunder Check")
COLD_STEPS = ("1", "2", "3", "4")


@dataclass
class Preflight:
    action: str  # SEND | WARM | WAIT | NEED_ROLE
    reasons: List[str] = field(default_factory=list)
    retry_at: Optional[datetime] = None


def is_cold(step: str) -> bool:
    return step in COLD_STEPS or step.startswith("NURTURE")


def conversation_evidence(db: Session, candidate: Candidate) -> List[str]:
    """What shows our people are already talking to this candidate (empty = a stranger to us)."""
    from app.models.candidate_history import CandidateHistory
    from app.models.internal_note import InternalNote
    from app.models.mailbox_intake import MailboxIntakeMessage
    from app.models.submission import Submission
    from app.models.user import Interview

    cid, found = candidate.candidateID, []
    interviews = db.query(Interview).filter(Interview.candidate_id == cid, Interview.status != "Cancelled").count()
    if interviews:
        found.append(f"{interviews} interview(s)")
    replies = db.query(ThunderEmailMessage.id).filter(ThunderEmailMessage.candidate_id == cid,
                                                      ThunderEmailMessage.direction == "IN").count()
    if replies:
        found.append(f"{replies} email(s) from them")
    staff_mail = db.query(ThunderEmailMessage.id).filter(ThunderEmailMessage.candidate_id == cid,
                                                         ThunderEmailMessage.direction == "OUT",
                                                         ThunderEmailMessage.step.is_(None)).count()
    if staff_mail:
        found.append(f"{staff_mail} email(s) from our people")
    if db.query(MailboxIntakeMessage.id).filter(MailboxIntakeMessage.candidate_id == cid).first():
        found.append("a forwarded email about them")
    if db.query(InternalNote.id).filter(InternalNote.candidate_id == cid).first():
        found.append("notes on their profile")
    if db.query(Submission.id).filter(Submission.candidate_id == cid).first():
        found.append("a client submission")
    logged = db.query(CandidateHistory.event_type).filter(
        CandidateHistory.candidateID == cid, CandidateHistory.event_type.notin_(SYSTEM_HISTORY_EVENTS)).first()
    if logged:
        found.append(f"history: {logged[0]}")
    return found


def check(db: Session, candidate: Candidate, step: str, job, now: Optional[datetime] = None) -> Preflight:
    now = now or datetime.utcnow()
    evidence = conversation_evidence(db, candidate)
    if evidence:
        return Preflight("WARM", evidence)
    created = getattr(candidate, "candidateCreatedAt", None)
    if step == "1" and candidate.created_by_user_id and created and now - created < CREATED_GRACE:
        return Preflight("WAIT", [f"added by one of our people {int((now - created).total_seconds() // 60)} min ago"],
                         retry_at=created + CREATED_GRACE)
    if step == "1" and job is None:
        return Preflight("NEED_ROLE", ["no role on file for the first email"])
    return Preflight("SEND", [f"role: {job.jobTitle}"] if job is not None else [])


def record(db: Session, candidate: Candidate, step: str, decision: Preflight) -> None:
    """The decision on the candidate's history (once per step and decision)."""
    from app.models.candidate_history import CandidateHistory

    note = f"Thunder check before email {step}: {decision.action}" + (
        f" ({'; '.join(decision.reasons)})" if decision.reasons else "")
    if db.query(CandidateHistory.id).filter(CandidateHistory.candidateID == candidate.candidateID,
                                            CandidateHistory.event_type == "Thunder Check",
                                            CandidateHistory.note == note).first():
        return
    db.add(CandidateHistory(candidateID=candidate.candidateID, event_type="Thunder Check", note=note[:2000]))
    logger.info(f"[ThunderPreflight] {candidate.candidateID} step={step}: {note}")
