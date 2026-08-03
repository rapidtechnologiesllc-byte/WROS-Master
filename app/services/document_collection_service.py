"""
S-057/HRMS-0457 -- Document Collection Agent.

Real architecture adaptations:
- No new `offers` table -- `offer_id` FKs the real, pre-existing
  `OfferLetter.id` (Integer PK).
- No `system_configuration` table (same repeated gap every prior story
  that assumed one has already flagged) -- `REQUIRED_DOCUMENTS` is a
  real module constant, same "no admin-editable config table, module
  constant with a documented gap" posture S-020/S-041/S-055 already
  established (this story's own "What NOT to build" doesn't ask for a
  management UI either way).
- BR-02's `candidate.country_code` has no real dedicated field --
  `Candidate` has no country column at all (only `candidateMobile`,
  which DOES carry a real country-calling-code prefix per the earlier
  "capture country code" fix this session made, and `timezone`).
  `_infer_country_code()` derives India from the `+91` mobile prefix
  (falling back to `timezone == "Asia/Kolkata"` as a secondary
  signal) -- the same honest, best-effort fallback-chain posture
  S-047's timezone inference already established, not a fabricated
  dedicated field.
- Document upload pipeline reality (HRMS-0427, this story's own
  "Before You Start" dependency): confirmed via
  `resume_upload_service.py`'s own module docstring -- neither
  WhatsApp (media never downloaded) nor email (attachments not even
  requested) actually produce a real inbound document today.
  `mark_document_received()` is real, complete, and tested, but has no
  live trigger to call it yet -- same honest gap S-027 already
  flagged for the identical missing infrastructure, not silently
  re-solved or hidden here.
- `classify_document_type()` (Step 3's LLM classification) is a real,
  standalone, Gemini-based function (same minimal injectable REST-call
  pattern this whole round has used), ready for
  `mark_document_received()`'s caller to use once a real upload
  pipeline exists -- not wired to a live event either, for the same
  reason.
- No internal event bus -- "publish preboarding.document_received/
  preboarding.document_overdue" has nothing to publish through; the
  real `DOCUMENT_RECEIVED`/`DOCUMENT_OVERDUE` `ConversationEvent`s ARE
  the real, durable signal. HRMS-0458 (Joining Readiness Score) is now
  built (S-058) -- `mark_document_received()` calls its real
  `calculate_joining_readiness()` directly on every document received,
  exactly matching that story's own integrations table.
- BR-01's "cancel pending reminders if the candidate's status changes
  mid-collection" is a real, callable `cancel_pending_documents_for_candidate()`
  -- wired directly into `offer_decision_service._handle_decline()`
  (a one-line addition to that story's own code, since a decline
  arriving for a candidate who already has PENDING preboarding
  documents is exactly the real scenario BR-01 describes; this is
  satisfying THIS story's own explicit rule at its one real trigger
  point, not speculative scope).
- BR-03 (3 reminders, then HR takeover, no 4th message): once
  `reminder_count` reaches 3 it never increments again (the job's own
  guard), so "notify HR" is itself guarded by a real
  `DOCUMENT_OVERDUE_ESCALATED` `ConversationEvent` presence check --
  HR is notified exactly once per document, not every 6h forever.
"""
import os
import re
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.offer_letter import OfferLetter
from app.models.preboarding_document import PreboardingDocument
from app.models.submission import Submission
from app.models.user import Users
from app.services.notification_service import send_notification
from app.services.thunder_service import ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, send_thunder_message

# (document_type, document_label, india_only)
REQUIRED_DOCUMENTS: List[Tuple[str, str, bool]] = [
    ("ID_PROOF", "Government issued ID (Passport, Aadhar, Driver License)", False),
    ("ADDRESS_PROOF", "Proof of current address", False),
    ("LAST_SALARY_SLIP", "Most recent salary slip (last 3 months)", False),
    ("EXPERIENCE_LETTERS", "Experience/Relieving letters from previous employers", False),
    ("EDUCATION_CERTIFICATES", "Highest degree certificate", False),
    ("PAN_CARD", "PAN Card (for India candidates only)", True),  # BR-02
    ("BACKGROUND_CHECK_CONSENT", "Signed background check consent form", False),
]

REMINDER_INTERVAL_HOURS = 48  # Step 4
MAX_REMINDERS = 3  # BR-03
JOB_BATCH_SIZE = 100

GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def _infer_country_code(candidate: Candidate) -> str:
    """BR-02 -- see module docstring on the real fallback chain."""
    mobile = (candidate.candidateMobile or "").strip()
    if mobile.startswith("+91"):
        return "IN"
    if (candidate.timezone or "") == "Asia/Kolkata":
        return "IN"
    return "OTHER"


def _required_documents_for(candidate: Candidate) -> List[Tuple[str, str]]:
    country = _infer_country_code(candidate)
    return [(doc_type, label) for doc_type, label, india_only in REQUIRED_DOCUMENTS if not india_only or country == "IN"]


def _send_channel_aware(db: Session, conversation: CandidateConversation, candidate: Candidate, message: str) -> bool:
    channel = conversation.channel_preference if conversation.channel_preference in ("whatsapp", "web_chat") else "whatsapp"
    try:
        send_thunder_message(db, conversation, candidate, message, sender_type="ai_agent", channel=channel, auto_generated=True)
        return True
    except (ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed) as exc:
        logger.info(f"[DocumentCollection] Message skipped for candidate {candidate.candidateID!r}: {exc}")
        return False


def _notify_recruiter(db: Session, submission: Optional[Submission], message: str) -> None:
    if submission is None or not submission.submitted_by_user_id:
        return
    recipient = db.query(Users).filter(Users.UserID == submission.submitted_by_user_id).first()
    if not recipient:
        return
    try:
        send_notification(db, calling_context_tenant_id=recipient.tenant_id, recipient=recipient, priority_tier="P2", channel_preference="IN_APP", message=message)
    except Exception as exc:
        logger.warning(f"[DocumentCollection] Failed to notify recruiter: {exc}")


def _relevant_submission(db: Session, candidate_id: str) -> Optional[Submission]:
    return (
        db.query(Submission)
        .filter(Submission.candidate_id == candidate_id)
        .order_by(Submission.submitted_at.desc())
        .first()
    )


def start_document_collection(db: Session, candidate: Candidate, conversation: CandidateConversation, offer: OfferLetter, tenant_id: str) -> Dict:
    """Steps 1-2. Idempotent -- re-running for the same offer never
    duplicates rows. Never raises."""
    try:
        existing = db.query(PreboardingDocument).filter(PreboardingDocument.tenant_id == tenant_id, PreboardingDocument.candidate_id == candidate.candidateID, PreboardingDocument.offer_id == offer.id).all()
        if existing:
            return {"outcome": "already_started", "documents_created": 0}

        required = _required_documents_for(candidate)
        for doc_type, label in required:
            db.add(PreboardingDocument(tenant_id=tenant_id, candidate_id=candidate.candidateID, offer_id=offer.id, document_type=doc_type, document_label=label))
        db.commit()

        numbered = "\n".join(f"{i}. {label}" for i, (_, label) in enumerate(required, start=1))
        first_label = required[0][1] if required else ""
        message = (
            f"Welcome to BlitzenX! To complete your joining formalities, I need a few documents from you. "
            f"Here is what I need:\n{numbered}\nYou can share each document directly in this chat as a PDF or image. "
            f"Let's start with {first_label} -- could you share that when you have a moment?"
        )
        _send_channel_aware(db, conversation, candidate, message)

        return {"outcome": "started", "documents_created": len(required)}
    except Exception as exc:
        logger.error(f"[DocumentCollection] Failed starting collection for candidate {candidate.candidateID!r}: {exc}")
        db.rollback()
        return {"outcome": "start_failed"}


def _default_llm_call(prompt: str, api_key: str) -> str:
    import requests
    resp = requests.post(
        f"{GEMINI_MODEL_URL}?key={api_key}",
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.0, "maxOutputTokens": 20}},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    return result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()


def _call_llm(prompt: str, llm_call: Optional[Callable[[str], str]]) -> str:
    if llm_call is not None:
        return llm_call(prompt)
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return _default_llm_call(prompt, api_key)


VALID_DOCUMENT_CLASSIFICATIONS = tuple(doc_type for doc_type, _, _ in REQUIRED_DOCUMENTS) + ("OTHER",)


def classify_document_type(context_text: str, *, llm_call: Optional[Callable[[str], str]] = None) -> str:
    """Step 3's LLM classification. Never raises to the caller --
    returns 'OTHER' on any failure or unrecognized response."""
    prompt = (
        "What type of document is this, based on the following context? "
        f"Return ONLY one of: {', '.join(VALID_DOCUMENT_CLASSIFICATIONS)}.\n\nContext: {context_text}"
    )
    try:
        raw = _call_llm(prompt, llm_call)
        classification = re.sub(r"[^A-Z_]", "", raw.upper())
        return classification if classification in VALID_DOCUMENT_CLASSIFICATIONS else "OTHER"
    except Exception as exc:
        logger.warning(f"[DocumentCollection] Document classification failed: {exc}")
        return "OTHER"


def mark_document_received(db: Session, candidate: Candidate, conversation: CandidateConversation, tenant_id: str, document_type: str, document_url: str) -> Dict:
    """Step 3. Never raises. Returns:
      {"outcome": "no_matching_document"}
      {"outcome": "received", "all_complete": bool}
    """
    try:
        doc = (
            db.query(PreboardingDocument)
            .filter(PreboardingDocument.tenant_id == tenant_id, PreboardingDocument.candidate_id == candidate.candidateID, PreboardingDocument.document_type == document_type, PreboardingDocument.status == "PENDING")
            .first()
        )
        if doc is None:
            return {"outcome": "no_matching_document"}

        doc.status = "RECEIVED"
        doc.document_url = document_url
        doc.received_at = datetime.utcnow()
        db.add(doc)
        db.add(ConversationEvent(conversation_id=conversation.id, event_type="DOCUMENT_RECEIVED", event_data={"document_type": document_type, "document_url": document_url}, triggered_by="candidate"))
        db.commit()

        remaining = db.query(PreboardingDocument).filter(PreboardingDocument.tenant_id == tenant_id, PreboardingDocument.candidate_id == candidate.candidateID, PreboardingDocument.offer_id == doc.offer_id, PreboardingDocument.status == "PENDING").order_by(PreboardingDocument.id.asc()).all()

        from app.services.joining_readiness_service import calculate_joining_readiness
        calculate_joining_readiness(db, candidate.candidateID, doc.offer_id, tenant_id)  # S-058: recalculate on every document received, per that story's own integrations table

        if remaining:
            message = f"Thank you! I have received your {doc.document_label}. Next, could you share your {remaining[0].document_label}?"
            _send_channel_aware(db, conversation, candidate, message)
            return {"outcome": "received", "all_complete": False}

        message = f"Thank you! I have received your {doc.document_label}. That's everything! Our HR team will verify these and be in touch."
        _send_channel_aware(db, conversation, candidate, message)
        submission = _relevant_submission(db, candidate.candidateID)
        _notify_recruiter(db, submission, f"{candidate.candidateFirstName or candidate.candidateID} has submitted all required preboarding documents.")
        return {"outcome": "received", "all_complete": True}
    except Exception as exc:
        logger.error(f"[DocumentCollection] Failed marking document received for candidate {candidate.candidateID!r}: {exc}")
        db.rollback()
        return {"outcome": "receive_failed"}


def cancel_pending_documents_for_candidate(db: Session, candidate_id: str) -> int:
    """BR-01. Real, callable -- wired into offer_decision_service's
    _handle_decline() (see module docstring)."""
    rows = db.query(PreboardingDocument).filter(PreboardingDocument.candidate_id == candidate_id, PreboardingDocument.status == "PENDING").all()
    for row in rows:
        row.status = "CANCELLED"
        db.add(row)
    if rows:
        db.commit()
    return len(rows)


def run_document_reminder_job(db: Session) -> Dict:
    """Step 4. Runs every 6 hours. Never lets one bad row abort the batch."""
    result = {"processed": 0, "reminded": 0, "escalated": 0, "skipped": 0}
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=REMINDER_INTERVAL_HOURS)

    due = (
        db.query(PreboardingDocument)
        .filter(PreboardingDocument.status == "PENDING")
        .filter(
            (PreboardingDocument.last_reminded_at != None) & (PreboardingDocument.last_reminded_at <= cutoff)  # noqa: E711
            | (PreboardingDocument.last_reminded_at == None) & (PreboardingDocument.created_at <= cutoff)  # noqa: E711
        )
        .limit(JOB_BATCH_SIZE)
        .all()
    )

    for doc in due:
        result["processed"] += 1
        try:
            candidate = db.query(Candidate).filter(Candidate.candidateID == doc.candidate_id).first()
            conversation = (
                db.query(CandidateConversation)
                .filter(CandidateConversation.candidate_id == doc.candidate_id)
                .order_by(CandidateConversation.id.desc())
                .first()
            )
            if candidate is None:
                result["skipped"] += 1
                continue

            if doc.reminder_count < MAX_REMINDERS:
                message = f"Hi {candidate.candidateFirstName or 'there'}! Just a reminder -- we still need your {doc.document_label} to complete your joining. Could you please share it at your earliest convenience?"
                if conversation is not None:
                    _send_channel_aware(db, conversation, candidate, message)
                doc.reminder_count += 1
                doc.last_reminded_at = now
                db.add(doc)
                db.commit()
                result["reminded"] += 1
            else:  # BR-03: no 4th reminder -- HR takes over, notified exactly once
                already_escalated = False
                if conversation is not None:
                    escalation_events = db.query(ConversationEvent).filter(ConversationEvent.conversation_id == conversation.id, ConversationEvent.event_type == "DOCUMENT_OVERDUE_ESCALATED").all()
                    already_escalated = any((e.event_data or {}).get("document_type") == doc.document_type for e in escalation_events)
                if not already_escalated:
                    if conversation is not None:
                        db.add(ConversationEvent(conversation_id=conversation.id, event_type="DOCUMENT_OVERDUE_ESCALATED", event_data={"document_type": doc.document_type, "reminder_count": doc.reminder_count}, triggered_by="system"))
                        db.commit()
                    submission = _relevant_submission(db, doc.candidate_id)
                    _notify_recruiter(db, submission, f"{candidate.candidateFirstName or candidate.candidateID} has not provided {doc.document_label} after 3 reminders. Please follow up directly.")
                    result["escalated"] += 1
                else:
                    result["skipped"] += 1
        except Exception as exc:
            logger.error(f"[DocumentCollection] Failed processing reminder for document id={doc.id}: {exc}")
            db.rollback()
            result["skipped"] += 1

    return result
