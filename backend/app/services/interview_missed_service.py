"""A candidate who did not join a live interview (CEO 2026-11-05: turn on the no-show and follow-up messages).

Nothing can yet tell by itself who joined a call, so an interviewer on the panel says so ("Candidate did not join").
That closes the panel's feedback tasks, records it in the candidate's history, tells the team and emails the candidate
to reschedule. Silence gets INTERVIEW_NO_SHOW_FOLLOWUPS more emails, INTERVIEW_NO_SHOW_FOLLOWUP_HOURS apart; a reply or a
new time ends them. The candidate is never rejected for it: that stays with the team."""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate import Candidate
from app.models.candidate_history import CandidateHistory
from app.models.pipeline_email import PipelineEmail
from app.models.task import FEEDBACK_TASK_CATEGORY, Task
from app.models.thunder_email import ThunderEmailMessage
from app.models.user import Interview, InterviewFeedback, InterviewPanel, Users
from app.services.candidate_activity_service import EVENT_INTERVIEW_NO_SHOW
from app.services.thunder_mail import candidate_notices

logger = logging.getLogger(__name__)

NO_SHOW = "No Show"
MARKABLE = ("Scheduled", "Completed")  # the clock closes an interview an hour after it ends


def _round_name(db: Session, interview: Interview) -> Optional[str]:
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
    return panel.round_name if panel else None


def mark_no_show(db: Session, interview: Interview, actor: Users, *, now: Optional[datetime] = None) -> Optional[str]:
    """Raises ValueError when it cannot be said of this interview. Commits; returns the candidate email's id, if queued."""
    from app.services.action_emails.interviews import notify_candidate_no_show

    now = now or datetime.utcnow()
    if interview.status not in MARKABLE:
        raise ValueError(f"This interview is {interview.status}.")
    if interview.start_time is None or interview.start_time > now:
        raise ValueError("This interview has not started yet.")
    if db.query(InterviewFeedback.id).filter(InterviewFeedback.interview_id == interview.id).first():
        raise ValueError("The panel has already given feedback on this interview.")
    interview.status = NO_SHOW
    interview.feedback_status = "Cancelled"
    round_name = _round_name(db, interview)
    db.add(CandidateHistory(candidateID=interview.candidate_id, event_type=EVENT_INTERVIEW_NO_SHOW, interview_id=interview.id,
                            note=f"Did not join the {round_name or 'interview'}. Reported by {actor.UserName or actor.UserEmail}.",
                            performed_by_id=actor.UserID, performed_by_name=actor.UserName or actor.UserEmail, event_at=now))
    for task in db.query(Task).filter(Task.interview_id == interview.id, Task.category == FEEDBACK_TASK_CATEGORY, Task.status != "COMPLETED").all():
        task.status = "COMPLETED"
        task.completed_at = now
    db.commit()
    notify_candidate_no_show(db, interview, actor=actor)
    return candidate_notices.safely("interview missed", candidate_notices.queue_interview_no_show, db, interview.candidate_id,
                                    interview.id, interview.start_time, round_name)


def _sent(db: Session, interview: Interview) -> List[PipelineEmail]:
    return (db.query(PipelineEmail).filter(PipelineEmail.candidate_id == interview.candidate_id,
                                           PipelineEmail.kind.in_((candidate_notices.INTERVIEW_NO_SHOW, candidate_notices.INTERVIEW_NO_SHOW_FOLLOWUP)),
                                           PipelineEmail.ref.like(f"{interview.id}:%"))
            .order_by(PipelineEmail.created_at.asc()).all())


def run_followups(db: Session, *, now: Optional[datetime] = None) -> Dict:
    """Hourly: the next email to a candidate who has not answered; the team hears of an answer. Commits."""
    from app.services.action_emails.interviews import notify_no_show_reply

    now = now or datetime.utcnow()
    result = {"followed_up": 0, "replied": 0, "rebooked": 0}
    for interview in db.query(Interview).filter(Interview.status == NO_SHOW).all():
        emails = _sent(db, interview)
        if not emails or emails[0].sent_at is None:
            continue
        rebooked = db.query(Interview.id).filter(Interview.candidate_id == interview.candidate_id, Interview.status == "Scheduled",
                                                 Interview.start_time > now).first()
        if rebooked:
            result["rebooked"] += 1
            continue
        replied = db.query(ThunderEmailMessage.id).filter(ThunderEmailMessage.candidate_id == interview.candidate_id,
                                                          ThunderEmailMessage.direction == "IN",
                                                          ThunderEmailMessage.received_at >= emails[0].sent_at).first()
        if replied:
            notify_no_show_reply(db, interview)
            result["replied"] += 1
            continue
        followups = len(emails) - 1
        last = emails[-1]
        if followups >= settings.INTERVIEW_NO_SHOW_FOLLOWUPS or last.sent_at is None \
                or now - last.sent_at < timedelta(hours=settings.INTERVIEW_NO_SHOW_FOLLOWUP_HOURS):
            continue
        candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
        if candidate_notices.safely("interview missed follow-up", candidate_notices.queue_interview_no_show_followup, db, candidate,
                                    interview.id, interview.start_time, _round_name(db, interview), followups + 1):
            result["followed_up"] += 1
    db.commit()
    return result


def backlog_guard(db: Session, now: datetime) -> None:
    """Nothing to expire: only an interview someone marks from now on is ever followed up."""
    logger.info(f"[InterviewMissed] first run at {now:%Y-%m-%d %H:%M} UTC: {db.query(Interview.id).filter(Interview.status == NO_SHOW).count()} marked")
