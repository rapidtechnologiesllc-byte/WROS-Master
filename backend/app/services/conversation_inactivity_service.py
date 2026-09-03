"""
Conversation inactivity safety net -- extends HRMS-0410's ownership
model with an automatic response when a candidate conversation goes
quiet too long, regardless of which side is silent. Genuinely new
capability, not from any existing story (same posture as
import logging
app.services.whatsapp_routing_service, which this builds directly on).

Two directions, one shared 30-(business-)hour clock, decided by whether
the LAST message in the conversation came from the candidate or from
staff/Thunder:

  - Candidate's last message unanswered by the owning human -> Thunder
    reclaims ownership (logged as a distinct event, NOT a manual
    hand-back, so HRMS-P612's human-dependency tracking can tell the
    two apart), notifies the previous owner, and immediately sends the
    candidate a check-in.
  - Staff's last message unanswered by the candidate -> an automated
    nudge goes out, attributed as the current owner's own message
    ("it goes as the recruiter is sending it" -- explicit product
    decision), tagged auto_generated=True internally on the event so
    R-06/HRMS-P612 metrics aren't inflated by sends that only *look*
    manual.

Timer model (explicit choice, optimizing for "don't lose the candidate"
over a more conservative count): a continuous 30-hour wall-clock
countdown, paused only across the weekend -- Friday 21:00 to Monday
09:00, in the candidate's local time. The same candidate timezone also
gates WHEN the resulting action may actually fire: only within a
09:00-21:00 window, reusing notification_service's tested timezone-
conversion helpers with a different window than its own 08:00-20:00.

Not wired to a scheduler -- evaluate_conversation_inactivity() is the
per-conversation function a cron would call across every open
conversation, same "idempotent function exists, cron wiring is
follow-up" posture as every other scheduled-job story this session.
"""
from datetime import datetime, time, timedelta, timezone as dt_timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.user import Users
from app.services.ai_conversation_service import AI_AGENT_NAME
from app.services.notification_service import (
    _is_within_business_hours,
    _next_business_hours_release,
    send_notification,
)
from app.services.thunder_service import send_thunder_message

INACTIVITY_THRESHOLD_HOURS = 30
SEND_WINDOW_START_HOUR = 9
SEND_WINDOW_END_HOUR = 21  # 9pm

# Which ConversationEvent.event_type values count as an actual message in
# either direction -- whichever is most recent decides who's "on the clock."
MESSAGE_EVENT_TYPES = ("ai_message_sent", "hr_message_sent", "candidate_reply")

DEFAULT_RECLAIM_CHECKIN_MESSAGE = (
    "Hi, just checking in -- wanted to make sure your application is still moving "
    "forward. Let us know if you have any questions!"
)
DEFAULT_NUDGE_MESSAGE = (
    "Hi, following up on my last message -- let me know if you have any questions "
    "or if there's anything I can help clarify."
)

def _weekend_pause_windows(start: datetime, end: datetime):
    """Every Friday-21:00-to-Monday-09:00 window that could overlap
    [start, end] (naive local datetimes), padded a few days either side
    to catch boundary cases."""
    windows = []
    day = start.date() - timedelta(days=3)
    last_day = end.date() + timedelta(days=1)
    seen = set()
    while day <= last_day:
        if day.weekday() == 4 and day not in seen:  # Friday
            seen.add(day)
            pause_start = datetime.combine(day, time(21, 0))
            windows.append((pause_start, pause_start + timedelta(hours=60)))  # -> Monday 09:00
        day += timedelta(days=1)
    return windows

def business_hours_elapsed(start: datetime, end: datetime) -> float:
    """
    Raw wall-clock hours between start and end, minus any time that
    fell inside a Friday-21:00-to-Monday-09:00 weekend pause. Both
    arguments are naive datetimes already in the same (candidate-local)
    timezone -- this function does no timezone conversion itself.
    """
    if end <= start:
        return 0.0
    total_hours = (end - start).total_seconds() / 3600.0
    paused_hours = 0.0
    for w_start, w_end in _weekend_pause_windows(start, end):
        overlap_start = max(start, w_start)
        overlap_end = min(end, w_end)
        if overlap_end > overlap_start:
            paused_hours += (overlap_end - overlap_start).total_seconds() / 3600.0
    return max(0.0, total_hours - paused_hours)

def _to_local(utc_naive: datetime, tz_name: str) -> datetime:
    tz = ZoneInfo(tz_name or "Asia/Kolkata")
    return utc_naive.replace(tzinfo=dt_timezone.utc).astimezone(tz).replace(tzinfo=None)

def get_last_message_event(db: Session, conversation: CandidateConversation) -> Optional[ConversationEvent]:
    return (
        db.query(ConversationEvent)
        .filter(
            ConversationEvent.conversation_id == conversation.id,
            ConversationEvent.event_type.in_(MESSAGE_EVENT_TYPES),
        )
        .order_by(ConversationEvent.id.desc())
        .first()
    )

def evaluate_conversation_inactivity(
    db: Session,
    conversation: CandidateConversation,
    candidate: Candidate,
    *,
    now: Optional[datetime] = None,
    whatsapp_client: Optional[Callable[[str, str, str], bool]] = None,
) -> dict:
    """
    The per-conversation check a cron would run across every open
    conversation. Returns a dict describing what happened (or didn't):
      {"action": "none" | "held" | "reclaimed" | "nudged", ...}
    """
    last_message = get_last_message_event(db, conversation)
    if last_message is None:
        return {"action": "none", "reason": "no messages yet"}

    tz_name = candidate.timezone
    now_utc = now or datetime.utcnow()

    last_local = _to_local(last_message.created_at, tz_name)
    now_local = _to_local(now_utc, tz_name)
    elapsed = business_hours_elapsed(last_local, now_local)

    if elapsed < INACTIVITY_THRESHOLD_HOURS:
        return {"action": "none", "elapsed_hours": elapsed}

    if not _is_within_business_hours(now_utc, tz_name, start_hour=SEND_WINDOW_START_HOUR, end_hour=SEND_WINDOW_END_HOUR):
        return {
            "action": "held",
            "elapsed_hours": elapsed,
            "next_eligible_at": _next_business_hours_release(
                now_utc, tz_name, start_hour=SEND_WINDOW_START_HOUR, end_hour=SEND_WINDOW_END_HOUR,
            ),
        }

    if last_message.triggered_by == "candidate":
        return _reclaim(db, conversation, candidate, elapsed_hours=elapsed, whatsapp_client=whatsapp_client)

    return _nudge(db, conversation, candidate, elapsed_hours=elapsed, whatsapp_client=whatsapp_client)

def _reclaim(
    db: Session, conversation: CandidateConversation, candidate: Candidate,
    *, elapsed_hours: float, whatsapp_client: Optional[Callable[[str, str, str], bool]],
) -> dict:
    previous_owner_type = conversation.owner_type
    previous_owner_id = conversation.owner_id

    conversation.owner_type = "ai_agent"
    conversation.owner_id = AI_AGENT_NAME
    db.add(conversation)

    db.add(ConversationEvent(
        conversation_id=conversation.id,
        event_type="ai_auto_reclaimed_ownership",  # distinct from a manual hand-back -- see module docstring
        event_data={
            "previous_owner_type": previous_owner_type,
            "previous_owner_id": previous_owner_id,
            "elapsed_hours": elapsed_hours,
        },
        triggered_by="system",
    ))

    if previous_owner_type == "hr_user" and previous_owner_id:
        recipient = db.query(Users).filter(Users.UserID == previous_owner_id).first()
        if recipient:
            try:
                send_notification(
                    db, calling_context_tenant_id=recipient.tenant_id, recipient=recipient,
                    priority_tier="P1", channel_preference="IN_APP",
                    message=(
                        f"Conversation with candidate {candidate.candidateID} was "
                        f"automatically reassigned to Thunder after {elapsed_hours:.1f} hours "
                        f"without a reply -- you no longer own it."
                    ),
                )
            except Exception:
                pass  # best-effort -- never blocks the reclaim itself

    checkin_event = send_thunder_message(
        db, conversation, candidate, DEFAULT_RECLAIM_CHECKIN_MESSAGE,
        sender_type="ai_agent", whatsapp_client=whatsapp_client, auto_generated=True,
    )

    return {"action": "reclaimed", "elapsed_hours": elapsed_hours, "checkin_event_id": checkin_event.id}

def _nudge(
    db: Session, conversation: CandidateConversation, candidate: Candidate,
    *, elapsed_hours: float, whatsapp_client: Optional[Callable[[str, str, str], bool]],
) -> dict:
    if conversation.owner_type == "hr_user" and conversation.owner_id:
        event = send_thunder_message(
            db, conversation, candidate, DEFAULT_NUDGE_MESSAGE,
            sender_type="hr_user", sender_id=conversation.owner_id,
            whatsapp_client=whatsapp_client, auto_generated=True,
        )
    else:
        event = send_thunder_message(
            db, conversation, candidate, DEFAULT_NUDGE_MESSAGE,
            sender_type="ai_agent", whatsapp_client=whatsapp_client, auto_generated=True,
        )

    return {"action": "nudged", "elapsed_hours": elapsed_hours, "nudge_event_id": event.id}
