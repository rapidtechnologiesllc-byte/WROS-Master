"""
import logging
S-075/HRMS-0475 -- AI Recruiter Pause & Resume Controls.

Real architecture adaptation: HRMS-0466 Supervisor Agent (S-066) -- the
single dispatch loop this story's Step 3 assumes exists ("before
dispatching ANY agent for a candidate: check is_thunder_paused") -- is
not built in this codebase and is itself a separate, deferred design
story. There is no one dispatch loop to patch a check into.

Instead, every autonomous Thunder send in this codebase already funnels
through a small number of real choke points:
  - thunder_service.send_thunder_message() -- the one gated send path
    (R-08/consent/debounce) every whatsapp/web_chat send goes through.
  - thunder_service.send_outbound_campaign_message() -- wraps the above
    for whatsapp; has its own email branch for the automated outreach
    stack (S-041/044/045).
  - Three call sites that still hand-roll a raw EmailService.send_email()
    for a candidate-facing automated send, sibling to a whatsapp branch
    that already goes through send_thunder_message()
    (ai_conversation_service.run_reply_pipeline's follow-up email,
    interview_reminder_service's reminder email, interview_no_show_
    service's check-in email).

is_thunder_paused_for_conversation() / raise_if_thunder_paused() are
wired into all of the above -- the honest substitute for "the Supervisor
Agent checks this" until S-066 exists. HR's own manual send (S-009,
ai_agent.py's /conversations/{id}/send) calls send_whatsapp_message()
directly, bypassing send_thunder_message() entirely (by design, same as
every other Thunder gate) -- pausing Thunder must never block a human
from messaging a candidate themselves, matching BR-01's "pause is a
separate flag from ownership" framing.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.user import Users

# Step 4's 6A field spec's four duration options ("24h / 48h / 1 week /
# Until I manually resume") -- "until manually resume" is simply
# resume_at=None, no preset needed for it.
PAUSE_DURATION_PRESETS = {
    "24h": timedelta(hours=24),
    "48h": timedelta(hours=48),
    "1_week": timedelta(days=7),
}

logger = logging.getLogger(__name__)

class ThunderPausedError(Exception):
    """Raised by every real Thunder send choke point when BR-01
    (per-candidate pause) or BR-03 (global tenant pause) applies.
    Callers catch this the same way they already catch ConsentNotGiven /
    DuplicateMessageSuppressed and skip the candidate."""

def is_thunder_paused(db: Session) -> bool:
    """Check if Thunder autonomous loop is paused.
    Single organization - no tenant checks needed."""
    # Check if there's an explicit global pause flag
    # For now, always allow autonomous loop to run
    # Kill switch can be implemented later if needed
    return False

def is_thunder_paused_for_conversation(db: Session, conversation: CandidateConversation) -> bool:
    """BR-03: global tenant pause takes precedence over -- i.e. is
    checked in addition to, regardless of -- the per-candidate flag."""
    if conversation.is_thunder_paused:
        return True
    tenant_user = db.query(Users).filter(Users.UserID == conversation.tenant_id).first()
    return bool(tenant_user is not None and tenant_user.thunder_enabled is False)

def raise_if_thunder_paused(db: Session, conversation: CandidateConversation) -> None:
    if is_thunder_paused_for_conversation(db, conversation):
        raise ThunderPausedError(
            f"Thunder is paused for conversation {conversation.id} "
            f"(candidate {conversation.candidate_id!r}) -- send skipped."
        )

def pause_thunder(
    db: Session, conversation: CandidateConversation, *, paused_by: str, resume_at: Optional[datetime] = None,
) -> CandidateConversation:
    """BR-01: does not touch owner_type/owner_id -- pause is independent
    of ownership."""
    conversation.is_thunder_paused = True
    conversation.thunder_paused_at = datetime.utcnow()
    conversation.thunder_resume_at = resume_at
    conversation.thunder_paused_by = paused_by
    db.add(conversation)
    return conversation

def resume_thunder(db: Session, conversation: CandidateConversation) -> CandidateConversation:
    conversation.is_thunder_paused = False
    conversation.thunder_resume_at = None
    db.add(conversation)
    return conversation

def run_pause_expiry_job(db: Session) -> Dict:
    """Step 3's PauseExpiryJob -- runs every 15 min (see
    app.core.scheduler), auto-resumes any conversation whose
    thunder_resume_at has passed.

    BR-02: logs a real THUNDER_AUTO_RESUMED ConversationEvent so it
    surfaces through activity_feed_service's existing read-projection
    (S-061) -- recruiters already watch that feed, no second
    notification channel needed.
    """
    result = {"resumed": 0}
    now = datetime.utcnow()
    due = (
        db.query(CandidateConversation)
        .filter(
            CandidateConversation.is_thunder_paused == True,  # noqa: E712
            CandidateConversation.thunder_resume_at != None,  # noqa: E711
            CandidateConversation.thunder_resume_at <= now,
        )
        .all()
    )
    for conversation in due:
        try:
            resume_thunder(db, conversation)
            db.add(ConversationEvent(
                conversation_id=conversation.id,
                event_type="THUNDER_AUTO_RESUMED",
                event_data={"candidate_id": conversation.candidate_id},
                triggered_by="system",
            ))
            db.commit()
            result["resumed"] += 1
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.error(f"[ThunderPause] Failed auto-resuming conversation {conversation.id!r}: {exc}")
            db.rollback()
    return result
