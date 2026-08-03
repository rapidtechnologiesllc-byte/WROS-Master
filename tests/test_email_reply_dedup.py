"""
S-003/HRMS-0403 -- real gaps fixed in the existing MS Graph email-reply
pipeline (app.services.ai_conversation_service.process_candidate_reply):
message_id deduplication (BR-01) and the empty-body placeholder (BR-03).

This system's real inbound-email path is the scheduled MS Graph poll
(poll_all_awaiting_candidates, every 15 min) plus the webhook-with-
known-candidate-id endpoint -- not a SendGrid/Mailgun push webhook, per
the "requirement is a direction, not the literal spec" standing rule.
Plain-text extraction (BR-02) was already correct (_parse_graph_message
strips HTML/decodes entities) -- not retested here.

get_missing_fields is monkeypatched to return [] so these tests only
exercise the dedup/placeholder logic added, not the full Gemini
extraction pipeline (covered elsewhere).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.ai_conversation_service as svc
from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.candidate_ghosting_status import CandidateGhostingStatus
from app.models.candidate_memory import CandidateMemory, CandidateMemoryFact
from app.models.follow_up_schedule import FollowUpSchedule
from app.models.user import Users


@pytest.fixture(autouse=True)
def _stub_pipeline(monkeypatch):
    """Keeps the conversation open across multiple calls (so dedup can
    be tested against a second message on the SAME conversation) by
    reporting one field still missing, and stubs the Gemini-calling
    extraction pipeline so these tests stay scoped to dedup/placeholder
    logic -- not a real LLM call."""
    monkeypatch.setattr(
        svc, "get_missing_fields",
        lambda candidate, db: [{"field": "candidateGender", "label": "Gender", "source": "candidate"}],
    )
    monkeypatch.setattr(
        svc, "run_reply_pipeline",
        lambda **kwargs: {"updated_fields": [], "skipped_fields": [], "still_missing": [{"field": "candidateGender", "label": "Gender"}]},
    )


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateInfoForm.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__, CandidateAIAssignment.__table__,
        CandidateMemory.__table__, CandidateMemoryFact.__table__, FollowUpSchedule.__table__,
        CandidateGhostingStatus.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def candidate_with_conversation(db_session):
    owner = Users(UserID="U-ORG", UserRole="Admin", UserEmail="admin@blitzenx.com", UserPassword="h")
    db_session.add(owner)
    db_session.commit()

    candidate = Candidate(candidateID="C-100", candidateEmail="cand@example.com", candidatePassword="h")
    db_session.add(candidate)
    db_session.commit()

    conversation = CandidateConversation(
        tenant_id="U-ORG", candidate_id="C-100", status="open",
        owner_type="ai_agent", owner_id=svc.AI_AGENT_NAME,
    )
    db_session.add(conversation)
    db_session.commit()
    return candidate, conversation


def test_first_reply_is_logged(db_session, candidate_with_conversation):
    result = svc.process_candidate_reply(
        "C-100", db_session, raw_reply_text="I'm interested, please share more details.",
        message_id="graph-msg-001",
    )
    assert result["status"] == "partial"

    events = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "candidate_reply").all()
    assert len(events) == 1
    assert events[0].event_data["message_id"] == "graph-msg-001"


def test_duplicate_message_id_is_not_logged_twice(db_session, candidate_with_conversation):
    svc.process_candidate_reply("C-100", db_session, raw_reply_text="First reply", message_id="graph-msg-DUP")
    result = svc.process_candidate_reply("C-100", db_session, raw_reply_text="First reply", message_id="graph-msg-DUP")

    assert result["status"] == "duplicate_message"
    events = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "candidate_reply").all()
    assert len(events) == 1


def test_different_message_ids_both_logged(db_session, candidate_with_conversation):
    svc.process_candidate_reply("C-100", db_session, raw_reply_text="First", message_id="graph-msg-A")
    svc.process_candidate_reply("C-100", db_session, raw_reply_text="Second", message_id="graph-msg-B")

    events = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "candidate_reply").all()
    assert len(events) == 2


def test_empty_body_stores_placeholder_not_null(db_session, candidate_with_conversation):
    svc.process_candidate_reply("C-100", db_session, raw_reply_text="", message_id="graph-msg-EMPTY")

    event = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "candidate_reply").first()
    assert event.event_data["reply_preview"] == "[Non-text email received]"


def test_whitespace_only_body_stores_placeholder(db_session, candidate_with_conversation):
    svc.process_candidate_reply("C-100", db_session, raw_reply_text="   \n  ", message_id="graph-msg-WS")

    event = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "candidate_reply").first()
    assert event.event_data["reply_preview"] == "[Non-text email received]"
