"""Candidate notices: the one way WROS emails a candidate about something that happened to them
(CEO 2026-10-31: "yes all 4 and every future candidate should get the emails").

queue_notice(db, candidate, template_key, ref) after the caller's commit. It is sent by the
send_pipeline_email handler from the Thunder mailbox, and Thunder's guardrails apply at queue
time and again at send time:

  - consent: a real contact address, email consent not revoked (an unsubscribe stops these too),
    and no post-rejection no-contact period -- except the rejection notice itself;
  - send window: queued for the next candidate-local weekday window (THUNDER_SEND_WINDOW); a send
    that falls outside it is deferred, never dropped;
  - send caps: THUNDER_MAX_SENDS_PER_HOUR / _PER_DAY count every email from the Thunder mailbox
    (cadence touches and these notices together); over a cap the send is deferred;
  - templates: the wording is the tenant's active message template for the key (Settings >
    Message Templates), seeded once per tenant and editable;
  - once: one email per (template, candidate, ref) -- the pipeline_emails row is the key.

Notices today: every pipeline status (candidate_status_notifications.STATUS_TEMPLATE; the
rejection notice is one per job and never names the client), an interview cancelled or removed,
and a released offer withdrawn. A new candidate-facing email adds a template here and calls
queue_notice; it never sends directly."""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.candidate import Candidate

logger = logging.getLogger(__name__)

INTERVIEW_CANCELLED = "CANDIDATE_INTERVIEW_CANCELLED"
OFFER_CANCELLED = "CANDIDATE_OFFER_CANCELLED"
REJECTED = "CANDIDATE_STATUS_REJECTED"

_SIGN = "\n\nBest regards,\nThe {{company_name}} Recruiting Team"
TEMPLATES: Dict[str, Dict[str, str]] = {
    INTERVIEW_CANCELLED: {
        "name": "Candidate: interview cancelled",
        "subject": "Your interview has been cancelled",
        "body": "Hi {{candidate_first_name}},\n\nYour {{round_name}} scheduled for {{interview_time}} has been "
                "cancelled. We're sorry for the change - your recruiter will be in touch about next steps." + _SIGN},
    OFFER_CANCELLED: {
        "name": "Candidate: offer withdrawn",
        "subject": "An update on your offer from {{company_name}}",
        "body": "Hi {{candidate_first_name}},\n\nWe're writing to let you know that the offer for the "
                "{{position}} role has been withdrawn. We're sorry to share this news. Your recruiter will "
                "reach out to talk it through and answer any questions." + _SIGN},
}


def all_templates() -> Dict[str, Dict[str, str]]:
    """Every candidate notice template: the status ones and the event ones."""
    from app.services.candidate_status_notifications import DEFAULT_TEMPLATES

    return {**DEFAULT_TEMPLATES, **TEMPLATES}


def is_notice(kind: Optional[str]) -> bool:
    return kind in all_templates()


# --------------------------------------------------------------------------- guardrails

def may_email(db: Session, candidate: Optional[Candidate], template_key: str) -> Tuple[bool, str]:
    """Consent for one notice: real address, consent not revoked, no no-contact period (the
    rejection notice itself is the exception -- it is what starts that period)."""
    from app.services.candidate_contact_policy import rejection_cooldown_until
    from app.services.linkedin_pipeline_task_service import is_placeholder_email
    from app.services.thunder_mail.cadence_service import email_consent_revoked

    if candidate is None:
        return False, "candidate not found"
    if not candidate.candidateEmail or is_placeholder_email(candidate.candidateEmail):
        return False, "no real contact email"
    if email_consent_revoked(db, candidate.candidateID):
        return False, "email consent revoked"
    if template_key != REJECTED:
        until = rejection_cooldown_until(db, candidate.candidateID)
        if until is not None:
            return False, f"no-contact period until {until.isoformat()}"
    return True, "ok"


def cap_retry_at(db: Session, now: datetime) -> Optional[datetime]:
    """When to retry if the Thunder mailbox is over a send cap (cadence emails and notices count
    together), else None."""
    from app.core.config import settings
    from app.models.pipeline_email import PipelineEmail
    from app.models.thunder_email import ThunderEmailMessage

    def sent_since(delta: timedelta) -> int:
        cadence = db.query(ThunderEmailMessage).filter(
            ThunderEmailMessage.direction == "OUT", ThunderEmailMessage.status == "SENT",
            ThunderEmailMessage.mailbox == settings.THUNDER_MAILBOX, ThunderEmailMessage.sent_at >= now - delta,
        ).count()
        notices = db.query(PipelineEmail).filter(PipelineEmail.sent_at >= now - delta).count()
        return cadence + notices

    if sent_since(timedelta(days=1)) >= settings.THUNDER_MAX_SENDS_PER_DAY:
        return now + timedelta(hours=6)
    if sent_since(timedelta(hours=1)) >= settings.THUNDER_MAX_SENDS_PER_HOUR:
        return now + timedelta(minutes=20)
    return None


# --------------------------------------------------------------------------- queue

def queue_notice(db: Session, candidate: Candidate, template_key: str, ref: str,
                 now: Optional[datetime] = None) -> Optional[str]:
    """Record and queue one notice after the caller's commit; returns its email id, or None when
    the candidate may not be emailed or this notice was already queued. Commits its own row."""
    from app.services.hiring_onboarding_service import PIPELINE_EMAIL_TASK, queue_candidate_email
    from app.services.thunder_mail.cadence_service import enqueue_once, next_send_slot

    if template_key not in all_templates():
        raise ValueError(f"Unknown candidate notice template {template_key!r}")
    allowed, reason = may_email(db, candidate, template_key)
    if not allowed:
        logger.info(f"[CandidateNotice] {template_key} for {getattr(candidate, 'candidateID', None)}: not sent ({reason})")
        return None
    email_id = queue_candidate_email(db, candidate, template_key, ref)
    if email_id is None:
        return None
    db.commit()
    now = now or datetime.utcnow()
    slot = next_send_slot(candidate, now)
    delay = int((slot - now).total_seconds()) if slot else 0
    enqueue_once(PIPELINE_EMAIL_TASK, email_id, {"email_id": email_id, "candidate_id": candidate.candidateID},
                 candidate.tenant_id, delay_seconds=max(delay, 0))
    logger.info(f"[CandidateNotice] {email_id} queued (delay {max(delay, 0)}s)")
    return email_id


def safely(label: str, fn, *args, **kwargs) -> Optional[str]:
    """For callers whose action is already committed: a notice that cannot be queued is logged with
    the stack and never undoes the action."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logger.error(f"[CandidateNotice] {label} not queued: {exc}", exc_info=True)
        return None


def interview_ref(interview_id: int, start: datetime, round_name: Optional[str]) -> str:
    """The cancelled interview's id, time and round travel in the ref: a deleted row is gone."""
    return f"{interview_id}:{start:%Y%m%dT%H%M}:{(round_name or 'interview')[:60]}"


def queue_interview_cancelled(db: Session, candidate_id: str, interview_id: int, start: datetime,
                              round_name: Optional[str]) -> Optional[str]:
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    return queue_notice(db, candidate, INTERVIEW_CANCELLED, interview_ref(interview_id, start, round_name))


def queue_offer_cancelled(db: Session, offer) -> Optional[str]:
    """Only an offer the candidate was given (released) is withdrawn to them."""
    if offer.released_at is None:
        return None
    candidate = db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()
    return queue_notice(db, candidate, OFFER_CANCELLED, str(offer.id))


def queue_status(db: Session, candidate: Candidate, new_status: str) -> Dict:
    """The stage's notice for a pipeline status, once per status and job (the rejection notice is
    therefore one per job)."""
    from app.core.config import settings
    from app.services.candidate_status_notifications import template_key_for

    key = template_key_for(new_status)
    if key is None:
        return {"queued": False, "reason": f"no candidate email for status {new_status!r}"}
    if not settings.CANDIDATE_STATUS_EMAILS_ENABLED:
        return {"queued": False, "reason": "CANDIDATE_STATUS_EMAILS_ENABLED is off"}
    email_id = queue_notice(db, candidate, key, f"{new_status}:{candidate.job_id or 'none'}")
    return {"queued": email_id is not None, "template": key, "email_id": email_id}


# --------------------------------------------------------------------------- send time

class NotSent(Exception):
    """The notice no longer applies or may no longer be sent; nothing is mailed."""


def _local(candidate: Candidate, value: datetime) -> str:
    from zoneinfo import ZoneInfo

    from app.core.config import settings

    tz_name = candidate.timezone or settings.INTERVIEW_DEFAULT_TIMEZONE
    local = value.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(tz_name))
    return f"{local:%A %d %B %Y, %H:%M} ({tz_name})"


def _variables(db: Session, candidate: Candidate, row, company: str) -> Dict[str, str]:
    """The template's variables, read at send time; NotSent when the event was undone."""
    from app.models.candidate import CandidateStatus
    from app.models.offer_letter import OfferLetter
    from app.models.user import Interview
    from app.services.candidate_status_notifications import STATUS_TEMPLATE

    variables = {"candidate_first_name": candidate.candidateFirstName or "there", "company_name": company}
    if row.kind == INTERVIEW_CANCELLED:
        interview_id, start_key, round_name = (row.ref.split(":", 2) + ["", ""])[:3]
        interview = db.query(Interview).filter(Interview.id == int(interview_id)).first() \
            if interview_id.isdigit() else None
        if interview is not None and interview.status == "Scheduled":
            raise NotSent(f"interview {interview_id} is scheduled again")
        variables["round_name"] = round_name or "interview"
        variables["interview_time"] = _local(candidate, datetime.strptime(start_key, "%Y%m%dT%H%M"))
    elif row.kind == OFFER_CANCELLED:
        offer = db.query(OfferLetter).filter(OfferLetter.id == int(row.ref)).first()
        if offer is None or offer.offer_status != "Cancelled":
            raise NotSent(f"offer {row.ref} is no longer cancelled")
        variables["position"] = offer.position
    elif row.kind in STATUS_TEMPLATE.values():
        status = (row.ref or "").split(":", 1)[0]
        current = db.query(CandidateStatus.piplineStatus).filter(
            CandidateStatus.candidateID == candidate.candidateID).scalar()
        if current is not None and current != status:
            raise NotSent(f"status moved on from {status} to {current}")
    return variables


def render(db: Session, candidate: Candidate, row, company: str, now: Optional[datetime] = None) -> Tuple[str, str]:
    """(subject, html) of a notice about to be drafted. Raises NotSent when it must not go,
    DeliveryDeferred when it must wait (send window, send cap)."""
    import html as html_lib

    from app.services.candidate_status_notifications import seed_templates
    from app.services.delivery_errors import DeliveryDeferred
    from app.services.message_template_service import render_template
    from app.services.thunder_mail.cadence_service import next_send_slot

    allowed, reason = may_email(db, candidate, row.kind)
    if not allowed:
        raise NotSent(reason)
    now = now or datetime.utcnow()
    slot = next_send_slot(candidate, now)
    if slot is not None:
        raise DeliveryDeferred("outside the candidate's send window", retry_at=slot)
    retry = cap_retry_at(db, now)
    if retry is not None:
        raise DeliveryDeferred("Thunder mailbox send cap reached", retry_at=retry)
    variables = _variables(db, candidate, row, company)
    if seed_templates(db, candidate.tenant_id):  # a tenant that predates a template gets it
        db.flush()
    rendered = render_template(db, row.kind, "EMAIL", str(candidate.tenant_id), variables)
    body = "<br>".join(html_lib.escape(line) for line in rendered["rendered_body"].split("\n"))
    return rendered["rendered_subject"], body
