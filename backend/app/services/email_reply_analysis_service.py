"""
S-347/HRMS-P117 -- Email Reply Analysis (NEW).

Detects candidate email replies and records desire signals, following
the exact pattern established by WhatsApp webhook (whatsapp_webhook_service.py
lines 220-235 + desire_signal_service).

Pattern established by WhatsApp:
  1. record_message_signal() - captures message body for LLM analysis
  2. record_response_speed_signal() - deterministic scoring
  3. process_unprocessed_signals() - real-time SLM update
  4. build_and_narrate() - rebuild desire profile

Email flow mirrors WhatsApp exactly, with one addition:
  - SPAM/marketing filter (simple keyword check before signal recording)

Non-breaking: every function is fire-and-forget, never raises.
Failures are logged but don't block mail sync.
"""

import re
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.services.desire_signal_service import (
    record_message_signal,
    record_response_speed_signal,
    minutes_since_last_outbound,
    process_unprocessed_signals,
)
from app.services.desire_profile_service import build_and_narrate
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation

# Marketing/spam keywords to filter out (non-candidate replies)
SPAM_PATTERNS = [
    r"unsubscribe",
    r"promotional offer",
    r"click here",
    r"limited time",
    r"out of office",
    r"auto-reply",
    r"vacation responder",
]

def _is_candidate_reply(email_body: Optional[str]) -> bool:
    """Filter out marketing/spam/auto-replies. Return False for obvious
    non-candidate messages. True for everything else (LLM will do deeper analysis)."""
    if not email_body:
        return True  # No body = assume it's from candidate (might be signature-only)

    body_lower = email_body.lower()
    for pattern in SPAM_PATTERNS:
        if re.search(pattern, body_lower, re.IGNORECASE):
            logger.info(f"[EmailAnalysis] Filtered out spam pattern: {pattern}")
            return False
    return True

def analyze_candidate_email_reply(
    db: Session,
    candidate_id: str,
    tenant_id: str,
    email_body: str,
    received_at: datetime,
) -> Optional[dict]:
    """
    Record signals from a candidate's email reply.

    Called from lifecycle_communication_linking_service when an EMAIL_RECEIVED
    event is linked to a candidate (mirror of how whatsapp_webhook_service
    calls record_message_signal/record_response_speed_signal after storing
    the inbound message).

    Returns dict with signal_count if successful, None on failure.
    Never raises -- see caller's try/except.
    """

    if not _is_candidate_reply(email_body):
        logger.info(f"[EmailAnalysis] Skipped non-candidate email for {candidate_id}")
        return None

    signal_count = 0

    try:
        # 1. Record message signal (same as WhatsApp line 220)
        if email_body:
            record_message_signal(
                db, tenant_id, candidate_id, "EMAIL_MESSAGE", email_body
            )
            signal_count += 1
            logger.info(f"[EmailAnalysis] Recorded EMAIL_MESSAGE signal for {candidate_id}")

        # 2. Record response speed (same as WhatsApp line 221-223)
        # This requires finding the active conversation and last outbound message
        conversation = (
            db.query(CandidateConversation)
            .filter(
                CandidateConversation.candidate_id == candidate_id,
                CandidateConversation.status != "closed"
            )
            .order_by(CandidateConversation.id.desc())
            .first()
        )

        if conversation:
            _prior_gap = minutes_since_last_outbound(db, conversation.id, before=received_at)
            if _prior_gap is not None:
                record_response_speed_signal(db, tenant_id, candidate_id, _prior_gap)
                signal_count += 1
                logger.info(
                    f"[EmailAnalysis] Recorded RESPONSE_SPEED signal: "
                    f"{_prior_gap:.1f} min for {candidate_id}"
                )
        else:
            logger.info(f"[EmailAnalysis] No active conversation for {candidate_id} - skipping response speed signal")

        return {"signal_count": signal_count, "candidate_id": candidate_id}

    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(
            f"[EmailAnalysis] Failed to analyze email for {candidate_id}: {exc} -- "
            f"email is still linked, no signals recorded."
        )
        db.rollback()
        return None

def trigger_realtime_slm_update(db: Session, tenant_id: str, candidate_id: str) -> None:
    """Trigger real-time SLM processing (same as WhatsApp line 225-235).
    Non-blocking, logged but doesn't fail the overall sync."""
    try:
        process_unprocessed_signals(db)  # LLM categorization
        profile = build_and_narrate(db, tenant_id, candidate_id)
        if profile:
            logger.info(
                f"[EmailAnalysis] SLM profile updated in real-time for "
                f"{candidate_id}: {profile.get('engagement_level', 'unknown')}"
            )
    except Exception as e:
        logger.warning(
            f"[EmailAnalysis] Real-time SLM update failed (non-blocking): {e} -- "
            f"scheduler will retry in 30 min"
        )
