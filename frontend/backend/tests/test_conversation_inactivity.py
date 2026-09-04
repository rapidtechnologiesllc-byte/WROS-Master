"""
Proves the conversation-inactivity safety net:

  - business_hours_elapsed()'s weekend-pause math (Friday 21:00 ->
    Monday 09:00), verified against the exact examples worked through
    with Avinash before building this.
  - Candidate-silent-on-human-owner -> Thunder reclaims ownership,
    logs a distinct ai_auto_reclaimed_ownership event (not a manual
    hand-back), notifies the previous owner, and immediately sends a
    candidate-facing check-in.
  - Staff-silent-on-candidate -> an automated nudge goes out attributed
    as the current owner's own message (auto_generated=True internally),
    or as Thunder directly if Thunder already owns.
  - The 09:00-21:00 candidate-local send window holds an eligible
    action rather than firing outside it.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.user import Users
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent, CandidateAIAssignment
from app.models.consent import ConsentRecord
from app.models.notification import Notification

from app.services.ai_conversation_service import AI_AGENT_NAME
import app.services.whatsapp_routing_service as routing
from app.services.conversation_inactivity_service import (
    business_hours_elapsed,
    get_last_message_event,
    evaluate_conversation_inactivity,
    INACTIVITY_THRESHOLD_HOURS,
)


@pytest.fixture(autouse=True)
def _default_whatsapp_number(monkeypatch):
    monkeypatch.setattr(routing, "DEFAULT_WHATSAPP_NUMBER", "+10005550000")


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__, CandidateAIAssignment.__table__,
        Notification.__table__, ConsentRecord.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


# ---------------------------------------------------------------------------
# business_hours_elapsed -- the timer model itself
# ---------------------------------------------------------------------------

def test_elapsed_matches_raw_hours_when_no_weekend_crossed():
    start = datetime(2026, 2, 2, 15, 0)   # Monday 3pm
    end = datetime(2026, 2, 3, 21, 0)     # Tuesday 9pm -- 30 raw hours later
    assert business_hours_elapsed(start, end) == 30.0


def test_elapsed_pauses_across_the_weekend():
    friday_6pm = datetime(2026, 2, 6, 18, 0)
    monday_9am = datetime(2026, 2, 9, 9, 0)
    # 3 counted hours (Fri 18:00-21:00), then paused through the weekend.
    assert business_hours_elapsed(friday_6pm, monday_9am) == 3.0


def test_elapsed_zero_when_end_before_start():
    start = datetime(2026, 2, 2, 15, 0)
    end = datetime(2026, 2, 2, 10, 0)
    assert business_hours_elapsed(start, end) == 0.0


def test_friday_evening_message_reaches_threshold_tuesday_noon():
    friday_6pm = datetime(2026, 2, 6, 18, 0)
    # 3h Friday + 27h resuming Monday 9am = 30h at Tuesday 12:00.
    tuesday_noon = datetime(2026, 2, 10, 12, 0)
    assert business_hours_elapsed(friday_6pm, tuesday_noon) == INACTIVITY_THRESHOLD_HOURS


# ---------------------------------------------------------------------------
# Fixtures for the full evaluate_conversation_inactivity() flow
# ---------------------------------------------------------------------------

@pytest.fixture()
def fixtures(db_session):
    org_owner = Users(UserID="U-ORG", UserRole="Admin", UserEmail="admin@blitzenx.com", UserPassword="h")
    recruiter = Users(UserID="U-REC", UserRole="Recruiter", UserEmail="rec@blitzenx.com", UserPassword="h")
    db_session.add_all([org_owner, recruiter])
    db_session.commit()

    candidate = Candidate(
        candidateID="C-001", candidateEmail="cand@example.com", candidatePassword="h",
        candidateMobile="+19995551234", timezone="Asia/Kolkata",
    )
    db_session.add(candidate)
    db_session.commit()

    conversation = CandidateConversation(
        tenant_id=org_owner.UserID, candidate_id=candidate.candidateID,
        status="open", ai_agent_name=AI_AGENT_NAME, channel_preference="whatsapp",
        owner_type="ai_agent", owner_id=AI_AGENT_NAME,
    )
    db_session.add(conversation)
    db_session.commit()

    # Thunder's send gate (app.services.thunder_service.send_thunder_message)
    # requires an active whatsapp_outreach consent record for every send,
    # including this safety net's automated reclaim/nudge sends.
    db_session.add(ConsentRecord(
        subject_type="candidate", subject_id=candidate.candidateID,
        consent_type="whatsapp_outreach", consent_given=True,
    ))
    db_session.commit()

    return org_owner, recruiter, candidate, conversation


def _add_message_event(db, conversation, *, event_type, triggered_by, created_at):
    event = ConversationEvent(
        conversation_id=conversation.id, event_type=event_type,
        event_data={"channel": "whatsapp"}, triggered_by=triggered_by,
        created_at=created_at,
    )
    db.add(event)
    db.commit()
    return event


# Monday 2026-02-02 06:30 UTC == 12:00 IST -- a safely mid-window timestamp.
LAST_MESSAGE_UTC = datetime(2026, 2, 2, 6, 30)


# ---------------------------------------------------------------------------
# get_last_message_event
# ---------------------------------------------------------------------------

def test_no_messages_returns_none(db_session, fixtures):
    org_owner, recruiter, candidate, conversation = fixtures
    assert get_last_message_event(db_session, conversation) is None


def test_ignores_non_message_event_types(db_session, fixtures):
    org_owner, recruiter, candidate, conversation = fixtures
    _add_message_event(db_session, conversation, event_type="candidate_reply", triggered_by="candidate", created_at=LAST_MESSAGE_UTC)
    db_session.add(ConversationEvent(
        conversation_id=conversation.id, event_type="field_check", event_data={}, triggered_by="ai_agent",
        created_at=LAST_MESSAGE_UTC + timedelta(hours=1),
    ))
    db_session.commit()

    last = get_last_message_event(db_session, conversation)
    assert last.event_type == "candidate_reply"


# ---------------------------------------------------------------------------
# evaluate_conversation_inactivity -- too early / held / reclaim / nudge
# ---------------------------------------------------------------------------

def test_no_action_when_no_messages_yet(db_session, fixtures):
    org_owner, recruiter, candidate, conversation = fixtures
    result = evaluate_conversation_inactivity(db_session, conversation, candidate, now=LAST_MESSAGE_UTC)
    assert result["action"] == "none"


def test_no_action_when_under_threshold(db_session, fixtures):
    org_owner, recruiter, candidate, conversation = fixtures
    _add_message_event(db_session, conversation, event_type="candidate_reply", triggered_by="candidate", created_at=LAST_MESSAGE_UTC)

    now = LAST_MESSAGE_UTC + timedelta(hours=10)  # well under 30
    result = evaluate_conversation_inactivity(db_session, conversation, candidate, now=now)
    assert result["action"] == "none"
    assert result["elapsed_hours"] < INACTIVITY_THRESHOLD_HOURS


def test_held_when_threshold_met_but_outside_send_window(db_session, fixtures):
    org_owner, recruiter, candidate, conversation = fixtures
    _add_message_event(db_session, conversation, event_type="candidate_reply", triggered_by="candidate", created_at=LAST_MESSAGE_UTC)

    # LAST_MESSAGE_UTC + 35h -> Tuesday 2026-02-03 17:30 UTC == 23:00 IST -- outside 09:00-21:00.
    now = LAST_MESSAGE_UTC + timedelta(hours=35)
    result = evaluate_conversation_inactivity(db_session, conversation, candidate, now=now)
    assert result["action"] == "held"
    assert result["next_eligible_at"] is not None


def test_reclaim_when_candidate_silent_on_human_owner(db_session, fixtures):
    org_owner, recruiter, candidate, conversation = fixtures
    conversation.owner_type = "hr_user"
    conversation.owner_id = recruiter.UserID
    db_session.commit()

    _add_message_event(db_session, conversation, event_type="candidate_reply", triggered_by="candidate", created_at=LAST_MESSAGE_UTC)

    # +31h -> Tuesday 2026-02-03 13:30 UTC == 19:00 IST -- within window.
    now = LAST_MESSAGE_UTC + timedelta(hours=31)
    result = evaluate_conversation_inactivity(
        db_session, conversation, candidate, now=now,
        whatsapp_client=lambda to, frm, body: True,
    )
    db_session.commit()

    assert result["action"] == "reclaimed"
    assert conversation.owner_type == "ai_agent"
    assert conversation.owner_id == AI_AGENT_NAME

    reclaim_events = db_session.query(ConversationEvent).filter(
        ConversationEvent.conversation_id == conversation.id,
        ConversationEvent.event_type == "ai_auto_reclaimed_ownership",
    ).all()
    assert len(reclaim_events) == 1
    assert reclaim_events[0].event_data["previous_owner_id"] == recruiter.UserID
    assert reclaim_events[0].triggered_by == "system"  # not a manual hand-back

    checkin_events = db_session.query(ConversationEvent).filter(
        ConversationEvent.conversation_id == conversation.id,
        ConversationEvent.event_type == "ai_message_sent",
    ).all()
    assert len(checkin_events) == 1
    assert checkin_events[0].event_data["auto_generated"] is True

    # Previous owner was notified.
    notifications = db_session.query(Notification).filter(Notification.recipient_id == recruiter.UserID).all()
    assert len(notifications) == 1
    assert notifications[0].priority_tier == "P1"


def test_nudge_when_staff_silent_on_candidate_with_human_owner(db_session, fixtures):
    org_owner, recruiter, candidate, conversation = fixtures
    conversation.owner_type = "hr_user"
    conversation.owner_id = recruiter.UserID
    db_session.commit()

    _add_message_event(db_session, conversation, event_type="hr_message_sent", triggered_by="hr_user", created_at=LAST_MESSAGE_UTC)

    now = LAST_MESSAGE_UTC + timedelta(hours=31)
    result = evaluate_conversation_inactivity(
        db_session, conversation, candidate, now=now,
        whatsapp_client=lambda to, frm, body: True,
    )
    db_session.commit()

    assert result["action"] == "nudged"
    # Ownership unchanged -- still the same recruiter, per HRMS-0410's model.
    assert conversation.owner_type == "hr_user"
    assert conversation.owner_id == recruiter.UserID

    nudge_events = db_session.query(ConversationEvent).filter(
        ConversationEvent.conversation_id == conversation.id,
        ConversationEvent.event_type == "hr_message_sent",
    ).order_by(ConversationEvent.id.desc()).all()
    # 2 total: the seeded message (logged directly, not via send_whatsapp_message)
    # plus the nudge itself.
    assert len(nudge_events) == 2
    assert nudge_events[0].event_data["auto_generated"] is True
    assert nudge_events[0].triggered_by == "hr_user"  # attributed as the recruiter's own message


def test_nudge_sent_as_thunder_when_ai_owns(db_session, fixtures):
    org_owner, recruiter, candidate, conversation = fixtures
    assert conversation.owner_type == "ai_agent"

    _add_message_event(db_session, conversation, event_type="ai_message_sent", triggered_by="ai_agent", created_at=LAST_MESSAGE_UTC)

    now = LAST_MESSAGE_UTC + timedelta(hours=31)
    result = evaluate_conversation_inactivity(
        db_session, conversation, candidate, now=now,
        whatsapp_client=lambda to, frm, body: True,
    )
    db_session.commit()

    assert result["action"] == "nudged"
    nudge_events = db_session.query(ConversationEvent).filter(
        ConversationEvent.conversation_id == conversation.id,
        ConversationEvent.event_type == "ai_message_sent",
    ).order_by(ConversationEvent.id.desc()).all()
    assert nudge_events[0].triggered_by == "ai_agent"
    assert nudge_events[0].event_data["auto_generated"] is True
