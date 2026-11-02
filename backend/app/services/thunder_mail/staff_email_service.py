"""Our own people writing in a candidate's thread (CEO 2026-11-02: "I sent this email, the system
couldnt read the from address and determine. It has still put the candidate in Active / Applied while
the message is clear we cant afford his expectations").

An email from an active staff member that the mailbox poll matches to a candidate's thread is OURS,
never the candidate's reply: it is stored as an outbound email (sent by that person) and handled here:

- a person has answered, so the candidate's open hand-off task closes and any drafted reply waiting
  for approval is discarded;
- a decision written in it is acted on (rules, no model): the pay expected is above what the role
  offers, or the person is not moving forward -> the candidate is rejected for that role with the
  staff member's words as the note. No rejection email: the staff member already wrote to them. The
  usual post-rejection pause on automated outreach applies (candidate_contact_policy).
"""
import logging
import re
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.thunder_email import ThunderCadenceState, ThunderEmailMessage
from app.models.user import Users

logger = logging.getLogger(__name__)

OPEN_TASK = ("NEW", "IN_PROGRESS", "ON_HOLD")
PAY = r"(pay|salary|compensation|expectations?|ctc|package|rate)"
ABOVE = (r"(greater than|higher than|more than|above|beyond|exceeds?|over|outside|cannot afford|can'?t afford|"
         r"cannot meet|can'?t meet|unable to meet|not able to meet|out of (our )?budget)")
DECISIONS = (
    ("Compensation expectation above the role's budget",
     re.compile(rf"\b{PAY}\b[^.\n]{{0,80}}\b{ABOVE}\b|\b{ABOVE}\b[^.\n]{{0,80}}\b{PAY}\b", re.I)),
    ("Not progressing for this role",
     re.compile(r"\b(not (be )?(moving|going) forward|decided not to (proceed|progress)|will not be progressing|"
                r"won'?t be progressing|not (be )?proceeding|unable to proceed|not a fit for this role|"
                r"position (has been|is) (filled|closed))\b", re.I)),
)


def staff_sender(db: Session, sender: str) -> Optional[Users]:
    """The active staff member who sent it, if the sender is one of ours."""
    from app.services.thunder_mail.forward_intake_service import forwarding_user
    return forwarding_user(db, sender)


def read_decision(text: str) -> Optional[Dict[str, str]]:
    """{reason, evidence} when the email states a decision about the candidate, else None."""
    for reason, pattern in DECISIONS:
        match = pattern.search(text or "")
        if match:
            start = text.rfind("\n", 0, match.start()) + 1
            end = text.find("\n", match.end())
            return {"reason": reason, "evidence": " ".join(text[start:end if end != -1 else None].split())[:500]}
    return None


def handle_staff_email(db: Session, row: ThunderEmailMessage, staff: Users) -> Dict:
    """Close what a person's email answered and act on a decision in it. Commits."""
    from app.models.reply_draft import ReplyDraft
    from app.models.task import Task
    from app.services.candidate_rejection_service import reject_candidate
    from app.services.thunder_mail.reply_classifier import candidate_words

    now = datetime.utcnow()
    who = staff.UserName or staff.UserEmail
    for task in db.query(Task).filter(Task.candidate_id == row.candidate_id, Task.category == "THUNDER_REPLY",
                                      Task.status.in_(OPEN_TASK)):
        task.status, task.completed_at = "COMPLETED", now
        task.description = (f"{who} answered by email on {row.received_at or now:%d %b %Y %H:%M}.\n\n"
                            + (task.description or ""))[:8000]
    for draft in db.query(ReplyDraft).filter(ReplyDraft.candidate_id == row.candidate_id, ReplyDraft.status == "DRAFT"):
        draft.status, draft.note, draft.decided_at = "DISCARDED", f"{who} answered personally", now
    db.commit()

    decision = read_decision(candidate_words(row.body_text or ""))
    rejected = False
    if decision is not None:
        state = db.query(ThunderCadenceState).filter_by(candidate_id=row.candidate_id).first()
        reject_candidate(db, candidate_id=row.candidate_id, rejection_reason=decision["reason"],
                         rejection_note=f"{who} wrote: \"{decision['evidence']}\"",
                         job_id=state.job_id if state else None, rejected_by_user_id=staff.UserID,
                         send_email=False, tenant_id=row.tenant_id)
        rejected = True
    logger.info(f"[StaffEmail] {row.candidate_id}: {who}'s email recorded; "
                + (f"rejected ({decision['reason']})" if rejected else "no decision in it"))
    return {"rejected": rejected, "reason": decision["reason"] if decision else None}
