"""Thunder acts instead of handing over (CEO 2026-11-03: "every task is asking me to do work and i dont like that").

After a candidate's reply is read:
- it only answered what we asked, or said thanks: nobody needs to do anything; Thunder keeps asking for what is missing;
- they asked something (pay, the role, anything with a question): the drafted answer goes by itself, from their recruiter.
  Pay is only ever quoted from the job's record (reply_draft_service);
- they want to talk: a call is booked at the first free time for their recruiter and the invite goes out.

If anything stops that (no recruiter, no free time, the 5-year rule, Thunder stopped for them) the task stays, because then
a person is needed. Replies go through every Thunder rule: consent, send window, send caps. THUNDER_AUTO_REPLY turns this off.
"""
import logging
from datetime import datetime
from types import SimpleNamespace
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate import Candidate
from app.models.user import Users

logger = logging.getLogger(__name__)

ANSWERED_INTENTS = ("QUESTION_COMP", "QUESTION_ROLE", "INTERESTED")


def needs_nobody(intent: str, words: str) -> bool:
    """A reply that gives what we asked for, or thanks, with no question in it."""
    return settings.THUNDER_AUTO_REPLY and intent == "OTHER" and "?" not in (words or "")


def will_answer(intent: str, words: str) -> bool:
    """Thunder answers this itself, so the holding acknowledgement would be a second email."""
    return settings.THUNDER_AUTO_REPLY and (intent in ANSWERED_INTENTS or (intent == "OTHER" and "?" in (words or "")))


def _recruiter(db: Session, candidate: Candidate) -> Optional[Users]:
    """Their recruiter; with none, who brought them in; else the recruiter pool picks one."""
    from app.services.recruiter_assignment_service import RecruiterAssignmentServiceForCandidates

    for user_id in (candidate.assigned_recruiter_id, candidate.created_by_user_id):
        user = db.get(Users, user_id) if user_id else None
        if user is not None and user.terminated_at is None:
            if not candidate.assigned_recruiter_id:
                candidate.assigned_recruiter_id = user.UserID
                candidate.assigned_recruiter_changed_at = datetime.utcnow()
                candidate.assigned_recruiter_changed_by = "THUNDER_AUTO_ASSIGN"
            return user
    try:
        chosen = RecruiterAssignmentServiceForCandidates.assign_recruiter_to_candidate(candidate.candidateID, candidate.tenant_id, db)
    except Exception as exc:
        logger.error(f"[ThunderAutonomy] no recruiter for {candidate.candidateID}: {exc}", exc_info=True)
        return None
    return db.get(Users, chosen["recruiter_id"]) if chosen and chosen.get("recruiter_id") else None


def book_call(db: Session, candidate: Candidate, recruiter: Users, now: Optional[datetime] = None):
    """A screening call at the first free time for the recruiter; the candidate and the recruiter get the invite. The
    Interview, or None when it cannot be booked (no free time; a hiring rule such as 5 years' experience)."""
    from app.services import interview_scheduling_service as scheduling
    from app.services.interview_slot_service import next_free_slot

    now = now or datetime.utcnow()
    try:
        slot = next_free_slot(db, recruiter, candidate, now=now)
    except Exception as exc:
        logger.error(f"[ThunderAutonomy] free time for {recruiter.UserID} not read: {exc}", exc_info=True)
        return None
    if slot is None:
        return None
    try:
        with db.begin_nested():
            created = scheduling.create_panel(db, recruiter, candidate_id=candidate.candidateID, job_id=candidate.job_id,
                                              round_name="Screening call", level=None)
            scheduling.assign_member(db, recruiter, panel_id=created.panel.id, interviewer_id=recruiter.UserID)
            interview = scheduling.schedule_interview(db, recruiter, panel_id=created.panel.id, candidate_id=candidate.candidateID,
                                                      start=slot[0], end=slot[1])
    except HTTPException as exc:
        logger.info(f"[ThunderAutonomy] call for {candidate.candidateID} not booked: {exc.detail}")
        return None
    db.commit()
    scheduling.after_panel_created(created.panel)
    scheduling.after_commit(db, interview, created.panel)
    return interview


def act_on_reply(db: Session, candidate: Candidate, intent: str, words: str, task, draft) -> Optional[str]:
    """Do what the reply asks for. Returns what was done; None leaves the task for a person. Never raises."""
    from app.services.reply_draft_service import _paragraphs_html, approve_draft, draft_text

    if not will_answer(intent, words) or draft is None:
        return None
    try:
        recruiter = _recruiter(db, candidate)
        if recruiter is None:
            return None
        done = "answered"
        if intent == "INTERESTED":
            interview = book_call(db, candidate, recruiter)
            if interview is not None:
                done = "call booked"
                when = f"{interview.start_time:%A %d %B at %H:%M} UTC"
                draft.body_html = _paragraphs_html(
                    f"Great to hear you are interested. I have put a short call in for {when}: the invite is on its way. "
                    "If that does not suit, reply with a time that does.", candidate, recruiter.UserName or settings.OUTREACH_SENDER_NAME, db)
        name = recruiter.UserName or settings.OUTREACH_SENDER_NAME
        approve_draft(db, draft, SimpleNamespace(UserID=None, UserName=name), draft_text(draft) if done == "answered" else None)
        if task is not None:
            task.status, task.completed_at = "COMPLETED", datetime.utcnow()
            task.description = (f"Thunder handled this: {done}.\n\n{task.description or ''}")[:8000]
            task.assigned_to_user_id = task.assigned_to_user_id or recruiter.UserID
        db.commit()
        logger.info(f"[ThunderAutonomy] {candidate.candidateID}: {done} ({intent})")
        return done
    except Exception as exc:
        db.rollback()
        logger.error(f"[ThunderAutonomy] {candidate.candidateID}: left for a person: {exc}", exc_info=True)
        return None
