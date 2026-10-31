"""Message Handler: send_pipeline_email  {email_id, candidate_id, kind, ref}

Emails a candidate the next step of their hiring pipeline from the HRMS mailbox, with a
link to their portal. The body (and its portal link) is built here, at send time, so the
link is never stored. Draft-then-send with the draft id on the pipeline_emails row: a
retry re-sends the same draft, never a second email. Anything that stops delivery raises
DeliveryDeferred, so the message stays PENDING ("not sent") until Graph accepts it.

Compensation: none needed; an unsent draft is re-sent by the next attempt.
"""
import html
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate import Candidate
from app.models.pipeline_email import PipelineEmail
from app.services.message_handlers.base_message_handler import time_bound
from app.services.thunder_mail.graph_mailbox import GraphMailbox

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 45


class Superseded(Exception):
    """The email no longer applies (the interview moved, was cancelled or was deleted)."""


def _onboarding_body(db: Session, candidate: Candidate, company: str, link: str, row: PipelineEmail) -> str:
    from app.models.preboarding_document import PreboardingDocument

    docs = db.query(PreboardingDocument).filter(PreboardingDocument.candidate_id == candidate.candidateID,
                                                PreboardingDocument.status == "PENDING").order_by(PreboardingDocument.id).all()
    items = "".join(f"<li>{html.escape(d.document_label)}</li>" for d in docs)
    return (f"<p>Hello {html.escape(candidate.candidateFirstName or 'there')},</p>"
            f"<p>Welcome to {html.escape(company)}! To complete your joining, please upload these documents "
            f"on your portal:</p><ul>{items}</ul>"
            f"<p><a href=\"{html.escape(link, quote=True)}\">Open my portal</a></p>"
            f"<p>Once they are verified we start your background verification. Reply to this email if you "
            f"have any questions.</p>")


def _interview_for(db: Session, row: PipelineEmail):
    """The interview an INTERVIEW_* email is about, still scheduled at the time in its ref."""
    from app.models.user import Interview, InterviewPanel

    interview_id, _, rest = (row.ref or "").partition(":")
    start_key = rest.split(":")[0]
    interview = db.query(Interview).filter(Interview.id == int(interview_id)).first() if interview_id.isdigit() else None
    if interview is None or interview.status != "Scheduled" or interview.start_time is None \
            or f"{interview.start_time:%Y%m%dT%H%M}" != start_key:
        raise Superseded(f"interview {interview_id} is no longer scheduled at {start_key}")
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
    return interview, (panel.round_name if panel and panel.round_name else "interview")


def _local_time(candidate: Candidate, value: datetime) -> str:
    """A stored (naive UTC) time in the candidate's time zone."""
    from zoneinfo import ZoneInfo

    tz_name = candidate.timezone or settings.INTERVIEW_DEFAULT_TIMEZONE
    local = value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz_name))
    return f"{local:%A %d %B %Y, %H:%M} ({tz_name})"


def _meeting_line(interview) -> str:
    if interview.meeting_link:
        link = html.escape(interview.meeting_link, quote=True)
        return f"<p>Join here: <a href=\"{link}\">{link}</a></p>"
    return "<p>The meeting link will follow in a separate email.</p>"


def _interview_invite_body(db: Session, candidate: Candidate, company: str, link: str, row: PipelineEmail) -> str:
    interview, round_name = _interview_for(db, row)
    return (f"<p>Hello {html.escape(candidate.candidateFirstName or 'there')},</p>"
            f"<p>Your {html.escape(round_name)} with {html.escape(company)} is scheduled for "
            f"<strong>{html.escape(_local_time(candidate, interview.start_time))}</strong>.</p>"
            f"{_meeting_line(interview)}"
            f"<p>If this time does not work for you, reply to this email and your recruiter will "
            f"find another slot.</p>"
            f"<p><a href=\"{html.escape(link, quote=True)}\">Open my portal</a></p>")


def _interview_reminder_body(db: Session, candidate: Candidate, company: str, link: str, row: PipelineEmail) -> str:
    interview, round_name = _interview_for(db, row)
    return (f"<p>Hello {html.escape(candidate.candidateFirstName or 'there')},</p>"
            f"<p>A reminder that your {html.escape(round_name)} with {html.escape(company)} starts at "
            f"<strong>{html.escape(_local_time(candidate, interview.start_time))}</strong>.</p>"
            f"{_meeting_line(interview)}"
            f"<p>Reply to this email if anything has changed.</p>")


COPY = {
    "ONBOARDING_START": ("Welcome to {company} - your joining documents", _onboarding_body),
    # every interview, from the screens or Flash (CEO 2026-10-15); ref = "{interview id}:{start}"
    "INTERVIEW_INVITE": ("Your interview with {company}", _interview_invite_body),
    # ref = "{interview id}:{start}:{minutes before}"
    "INTERVIEW_REMINDER": ("Reminder: your interview with {company}", _interview_reminder_body),
}


class SendPipelineEmailHandler:
    TIMEOUT_SECONDS = TIMEOUT_SECONDS
    MAX_RETRIES = 6

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session, mailbox: Optional[GraphMailbox] = None) -> Dict[str, Any]:
        from app.models.tenant import Tenant
        from app.services.candidate_portal_service import generate_portal_link_url

        payload = message.payload or {}
        email_id = payload.get("email_id")
        row = db.query(PipelineEmail).filter(PipelineEmail.id == email_id).with_for_update().first()
        from app.services.thunder_mail import candidate_notices

        if row is None or (row.kind not in COPY and not candidate_notices.is_notice(row.kind)):
            raise ValueError(f"Message {message.id}: pipeline email {email_id!r} not found or unknown kind")
        if row.sent_at is not None:
            return {"status": "already_sent", "email_id": email_id}
        candidate = db.query(Candidate).filter(Candidate.candidateID == row.candidate_id).first()
        if candidate is None or not candidate.candidateEmail:
            raise ValueError(f"Candidate {row.candidate_id} not found or has no email")
        logger.info(f"[PipelineEmail] handler_start {email_id} kind={row.kind}")

        mailbox = mailbox or GraphMailbox(settings.THUNDER_MAILBOX)
        if row.graph_id is None:
            tenant = db.query(Tenant).filter(Tenant.id == candidate.tenant_id).first()
            company = tenant.name if tenant else "BlitzenX"
            try:
                if row.kind in COPY:
                    subject, build = COPY[row.kind]
                    subject = subject.format(company=company)
                    body = build(db, candidate, company, generate_portal_link_url(db, candidate.candidateID), row)
                else:  # a candidate notice: Thunder's consent, window, caps and the tenant's template
                    subject, body = candidate_notices.render(db, candidate, row, company)
            except (Superseded, candidate_notices.NotSent) as exc:
                logger.info(f"[PipelineEmail] handler_complete {email_id}: not sent, {exc}")
                return {"status": "superseded", "email_id": email_id, "reason": str(exc)}
            row.graph_id, _, _ = mailbox.create_draft(candidate.candidateEmail, subject, body, f"pipeline:{row.id}")
            db.commit()
        if mailbox.is_draft(row.graph_id):
            mailbox.send(row.graph_id)
        row.sent_at = datetime.utcnow()
        db.commit()
        logger.info(f"[PipelineEmail] handler_complete {email_id}")
        return {"status": "sent", "email_id": email_id, "message_sent": True, "delivery_confirmed": True}
