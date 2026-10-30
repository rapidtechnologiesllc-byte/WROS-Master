"""Thunder email cadence: what to send next, when, and how a reply changes the plan.

Silence never ends a cadence: after the 4 active touches a candidate moves to
monthly NURTURE indefinitely. Only an opt-out or a hostile reply stops it.
"""
from app.core.tenant_context import sole_tenant_id
import html
import logging
import re
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate import Candidate
from app.models.consent import ConsentRecord
from app.models.thunder_email import (
    ThunderCadenceState, ThunderEmailMessage, ThunderMonthlyHighlight, ThunderOutreachVariant,
)
from app.models.user import Jobs

logger = logging.getLogger(__name__)

SEND_TASK = "thunder_send_email"
INBOUND_TASK = "thunder_process_inbound_email"
# Silence after step N -> step N+1 after this many days; after step 4 -> NURTURE
SILENCE_DELAY_DAYS = {"1": 3, "2": 7, "3": 14}
NOT_NOW_PAUSE_DAYS = 90
AUTO_REPLY_PUSH_DAYS = 3
MAX_NURTURE_JOBS = 5
ACK_STEP_FOR_INTENT = {"INTERESTED": "ACK_INTERESTED", "QUESTION_COMP": "ACK_COMP", "QUESTION_ROLE": "ACK_ROLE"}
# Compensation asked but no salary on record: a holding reply (a person answers the pay question)
ACK_HOLD = "ACK_HOLD"
# Any other reply while profile details are still missing: thank them and ask for the rest
ACK_FIELDS = "ACK_FIELDS"
# Each further reply gets its own acknowledgement ("ACK_ROLE#2"...); never more than this many per
# kind in one cadence, so a candidate's mail loop cannot make Thunder answer forever
MAX_ACKS_PER_KIND = 5


def step_family(step: str) -> str:
    if step.startswith("NURTURE"):
        return "NURTURE"
    return step.split("#", 1)[0] if step.startswith("ACK_") else step


def next_ack_step(db: Session, candidate_id: str, cadence_seq: int, ack: str) -> Optional[str]:
    """The step id for this acknowledgement: the kind itself the first time, then "<kind>#<n>";
    None once MAX_ACKS_PER_KIND were planned in this cadence. Counted on the inbound rows (each
    records the acknowledgement it was answered with), so replies that arrive before the first
    acknowledgement is sent still get their own."""
    used = db.query(ThunderEmailMessage.step).filter(
        ThunderEmailMessage.candidate_id == candidate_id, ThunderEmailMessage.cadence_seq == cadence_seq,
        ThunderEmailMessage.direction == "IN",
        (ThunderEmailMessage.step == ack) | ThunderEmailMessage.step.like(f"{ack}#%"),
    ).count()
    if used >= MAX_ACKS_PER_KIND:
        return None
    return ack if used == 0 else f"{ack}#{used + 1}"


def fields_request_html(fields: List[Dict[str, str]]) -> str:
    """The profile details still missing, as the paragraph an acknowledgement ends with."""
    if not fields:
        return ""
    items = "".join(f"<li>{html.escape(f['label'])}</li>" for f in fields)
    return f"<p>To move things forward, could you reply with these details?</p><ul>{items}</ul>"


def with_fields_request(template: str) -> str:
    """The template with a {fields_request} slot before the signature: approved copy written
    before the slot existed has none, and an empty request renders as nothing."""
    if "{fields_request}" in template:
        return template
    at = template.find("<p>Regards,")
    return template + "{fields_request}" if at < 0 else template[:at] + "{fields_request}" + template[at:]


def nurture_step(when: datetime) -> str:
    # Day-level key: two nurture touches can never collide on (candidate, seq, step)
    return f"NURTURE-{when:%Y%m%d}"


def send_task_id(candidate_id: str, cadence_seq: int, step: str) -> str:
    return f"thunder_send:{candidate_id}:{cadence_seq}:{step}"


def enqueue_once(task_name: str, task_id: str, data: Dict, tenant_id: Optional[int], delay_seconds: int = 0) -> bool:
    """Deterministic task_id is the queue's primary key, so this is idempotent."""
    from app.core.database import SessionLocal
    from app.models.channel_queue import ChannelQueueItem
    from app.services.message_queue_service import MessageQueueService

    check = SessionLocal()
    try:
        if check.query(ChannelQueueItem.id).filter(ChannelQueueItem.id == task_id).first():
            return False
    finally:
        check.close()
    try:
        MessageQueueService.enqueue(task_name=task_name, task_id=task_id, data=data,
                                    delay_seconds=delay_seconds, tenant_id=tenant_id)
        return True
    except RuntimeError as exc:
        check = SessionLocal()
        try:
            if check.query(ChannelQueueItem.id).filter(ChannelQueueItem.id == task_id).first():
                return False  # lost a race with another enqueuer: already queued
        finally:
            check.close()
        raise RuntimeError(f"Could not enqueue {task_id}: {exc}") from exc


def enqueue_send(state: ThunderCadenceState) -> bool:
    return enqueue_once(
        SEND_TASK, send_task_id(state.candidate_id, state.cadence_seq, state.next_step),
        {"candidate_id": state.candidate_id, "cadence_seq": state.cadence_seq,
         "step": state.next_step, "tenant_id": state.tenant_id},
        state.tenant_id,
    )


def start_cadence(db: Session, candidate: Candidate, *, job_id: Optional[str] = None,
                  now: Optional[datetime] = None) -> ThunderCadenceState:
    """Idempotent. Caller commits, then calls enqueue_send(state)."""
    now = now or datetime.utcnow()
    state = db.query(ThunderCadenceState).filter_by(candidate_id=candidate.candidateID).first()
    if state is not None:
        return state
    state = ThunderCadenceState(
        candidate_id=candidate.candidateID, tenant_id=candidate.tenant_id, job_id=job_id or candidate.job_id,
        cadence_seq=1, stage="ACTIVE", next_step="1", next_action_at=now, touches_sent=0,
    )
    db.add(state)
    return state


# ---- guardrails -----------------------------------------------------------------

def email_consent_revoked(db: Session, candidate_id: str) -> bool:
    latest = db.query(ConsentRecord).filter(
        ConsentRecord.subject_id == candidate_id, ConsentRecord.consent_type == "email_outreach",
    ).order_by(ConsentRecord.id.desc()).first()
    return latest is not None and not latest.consent_given


def next_send_slot(candidate: Candidate, now: datetime) -> Optional[datetime]:
    """None if `now` is inside the candidate-local weekday send window,
    otherwise the next window opening (naive UTC)."""
    start_hour, end_hour = (int(h) for h in settings.THUNDER_SEND_WINDOW.split("-"))
    try:
        tz = ZoneInfo(candidate.timezone or "Asia/Kolkata")
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("Asia/Kolkata")
    local = now.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
    if local.weekday() < 5 and start_hour <= local.hour < end_hour:
        return None
    day = local.date() if local.hour < start_hour else local.date() + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    opening = datetime.combine(day, time(start_hour), tzinfo=tz)
    return opening.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def send_cap_retry_at(db: Session, now: datetime) -> Optional[datetime]:
    sent_since = lambda delta: db.query(ThunderEmailMessage).filter(  # noqa: E731
        ThunderEmailMessage.direction == "OUT", ThunderEmailMessage.status == "SENT",
        ThunderEmailMessage.mailbox == settings.THUNDER_MAILBOX, ThunderEmailMessage.sent_at >= now - delta,
    ).count()
    if sent_since(timedelta(days=1)) >= settings.THUNDER_MAX_SENDS_PER_DAY:
        return now + timedelta(hours=6)
    if sent_since(timedelta(hours=1)) >= settings.THUNDER_MAX_SENDS_PER_HOUR:
        return now + timedelta(minutes=20)
    return None


# ---- content -------------------------------------------------------------------

class _SafeFields(dict):
    def __missing__(self, key):
        return ""


def _tokens(text: Optional[str]) -> set:
    return {t for t in re.split(r"[^a-z0-9+#.]+", (text or "").lower()) if len(t) > 1}


def matching_open_jobs(db: Session, candidate: Candidate, limit: int = MAX_NURTURE_JOBS) -> List[Jobs]:
    skills = _tokens(candidate.candidateSkills) | _tokens(candidate.candidateJobTitle)
    location = _tokens(candidate.candidateCurrentLocation)
    scored = []
    for job in db.query(Jobs).filter(Jobs.jobStatus != "Closed").order_by(Jobs.jobCreatedAt.desc()).limit(200):
        overlap = len(skills & (_tokens(job.jobSkills) | _tokens(job.jobTitle)))
        if overlap:
            scored.append((overlap + (1 if location & _tokens(job.jobLocation) else 0), job))
    scored.sort(key=lambda pair: -pair[0])
    return [job for _, job in scored[:limit]]


def nurture_content(db: Session, candidate: Candidate, when: datetime) -> Optional[Dict[str, str]]:
    """Real content only: matching open jobs + this month's approved highlight.
    None when there is nothing new, so no empty email is sent."""
    jobs = matching_open_jobs(db, candidate)
    highlight = db.query(ThunderMonthlyHighlight).filter_by(
        tenant_id=candidate.tenant_id if candidate.tenant_id is not None else sole_tenant_id(db), month=f"{when:%Y-%m}").first()
    if not jobs and highlight is None:
        return None
    items = "".join(
        f"<li>{html.escape(job.jobTitle)} &middot; {html.escape(job.jobLocation or '')}</li>" for job in jobs
    )
    return {
        "jobs_list": f"<ul>{items}</ul>" if items else "",
        "highlight": (f"<h3>{html.escape(highlight.title)}</h3>{highlight.body_html}" if highlight else ""),
    }


def _intelligence(db: Session, candidate: Candidate) -> Dict:
    from app.models.candidate_intelligence import CandidateIntelligenceProfile

    profile = db.query(CandidateIntelligenceProfile).filter_by(
        candidate_id=candidate.candidateID).order_by(CandidateIntelligenceProfile.id.desc()).first()
    return (profile.profile_json or {}) if profile else {}


def source_note(db: Session, candidate: Candidate) -> str:
    """Where we found an enriched candidate's address (GDPR Art. 14 / DPDP notice)."""
    source = ((_intelligence(db, candidate).get("contact_source") or {}).get("value") or "")
    site = source.split(":", 1)[-1] if source.startswith("personal_site:") else ""
    return f" We found your contact address on {html.escape(site)}." if site else ""


def personal_hook(db: Session, candidate: Candidate) -> str:
    """One specific, true sentence from enrichment evidence (escaped), or ''."""
    data = _intelligence(db, candidate)
    repos = ((data.get("open_source") or {}).get("value") or {}).get("top_repos") or []
    if repos and repos[0].get("name"):
        return f"I came across your work on {html.escape(repos[0]['name'])}. "
    headline = (data.get("headline") or {}).get("value")
    if headline:
        return f"Your experience as {html.escape(headline)} stood out. "
    return ""


def render(variant: ThunderOutreachVariant, candidate: Candidate, job: Optional[Jobs],
           extra: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    """Approved template + escaped merge fields. Salary is copied verbatim from
    the job record, never generated."""
    fields = _SafeFields({
        "first_name": html.escape(candidate.candidateFirstName or "there"),
        "sender_name": html.escape(settings.OUTREACH_SENDER_NAME),
        "job_title": html.escape(job.jobTitle) if job else "",
        "job_location": html.escape(job.jobLocation or "") if job else "",
        "salary_range": html.escape(job.salaryRange or "") if job else "",
        **(extra or {}),
    })
    subject = variant.subject_template.format_map(_SafeFields({k: html.unescape(v) for k, v in fields.items()}))
    return subject, with_fields_request(variant.body_template).format_map(fields)


# ---- plan updates ----------------------------------------------------------------

def schedule_after_send(state: ThunderCadenceState, sent_step: str, now: datetime) -> None:
    family = step_family(sent_step)
    if family in SILENCE_DELAY_DAYS:
        state.next_step = str(int(family) + 1)
        state.next_action_at = now + timedelta(days=SILENCE_DELAY_DAYS[family])
    elif family in ("4", "NURTURE"):
        state.stage = "NURTURE"
        when = now + timedelta(days=settings.THUNDER_NURTURE_INTERVAL_DAYS)
        state.next_step, state.next_action_at = nurture_step(when), when
    # ACK_* sends leave the HANDOFF fallback (set by apply_reply) untouched


def stop(db: Session, state: ThunderCadenceState, candidate: Candidate, reason: str) -> None:
    state.stage, state.stop_reason = "STOPPED", reason
    state.next_step, state.next_action_at = None, None
    candidate.thunder_enabled = False
    db.add(ConsentRecord(
        subject_type="candidate", subject_id=candidate.candidateID, tenant_id=candidate.tenant_id,
        consent_type="email_outreach", consent_given=False, captured_by="candidate_email_reply",
    ))
    db.add(candidate)


def apply_reply(db: Session, state: ThunderCadenceState, candidate: Candidate, intent: str,
                erasure_requested: bool, job: Optional[Jobs], now: datetime,
                missing_fields: Optional[List[Dict[str, str]]] = None) -> Dict:
    """Re-plan after an inbound email. Returns the actions for the caller to
    execute after commit: {'ack_step', 'handoff', 'erasure'}."""
    actions = {"ack_step": None, "handoff": None, "erasure": False}
    if intent == "AUTO":
        if state.next_action_at:
            state.next_action_at = max(state.next_action_at, now + timedelta(days=AUTO_REPLY_PUSH_DAYS))
        return actions

    state.last_inbound_at = now
    if intent in ("UNSUBSCRIBE", "HOSTILE"):
        stop(db, state, candidate, f"candidate {intent.lower()}")
        actions["erasure"] = erasure_requested
        if erasure_requested:
            actions["handoff"] = "Data erasure requested by candidate (DPDP/GDPR) — action within statutory deadline"
        return actions

    if intent == "NOT_NOW":
        when = now + timedelta(days=NOT_NOW_PAUSE_DAYS)
        state.stage, state.next_step, state.next_action_at = "NURTURE", nurture_step(when), when
        return actions
    if intent == "NOT_INTERESTED":
        when = now + timedelta(days=settings.THUNDER_NURTURE_INTERVAL_DAYS)
        state.stage, state.next_step, state.next_action_at = "NURTURE", nurture_step(when), when
        return actions

    # Positive or unclear: a recruiter takes the conversation. If nobody follows
    # up, the candidate falls back to monthly nurture instead of being left.
    when = now + timedelta(days=settings.THUNDER_NURTURE_INTERVAL_DAYS)
    state.stage, state.next_step, state.next_action_at = "HANDOFF", nurture_step(when), when
    ack = ACK_STEP_FOR_INTENT.get(intent)
    if ack == "ACK_COMP" and not (job and job.salaryRange):
        ack = ACK_HOLD  # never quote pay we don't have on record; never leave them unanswered
    if ack is None and missing_fields:
        ack = ACK_FIELDS
    actions["ack_step"] = next_ack_step(db, state.candidate_id, state.cadence_seq, ack) if ack else None
    actions["handoff"] = {
        "INTERESTED": "Candidate is interested — book a call",
        "QUESTION_COMP": "Candidate asked about compensation" + ("" if ack != ACK_HOLD else " (no salary on record — answer personally)"),
        "QUESTION_ROLE": "Candidate asked about the role — follow up",
    }.get(intent, "Candidate replied — review and respond")
    return actions
