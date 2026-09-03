"""
import logging
S-017/HRMS-0417 -- Candidate Self-Service Web Portal.

Adapted to this codebase's real architecture:

- BR-01 ("magic link, no password ever") is satisfied without a
  separate magic-link table or a validate/exchange endpoint. A portal
  link IS a real candidate JWT (same shape S-004/auth.py already issue
  -- {"sub": candidate_id, "type": "candidate"}), just long-lived
  (PORTAL_LINK_EXPIRY_DAYS) and handed to the candidate as a URL
  instead of typed in after a password login. It works with every
  existing get_current_candidate-gated endpoint unchanged -- no
  parallel session-cookie auth system, consistent with S-004's own
  documented decision to skip the spec's never-built HRMS-P111 magic
  link in favor of real JWT auth.
- Stage badge is derived from the real CandidateConversation.status
  ("open"/"awaiting_candidate"/"closed"), not the spec's fictional
  Qualifying/Qualified/Interview/Offer/Preboarding enum.
- Pending actions reuse the same get_missing_fields() this whole EPIC-04
  round already standardized on (S-011/S-014/S-016), not a fictional
  candidate_missing_fields table.
- Recent/full message history reuses get_conversation_thread() (the
  same cross-channel event log the recruiter-facing Thunder UI reads),
  not portal_message_service.get_portal_message_history() -- that
  function deliberately scopes to channel="portal" only for a
  recruiter-side per-channel view; a candidate opening their own
  portal should see the WhatsApp/email exchange they already had with
  Thunder too, not just messages sent through this one channel.
  Replies are still written via portal_message_service.send_portal_message()
  so the channel="portal" tagging on new messages is unchanged.
- Interviews reuse the real app.models.user.Interview table (already
  used by the existing recruiter-facing interview scheduling screens);
  no timezone column exists per-candidate, so the ICS/interview payload
  carries UTC and the browser renders it in the viewer's local zone --
  the real, honest version of "candidate's local timezone" without
  inventing a stored preference that doesn't exist.
- Reschedule requests don't get a new table -- they're logged as a
  ConversationEvent (event_type="reschedule_requested") on the
  candidate's own conversation and flip escalation_state to "pending",
  the same mechanism every other "a human needs to look at this" case
  in this codebase already uses.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import create_access_token
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.user import Interview
from app.services.ai_conversation_service import get_conversation_thread, get_missing_fields
from app.core.dependencies import get_current_candidate

PORTAL_LINK_EXPIRY_DAYS = 14

# Real status -> (label, color) mapping. Not the spec's fictional
# Qualifying/Qualified/Interview/Offer/Preboarding enum -- see module
# docstring.
STAGE_BADGE = {
    "open": {"label": "In Progress", "color": "blue"},
    "awaiting_candidate": {"label": "Awaiting Your Reply", "color": "amber"},
    "closed": {"label": "Completed", "color": "green"},
}
DEFAULT_STAGE_BADGE = {"label": "In Progress", "color": "blue"}


def generate_portal_link_token(candidate_id: str) -> str:
    """The 'magic link' itself -- a real, long-lived candidate JWT."""
    return create_access_token(
        data={"sub": candidate_id, "type": "candidate"},
        expires_delta=timedelta(days=PORTAL_LINK_EXPIRY_DAYS),
    )


def generate_portal_link_url(candidate_id: str) -> str:
    token = generate_portal_link_token(candidate_id)
    return f"{Settings.FRONTEND_BASE_URL.rstrip('/')}/candidate/{token}"


def _active_conversation(db: Session, candidate_id: str) -> Optional[CandidateConversation]:
    return (
        db.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate_id)
        .order_by(CandidateConversation.created_at.desc())
        .first()
    )


def _candidate_display_name(candidate: Candidate) -> str:
    return " ".join(filter(None, [candidate.candidateFirstName, candidate.candidateLastName])).strip() or "there"


def _map_thread_message(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if event["event_type"] not in ("candidate_reply", "ai_message_sent", "hr_message_sent"):
        return None
    data = event.get("event_data") or {}
    return {
        "id": event["id"],
        "direction": "INBOUND" if event["event_type"] == "candidate_reply" else "OUTBOUND",
        "sender_type": (
            "CANDIDATE" if event["event_type"] == "candidate_reply"
            else "AI" if event["event_type"] == "ai_message_sent"
            else "RECRUITER"
        ),
        "channel": (data.get("channel") or "").upper(),
        "message_body": data.get("body", ""),
        "sent_at": event["created_at"],
    }


def track_portal_page_view(db: Session, candidate: Candidate, page: str, time_on_page_seconds: int, scroll_depth_pct: Optional[int]) -> bool:
    """S-346 Step 4 / S-347 Step 4 -- real behavioral signal, invisible
    to the candidate (BR-01). Silently no-ops (returns False) when the
    candidate has no conversation yet -- there's no tenant to attribute
    the signal to before Thunder is assigned, same real precondition
    every other candidate_desire_signals row in this codebase has."""
    conversation = _active_conversation(db, candidate.candidateID)
    if conversation is None:
        return False
    from app.services.desire_signal_service import record_portal_page_view_signal
    signal = record_portal_page_view_signal(
        db, conversation.tenant_id, candidate.candidateID, page, time_on_page_seconds, scroll_depth_pct,
    )
    return signal is not None


def get_portal_home(db: Session, candidate: Candidate) -> Dict[str, Any]:
    conversation = _active_conversation(db, candidate.candidateID)
    badge = STAGE_BADGE.get(conversation.status, DEFAULT_STAGE_BADGE) if conversation else DEFAULT_STAGE_BADGE

    missing = get_missing_fields(candidate, db)
    pending_actions = [f"Provide your {m['label'].split('(')[0].strip()}" for m in missing]

    upcoming_interview_count = (
        db.query(Interview)
        .filter(Interview.candidate_id == candidate.candidateID, Interview.start_time >= datetime.utcnow(), Interview.status == "Scheduled")
        .count()
    )
    if upcoming_interview_count:
        pending_actions.append("Confirm your interview time")

    thread = get_conversation_thread(candidate.candidateID, db)
    recent_messages: List[Dict[str, Any]] = []
    if thread:
        events = thread[0]["events"]
        mapped = [m for m in (_map_thread_message(e) for e in events) if m]
        recent_messages = mapped[-3:][::-1]

    return {
        "candidate_name": _candidate_display_name(candidate),
        "stage": badge,
        "pending_actions": pending_actions,
        "recent_messages": recent_messages,
        "conversation_id": conversation.id if conversation else None,
    }


def get_portal_thread(db: Session, candidate: Candidate) -> Dict[str, Any]:
    thread = get_conversation_thread(candidate.candidateID, db)
    if not thread:
        return {"conversation_id": None, "messages": []}
    events = thread[0]["events"]
    messages = [m for m in (_map_thread_message(e) for e in events) if m]
    return {"conversation_id": thread[0]["conversation_id"], "messages": messages}


def get_portal_profile_fields(db: Session, candidate: Candidate) -> Dict[str, Any]:
    missing = get_missing_fields(candidate, db)
    return {"total_missing": len(missing), "missing_fields": missing}


def get_portal_interviews(db: Session, candidate: Candidate) -> List[Dict[str, Any]]:
    rows = (
        db.query(Interview)
        .filter(
            Interview.candidate_id == candidate.candidateID,
            Interview.start_time >= datetime.utcnow(),
            Interview.status == "Scheduled",
        )
        .order_by(Interview.start_time.asc())
        .all()
    )
    return [
        {
            "id": i.id,
            "start_time": i.start_time,
            "end_time": i.end_time,
            "format": "video" if i.meeting_link else "onsite/phone -- see prep notes",
            "meeting_link": i.meeting_link,
            "prep_tip": "Have your resume ready and join 5 minutes early.",
        }
        for i in rows
    ]

logger = logging.getLogger(__name__)

class PortalInterviewNotFound(Exception):
    pass


def _get_owned_interview(db: Session, candidate: Candidate, interview_id: int) -> Interview:
    interview = (
        db.query(Interview)
        .filter(Interview.id == interview_id, Interview.candidate_id == candidate.candidateID)
        .first()
    )
    if not interview:
        raise PortalInterviewNotFound(f"Interview {interview_id} not found for this candidate.")
    return interview


def build_ics(interview: Interview, candidate: Candidate) -> bytes:
    """Minimal, real VEVENT -- no external calendar library needed for one event."""
    def fmt(dt: datetime) -> str:
        return dt.strftime("%Y%m%dT%H%M%SZ")

    now = fmt(datetime.utcnow())
    start = fmt(interview.start_time) if interview.start_time else now
    end = fmt(interview.end_time) if interview.end_time else start
    summary = f"BlitzenX Interview -- {_candidate_display_name(candidate)}"
    description = "Have your resume ready and join 5 minutes early."
    if interview.meeting_link:
        description += f"\\nJoin link: {interview.meeting_link}"

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//BlitzenX//WROS Candidate Portal//EN",
        "BEGIN:VEVENT",
        f"UID:interview-{interview.id}@blitzenx",
        f"DTSTAMP:{now}",
        f"DTSTART:{start}",
        f"DTEND:{end}",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{description}",
    ]
    if interview.meeting_link:
        lines.append(f"LOCATION:{interview.meeting_link}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def get_interview_ics(db: Session, candidate: Candidate, interview_id: int) -> bytes:
    interview = _get_owned_interview(db, candidate, interview_id)
    return build_ics(interview, candidate)


def create_reschedule_request(db: Session, candidate: Candidate, interview_id: int, note: str) -> Dict[str, Any]:
    interview = _get_owned_interview(db, candidate, interview_id)
    conversation = _active_conversation(db, candidate.candidateID)
    if not conversation:
        raise PortalInterviewNotFound("No active conversation found for this candidate.")

    event = ConversationEvent(
        conversation_id=conversation.id,
        event_type="reschedule_requested",
        event_data={"interview_id": interview.id, "note": (note or "").strip()[:1000]},
        triggered_by="candidate",
    )
    db.add(event)
    conversation.escalation_state = "pending"
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    db.commit()
    db.refresh(event)
    return {"request_id": event.id, "submitted_at": event.created_at}
