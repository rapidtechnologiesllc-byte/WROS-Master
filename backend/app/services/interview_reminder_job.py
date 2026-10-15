"""interview_reminders scheduled job (every 5 minutes; app.core.scheduled_jobs).

For every Scheduled interview (the live panel system: InterviewPanel / Interview):
  - reminders INTERVIEW_REMINDER_MINUTES_BEFORE the start (default 60 and 15): the candidate
    (pipeline email INTERVIEW_REMINDER, when can_receive_transactional) and each interviewer;
  - feedback nudges INTERVIEW_FEEDBACK_NUDGE_MINUTES_AFTER the end (default 60 and 1440) to each
    interviewer whose feedback is still missing.
A notice is sent only within INTERVIEW_REMINDER_GRACE_MINUTES of its due time, so a stopped
worker or a first run never sends a stale "starts in 15 minutes". Each notice has a
deterministic id (interview, its start time, the offset, the person), so it goes out once;
a rescheduled interview gets fresh reminders for its new time. Times are naive UTC.

Replaces the APScheduler jobs the interview endpoints used to register (production never ran
that scheduler, so no reminder was ever sent).
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.user import Interview, InterviewFeedback, PanelMember

logger = logging.getLogger(__name__)

NOTICE_TASK = "send_interview_notice"


def backlog_guard(db: Session, now: datetime) -> None:
    """Nothing to expire: run() only acts on notices due in the last grace window, so
    enabling the job never reaches interviews from before its first run."""
    from app.core.config import settings

    logger.info(f"[InterviewReminders] first run: notices due before "
                f"{now - timedelta(minutes=settings.INTERVIEW_REMINDER_GRACE_MINUTES):%Y-%m-%d %H:%M} UTC are never sent")


def _due(anchor: Optional[datetime], offset: timedelta, now: datetime, grace: timedelta) -> bool:
    return anchor is not None and anchor + offset <= now < anchor + offset + grace


def _start_key(interview: Interview) -> str:
    return f"{interview.start_time:%Y%m%dT%H%M}"


def _notice(interview: Interview, user_id: str, notice: str, minutes: int, tenant_id) -> bool:
    from app.services.thunder_mail.cadence_service import enqueue_once

    task_id = f"iv-notice:{interview.id}:{_start_key(interview)}:{notice}:{minutes}:{user_id}"[:255]
    return enqueue_once(NOTICE_TASK, task_id, {
        "interview_id": interview.id, "user_id": user_id, "notice": notice, "minutes": minutes,
        "start_key": _start_key(interview),
    }, tenant_id)


def _candidate_reminder(db: Session, interview: Interview, minutes: int) -> Optional[str]:
    """Records the candidate's reminder email (once); returns its id to queue after commit."""
    from app.services.candidate_contact_policy import can_receive_transactional
    from app.services.hiring_onboarding_service import queue_candidate_email

    candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
    allowed, _ = can_receive_transactional(db, candidate)
    if not allowed:
        return None
    return queue_candidate_email(db, candidate, "INTERVIEW_REMINDER", f"{interview.id}:{_start_key(interview)}:{minutes}")


def run(db: Session, now: Optional[datetime] = None) -> Dict:
    from app.core.config import settings
    from app.services.hiring_onboarding_service import PIPELINE_EMAIL_TASK
    from app.services.thunder_mail.cadence_service import enqueue_once

    now = now or datetime.utcnow()
    grace = timedelta(minutes=settings.INTERVIEW_REMINDER_GRACE_MINUTES)
    before = [timedelta(minutes=m) for m in settings.INTERVIEW_REMINDER_MINUTES_BEFORE]
    after = [timedelta(minutes=m) for m in settings.INTERVIEW_FEEDBACK_NUDGE_MINUTES_AFTER]
    latest_before = max(before, default=timedelta(0))
    latest_after = max(after, default=timedelta(0))

    upcoming = db.query(Interview).filter(
        Interview.status == "Scheduled", Interview.start_time > now,
        Interview.start_time <= now + latest_before).all()
    ended = db.query(Interview).filter(
        Interview.status.in_(("Scheduled", "Completed")), Interview.end_time <= now,
        Interview.end_time > now - latest_after - grace).all()

    tenants = {c.candidateID: c.tenant_id for c in db.query(Candidate.candidateID, Candidate.tenant_id).filter(
        Candidate.candidateID.in_({i.candidate_id for i in upcoming + ended}))}
    emails, notices = [], 0
    for interview in upcoming:
        for offset in before:
            if now >= interview.start_time or not _due(interview.start_time, -offset, now, grace):
                continue  # a reminder is never sent once the interview has started
            minutes = int(offset.total_seconds() // 60)
            email_id = _candidate_reminder(db, interview, minutes)
            if email_id:
                emails.append((email_id, interview.candidate_id))
            for member in db.query(PanelMember).filter(PanelMember.panel_id == interview.panel_id).all():
                notices += int(_notice(interview, member.interviewer_id, "REMINDER", minutes,
                                       tenants.get(interview.candidate_id)))
    for interview in ended:
        for offset in after:
            if not _due(interview.end_time, offset, now, grace):
                continue
            submitted = {f.interviewer_id for f in db.query(InterviewFeedback.interviewer_id).filter(
                InterviewFeedback.interview_id == interview.id)}
            for member in db.query(PanelMember).filter(PanelMember.panel_id == interview.panel_id).all():
                if member.interviewer_id not in submitted:
                    notices += int(_notice(interview, member.interviewer_id, "FEEDBACK",
                                           int(offset.total_seconds() // 60), tenants.get(interview.candidate_id)))

    db.commit()  # the pipeline_emails rows exist before their queue messages
    for email_id, candidate_id in emails:
        enqueue_once(PIPELINE_EMAIL_TASK, email_id, {"email_id": email_id, "candidate_id": candidate_id},
                     tenants.get(candidate_id))
    logger.info(f"[InterviewReminders] {len(emails)} candidate reminders, {notices} interviewer notices queued")
    return {"candidate_reminders": len(emails), "interviewer_notices": notices}
