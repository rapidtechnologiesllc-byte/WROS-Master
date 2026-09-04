"""
import logging
S-061/HRMS-0461 -- AI Activity Feed, Recruiter Copilot.

Real architecture adaptation:
- No internal event bus and no separate `thunder_activity_feed`
  denormalized table populated by an "ActivityFeedPublisher" listening
  to events. This story's own "Before You Start" note says it
  outright: "All Thunder actions already logged -- this story surfaces
  them in a structured feed." This codebase's `ConversationEvent` log
  (immutable, append-only, already populated at every real trigger
  point this whole EPIC-04 round has built) already IS that log. Every
  one of Step 2's 8 named event categories already has a real,
  existing ConversationEvent equivalent:
    message.received              -> candidate_reply
    conversation.state_changed    -> STATE_TRANSITION (S-018)
    candidate.ghosted             -> CANDIDATE_GHOSTED (S-043)
    sla.breach_detected           -> sla_breach_detected (S-020)
    candidate.high_abandonment_risk -> HIGH_ABANDONMENT_RISK (new --
        the one real gap: S-046's calculate_abandonment_score() never
        logged a ConversationEvent for its own newly_flagged
        transition, only upserted the score row. Added there directly,
        the one real trigger point, not published through a bus.)
    interview.confirmed           -> INTERVIEW_CONFIRMED (S-049)
    offer.released                -> OFFER_RELEASED (S-054)
    ESCALATION_TRIGGERED          -> escalation_triggered (S-035)
  The feed is therefore a real-time READ PROJECTION over
  ConversationEvent, filtered to this whitelist and transformed into
  the human-readable summaries Step 2 specifies -- not a second copy
  of the same data requiring 8 separate publisher call sites (each a
  real risk of drifting out of sync with the log it's supposedly
  mirroring).
- candidate_name is resolved via a live JOIN at read time, not
  denormalized at insert time as the spec's Step 1 schema sketches --
  this feed has no INSERT step of its own to snapshot a name at, and a
  live join is always correct (never a stale name) at this feed's real
  read volume (a paginated recruiter dashboard, not a high-throughput
  stream).
- BR-01 (ACTION_REQUIRED never auto-marked read) is enforced directly
  in mark_all_read() -- it only ever touches INFO/WARNING severities,
  matching this story's own AC-7 literally ("PATCH .../read-all clears
  all INFO and WARNING items").
- BR-02 (30 days retained, not deleted) needs no separate archival job:
  ConversationEvent is already immutable/append-only and never deleted
  by any code in this codebase. The UI's "last 30 days by default" is
  simply this service's own default `since` filter -- older rows stay
  in the real table, just outside the default window, exactly matching
  "archived not deleted" without inventing a second archive table this
  story's own "no export" scope note makes unnecessary.
- Per-item read tracking (BR-01) uses a new, sparse
  `ActivityFeedReadState` table (one row per conversation_event that
  has actually been marked read; no row = unread) rather than adding
  an is_read column to the shared, generic ConversationEvent table
  that every other story in this codebase also writes to.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.activity_feed_read_state import ActivityFeedReadState
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.interview_pipeline import SubmissionInterview
from app.models.offer_letter import OfferLetter

DEFAULT_RETENTION_DAYS = 30  # BR-02

# Step 2's 8 named categories, mapped to this codebase's real event_type values.
ACTIVITY_EVENT_SEVERITY = {
    "candidate_reply": "INFO",
    "STATE_TRANSITION": "INFO",
    "CANDIDATE_GHOSTED": "WARNING",
    "sla_breach_detected": "WARNING",
    "HIGH_ABANDONMENT_RISK": "ACTION_REQUIRED",
    "INTERVIEW_CONFIRMED": "INFO",
    "OFFER_RELEASED": "INFO",
    "escalation_triggered": "ACTION_REQUIRED",
    # S-075/HRMS-0475 BR-02 -- PauseExpiryJob's auto-resume notification.
    "THUNDER_AUTO_RESUMED": "INFO",
    # Thunder autonomous outreach with context (search, merge, notes, confidence)
    "THUNDER_OUTREACH_INITIATED": "INFO",
    # Thunder AI message sent (email/WhatsApp to candidate)
    "ai_message_sent": "INFO",
}
ACTIVITY_EVENT_TYPES = tuple(ACTIVITY_EVENT_SEVERITY.keys())

def _candidate_display_name(candidate: Optional[Candidate]) -> str:
    if candidate is None:
        return "A candidate"
    parts = [candidate.candidateFirstName, candidate.candidateLastName]
    name = " ".join(p for p in parts if p).strip()
    return name or candidate.candidateEmail

def _build_summary(db: Session, event: ConversationEvent, candidate_name: str) -> str:
    data = event.event_data or {}
    if event.event_type == "candidate_reply":
        return f"Thunder received a reply from {candidate_name}."
    if event.event_type == "STATE_TRANSITION":
        return f"Thunder moved {candidate_name} from {data.get('from_state', '?')} to {data.get('to_state', '?')}."
    if event.event_type == "CANDIDATE_GHOSTED":
        return f"Thunder detected {candidate_name} has not responded after 3 follow-ups. Marked as ghosted."
    if event.event_type == "sla_breach_detected":
        breached_at = data.get("breached_at")
        hours = "several"
        if breached_at:
            try:
                elapsed = datetime.utcnow() - datetime.fromisoformat(breached_at)
                hours = str(round(elapsed.total_seconds() / 3600))
            except ValueError:
                pass
        return f"SLA breach: {candidate_name} has not been contacted in {hours} hours."
    if event.event_type == "HIGH_ABANDONMENT_RISK":
        score = data.get("abandonment_score", "?")
        return f"{candidate_name} has a {score}% abandonment risk. Review recommended."
    if event.event_type == "INTERVIEW_CONFIRMED":
        interview = db.query(SubmissionInterview).filter(SubmissionInterview.id == data.get("interview_id")).first()
        level = interview.level if interview else "an"
        when = data.get("scheduled_at_utc", "")[:16].replace("T", " ")
        return f"Thunder scheduled {candidate_name} for {level} interview on {when or 'TBD'}."
    if event.event_type == "OFFER_RELEASED":
        offer = db.query(OfferLetter).filter(OfferLetter.id == data.get("offer_id")).first()
        role = offer.position if offer else "their role"
        return f"Offer released to {candidate_name} for {role}. Awaiting their decision."
    if event.event_type == "escalation_triggered":
        reason = data.get("reason", "requested human review")
        return f"Thunder escalated {candidate_name} -- {reason}. Human review required."
    if event.event_type == "THUNDER_AUTO_RESUMED":
        return f"Thunder has automatically resumed for {candidate_name} -- pause duration expired."
    if event.event_type == "THUNDER_OUTREACH_INITIATED":
        merge_info = ""
        if data.get("existing_candidate_merged"):
            merge_info = " Found and merged with existing profile. "
        context = data.get("context_summary", "")
        confidence = data.get("confidence_level", "")
        detail = ""
        if context:
            detail = f" Context: {context}"
        if confidence:
            detail += f" (Confidence: {confidence})"
        return f"Thunder initiated outreach to {candidate_name}.{merge_info}Searched profile, reviewed notes, reached out as recruiter with full context.{detail}"
    if event.event_type == "ai_message_sent":
        channel = data.get("channel", "email").upper()
        message_type = data.get("message_type", "message")
        subject = data.get("subject", "")
        # 2026-08-12 real bug fix -- Avinash: "How did this happen when
        # whatsapp is not connected." The event's own data already had
        # delivered: false (the send genuinely failed, e.g. no WhatsApp
        # integration configured), but this summary ignored that field
        # and always said "sent" regardless -- a misleading activity
        # entry claiming success for a message that never went out.
        verb = "sent" if data.get("delivered", True) else "attempted to send (delivery failed)"
        if message_type == "missing_fields_request":
            fields_count = len(data.get("missing_fields", []))
            return f"Thunder {verb} {channel} to {candidate_name} requesting {fields_count} missing profile field(s). Subject: {subject}"
        return f"Thunder {verb} {channel} to {candidate_name}."
    return f"Thunder activity for {candidate_name}."

def _serialize(db: Session, event: ConversationEvent, candidate: Optional[Candidate], is_read: bool) -> Dict:
    candidate_name = _candidate_display_name(candidate)
    return {
        "id": event.id,
        "candidate_id": candidate.candidateID if candidate else None,
        "candidate_name": candidate_name,
        "activity_type": event.event_type,
        "activity_summary": _build_summary(db, event, candidate_name),
        "severity": ACTIVITY_EVENT_SEVERITY.get(event.event_type, "INFO"),
        "is_read": is_read,
        "created_at": event.created_at,
    }

def get_activity_feed(
    db: Session, tenant_id: str, *, candidate_id: Optional[str] = None, severity: Optional[str] = None,
    page: int = 1, per_page: int = 25, since_days: int = DEFAULT_RETENTION_DAYS,
) -> Dict:
    """Step 3. Never raises -- callers should still catch to satisfy
    this story's own "show 'Activity feed unavailable', do not crash"
    integration note, but internal query failures aren't expected here."""
    since = datetime.utcnow() - timedelta(days=since_days)

    query = (
        db.query(ConversationEvent, CandidateConversation)
        .join(CandidateConversation, ConversationEvent.conversation_id == CandidateConversation.id)
        .filter(CandidateConversation.tenant_id == tenant_id, ConversationEvent.event_type.in_(ACTIVITY_EVENT_TYPES), ConversationEvent.created_at >= since)
    )
    if candidate_id:
        query = query.filter(CandidateConversation.candidate_id == candidate_id)
    if severity:
        matching_types = [t for t, s in ACTIVITY_EVENT_SEVERITY.items() if s == severity]
        query = query.filter(ConversationEvent.event_type.in_(matching_types))

    total_count = query.count()
    rows = query.order_by(ConversationEvent.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    event_ids = [event.id for event, _ in rows]
    read_ids = set()
    if event_ids:
        read_ids = {r.conversation_event_id for r in db.query(ActivityFeedReadState.conversation_event_id).filter(ActivityFeedReadState.conversation_event_id.in_(event_ids)).all()}

    candidate_ids = {conv.candidate_id for _, conv in rows}
    candidates_by_id = {c.candidateID: c for c in db.query(Candidate).filter(Candidate.candidateID.in_(candidate_ids)).all()} if candidate_ids else {}

    activities = [_serialize(db, event, candidates_by_id.get(conv.candidate_id), event.id in read_ids) for event, conv in rows]

    unread_count_query = (
        db.query(ConversationEvent)
        .join(CandidateConversation, ConversationEvent.conversation_id == CandidateConversation.id)
        .filter(CandidateConversation.tenant_id == tenant_id, ConversationEvent.event_type.in_(ACTIVITY_EVENT_TYPES), ConversationEvent.created_at >= since)
    )
    if candidate_id:
        unread_count_query = unread_count_query.filter(CandidateConversation.candidate_id == candidate_id)
    all_ids_in_window = [e.id for e in unread_count_query.all()]
    read_in_window = {r.conversation_event_id for r in db.query(ActivityFeedReadState.conversation_event_id).filter(ActivityFeedReadState.conversation_event_id.in_(all_ids_in_window)).all()} if all_ids_in_window else set()
    unread_count = len(all_ids_in_window) - len(read_in_window)

    return {
        "activities": activities,
        "total_count": total_count,
        "unread_count": unread_count,
        "has_more": (page * per_page) < total_count,
    }

def mark_read(db: Session, tenant_id: str, activity_id: int) -> bool:
    """Step 3 PATCH /activity-feed/{id}/read. Idempotent."""
    event = db.query(ConversationEvent).filter(ConversationEvent.id == activity_id).first()
    if event is None:
        return False
    existing = db.query(ActivityFeedReadState).filter(ActivityFeedReadState.conversation_event_id == activity_id).first()
    if existing is None:
        db.add(ActivityFeedReadState(tenant_id=tenant_id, conversation_event_id=activity_id))
        db.commit()
    return True

def mark_all_read(db: Session, tenant_id: str, *, candidate_id: Optional[str] = None, since_days: int = DEFAULT_RETENTION_DAYS) -> int:
    """Step 3 PATCH /activity-feed/read-all. BR-01: only INFO/WARNING --
    ACTION_REQUIRED items are never auto-marked read here."""
    since = datetime.utcnow() - timedelta(days=since_days)
    clearable_types = [t for t, s in ACTIVITY_EVENT_SEVERITY.items() if s in ("INFO", "WARNING")]

    query = (
        db.query(ConversationEvent)
        .join(CandidateConversation, ConversationEvent.conversation_id == CandidateConversation.id)
        .filter(CandidateConversation.tenant_id == tenant_id, ConversationEvent.event_type.in_(clearable_types), ConversationEvent.created_at >= since)
    )
    if candidate_id:
        query = query.filter(CandidateConversation.candidate_id == candidate_id)

    event_ids = [e.id for e in query.all()]
    already_read = {r.conversation_event_id for r in db.query(ActivityFeedReadState.conversation_event_id).filter(ActivityFeedReadState.conversation_event_id.in_(event_ids)).all()} if event_ids else set()

    newly_marked = 0
    for event_id in event_ids:
        if event_id not in already_read:
            db.add(ActivityFeedReadState(tenant_id=tenant_id, conversation_event_id=event_id))
            newly_marked += 1
    if newly_marked:
        db.commit()
    return newly_marked
