"""Message Handler: send_interview_notice  {interview_id, user_id, notice, minutes, start_key}

One email to one interviewer, queued by the interview_reminders job (app.services.
interview_reminder_job) with a deterministic task id, so each notice is sent once:
  - REMINDER: the interview starts in `minutes` minutes;
  - FEEDBACK: the interview ended `minutes` minutes ago and their feedback is still missing.
The state is re-read at send time: a moved, cancelled or deleted interview, or feedback that
arrived meanwhile, sends nothing. A send the mail service did not accept raises RuntimeError,
so the queue retries it.

Compensation: none needed; nothing is written, and a retry re-sends the same one notice.
"""
import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.user import Interview, InterviewFeedback, InterviewPanel, PanelMember, Users
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 30
NOTICES = ("REMINDER", "FEEDBACK")


def _duration(minutes: int) -> str:
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour" + ("s" if hours != 1 else "")
    return f"{minutes} minutes"


class InterviewNoticeHandler:
    TIMEOUT_SECONDS = TIMEOUT_SECONDS
    MAX_RETRIES = 5

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session, send=None) -> Dict[str, Any]:
        from app.services.email_service import EmailService
        from app.services.interview_scheduling_service import candidate_display_name

        payload = message.payload or {}
        notice, minutes = payload.get("notice"), payload.get("minutes")
        interview_id, user_id = payload.get("interview_id"), payload.get("user_id")
        if notice not in NOTICES or not isinstance(minutes, int) or not interview_id or not user_id:
            raise ValueError(f"Message {message.id}: malformed interview notice {payload}")
        logger.info(f"[InterviewNotice] handler_start {message.id} {notice} interview={interview_id} user={user_id}")

        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if interview is None or interview.status == "Cancelled" or interview.start_time is None \
                or f"{interview.start_time:%Y%m%dT%H%M}" != payload.get("start_key"):
            logger.info(f"[InterviewNotice] handler_complete {message.id}: interview moved or gone, not sent")
            return {"status": "superseded"}
        if notice == "REMINDER" and interview.status != "Scheduled":
            return {"status": "superseded"}
        if db.query(PanelMember.id).filter(PanelMember.panel_id == interview.panel_id,
                                           PanelMember.interviewer_id == user_id).first() is None:
            return {"status": "superseded"}  # no longer on the panel
        if notice == "FEEDBACK" and db.query(InterviewFeedback.id).filter(
                InterviewFeedback.interview_id == interview.id, InterviewFeedback.interviewer_id == user_id).first():
            return {"status": "feedback_already_submitted"}
        interviewer = db.query(Users).filter(Users.UserID == user_id).first()
        if interviewer is None or not interviewer.UserEmail:
            raise ValueError(f"Interviewer {user_id} not found or has no email")

        panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
        round_name = panel.round_name if panel and panel.round_name else "Interview"
        candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
        name = candidate_display_name(candidate)
        if notice == "REMINDER":
            heading = f"Reminder: {round_name} with {name} in {_duration(minutes)}"
            body = (f"The {round_name} interview with <strong>{name}</strong> starts in {_duration(minutes)}"
                    f" ({interview.start_time:%d %b %Y %H:%M} UTC).<br>"
                    + (f"Meeting link: <a href='{interview.meeting_link}'>{interview.meeting_link}</a>"
                       if interview.meeting_link else "No meeting link is on the interview yet; please add one."))
        else:
            heading = f"Please submit your feedback: {name} | {round_name}"
            body = (f"Your feedback for the {round_name} interview with <strong>{name}</strong> is still "
                    f"missing. The candidate's next step waits for it; please submit it in the HRMS portal.")
        send = send or EmailService.send_notification
        result = send(to_email=interviewer.UserEmail, heading=heading, message=body)
        if not isinstance(result, dict) or result.get("status") != "success":
            raise RuntimeError(f"Interview notice to {interviewer.UserEmail} not sent: {result}")
        logger.info(f"[InterviewNotice] handler_complete {message.id}: sent to {user_id}")
        return {"status": "sent", "message_sent": True, "interview_id": interview.id, "user_id": user_id}
