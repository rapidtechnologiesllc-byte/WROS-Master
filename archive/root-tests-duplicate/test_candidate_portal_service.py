"""
S-017/HRMS-0417 -- Candidate Self-Service Web Portal (service layer).

Real architecture adaptations under test:
- generate_portal_link_token() issues a real candidate JWT decodable by
  the same app.core.security.decode_access_token() every other
  candidate-authenticated route already uses -- no separate magic-link
  validate/exchange endpoint needed.
- Stage badge derives from CandidateConversation.status, not a
  fictional enum.
- get_portal_home()/get_portal_thread() read the cross-channel
  ConversationEvent log via get_conversation_thread(), so a WhatsApp
  message shows up in the candidate's own portal view too.
- get_portal_interviews()/build_ics()/create_reschedule_request() use
  the real app.models.user.Interview table.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import decode_access_token
from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.sla_breach import CandidateSLABreach
from app.models.user import Interview, Users

import app.services.candidate_portal_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateInfoForm.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__, Interview.__table__,
        CandidateSLABreach.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def seeded(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    db_session.add(owner)
    db_session.commit()

    candidate = Candidate(
        candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h",
        candidateFirstName="Priya", candidateLastName="Sharma",
    )
    db_session.add(candidate)
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="awaiting_candidate", owner_type="ai_agent", owner_id="thunder")
    db_session.add(conv)
    db_session.commit()

    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="ai_message_sent", event_data={"channel": "whatsapp", "body": "Hi Priya, are you open to new roles?"}, triggered_by="ai_agent"))
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={"channel": "portal", "body": "Yes, tell me more."}, triggered_by="candidate"))
    db_session.commit()

    interview = Interview(candidate_id="C-1", start_time=datetime.utcnow() + timedelta(days=2), end_time=datetime.utcnow() + timedelta(days=2, hours=1), meeting_link="https://meet.example.com/abc", status="Scheduled")
    db_session.add(interview)
    db_session.commit()

    return candidate, conv, interview


def test_generate_portal_link_token_decodes_as_real_candidate_jwt():
    token = svc.generate_portal_link_token("C-1")
    payload = decode_access_token(token)
    assert payload["sub"] == "C-1"
    assert payload["type"] == "candidate"


def test_generate_portal_link_url_points_at_frontend():
    url = svc.generate_portal_link_url("C-1")
    assert "/candidate/" in url
    token = url.split("/candidate/")[1]
    assert decode_access_token(token)["sub"] == "C-1"


def test_portal_home_stage_badge_and_pending_actions(db_session, seeded):
    candidate, conv, interview = seeded
    home = svc.get_portal_home(db_session, candidate)
    assert home["stage"]["label"] == "Awaiting Your Reply"
    assert home["stage"]["color"] == "amber"
    assert "Confirm your interview time" in home["pending_actions"]
    assert any("Mobile Number" in a for a in home["pending_actions"])


def test_portal_home_recent_messages_cross_channel(db_session, seeded):
    candidate, conv, interview = seeded
    home = svc.get_portal_home(db_session, candidate)
    channels = {m["channel"] for m in home["recent_messages"]}
    assert "WHATSAPP" in channels
    assert "PORTAL" in channels


def test_portal_thread_returns_full_conversation(db_session, seeded):
    candidate, conv, interview = seeded
    thread = svc.get_portal_thread(db_session, candidate)
    assert thread["conversation_id"] == conv.id
    assert len(thread["messages"]) == 2


def test_portal_interviews_only_future_scheduled(db_session, seeded):
    candidate, conv, interview = seeded
    past = Interview(candidate_id="C-1", start_time=datetime.utcnow() - timedelta(days=5), status="Scheduled")
    db_session.add(past)
    db_session.commit()

    interviews = svc.get_portal_interviews(db_session, candidate)
    assert len(interviews) == 1
    assert interviews[0]["id"] == interview.id
    assert interviews[0]["format"] == "video"


def test_build_ics_contains_vevent(db_session, seeded):
    candidate, conv, interview = seeded
    ics = svc.build_ics(interview, candidate)
    text = ics.decode("utf-8")
    assert "BEGIN:VEVENT" in text
    assert "END:VEVENT" in text
    assert interview.meeting_link in text


def test_reschedule_request_escalates_conversation(db_session, seeded):
    candidate, conv, interview = seeded
    result = svc.create_reschedule_request(db_session, candidate, interview.id, "Can we do the afternoon instead?")
    assert result["request_id"]
    db_session.refresh(conv)
    assert conv.escalation_state == "pending"

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "reschedule_requested").all()
    assert len(events) == 1
    assert events[0].event_data["interview_id"] == interview.id


def test_reschedule_request_rejects_interview_not_owned_by_candidate(db_session, seeded):
    candidate, conv, interview = seeded
    other = Candidate(candidateID="C-2", candidateEmail="c2@example.com", candidatePassword="h")
    db_session.add(other)
    db_session.commit()

    with pytest.raises(svc.PortalInterviewNotFound):
        svc.create_reschedule_request(db_session, other, interview.id, "note")
