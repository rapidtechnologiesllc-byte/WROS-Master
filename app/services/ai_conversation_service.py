"""
AI Conversation Agent Service
==============================
Core brain for the email-based AI hiring agent.

Responsibilities:
  1. Detect missing fields in the candidate record (core table + info form only,
     NOT Aadhar/PAN — those are handled as document uploads).
  2. Build and send a branded missing-fields email to the candidate.
  3. Poll the service mailbox (helpdesk_hrms@blitzenx.com) via Microsoft Graph
     to read candidate replies.
  4. Use Gemini to parse the reply and extract field values.
  5. Merge extracted values back into the candidates / candidate_forms tables.
  6. Log every action as a ConversationEvent.
"""

import json
import os
import re
import requests
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.graph_auth import get_graph_token
from app.core.logging import logger
from app.models.candidate import (
    Candidate,
    CandidateInfoForm,
    CandidateExperienceForm,
    CandidateEducationForm,
)
from app.models.candidate_ai import (
    CandidateAIAssignment,
    CandidateConversation,
    ConversationEvent,
)
from app.services.email_service import EmailService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AI_AGENT_NAME = "onboarding-ai"
AI_AGENT_PERSONA = "friendly-hr"
SERVICE_MAILBOX = "helpdesk_hrms@blitzenx.com"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Ordered list of (candidate_field, friendly_label) tuples.
# Only core `candidates` table fields — Aadhar / PAN are handled as documents.
CANDIDATE_CORE_FIELDS: List[Tuple[str, str]] = [
    ("candidateFirstName",       "First Name"),
    ("candidateLastName",        "Last Name"),
    ("candidateMobile",          "Mobile Number"),
    ("candidateGender",          "Gender"),
    ("candidateDateOfBirth",     "Date of Birth (YYYY-MM-DD)"),
    ("candidateCurrentLocation", "Current Location"),
    ("candidateJoiningDate",     "Expected Joining Date (YYYY-MM-DD)"),
    ("candidateExperience",      "Years of Experience"),
    ("candidateJobTitle",        "Job Title / Role Applied For"),
    ("candidateEmployeeType",    "Employment Type (Intern / Full Time / Contract)"),
]

# Fields from the CandidateInfoForm (personal details form)
INFO_FORM_FIELDS: List[Tuple[str, str]] = [
    ("marital_status",   "Marital Status"),
    ("nationality",      "Nationality"),
    ("permanent_address","Permanent Address"),
]


# ===========================================================================
# 1. Missing-field detection
# ===========================================================================

def get_missing_fields(candidate: Candidate, db: Session) -> List[Dict[str, str]]:
    """
    Return a list of {field, label, source} dicts for every empty field.
    source = 'candidate' | 'info_form'
    """
    missing: List[Dict[str, str]] = []

    # ── Core candidate table ──────────────────────────────────────────────
    for field, label in CANDIDATE_CORE_FIELDS:
        value = getattr(candidate, field, None)
        if not value:
            missing.append({"field": field, "label": label, "source": "candidate"})

    # ── CandidateInfoForm ─────────────────────────────────────────────────
    info = (
        db.query(CandidateInfoForm)
        .filter(CandidateInfoForm.candidateID == candidate.candidateID)
        .first()
    )
    for field, label in INFO_FORM_FIELDS:
        value = getattr(info, field, None) if info else None
        if not value:
            missing.append({"field": field, "label": label, "source": "info_form"})

    return missing


# ===========================================================================
# 2. Email templates
# ===========================================================================

def _build_missing_fields_email(
    candidate_name: str,
    missing: List[Dict[str, str]],
    conversation_id: int,
) -> str:
    """
    Build a branded HTML email body listing the missing fields.
    The candidate must reply to this email with the requested details.
    """
    rows = "".join(
        f"""
        <tr>
          <td style="padding:8px 16px;border-bottom:1px solid #e5e7eb;
                     font-size:14px;color:#374151;">
            {i + 1}. {item['label']}
          </td>
        </tr>"""
        for i, item in enumerate(missing)
    )

    body = f"""
    <p style="font-size:16px;color:#111827;margin:0 0 16px;">
      Dear <strong>{candidate_name}</strong>,
    </p>
    <p style="font-size:14px;color:#374151;line-height:1.7;">
      Thank you for joining us! To complete your candidate profile and move forward
      with the hiring process, we need a few more details from you.
    </p>
    <p style="font-size:14px;color:#374151;margin:16px 0 8px;">
      <strong>Please reply to this email with the following information:</strong>
    </p>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border:1px solid #e5e7eb;border-radius:6px;overflow:hidden;margin-bottom:20px;">
      {rows}
    </table>
    <p style="font-size:13px;color:#6b7280;line-height:1.6;">
      Simply hit <strong>Reply</strong> to this email and provide the details above.
      Our AI assistant will automatically update your profile — no login required.
    </p>
    <p style="font-size:13px;color:#9ca3af;margin-top:8px;">
      Reference ID: <code>CONV-{conversation_id}</code>
    </p>
    <p style="font-size:14px;color:#374151;margin-top:24px;">
      Warm regards,<br/><strong>BlitzenX HR Team</strong>
    </p>
    """
    return EmailService._base_html("Profile Completion Request", body)


def _build_followup_email(
    candidate_name: str,
    still_missing: List[Dict[str, str]],
    conversation_id: int,
) -> str:
    """Gentle follow-up email for fields that are still empty after a partial reply."""
    rows = "".join(
        f"""
        <tr>
          <td style="padding:8px 16px;border-bottom:1px solid #fde68a;
                     font-size:14px;color:#374151;">
            {i + 1}. {item['label']}
          </td>
        </tr>"""
        for i, item in enumerate(still_missing)
    )

    body = f"""
    <p style="font-size:16px;color:#111827;margin:0 0 16px;">
      Dear <strong>{candidate_name}</strong>,
    </p>
    <p style="font-size:14px;color:#374151;line-height:1.7;">
      Thank you for your response! We still need a few more details to complete
      your profile. Could you please provide the following?
    </p>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border:1px solid #fde68a;border-radius:6px;overflow:hidden;
                  background:#fffbeb;margin-bottom:20px;">
      {rows}
    </table>
    <p style="font-size:13px;color:#6b7280;">
      Reference ID: <code>CONV-{conversation_id}</code>
    </p>
    <p style="font-size:14px;color:#374151;margin-top:24px;">
      Warm regards,<br/><strong>BlitzenX HR Team</strong>
    </p>
    """
    return EmailService._base_html("Follow-up: Profile Completion", body)


# ===========================================================================
# 3. Conversation & event helpers
# ===========================================================================

def _log_event(
    db: Session,
    conversation_id: int,
    event_type: str,
    event_data: Optional[Dict],
    triggered_by: str = "ai_agent",
) -> ConversationEvent:
    """Append an immutable event row to conversation_events."""
    event = ConversationEvent(
        conversation_id=conversation_id,
        event_type=event_type,
        event_data=event_data,
        triggered_by=triggered_by,
    )
    db.add(event)
    db.flush()  # get event.id without committing yet
    return event


def _candidate_display_name(candidate: Candidate) -> str:
    parts = [
        candidate.candidateFirstName,
        candidate.candidateMiddleName,
        candidate.candidateLastName,
    ]
    name = " ".join(p for p in parts if p).strip()
    return name or candidate.candidateEmail


# ===========================================================================
# 4. Core agent actions
# ===========================================================================

def assign_ai_agent(
    candidate_id: str,
    tenant_id: str,
    assigned_by: str,
    db: Session,
) -> Dict[str, Any]:
    """
    Assign the AI agent to a candidate:
      1. Deactivate any existing active assignment.
      2. Create a new CandidateAIAssignment row.
      3. Open a new CandidateConversation.
      4. Detect missing fields → send email → log events.

    Returns a summary dict.
    """
    candidate = db.query(Candidate).filter(
        Candidate.candidateID == candidate_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")

    # Deactivate previous assignments
    db.query(CandidateAIAssignment).filter(
        CandidateAIAssignment.candidate_id == candidate_id,
        CandidateAIAssignment.is_active == True,
    ).update({"is_active": False})

    # Create new assignment
    assignment = CandidateAIAssignment(
        tenant_id=tenant_id,
        candidate_id=candidate_id,
        ai_agent_name=AI_AGENT_NAME,
        ai_agent_persona=AI_AGENT_PERSONA,
        assigned_by=assigned_by,
        is_active=True,
    )
    db.add(assignment)
    db.flush()

    # Open conversation
    conversation = CandidateConversation(
        tenant_id=tenant_id,
        candidate_id=candidate_id,
        status="open",
        ai_agent_name=AI_AGENT_NAME,
        channel_preference="email",
        owner_type="ai_agent",
        owner_id=AI_AGENT_NAME,
        escalation_state="none",
        summary="AI agent assigned. Checking for missing profile fields.",
        next_action="send_missing_fields_email",
    )
    db.add(conversation)
    db.flush()

    # Log ai_assigned event
    _log_event(
        db, conversation.id, "ai_assigned",
        {
            "ai_agent_name": AI_AGENT_NAME,
            "assigned_by": assigned_by,
            "assignment_id": assignment.id,
        },
        triggered_by="hr_user",
    )

    # Detect missing fields
    missing = get_missing_fields(candidate, db)

    _log_event(
        db, conversation.id, "field_check",
        {
            "total_missing": len(missing),
            "missing_fields": [m["field"] for m in missing],
        },
    )

    email_sent = False
    if missing:
        email_sent = _send_missing_fields_email(
            candidate, missing, conversation, db
        )
        conversation.status = "awaiting_candidate"
        conversation.next_action = "wait_for_reply"
        conversation.summary = (
            f"Sent initial missing-fields email. "
            f"{len(missing)} field(s) pending: "
            + ", ".join(m['label'] for m in missing)
        )
    else:
        conversation.status = "closed"
        conversation.next_action = "none"
        conversation.summary = "All required fields are present. No email needed."

    db.commit()

    return {
        "assignment_id": assignment.id,
        "conversation_id": conversation.id,
        "candidate_id": candidate_id,
        "missing_fields_count": len(missing),
        "missing_fields": missing,
        "email_sent": email_sent,
        "conversation_status": conversation.status,
    }


def _send_missing_fields_email(
    candidate: Candidate,
    missing: List[Dict[str, str]],
    conversation: CandidateConversation,
    db: Session,
) -> bool:
    """Build and dispatch the missing-fields email; log the event."""
    name = _candidate_display_name(candidate)
    subject = f"Action Required: Complete Your Candidate Profile — CONV-{conversation.id}"
    html = _build_missing_fields_email(name, missing, conversation.id)

    try:
        EmailService.send_email(
            to_email=candidate.candidateEmail,
            subject=subject,
            body_content=html,
            is_html=True,
        )
        _log_event(
            db, conversation.id, "ai_message_sent",
            {
                "channel": "email",
                "subject": subject,
                "to": candidate.candidateEmail,
                "missing_fields": [m["field"] for m in missing],
                "message_type": "missing_fields_request",
            },
        )
        logger.info(
            f"[AIAgent] Missing-fields email sent to {candidate.candidateEmail} "
            f"| CONV-{conversation.id} | {len(missing)} fields"
        )
        return True
    except Exception as exc:
        logger.error(f"[AIAgent] Email send failed: {exc}")
        _log_event(
            db, conversation.id, "email_send_failed",
            {"error": str(exc), "to": candidate.candidateEmail},
        )
        return False


# ===========================================================================
# 5. Read inbox replies via Graph API
# ===========================================================================

def read_candidate_replies(
    candidate_email: str,
    after_datetime: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Poll the service mailbox Inbox for messages FROM candidate_email.
    Returns a list of message dicts: {id, subject, body_text, received_at}.
    """
    try:
        token = get_graph_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        filter_parts = [f"from/emailAddress/address eq '{candidate_email}'"]
        if after_datetime:
            iso_str = after_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
            filter_parts.append(f"receivedDateTime gt {iso_str}")

        filter_str = " and ".join(filter_parts)
        url = (
            f"https://graph.microsoft.com/v1.0/users/{SERVICE_MAILBOX}"
            f"/mailFolders/Inbox/messages"
            f"?$filter={filter_str}"
            f"&$orderby=receivedDateTime desc"
            f"&$top=5"
            f"&$select=id,subject,body,receivedDateTime,from"
        )

        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        messages = []
        for msg in data.get("value", []):
            body_content = msg.get("body", {}).get("content", "")
            # Strip HTML tags for plain text extraction
            plain = re.sub(r"<[^>]+>", " ", body_content)
            plain = re.sub(r"\s+", " ", plain).strip()
            messages.append({
                "id": msg["id"],
                "subject": msg.get("subject", ""),
                "body_text": plain,
                "received_at": msg.get("receivedDateTime"),
            })

        return messages

    except Exception as exc:
        logger.error(f"[AIAgent] Graph inbox read failed: {exc}")
        return []


# ===========================================================================
# 6. Gemini-powered reply parser
# ===========================================================================

def parse_reply_with_gemini(
    reply_text: str,
    missing_fields: List[Dict[str, str]],
) -> Dict[str, str]:
    """
    Call Gemini API to extract field values from a candidate's reply email.

    Returns {field_name: extracted_value} for every field Gemini could identify.
    Fields not found in the reply are omitted from the dict.
    """
    if not GEMINI_API_KEY:
        logger.error("[AIAgent] GEMINI_API_KEY not set.")
        return {}

    field_list = "\n".join(
        f"- {item['field']} ({item['label']})"
        for item in missing_fields
    )

    prompt = f"""You are a data extraction assistant for an HR system.
A candidate has replied to an email requesting their missing profile details.

Extract the following fields from their reply:
{field_list}

Candidate's reply:
\"\"\"
{reply_text}
\"\"\"

Rules:
- Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
- Keys must exactly match the field names listed above.
- Include only fields that are clearly present in the reply.
- For dates, use YYYY-MM-DD format.
- For gender, use one of: Male, Female, Other.
- If a field is not mentioned, do not include it in the JSON.
- Example output: {{"candidateFirstName": "Priya", "candidateGender": "Female"}}

JSON output:"""

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 512,
        },
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        text = (
            result.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )

        # Clean up any accidental markdown code fences
        text = re.sub(r"```(?:json)?", "", text).strip()

        extracted = json.loads(text)
        logger.info(f"[AIAgent] Gemini extracted: {extracted}")
        return extracted

    except json.JSONDecodeError as e:
        logger.error(f"[AIAgent] Gemini returned invalid JSON: {e} | Raw: {text!r}")
        return {}
    except Exception as exc:
        logger.error(f"[AIAgent] Gemini call failed: {exc}")
        return {}


# ===========================================================================
# 7. Merge extracted fields into DB
# ===========================================================================

def merge_extracted_fields(
    candidate_id: str,
    extracted: Dict[str, str],
    db: Session,
) -> Dict[str, List[str]]:
    """
    Apply the extracted values to the appropriate DB models.
    Returns {"updated": [...field names...], "skipped": [...field names...]}.
    """
    candidate = db.query(Candidate).filter(
        Candidate.candidateID == candidate_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    core_fields = {f for f, _ in CANDIDATE_CORE_FIELDS}
    info_fields = {f for f, _ in INFO_FORM_FIELDS}

    updated: List[str] = []
    skipped: List[str] = []

    for field, raw_value in extracted.items():
        if not raw_value:
            skipped.append(field)
            continue

        # ── Core candidate table ─────────────────────────────────────────
        if field in core_fields:
            try:
                # Date fields
                if field in ("candidateDateOfBirth", "candidateJoiningDate"):
                    from datetime import date
                    value = date.fromisoformat(str(raw_value))
                else:
                    value = str(raw_value).strip()
                setattr(candidate, field, value)
                updated.append(field)
            except Exception as exc:
                logger.warning(f"[AIAgent] Could not set {field}={raw_value!r}: {exc}")
                skipped.append(field)

        # ── CandidateInfoForm ────────────────────────────────────────────
        elif field in info_fields:
            info = db.query(CandidateInfoForm).filter(
                CandidateInfoForm.candidateID == candidate_id
            ).first()
            if not info:
                info = CandidateInfoForm(candidateID=candidate_id)
                db.add(info)
            try:
                setattr(info, field, str(raw_value).strip())
                updated.append(field)
            except Exception as exc:
                logger.warning(f"[AIAgent] InfoForm set {field}={raw_value!r}: {exc}")
                skipped.append(field)

        else:
            skipped.append(field)

    db.flush()
    return {"updated": updated, "skipped": skipped}


# ===========================================================================
# 8. Process a candidate reply (full pipeline)
# ===========================================================================

def process_candidate_reply(
    candidate_id: str,
    db: Session,
    raw_reply_text: Optional[str] = None,   # supplied directly (webhook mode)
    message_id: Optional[str] = None,        # Graph message ID (webhook mode)
) -> Dict[str, Any]:
    """
    End-to-end reply processing pipeline:
      1. Load active conversation.
      2. If raw_reply_text is None → poll Graph inbox for new messages.
      3. Parse reply with Gemini.
      4. Merge extracted fields into DB.
      5. Log events.
      6. Check if still missing → send follow-up OR close conversation.

    Returns a processing summary dict.
    """
    # Load active conversation
    conversation = (
        db.query(CandidateConversation)
        .filter(
            CandidateConversation.candidate_id == candidate_id,
            CandidateConversation.status.in_(["open", "awaiting_candidate"]),
        )
        .order_by(CandidateConversation.created_at.desc())
        .first()
    )
    if not conversation:
        raise HTTPException(
            status_code=404,
            detail=f"No active conversation found for candidate '{candidate_id}'.",
        )

    candidate = db.query(Candidate).filter(
        Candidate.candidateID == candidate_id
    ).first()

    # ── Step 1: Obtain reply text ─────────────────────────────────────────
    if raw_reply_text is None:
        # Poll the inbox for replies received after the last AI message
        last_sent_event = (
            db.query(ConversationEvent)
            .filter(
                ConversationEvent.conversation_id == conversation.id,
                ConversationEvent.event_type == "ai_message_sent",
            )
            .order_by(ConversationEvent.created_at.desc())
            .first()
        )
        after_dt = last_sent_event.created_at if last_sent_event else None
        messages = read_candidate_replies(candidate.candidateEmail, after_dt)
        if not messages:
            return {
                "conversation_id": conversation.id,
                "status": "no_reply_found",
                "message": "No new replies found in the service mailbox.",
            }
        # Use the most recent reply
        reply_msg = messages[0]
        raw_reply_text = reply_msg["body_text"]
        message_id = reply_msg["id"]

    # ── Step 2: Log candidate_reply event ────────────────────────────────
    _log_event(
        db, conversation.id, "candidate_reply",
        {
            "message_id": message_id,
            "reply_preview": raw_reply_text[:300],
        },
        triggered_by="candidate",
    )

    # ── Step 3: Determine what's still missing ────────────────────────────
    missing = get_missing_fields(candidate, db)
    if not missing:
        # All fields already filled — nothing to parse
        conversation.status = "closed"
        conversation.summary = "All fields complete. Conversation closed."
        conversation.next_action = "none"
        db.commit()
        return {
            "conversation_id": conversation.id,
            "status": "all_fields_complete",
            "updated_fields": [],
        }

    # ── Step 4: Parse reply with Gemini ──────────────────────────────────
    extracted = parse_reply_with_gemini(raw_reply_text, missing)

    _log_event(
        db, conversation.id, "gemini_parse",
        {
            "fields_attempted": [m["field"] for m in missing],
            "fields_extracted": list(extracted.keys()),
            "extracted_values": extracted,
        },
    )

    # ── Step 5: Merge into DB ─────────────────────────────────────────────
    merge_result = merge_extracted_fields(candidate_id, extracted, db)

    _log_event(
        db, conversation.id, "fields_merged",
        merge_result,
    )

    # ── Step 6: Re-check what's still missing ────────────────────────────
    still_missing = get_missing_fields(candidate, db)

    if not still_missing:
        conversation.status = "closed"
        conversation.summary = "All fields complete after candidate reply. Conversation closed."
        conversation.next_action = "none"
        _log_event(
            db, conversation.id, "status_changed",
            {"old_status": "awaiting_candidate", "new_status": "closed"},
        )
        db.commit()
        return {
            "conversation_id": conversation.id,
            "status": "completed",
            "updated_fields": merge_result["updated"],
            "skipped_fields": merge_result["skipped"],
        }

    # ── Step 7: Still missing → send follow-up ───────────────────────────
    name = _candidate_display_name(candidate)
    subject = (
        f"Follow-up: Additional Information Needed — CONV-{conversation.id}"
    )
    html = _build_followup_email(name, still_missing, conversation.id)
    try:
        EmailService.send_email(
            to_email=candidate.candidateEmail,
            subject=subject,
            body_content=html,
            is_html=True,
        )
        _log_event(
            db, conversation.id, "ai_message_sent",
            {
                "channel": "email",
                "subject": subject,
                "to": candidate.candidateEmail,
                "missing_fields": [m["field"] for m in still_missing],
                "message_type": "followup_request",
            },
        )
        conversation.status = "awaiting_candidate"
        conversation.summary = (
            f"Follow-up sent. {len(still_missing)} field(s) still missing: "
            + ", ".join(m["label"] for m in still_missing)
        )
        conversation.next_action = "wait_for_reply"
    except Exception as exc:
        logger.error(f"[AIAgent] Follow-up email failed: {exc}")

    db.commit()

    return {
        "conversation_id": conversation.id,
        "status": "partial",
        "updated_fields": merge_result["updated"],
        "skipped_fields": merge_result["skipped"],
        "still_missing": [m["field"] for m in still_missing],
        "followup_email_sent": True,
    }


# ===========================================================================
# 9. Get full conversation thread (for UI display)
# ===========================================================================

def get_conversation_thread(
    candidate_id: str,
    db: Session,
) -> List[Dict[str, Any]]:
    """
    Return all conversations for a candidate, each with their full event log,
    ordered newest-first.

    Used by the UI to render the agent ↔ candidate dialogue timeline.
    """
    conversations = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate_id)
        .order_by(CandidateConversation.created_at.desc())
        .all()
    )

    result = []
    for conv in conversations:
        events = (
            db.query(ConversationEvent)
            .filter(ConversationEvent.conversation_id == conv.id)
            .order_by(ConversationEvent.created_at.asc())
            .all()
        )

        result.append({
            "conversation_id": conv.id,
            "status": conv.status,
            "ai_agent_name": conv.ai_agent_name,
            "channel_preference": conv.channel_preference,
            "summary": conv.summary,
            "next_action": conv.next_action,
            "owner_type": conv.owner_type,
            "escalation_state": conv.escalation_state,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            "events": [
                {
                    "id": ev.id,
                    "event_type": ev.event_type,
                    "event_data": ev.event_data,
                    "triggered_by": ev.triggered_by,
                    "created_at": ev.created_at.isoformat() if ev.created_at else None,
                }
                for ev in events
            ],
        })

    return result
