"""
import logging
S-033/HRMS-0433 -- Intent Detection Engine.

Real architecture under test (see detect_intent_service module
docstring): callLLM()/getContextForPrompt() are S-031/S-032's real,
already-tested functions; BR-01 collapses LLM failure/invalid
JSON/unknown intent value to {intent: unclear, confidence: 0.0} and
never raises; BR-03 logs INTENT_DETECTED to conversation_events on
every path, success or failure; get_intent_routing_decision() reports
LIVE/NOT_WIRED/NOT_BUILT honestly rather than invoking handlers that
don't exist yet (HRMS-0472/HRMS-0447 aren't built this round).

Throwaway SQLite -- never the real database.
"""
import json
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_field_skip import CandidateFieldSkip
from app.models.candidate_memory import CandidateMemory, CandidateMemoryFact
from app.models.prompt_execution_log import PromptExecutionLog
from app.models.sla_breach import CandidateSLABreach
from app.models.user import Users, Jobs

import app.services.detect_intent_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateInfoForm.__table__, Jobs.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__, CandidateFieldSkip.__table__,
        CandidateMemory.__table__, CandidateMemoryFact.__table__, CandidateSLABreach.__table__,
        PromptExecutionLog.__table__,
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
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h", ai_agent_name="Thunder")
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya")
    db_session.add_all([owner, candidate])
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none")
    db_session.add(conv)
    db_session.commit()
    return candidate, conv


def _llm_returning(payload_dict):
    return lambda sp, up, mt, t: json.dumps(payload_dict)


def _llm_raising(exc):
    def _raise(sp, up, mt, t):
        raise exc
    return _raise


# ── TC-001..TC-003: correct intent+confidence for real examples ──────

def test_detects_answering_question(db_session, seeded):
    candidate, conv = seeded
    result = svc.detect_intent(
        db_session, "U-ORG", "C-1", "My notice period is 30 days.",
        conversation_id=conv.id, llm_call=_llm_returning({"intent": "answering_question", "confidence": 0.92}),
    )
    assert result["intent"] == "answering_question"
    assert result["confidence"] >= 0.8


def test_detects_asking_question(db_session, seeded):
    candidate, conv = seeded
    result = svc.detect_intent(
        db_session, "U-ORG", "C-1", "What is the salary range for this role?",
        conversation_id=conv.id, llm_call=_llm_returning({"intent": "asking_question", "confidence": 0.88}),
    )
    assert result["intent"] == "asking_question"
    assert result["confidence"] >= 0.7


def test_detects_not_interested(db_session, seeded):
    candidate, conv = seeded
    result = svc.detect_intent(
        db_session, "U-ORG", "C-1", "Not interested, please remove me.",
        conversation_id=conv.id, llm_call=_llm_returning({"intent": "not_interested", "confidence": 0.95}),
    )
    assert result["intent"] == "not_interested"
    assert result["confidence"] >= 0.9


def test_detects_scheduling_request(db_session, seeded):
    candidate, conv = seeded
    result = svc.detect_intent(
        db_session, "U-ORG", "C-1", "Can we reschedule the interview to next week?",
        conversation_id=conv.id, llm_call=_llm_returning({"intent": "scheduling_request", "confidence": 0.85}),
    )
    assert result["intent"] == "scheduling_request"


# ── TC-004: LLM failure returns unclear/0.0, never crashes ───────────

def test_llm_failure_returns_unclear_never_raises(db_session, seeded):
    candidate, conv = seeded
    result = svc.detect_intent(
        db_session, "U-ORG", "C-1", "Some message",
        conversation_id=conv.id, llm_call=_llm_raising(RuntimeError("Gemini down")),
    )
    assert result == {"intent": "unclear", "confidence": 0.0, "raw_response": None, "secondary_intent": None}


def test_invalid_json_returns_unclear_never_raises(db_session, seeded):
    candidate, conv = seeded
    result = svc.detect_intent(
        db_session, "U-ORG", "C-1", "Some message",
        conversation_id=conv.id, llm_call=lambda sp, up, mt, t: "not json at all",
    )
    assert result["intent"] == "unclear"
    assert result["confidence"] == 0.0


def test_unknown_intent_value_mapped_to_unclear(db_session, seeded):
    candidate, conv = seeded
    result = svc.detect_intent(
        db_session, "U-ORG", "C-1", "Some message",
        conversation_id=conv.id, llm_call=_llm_returning({"intent": "totally_made_up", "confidence": 0.9}),
    )
    assert result["intent"] == "unclear"


def test_unknown_candidate_returns_unclear_never_raises(db_session, seeded):
    """BR-01 applies even when context assembly itself fails (candidate not found)."""
    result = svc.detect_intent(
        db_session, "U-ORG", "NOPE", "Some message",
        conversation_id=None, llm_call=_llm_returning({"intent": "answering_question", "confidence": 0.9}),
    )
    assert result["intent"] == "unclear"
    assert result["confidence"] == 0.0


# ── BR-03: every message logged, success or failure ──────────────────

def test_intent_logged_on_success(db_session, seeded):
    candidate, conv = seeded
    svc.detect_intent(
        db_session, "U-ORG", "C-1", "My notice period is 30 days.",
        conversation_id=conv.id, message_event_id=42, llm_call=_llm_returning({"intent": "answering_question", "confidence": 0.9}),
    )
    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "INTENT_DETECTED").all()
    assert len(events) == 1
    assert events[0].event_data["intent"] == "answering_question"
    assert events[0].event_data["confidence"] == 0.9
    assert events[0].event_data["message_id"] == 42


def test_intent_logged_on_llm_failure(db_session, seeded):
    candidate, conv = seeded
    svc.detect_intent(
        db_session, "U-ORG", "C-1", "Some message",
        conversation_id=conv.id, llm_call=_llm_raising(RuntimeError("down")),
    )
    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "INTENT_DETECTED").all()
    assert len(events) == 1
    assert events[0].event_data["intent"] == "unclear"


def test_no_conversation_id_skips_logging_without_raising(db_session, seeded):
    candidate, conv = seeded
    result = svc.detect_intent(
        db_session, "U-ORG", "C-1", "Some message", conversation_id=None,
        llm_call=_llm_returning({"intent": "unclear", "confidence": 0.1}),
    )
    assert result["intent"] == "unclear"


# ── Step 4: compound-message secondary indicator ──────────────────────

def test_compound_message_detects_secondary_asking_question(db_session, seeded):
    candidate, conv = seeded
    result = svc.detect_intent(
        db_session, "U-ORG", "C-1", "My notice is 30 days but do you know the salary?",
        conversation_id=conv.id, llm_call=_llm_returning({"intent": "answering_question", "confidence": 0.8}),
    )
    assert result["intent"] == "answering_question"
    assert result["secondary_intent"] == "asking_question"


def test_no_question_mark_no_secondary_intent(db_session, seeded):
    candidate, conv = seeded
    result = svc.detect_intent(
        db_session, "U-ORG", "C-1", "My notice is 30 days.",
        conversation_id=conv.id, llm_call=_llm_returning({"intent": "answering_question", "confidence": 0.8}),
    )
    assert result["secondary_intent"] is None


# ── get_intent_routing_decision(): honest routing, no fake handlers ───

def test_routing_not_interested_is_live_graceful_exit(db_session):
    decision = svc.get_intent_routing_decision("not_interested")
    assert decision["status"] == "LIVE"


def test_routing_objecting_reports_not_built():
    decision = svc.get_intent_routing_decision("objecting")
    assert decision["status"] == "NOT_BUILT"


def test_routing_scheduling_request_reports_not_wired():
    # S-047-051 are all built now (availability collection, calendar
    # matching, confirmation, reminders, reschedule), but none has a
    # live trigger yet -- see detect_intent_service's own routing note.
    decision = svc.get_intent_routing_decision("scheduling_request")
    assert decision["status"] == "NOT_WIRED"


def test_routing_document_sharing_reports_not_wired():
    decision = svc.get_intent_routing_decision("document_sharing")
    assert decision["status"] == "NOT_WIRED"


def test_routing_unknown_intent_falls_back_to_unclear_routing():
    decision = svc.get_intent_routing_decision("bogus")
    assert decision == svc.INTENT_ROUTING["unclear"]


# ── Confidence clamping ────────────────────────────────────────────────

def test_confidence_out_of_range_is_clamped(db_session, seeded):
    candidate, conv = seeded
    result = svc.detect_intent(
        db_session, "U-ORG", "C-1", "Some message",
        conversation_id=conv.id, llm_call=_llm_returning({"intent": "asking_question", "confidence": 1.7}),
    )
    assert result["confidence"] == 1.0
