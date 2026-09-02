"""
import logging
S-019/HRMS-0419 -- Conversation Summary Auto-Generation.

Real architecture adaptations under test (see conversation_summary_
service module docstring): last-20-messages reads ConversationEvent
(no conversation_messages table), known facts come from the real
Candidate row + get_missing_fields() (no candidate_memory table), the
real LLM is Gemini via an injectable llm_call (never the real network
in tests).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.user import Users

import app.services.conversation_summary_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateInfoForm.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__,
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
    candidate = Candidate(
        candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h",
        candidateFirstName="Priya", candidateLastName="Sharma", candidateJobTitle="Engineer",
    )
    db_session.add_all([owner, candidate])
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="awaiting_candidate", owner_type="ai_agent", owner_id="thunder")
    db_session.add(conv)
    db_session.commit()
    return candidate, conv


def _add_candidate_reply(db_session, conv, body="Here are my details"):
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={"channel": "email", "body": body}, triggered_by="candidate"))
    db_session.commit()


def test_should_generate_after_5th_reply_only(db_session, seeded):
    candidate, conv = seeded
    for i in range(4):
        _add_candidate_reply(db_session, conv, f"reply {i}")
        assert svc.should_generate_summary_after_reply(db_session, conv.id) is False
    _add_candidate_reply(db_session, conv, "reply 5")
    assert svc.should_generate_summary_after_reply(db_session, conv.id) is True


def test_generate_conversation_summary_success_stores_summary_and_timestamp(db_session, seeded):
    candidate, conv = seeded
    _add_candidate_reply(db_session, conv, "I have 5 years experience and can join in 30 days.")

    fake_summary = "Priya has 5 years experience and can join in 30 days. Profile is nearly complete. Engagement is high."
    result = svc.generate_conversation_summary(db_session, conv, candidate, llm_call=lambda prompt: fake_summary)
    db_session.commit()

    assert result == fake_summary
    db_session.refresh(conv)
    assert conv.summary == fake_summary
    assert conv.summary_generated_at is not None

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "SUMMARY_GENERATED").all()
    assert len(events) == 1
    assert events[0].event_data["summary"] == fake_summary


def test_summary_over_max_length_is_truncated(db_session, seeded):
    candidate, conv = seeded
    long_text = "x" * 500
    result = svc.generate_conversation_summary(db_session, conv, candidate, llm_call=lambda prompt: long_text)
    assert result is not None
    assert len(result) == svc.MAX_SUMMARY_LENGTH


def test_summary_under_min_length_regenerates_once_then_succeeds(db_session, seeded):
    candidate, conv = seeded
    attempts = []

    def flaky_llm(prompt):
        attempts.append(1)
        if len(attempts) == 1:
            return "too short"
        return "A properly detailed summary that clears the fifty character minimum easily."

    result = svc.generate_conversation_summary(db_session, conv, candidate, llm_call=flaky_llm)
    assert len(attempts) == 2
    assert result is not None
    assert len(result) >= svc.MIN_SUMMARY_LENGTH


def test_summary_still_too_short_after_regeneration_keeps_previous_and_logs_failure(db_session, seeded):
    candidate, conv = seeded
    conv.summary = "Previous good summary that should be retained on failure."
    db_session.commit()

    result = svc.generate_conversation_summary(db_session, conv, candidate, llm_call=lambda prompt: "short")
    db_session.commit()

    assert result is None
    db_session.refresh(conv)
    assert conv.summary == "Previous good summary that should be retained on failure."

    failures = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "SUMMARY_GENERATION_FAILED").all()
    assert len(failures) == 1


def test_llm_failure_keeps_previous_summary_and_logs_failure_no_crash(db_session, seeded):
    candidate, conv = seeded
    conv.summary = "Stable prior summary."
    db_session.commit()

    def broken_llm(prompt):
        raise RuntimeError("Gemini API down")

    result = svc.generate_conversation_summary(db_session, conv, candidate, llm_call=broken_llm)
    db_session.commit()

    assert result is None
    db_session.refresh(conv)
    assert conv.summary == "Stable prior summary."

    failures = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "SUMMARY_GENERATION_FAILED").all()
    assert len(failures) == 1


def test_maybe_generate_after_reply_noop_below_threshold(db_session, seeded):
    candidate, conv = seeded
    _add_candidate_reply(db_session, conv, "just one reply")

    called = []
    result = svc.maybe_generate_summary_after_reply(db_session, conv, candidate, llm_call=lambda p: called.append(1) or "should not be used")
    assert result is None
    assert called == []


def test_maybe_generate_after_reply_fires_at_threshold(db_session, seeded):
    candidate, conv = seeded
    for i in range(5):
        _add_candidate_reply(db_session, conv, f"reply {i}")

    fake_summary = "Real generated summary text that clears the fifty character minimum length easily."
    result = svc.maybe_generate_summary_after_reply(db_session, conv, candidate, llm_call=lambda p: fake_summary)
    db_session.commit()
    assert result == fake_summary


def test_maybe_generate_after_transition_always_generates(db_session, seeded):
    candidate, conv = seeded
    fake_summary = "Transition-triggered summary with enough characters to clear the minimum length bar."
    result = svc.maybe_generate_summary_after_transition(db_session, conv, candidate, llm_call=lambda p: fake_summary)
    db_session.commit()
    assert result == fake_summary


def test_known_facts_includes_missing_fields(db_session, seeded):
    candidate, conv = seeded
    text = svc._known_facts_text(db_session, candidate)
    assert "Priya" in text
    assert "Still missing" in text or "Profile is complete" in text
