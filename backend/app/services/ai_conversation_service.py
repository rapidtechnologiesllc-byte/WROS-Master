"""
AI Conversation Agent Service
==============================
The email-based profile-completion agent (Thunder's intake conversation):

  1. Detect missing fields in the candidate record (core table + personal-details form).
  2. Email the candidate a branded list of what is missing.
  3. Read the candidate's reply from the Thunder mailbox (Microsoft Graph).
  4. Extract the values with the LLM (the reply is fenced as untrusted data).
  5. Merge them into candidates / candidate_forms, and follow up on anything still missing.
  6. Log every step as a ConversationEvent.

Restored 2026-10-14: an automated cleanup on 2026-09-03 had replaced this module with stubs that
reported success without doing anything (portal profile saves were dropped, nothing was ever
"missing"). Engagement records are keyed by the tenant (app.core.tenant_context.
conversation_tenant_key); Thunder's name/persona come from the tenant's AI configuration.
"""
import html as _html
import json
import logging
import os
import re
from datetime import date as _date
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm_prompt_safety import build_safe_prompt, flag_suspicious_patterns
from app.core.tenant_context import conversation_tenant_key, sole_tenant_id
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AI_AGENT_NAME = "onboarding-ai"  # CandidateConversation.owner_id token for the AI owner (R-08)
AI_AGENT_PERSONA = "friendly-hr"
SERVICE_MAILBOX = settings.THUNDER_MAILBOX
DEFAULT_THUNDER_DISPLAY_NAME = "Thunder"
DEFAULT_THUNDER_PERSONA_TEXT = (
    "I am Thunder, Talent Scout at BlitzenX -- powering our global team at lightning speed. "
    "I help candidates through the application process with professionalism and speed."
)

# (candidate column, label the candidate sees). Aadhar / PAN are documents, not asked here.
# Everything the HR profile's Basic and Professional sections show, except the optional middle name.
CANDIDATE_CORE_FIELDS: List[Tuple[str, str]] = [
    ("candidateFirstName", "First Name"),
    ("candidateLastName", "Last Name"),
    # The country code matters: WhatsApp sends to this number as-is
    ("candidateMobile", "Mobile Number (with country code, e.g. +91 98765 43210)"),
    ("candidateGender", "Gender"),
    ("candidateDateOfBirth", "Date of Birth (YYYY-MM-DD)"),
    ("candidateCurrentLocation", "Current Location"),
    ("candidateJobTitle", "Job Title / Role Applied For"),
    ("candidateExperience", "Years of Experience"),
    ("candidateSkills", "Top Skills (with years of experience in each)"),
    ("employment_type", "Employment Type you are looking for (full-time or contract)"),
    ("candidate_notice_period", "Notice Period (in days)"),
    ("candidateJoiningDate", "Earliest Available Start Date (YYYY-MM-DD)"),
    ("candidateCurrentSalary", "Current Salary (amount, and per hour or per year)"),
    ("candidateExpectedSalary", "Expected Salary (amount, and per hour or per year)"),
]
DATE_FIELDS = ("candidateDateOfBirth", "candidateJoiningDate")
# Asked as their amount; the reply may also give the rate, saved alongside
SALARY_TYPE_FIELDS = {"candidateCurrentSalary": "candidateCurrentSalaryType",
                      "candidateExpectedSalary": "candidateExpectedSalaryType"}
SALARY_RATE_TYPES = ("$/Hour", "$/Day", "$/Week", "$/Month", "$/Year")  # the profile's RateField options
# Types a candidate can say they want; C2C / 1099 / UNKNOWN are never accepted (employment_type_policy)
ASKABLE_EMPLOYMENT_TYPES = ("FULLTIME", "CONTRACT")
# Not a typed value: Thunder asks the candidate to attach it to their email reply
RESUME_FIELD = {"field": "resume", "label": "Your latest resume (please attach it to your reply)", "source": "document"}

# Personal-details form (candidate_forms). The AI only needs city/state/country of the address.
INFO_FORM_FIELDS: List[Tuple[str, str]] = [
    ("marital_status", "Marital Status"),
    ("nationality", "Nationality"),
    ("permanent_address", "Permanent Address (City, State, Country only -- no street address needed)"),
]

GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


# ===========================================================================
# Tenant and Thunder identity
# ===========================================================================

def resolve_default_tenant_id(db: Optional[Session] = None) -> str:
    """The engagement-record key of the deployment's tenant, for callers that have no tenant
    of their own (scheduled jobs, dashboards). Looked up, never a literal: with more than one
    tenant this raises, and the caller must pass the tenant explicitly."""
    if db is not None:
        return conversation_tenant_key(sole_tenant_id(db))
    from app.core.database import SessionLocal

    session = SessionLocal()
    try:
        return conversation_tenant_key(sole_tenant_id(session))
    finally:
        session.close()


def resolve_thunder_config(db: Session, tenant_id: Optional[str] = None) -> Dict[str, str]:
    """Thunder's candidate-facing {"name", "persona"} for the tenant (never blank, BR-02)."""
    from app.services.tenant_ai_config_service import thunder_identity

    return thunder_identity(db, tenant_id)


# ===========================================================================
# 1. Missing-field detection and merge
# ===========================================================================

def _core_value_missing(candidate: Candidate, field: str, db: Session) -> bool:
    if field == "employment_type":
        return candidate.employment_type in (None, "", "UNKNOWN")
    if field == "candidateSkills":
        from app.models.candidate_profile_extras import CandidateProfileSkill

        return not candidate.candidateSkills and not db.query(CandidateProfileSkill.id).filter(
            CandidateProfileSkill.candidate_id == candidate.candidateID).first()
    return getattr(candidate, field, None) in (None, "")


def get_missing_fields(candidate: Candidate, db: Session, include_documents: bool = False) -> List[Dict[str, str]]:
    """Every empty field as {field, label, source}; source = 'candidate' | 'info_form' | 'document'.
    include_documents adds the resume when none is on file: only an email channel (Thunder) can
    receive it, as an attachment."""
    missing = [{"field": field, "label": label, "source": "candidate"}
               for field, label in CANDIDATE_CORE_FIELDS if _core_value_missing(candidate, field, db)]
    info = db.query(CandidateInfoForm).filter(CandidateInfoForm.candidateID == candidate.candidateID).first()
    missing += [{"field": field, "label": label, "source": "info_form"}
                for field, label in INFO_FORM_FIELDS if not (getattr(info, field, None) if info else None)]
    if include_documents:
        from app.services.candidate_resume_intake import has_resume

        if not has_resume(db, candidate.candidateID):
            missing.append(dict(RESUME_FIELD))
    return missing


def _skill_names(value: Any) -> List[Tuple[str, Optional[str]]]:
    """[(skill, years)] from a list ("Java", {"name": "Java", "years": 5}) or "Java (5 years), SQL"."""
    items = value if isinstance(value, list) else re.split(r"[,;\n]", str(value))
    skills: List[Tuple[str, Optional[str]]] = []
    for item in items:
        if isinstance(item, dict):
            name, years = str(item.get("name") or "").strip(), item.get("years")
        else:
            match = re.match(r"\s*(.+?)\s*(?:\((\d+(?:\.\d+)?)\s*(?:\+\s*)?y(?:ea)?rs?\)?)?\s*$", str(item))
            name, years = (match.group(1).strip(), match.group(2)) if match else (str(item).strip(), None)
        if name:
            skills.append((name[:255], str(years) if years not in (None, "") else None))
    return skills


def _save_skills(db: Session, candidate: Candidate, value: Any) -> bool:
    """The profile's Skills section (when empty) and the comma list used for matching."""
    from app.models.candidate_profile_extras import CandidateProfileSkill

    skills = _skill_names(value)
    if not skills:
        return False
    if not db.query(CandidateProfileSkill.id).filter(CandidateProfileSkill.candidate_id == candidate.candidateID).first():
        for index, (name, years) in enumerate(skills):
            db.add(CandidateProfileSkill(candidate_id=candidate.candidateID, name=name,
                                         years_of_experience=years, is_primary=index == 0))
    candidate.candidateSkills = ", ".join(name for name, _ in skills)
    return True


NOTICE_UNIT_DAYS = (("month", 30), ("week", 7), ("day", 1))
IMMEDIATE_NOTICE = re.compile(r"\b(immediate(ly)?|right away|now|none|no notice|serving)\b", re.IGNORECASE)


def notice_period_days(value: str) -> Optional[int]:
    """Whole days from a notice period as people write it: "30", "45 days", "2 months", "2/3 weeks"
    (a range counts as its longer end: they may not be free sooner), "immediately" (0)."""
    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", value or "")]
    if not numbers:
        return 0 if IMMEDIATE_NOTICE.search(value or "") else None
    per_unit = next((days for unit, days in NOTICE_UNIT_DAYS if unit in value.lower()), 1)
    return int(round(max(numbers) * per_unit))


def askable_employment_type(value: str) -> Optional[str]:
    """FULLTIME / CONTRACT from how people write it; C2C and 1099 are never accepted
    (employment_type_policy), so a reply naming them stays unanswered."""
    text = re.sub(r"[^a-z0-9]", "", (value or "").lower())
    if not text or "c2c" in text or "corp" in text or "1099" in text:
        return None
    if text.upper() in ASKABLE_EMPLOYMENT_TYPES:
        return text.upper()
    if text.startswith(("fulltime", "permanent", "fte", "w2", "direct")):
        return "FULLTIME"
    if text.startswith(("contract", "c2h")):
        return "CONTRACT"
    return None


def _core_value(field: str, value: str) -> Any:
    """The value to store for a core field, or None when it is not valid for that field."""
    if field in DATE_FIELDS:
        try:
            return _date.fromisoformat(value)
        except ValueError:
            return None
    if field == "candidateMobile":
        return value if value.startswith("+") else None
    if field == "candidate_notice_period":
        days = notice_period_days(value)
        return days if days is not None and days <= 365 else None
    if field == "employment_type":
        return askable_employment_type(value)
    if field in SALARY_TYPE_FIELDS.values():
        return value if value in SALARY_RATE_TYPES else None
    return value


def merge_fields_to_db(candidate_id: str, extracted: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """Write field values to the candidate's record (flushes; the caller commits).

    Returns {"updated": [...], "skipped": [...]} -- a field is skipped when it is empty, unknown,
    or invalid (a date that is not YYYY-MM-DD; a mobile number without a country code, which
    WhatsApp cannot reach, so it stays missing and is asked for again)."""
    if not extracted:
        return {"updated": [], "skipped": []}
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")

    core_fields = {f for f, _ in CANDIDATE_CORE_FIELDS} | set(SALARY_TYPE_FIELDS.values())
    info_fields = {f for f, _ in INFO_FORM_FIELDS}
    updated: List[str] = []
    skipped: List[str] = []
    info = None
    for field, raw_value in extracted.items():
        if field == "candidateSkills" and isinstance(raw_value, list):
            (updated if _save_skills(db, candidate, raw_value) else skipped).append(field)
            continue
        value = str(raw_value).strip() if raw_value is not None else ""
        if not value:
            skipped.append(field)
        elif field == "candidateSkills":
            (updated if _save_skills(db, candidate, value) else skipped).append(field)
        elif field in core_fields:
            stored = _core_value(field, value)
            if stored is None:
                logger.warning(f"[ProfileMerge] {candidate_id}: {field}={value!r} is not a valid value")
                skipped.append(field)
                continue
            setattr(candidate, field, stored)
            updated.append(field)
        elif field in info_fields:
            if info is None:
                info = db.query(CandidateInfoForm).filter(CandidateInfoForm.candidateID == candidate_id).first()
                if info is None:
                    info = CandidateInfoForm(candidateID=candidate_id)
                    db.add(info)
            setattr(info, field, value)
            updated.append(field)
        else:
            skipped.append(field)
    db.flush()
    logger.info(f"[ProfileMerge] {candidate_id}: updated={updated} skipped={skipped}")
    return {"updated": updated, "skipped": skipped}


# ===========================================================================
# 2. Emails
# ===========================================================================

def _candidate_display_name(candidate: Candidate) -> str:
    parts = [candidate.candidateFirstName, candidate.candidateMiddleName, candidate.candidateLastName]
    return " ".join(p for p in parts if p).strip() or candidate.candidateEmail


def _fields_email(title: str, intro: str, candidate_name: str, fields: List[Dict[str, str]],
                  conversation_id: int, thunder_name: str) -> str:
    from app.services.email_service import EmailService

    rows = "".join(
        f'<tr><td style="padding:8px 16px;border-bottom:1px solid #e5e7eb;font-size:14px;color:#374151;">'
        f"{i + 1}. {_html.escape(item['label'])}</td></tr>"
        for i, item in enumerate(fields)
    )
    body = f"""
    <p style="font-size:16px;color:#111827;margin:0 0 16px;">Dear <strong>{_html.escape(candidate_name)}</strong>,</p>
    <p style="font-size:14px;color:#374151;line-height:1.7;">{intro}</p>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border:1px solid #e5e7eb;border-radius:6px;overflow:hidden;margin:16px 0 20px;">{rows}</table>
    <p style="font-size:13px;color:#6b7280;line-height:1.6;">
      Simply hit <strong>Reply</strong> and provide the details above -- your profile is updated automatically.
    </p>
    <p style="font-size:13px;color:#9ca3af;margin-top:8px;">Reference ID: <code>CONV-{conversation_id}</code></p>
    <p style="font-size:14px;color:#374151;margin-top:24px;">Warm regards,<br/><strong>{_html.escape(thunder_name)}</strong>,
      BlitzenX</p>
    """
    return EmailService._base_html(title, body)


def _log_event(db: Session, conversation_id: int, event_type: str, event_data: Optional[Dict],
               triggered_by: str = "ai_agent") -> ConversationEvent:
    """Append an immutable row to conversation_events (flushed, not committed)."""
    event = ConversationEvent(conversation_id=conversation_id, event_type=event_type, event_data=event_data,
                              triggered_by=triggered_by)
    db.add(event)
    db.flush()
    return event


def _send_fields_email(db: Session, candidate: Candidate, conversation: CandidateConversation,
                       fields: List[Dict[str, str]], *, followup: bool) -> Dict[str, Any]:
    """Email the candidate the fields still needed. Honours the per-candidate pause and the
    organisation's kill switch; a send failure is logged on the conversation and returned."""
    from app.services.email_service import EmailService
    from app.services.thunder_pause_service import is_thunder_paused_for_conversation

    if is_thunder_paused_for_conversation(db, conversation):
        _log_event(db, conversation.id, "email_skipped_thunder_paused", {"missing_fields": [f["field"] for f in fields]})
        return {"sent": False, "reason": "Thunder is paused for this candidate or organisation"}
    thunder = resolve_thunder_config(db, conversation.tenant_id)
    name = _candidate_display_name(candidate)
    if followup:
        subject = f"Follow-up: a few more details needed -- CONV-{conversation.id}"
        html = _fields_email("Follow-up: Profile Completion",
                             "Thank you for your reply! We still need a few details to complete your profile:",
                             name, fields, conversation.id, thunder["name"])
    else:
        subject = f"Action Required: Complete Your Candidate Profile -- CONV-{conversation.id}"
        html = _fields_email("Profile Completion Request",
                             "Thank you for your interest in BlitzenX! To move forward we need a few more details "
                             "from you. Please reply to this email with:",
                             name, fields, conversation.id, thunder["name"])
    try:
        outcome = EmailService.send_email(to_email=candidate.candidateEmail, subject=subject, body_content=html,
                                          is_html=True)
        if isinstance(outcome, dict) and outcome.get("status") == "skipped":  # mail not configured: nothing sent
            raise RuntimeError(outcome.get("reason") or "email sending is not configured")
    except Exception as exc:
        logger.error(f"[AIAgent] Email to {candidate.candidateEmail} failed: {exc}", exc_info=True)
        _log_event(db, conversation.id, "email_send_failed", {"error": str(exc), "to": candidate.candidateEmail})
        return {"sent": False, "reason": str(exc)}
    _log_event(db, conversation.id, "ai_message_sent", {
        "channel": "email", "subject": subject, "to": candidate.candidateEmail,
        "missing_fields": [f["field"] for f in fields],
        "message_type": "followup_request" if followup else "missing_fields_request",
    })
    return {"sent": True, "subject": subject}


# ===========================================================================
# 3. Assignment and conversation thread
# ===========================================================================

def assign_ai_agent(candidate_id: str, tenant_id: Optional[str], assigned_by: Optional[str], db: Session) -> Dict[str, Any]:
    """Assign Thunder to a candidate: deactivate any active assignment, record a new one, open a
    conversation, and email the missing fields (or close it when nothing is missing).
    assigned_by is None for a system assignment. Commits."""
    from app.services.conversation_state_service import transition_status

    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")
    key = conversation_tenant_key(tenant_id if tenant_id is not None else candidate.tenant_id)

    db.query(CandidateAIAssignment).filter(
        CandidateAIAssignment.candidate_id == candidate_id, CandidateAIAssignment.is_active.is_(True),
    ).update({"is_active": False})
    thunder = resolve_thunder_config(db, key)
    assignment = CandidateAIAssignment(tenant_id=key, candidate_id=candidate_id, ai_agent_name=thunder["name"],
                                       ai_agent_persona=thunder["persona"], assigned_by=assigned_by, is_active=True)
    db.add(assignment)
    conversation = CandidateConversation(
        tenant_id=key, candidate_id=candidate_id, status="open", ai_agent_name=AI_AGENT_NAME,
        channel_preference="email", owner_type="ai_agent", owner_id=AI_AGENT_NAME, escalation_state="none",
        summary="AI agent assigned. Checking for missing profile fields.", next_action="send_missing_fields_email",
    )
    db.add(conversation)
    db.flush()
    _log_event(db, conversation.id, "ai_assigned",
               {"ai_agent_name": thunder["name"], "assigned_by": assigned_by, "assignment_id": assignment.id},
               triggered_by="hr_user" if assigned_by else "system")

    missing = get_missing_fields(candidate, db)
    _log_event(db, conversation.id, "field_check",
               {"total_missing": len(missing), "missing_fields": [m["field"] for m in missing]})
    email_sent = False
    if missing:
        email_sent = _send_fields_email(db, candidate, conversation, missing, followup=False)["sent"]
        transition_status(db, conversation, "awaiting_candidate", reason="Missing-fields email sent"
                          if email_sent else "Missing-fields email not sent", triggered_by="ai_agent")
        conversation.next_action = "wait_for_reply" if email_sent else "retry_missing_fields_email"
        conversation.summary = (f"{len(missing)} field(s) pending: " + ", ".join(m["label"] for m in missing))
    else:
        transition_status(db, conversation, "closed", reason="All required fields already present",
                          triggered_by="ai_agent")
        conversation.next_action = "none"
        conversation.summary = "All required fields are present. No email needed."
    db.commit()
    return {"assignment_id": assignment.id, "conversation_id": conversation.id, "candidate_id": candidate_id,
            "missing_fields_count": len(missing), "missing_fields": missing, "email_sent": email_sent,
            "conversation_status": conversation.status}


def get_active_ai_assignment(db: Session, candidate_id: str, tenant_id: str) -> Optional[CandidateAIAssignment]:
    return (db.query(CandidateAIAssignment)
            .filter(CandidateAIAssignment.candidate_id == candidate_id,
                    CandidateAIAssignment.tenant_id == conversation_tenant_key(tenant_id),
                    CandidateAIAssignment.is_active.is_(True))
            .order_by(CandidateAIAssignment.assigned_at.desc()).first())


def get_conversation_thread(candidate_id: str, db: Session) -> List[Dict[str, Any]]:
    """Every conversation for the candidate with its full event log, newest first."""
    from app.services.sla_monitoring_service import get_active_no_contact_breach_for_conversation

    result = []
    conversations = (db.query(CandidateConversation).filter(CandidateConversation.candidate_id == candidate_id)
                     .order_by(CandidateConversation.created_at.desc()).all())
    for conv in conversations:
        events = (db.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id)
                  .order_by(ConversationEvent.created_at.asc(), ConversationEvent.id.asc()).all())
        breach = get_active_no_contact_breach_for_conversation(db, conv.id)
        result.append({
            "conversation_id": conv.id, "status": conv.status, "ai_agent_name": conv.ai_agent_name,
            "channel_preference": conv.channel_preference, "summary": conv.summary,
            "summary_generated_at": conv.summary_generated_at.isoformat() if conv.summary_generated_at else None,
            "no_contact_breach_hours": round((datetime.utcnow() - breach.breached_at).total_seconds() / 3600.0, 1)
            if breach else None,
            "next_action": conv.next_action, "owner_type": conv.owner_type, "escalation_state": conv.escalation_state,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            "is_thunder_paused": bool(conv.is_thunder_paused),
            "thunder_resume_at": conv.thunder_resume_at.isoformat() if conv.thunder_resume_at else None,
            "events": [{"id": ev.id, "event_type": ev.event_type, "event_data": ev.event_data,
                        "triggered_by": ev.triggered_by,
                        "created_at": ev.created_at.isoformat() if ev.created_at else None} for ev in events],
        })
    return result


_PROVIDER_EVENT_WORDS = {"unsubscribed": "unsubscribe link", "complained": "spam complaint"}


def opt_out_source(captured_by: Optional[str]) -> str:
    """Where an email opt-out came from, in words (ConsentRecord.captured_by)."""
    if captured_by == "candidate_email_reply":
        return "the candidate's email reply"
    if captured_by and captured_by.startswith("provider_") and ":" in captured_by:
        event, provider = captured_by[len("provider_"):].split(":", 1)
        return f"{provider} {_PROVIDER_EVENT_WORDS.get(event, event)}"
    return captured_by or "not recorded"


def get_thunder_email_thread(candidate_id: str, db: Session) -> Dict[str, Any]:
    """Thunder's emails to the candidate, the candidate's emails (with how each was read) and any
    email opt-out, oldest first, plus which of them stopped Thunder."""
    from app.models.consent import ConsentRecord
    from app.models.thunder_email import ThunderCadenceState, ThunderEmailMessage

    state = db.query(ThunderCadenceState).filter_by(candidate_id=candidate_id).first()
    emails = db.query(ThunderEmailMessage).filter(
        ThunderEmailMessage.candidate_id == candidate_id,
        ((ThunderEmailMessage.direction == "OUT") & (ThunderEmailMessage.status == "SENT"))
        | (ThunderEmailMessage.direction == "IN"),
    ).all()
    opt_outs = db.query(ConsentRecord).filter(
        ConsentRecord.subject_type == "candidate", ConsentRecord.subject_id == candidate_id,
        ConsentRecord.consent_type == "email_outreach", ConsentRecord.consent_given.is_(False),
    ).all()

    items = []
    for row in emails:
        at = row.sent_at if row.direction == "OUT" else row.received_at
        items.append((at, {
            "id": row.id, "kind": "email", "at": at.isoformat() if at else None, "direction": row.direction,
            "subject": row.subject, "body": row.body_text, "step": row.step if row.direction == "OUT" else None,
            "intent": row.intent, "intent_confidence": row.intent_confidence, "intent_source": row.intent_source,
            "intent_evidence": row.intent_evidence,
        }))
    for record in opt_outs:
        items.append((record.captured_at, {
            "id": f"consent-{record.id}", "kind": "opt_out",
            "at": record.captured_at.isoformat() if record.captured_at else None,
            "source": opt_out_source(record.captured_by),
        }))
    items.sort(key=lambda pair: (pair[0] is None, pair[0] or datetime.min))

    stopped_by = None
    if state is not None and state.stage == "STOPPED":
        if (state.stop_reason or "").startswith("candidate "):
            stops = [i for _, i in items if i["kind"] == "email" and i["direction"] == "IN"
                     and i["intent"] in ("UNSUBSCRIBE", "HOSTILE")]
        else:
            stops = [i for _, i in items if i["kind"] == "opt_out"]
        stopped_by = stops[-1]["id"] if stops else None
    return {"stage": state.stage if state else None, "stop_reason": state.stop_reason if state else None,
            "stopped_by_item_id": stopped_by, "items": [i for _, i in items]}


# ===========================================================================
# 4. Reading the reply and extracting fields
# ===========================================================================

_QUOTE_PATTERNS = re.compile(
    r"(^On\s+.+wrote:\s*$|^-{3,}\s*Original Message\s*-{3,}|^From:\s.+Sent:|^>{1,}\s)",
    re.MULTILINE | re.IGNORECASE,
)


def _extract_candidate_reply(full_text: str) -> str:
    """Only the candidate's new text: drop the quoted thread below the first quote marker."""
    text = _html.unescape(full_text or "")
    match = _QUOTE_PATTERNS.search(text)
    candidate_part = text[: match.start()].strip() if match else text.strip()
    return candidate_part if len(candidate_part) > 20 else text.strip()


def read_candidate_replies(candidate_email: str, after: Optional[datetime], mailbox=None) -> List[Dict[str, Any]]:
    """The candidate's emails in the Thunder mailbox since `after` (oldest first), as
    {id, subject, body_text, received_at}."""
    from datetime import timedelta

    from app.services.thunder_mail.graph_mailbox import GraphMailbox

    mailbox = mailbox or GraphMailbox(settings.THUNDER_MAILBOX)
    sender = (candidate_email or "").strip().lower()
    messages = mailbox.list_inbox(after or datetime.utcnow() - timedelta(days=30))
    replies = []
    for msg in messages:
        address = ((msg.get("from") or {}).get("emailAddress") or {}).get("address", "").lower()
        if address != sender:
            continue
        replies.append({"id": msg.get("id"), "subject": msg.get("subject"),
                        "body_text": (msg.get("body") or {}).get("content") or msg.get("bodyPreview") or "",
                        "received_at": msg.get("receivedDateTime")})
    return replies


def _default_llm_call(prompt: str) -> str:
    import requests

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured -- candidate replies cannot be read")
    resp = requests.post(f"{GEMINI_MODEL_URL}?key={api_key}", timeout=30, json={
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
    })
    resp.raise_for_status()
    text = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    return re.sub(r"```(?:json)?", "", text).strip()


_BULLET = re.compile(r"^\s*(?:[*\-\u2022\u25cf\u25aa]+|\d{1,2}[.)])?\s*")  # "* ", "- ", "1." -- not "60 days"
_ANSWER_SEPARATOR = re.compile(r"^[\s:\-\u2013\u2014=>|]*")
_MONEY = re.compile(r"\d[\d,]*(?:\.\d+)?\s*[kK]?")
SALARY_RATE_WORDS = (
    ("$/Hour", r"hour|/\s*hr\b|hourly"), ("$/Day", r"\bday\b|daily"), ("$/Week", r"week"),
    ("$/Month", r"month"), ("$/Year", r"year|annum|annual|\byr\b|\bpa\b|lpa|ctc"),
)
MARITAL_WORDS = (("Single", r"single|unmarried"), ("Married", r"married"), ("Divorced", r"divorced"),
                 ("Widowed", r"widow"))
GENDER_WORDS = (("Female", r"\b(female|woman|f)\b"), ("Male", r"\b(male|man|m)\b"),
                ("Other", r"\b(other|non.?binary)\b"))
EMPTY_ANSWERS = ("na", "n/a", "-", "none", "nil")


def _label_head(label: str) -> str:
    """The words a reply repeats: "Notice Period (in days)" -> "notice period"."""
    return " ".join(label.split("(")[0].lower().split())


def _flat_line(line: str) -> str:
    return " ".join(_BULLET.sub("", line).split())


def _normalised_answer(field: str, answer: str) -> Dict[str, Any]:
    """{field: value[, rate field: rate]} in the shape merge_fields_to_db stores, or {}."""
    answer = answer.strip().rstrip(".").strip()
    if not answer or answer.lower() in EMPTY_ANSWERS:
        return {}
    if field in DATE_FIELDS:
        found = re.search(r"\d{4}-\d{2}-\d{2}", answer)
        return {field: found.group(0)} if found else {}
    if field == "candidateExperience":
        found = re.search(r"\d+(?:\.\d+)?", answer)
        return {field: found.group(0)} if found else {}
    if field in SALARY_TYPE_FIELDS:
        amount = _MONEY.search(answer)
        if amount is None:
            return {field: answer}  # e.g. "Industry standard": what they said, nothing invented
        written = amount.group(0).strip()
        number = float(written.rstrip("kK").replace(",", "").strip())
        if written.lower().endswith("k"):
            number *= 1000
        result = {field: str(int(number)) if number.is_integer() else str(number)}
        # the rate word nearest after the amount ("232,000 per year + ... 176 hours PTO" is per year)
        after = answer[amount.end():]
        hits = [(m.start(), r) for r, words in SALARY_RATE_WORDS
                for m in [re.search(words, after, re.IGNORECASE)] if m]
        rate = min(hits)[1] if hits else None
        if rate:
            result[SALARY_TYPE_FIELDS[field]] = rate
        return result
    if field == "marital_status":
        found = next((v for v, words in MARITAL_WORDS if re.search(words, answer, re.IGNORECASE)), None)
        return {field: found} if found else {}
    if field == "candidateGender":
        found = next((v for v, words in GENDER_WORDS if re.search(words, answer, re.IGNORECASE)), None)
        return {field: found} if found else {}
    if field == "candidateSkills":
        return {}  # a free-form list: left to the AI reader
    return {field: answer}


def parse_labelled_answers(reply_text: str, missing_fields: List[Dict[str, str]]) -> Dict[str, Any]:
    """Answers given against our own labels, read without any AI. Our emails list each missing
    detail by label ("Notice Period (in days)"); a reply that keeps the label and adds the answer
    after it ("Notice Period (in days) - 2/3 weeks"), or on the next line, is read here. Only the
    candidate's part of the email is read (the quoted thread below it repeats the empty labels)."""
    lines = [_flat_line(line) for line in _extract_candidate_reply(reply_text).splitlines()]
    heads = {m["field"]: _label_head(m["label"]) for m in missing_fields if m.get("source") != "document"}
    all_heads = tuple(heads.values())
    found: Dict[str, Any] = {}
    for field, head in heads.items():
        for index, line in enumerate(lines):
            if not head or not line.lower().startswith(head):
                continue
            rest = line[len(head):].lstrip()
            if rest.startswith("(") and ")" in rest:  # the label's own hint, e.g. "(YYYY-MM-DD)"
                rest = rest[rest.index(")") + 1:]
            answer = _ANSWER_SEPARATOR.sub("", rest)
            if not answer and index + 1 < len(lines) and not lines[index + 1].lower().startswith(all_heads):
                answer = lines[index + 1]
            found.update(_normalised_answer(field, answer))
            break
    return found


def _llm_configured() -> bool:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return bool(key) and not key.lower().startswith(("your_", "changeme"))


def extract_fields_from_reply(reply_text: str, missing_fields: List[Dict[str, str]],
                              llm_call: Optional[Callable[[str], str]] = None) -> Dict[str, Any]:
    """field -> value for every missing field the reply answers.

    Rules first (CEO 2026-11-02: "we shouldnt depend on gemini to get the answer and save it on
    candidate record"): answers written against our labels are read by parse_labelled_answers.
    The AI reader only tries the fields the rules did not find, and only when one is configured
    (or passed in). An AI failure is raised only when the rules found nothing either -- the caller
    records the error; otherwise what the rules read is kept and the failure is logged."""
    found = parse_labelled_answers(reply_text, missing_fields)
    remaining = [m for m in missing_fields if m["field"] not in found and m.get("source") != "document"]
    if not remaining:
        return found
    if llm_call is None and not _llm_configured():
        logger.warning(f"[ReplyPipeline] No AI key configured: {len(remaining)} field(s) not read by rules "
                       f"({', '.join(m['field'] for m in remaining)}) stay missing and are asked again")
        return found
    try:
        found.update(_extract_fields_with_llm(reply_text, remaining, llm_call))
    except Exception as exc:
        if not found:
            raise
        logger.error(f"[ReplyPipeline] AI reader failed; keeping {len(found)} field(s) read by rules: {exc}",
                     exc_info=True)
    return found


def _extract_fields_with_llm(reply_text: str, missing_fields: List[Dict[str, str]],
                             llm_call: Optional[Callable[[str], str]] = None) -> Dict[str, Any]:
    """The AI reader. The reply is untrusted: it is fenced as data (build_safe_prompt), never
    concatenated as instructions. Raises on an LLM failure or an unparseable answer."""
    clean_text = _extract_candidate_reply(reply_text)
    suspicious = flag_suspicious_patterns(clean_text)
    if suspicious:
        logger.warning(f"[ReplyPipeline] Candidate reply contains injection-shaped phrasing: {suspicious}")
    field_lines = "\n".join(f'  - field_name: "{m["field"]}"  |  label: "{m["label"]}"' for m in missing_fields)
    instruction = f"""You are a data extraction assistant for an HR onboarding system.
A candidate replied to an HR email with their missing profile information.

Extract these fields (by field_name, label, or an obvious paraphrase):
{field_lines}

Rules:
- Return ONLY a JSON object, no explanation or code fences. Keys are the field_name values above.
- Include only fields you can confidently identify; omit the rest.
- Marital Status: Single, Married, Divorced or Widowed ("unmarried" -> "Single").
- Gender: Male, Female or Other. Dates: YYYY-MM-DD.
- permanent_address: only "City, State, Country" -- never street, house or pincode details.
- candidateExperience: total years as a number, e.g. "6".
- candidateSkills: a JSON list of {{"name": "...", "years": number or null}}, most important first.
- employment_type: "FULLTIME" for full-time / permanent / W2, "CONTRACT" for contract; omit anything else.
- candidate_notice_period: whole days ("2 months" -> 60, "immediately" -> 0).
- candidateCurrentSalary / candidateExpectedSalary: the amount only, e.g. "120000". When the reply
  gives the rate, also return candidateCurrentSalaryType / candidateExpectedSalaryType as one of
  {", ".join(SALARY_RATE_TYPES)}.
JSON output:"""
    prompt = build_safe_prompt(instruction=instruction, untrusted_label="CANDIDATE_REPLY", untrusted_content=clean_text)
    raw = (llm_call or _default_llm_call)(prompt)
    raw = re.sub(r"```(?:json)?", "", raw or "").strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"The reply parser did not return JSON: {raw[:200]!r}") from exc
    if not isinstance(result, dict):
        raise ValueError(f"The reply parser returned {type(result).__name__}, not an object")
    allowed = {m["field"] for m in missing_fields}
    allowed |= {SALARY_TYPE_FIELDS[f] for f in allowed if f in SALARY_TYPE_FIELDS}
    return {k: v for k, v in result.items() if k in allowed}


# ===========================================================================
# 5. Processing a reply
# ===========================================================================

def _is_duplicate_email_reply(db: Session, conversation_id: int, message_id: str) -> bool:
    events = (db.query(ConversationEvent)
              .filter(ConversationEvent.conversation_id == conversation_id,
                      ConversationEvent.event_type == "candidate_reply").all())
    return any((event.event_data or {}).get("message_id") == message_id for event in events)


def _record_inbound_signals(db: Session, candidate: Candidate, conversation: CandidateConversation,
                            reply_text: str, reply_event: ConversationEvent) -> None:
    """Everything an inbound message means elsewhere: channel preference, cancel pending
    follow-ups and campaigns, reactivate a ghosted candidate, facts and desire signals."""
    from app.services.channel_preference_service import detect_channel_preference
    from app.services.desire_signal_service import (
        minutes_since_last_outbound, record_message_signal, record_response_speed_signal,
    )
    from app.services.facts_extraction_service import extract_facts
    from app.services.follow_up_scheduler_service import cancel_pending_follow_ups
    from app.services.ghosting_detection_service import reactivate_candidate
    from app.services.outreach_campaign_service import cancel_campaign_on_reply

    tenant = conversation.tenant_id
    detect_channel_preference(db, conversation)
    cancel_pending_follow_ups(db, candidate.candidateID, tenant)
    reactivate_candidate(db, candidate.candidateID, tenant, conversation.id)
    cancel_campaign_on_reply(db, candidate.candidateID, tenant)
    extract_facts(db, candidate, tenant, conversation.id, reply_text, source_message_id=reply_event.id)
    record_message_signal(db, tenant, candidate.candidateID, "EMAIL_MESSAGE", reply_text)
    gap = minutes_since_last_outbound(db, conversation.id, before=reply_event.created_at)
    if gap is not None:
        record_response_speed_signal(db, tenant, candidate.candidateID, gap)


def process_candidate_reply(candidate_id: str, db: Session, raw_reply_text: Optional[str] = None,
                            message_id: Optional[str] = None, mailbox=None,
                            llm_call: Optional[Callable[[str], str]] = None) -> Dict[str, Any]:
    """Process the candidate's reply on their active conversation. With no raw_reply_text the
    Thunder mailbox is read for their newest email since our last message. Extract -> merge ->
    recheck -> follow up on anything still missing. Commits; returns a summary with a status of
    no_reply_found | duplicate_message | all_fields_complete | completed | partial."""
    from app.services.conversation_state_service import transition_status

    conversation = (db.query(CandidateConversation)
                    .filter(CandidateConversation.candidate_id == candidate_id,
                            CandidateConversation.status.in_(["open", "awaiting_candidate"]))
                    .order_by(CandidateConversation.created_at.desc()).first())
    if conversation is None:
        raise HTTPException(status_code=404, detail=f"No active conversation found for candidate '{candidate_id}'.")
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")

    if raw_reply_text is None:
        last_sent = (db.query(ConversationEvent)
                     .filter(ConversationEvent.conversation_id == conversation.id,
                             ConversationEvent.event_type == "ai_message_sent")
                     .order_by(ConversationEvent.created_at.desc()).first())
        replies = read_candidate_replies(candidate.candidateEmail, last_sent.created_at if last_sent else None, mailbox)
        if not replies:
            return {"conversation_id": conversation.id, "status": "no_reply_found",
                    "message": "No new replies found in the Thunder mailbox."}
        newest = replies[-1]
        raw_reply_text, message_id = newest["body_text"], newest["id"]

    if message_id and _is_duplicate_email_reply(db, conversation.id, message_id):
        return {"conversation_id": conversation.id, "status": "duplicate_message",
                "message": f"Email message_id {message_id} was already processed."}
    if not raw_reply_text or not raw_reply_text.strip():
        raw_reply_text = "[Non-text email received]"  # never store an empty body for a real message

    reply_event = _log_event(db, conversation.id, "candidate_reply",
                             {"message_id": message_id, "reply_preview": raw_reply_text[:300], "channel": "email"},
                             triggered_by="candidate")
    _record_inbound_signals(db, candidate, conversation, raw_reply_text, reply_event)

    missing = get_missing_fields(candidate, db)
    if not missing:
        transition_status(db, conversation, "closed", reason="All fields complete on inbound reply",
                          triggered_by="candidate")
        conversation.summary, conversation.next_action = "All fields complete. Conversation closed.", "none"
        db.commit()
        return {"conversation_id": conversation.id, "status": "all_fields_complete", "updated_fields": []}

    _log_event(db, conversation.id, "pipeline_start", {"missing_fields": [m["field"] for m in missing]})
    try:
        extracted = extract_fields_from_reply(raw_reply_text, missing, llm_call=llm_call)
    except Exception as exc:
        logger.error(f"[ReplyPipeline] Could not read the reply for {candidate_id}: {exc}", exc_info=True)
        _log_event(db, conversation.id, "pipeline_error", {"error": str(exc)})
        conversation.next_action = "review_reply_manually"
        db.commit()
        raise HTTPException(status_code=502, detail=f"The candidate's reply could not be read: {exc}")

    merge = merge_fields_to_db(candidate_id, extracted, db)
    db.refresh(candidate)
    still_missing = get_missing_fields(candidate, db)
    _log_event(db, conversation.id, "fields_merged", {
        "updated_fields": merge["updated"], "skipped_fields": merge["skipped"],
        "still_missing": [m["field"] for m in still_missing],
    })
    if not still_missing:
        transition_status(db, conversation, "closed", reason="All fields complete after candidate reply",
                          triggered_by="candidate")
        conversation.summary = "All fields complete after candidate reply. Conversation closed."
        conversation.next_action = "none"
        db.commit()
        return {"conversation_id": conversation.id, "status": "completed", "updated_fields": merge["updated"],
                "skipped_fields": merge["skipped"], "still_missing": [], "followup_email_sent": False}

    followup = _send_fields_email(db, candidate, conversation, still_missing, followup=True)
    transition_status(db, conversation, "awaiting_candidate",
                      reason="Follow-up sent, fields still missing" if followup["sent"]
                      else "Follow-up not sent", triggered_by="ai_agent" if followup["sent"] else "system")
    conversation.summary = (f"{len(still_missing)} field(s) still missing: " + ", ".join(m["field"] for m in still_missing)
                            + ("" if followup["sent"] else f" -- follow-up not sent: {followup['reason']}"))
    conversation.next_action = "wait_for_reply" if followup["sent"] else "retry_followup"
    db.commit()
    return {"conversation_id": conversation.id, "status": "partial", "updated_fields": merge["updated"],
            "skipped_fields": merge["skipped"], "still_missing": [m["field"] for m in still_missing],
            "followup_email_sent": followup["sent"],
            **({} if followup["sent"] else {"message": f"Follow-up not sent: {followup['reason']}"})}


def poll_all_awaiting_candidates(db: Session) -> Dict[str, Any]:
    """process_candidate_reply for every conversation awaiting the candidate; one candidate's
    failure is recorded and never stops the batch."""
    awaiting = db.query(CandidateConversation).filter(CandidateConversation.status == "awaiting_candidate").all()
    processed = updated = 0
    errors: List[str] = []
    for conversation in awaiting:
        try:
            result = process_candidate_reply(candidate_id=conversation.candidate_id, db=db)
            processed += 1
            if result.get("updated_fields"):
                updated += 1
        except Exception as exc:
            db.rollback()
            logger.error(f"[AutoPoll] {conversation.candidate_id}: {exc}", exc_info=True)
            errors.append(f"{conversation.candidate_id}: {exc}")
    return {"checked": len(awaiting), "processed": processed, "updated": updated, "errors": errors}
