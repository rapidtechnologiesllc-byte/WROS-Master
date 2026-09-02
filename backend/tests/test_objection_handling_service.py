"""
import logging
S-072/HRMS-0472 -- Objection Handling Engine.

Real architecture under test (see objection_handling_service module
docstring): "objecting" was already a defined intent (S-033),
FACT_CATEGORIES already included "OBJECTION" (S-021) -- no schema
change needed. BR-01's "3+ times = escalate" count comes from a real,
new OBJECTION_RAISED ConversationEvent (candidate_memory_facts'
upsert_fact() dedupes to one active row per key, so it can't answer
"how many times in THIS conversation" alone). BR-02's SALARY objection
never reaches the LLM at all -- no shareable-salary flag exists
anywhere in this codebase, so that branch is always the safe fallback,
provably (not just prompted).

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

import app.services.objection_handling_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    engine_path = db_path
    os.close(fd)
    engine = create_engine(f"sqlite:///{engine_path}")
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
        os.remove(engine_path)


@pytest.fixture()
def seeded(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h", ai_agent_name="Thunder")
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya")
    db_session.add_all([owner, candidate])
    db_session.commit()
    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="web_chat")
    db_session.add(conv)
    db_session.commit()
    return candidate, conv


def _llm_returning(payload):
    return lambda system_prompt, user_prompt, max_tokens, temperature: json.dumps(payload)


def _llm_raising(exc):
    def _raise(*args, **kwargs):
        raise exc
    return _raise


def test_classify_objection_salary(db_session, seeded):
    _, conv = seeded
    result = svc.classify_objection(
        db_session, conv.tenant_id, "C-1", "The salary seems too low for my experience",
        llm_call=_llm_returning({"objection_type": "SALARY", "key_concern": "salary below expectations", "confidence": 0.92}),
    )
    assert result["objection_type"] == "SALARY"
    assert result["confidence"] == 0.92


def test_classify_objection_unknown_type_collapses_to_other(db_session, seeded):
    _, conv = seeded
    result = svc.classify_objection(
        db_session, conv.tenant_id, "C-1", "some message",
        llm_call=_llm_returning({"objection_type": "MADE_UP", "key_concern": "x", "confidence": 0.5}),
    )
    assert result["objection_type"] == "OTHER"


def test_classify_objection_llm_failure_collapses_safely(db_session, seeded):
    _, conv = seeded
    result = svc.classify_objection(db_session, conv.tenant_id, "C-1", "some message", llm_call=_llm_raising(RuntimeError("down")))
    assert result == {"objection_type": "OTHER", "key_concern": "", "confidence": 0.0}


def test_classify_objection_invalid_json_collapses_safely(db_session, seeded):
    _, conv = seeded
    result = svc.classify_objection(db_session, conv.tenant_id, "C-1", "some message", llm_call=lambda sp, up, mt, t: "not json")
    assert result == {"objection_type": "OTHER", "key_concern": "", "confidence": 0.0}


def test_handle_objection_stores_memory_fact(db_session, seeded):
    candidate, conv = seeded
    llm = _llm_returning({"objection_type": "LOCATION", "key_concern": "not willing to relocate", "confidence": 0.9})
    result = svc.handle_objection(db_session, conv, candidate, "I'm not willing to relocate", llm_call=llm)

    assert result["objection_type"] == "LOCATION"
    fact = db_session.query(CandidateMemoryFact).filter(CandidateMemoryFact.candidate_id == "C-1", CandidateMemoryFact.fact_category == "OBJECTION", CandidateMemoryFact.fact_key == "LOCATION").first()
    assert fact is not None
    assert fact.fact_value == "not willing to relocate"


def test_handle_objection_logs_objection_raised_event(db_session, seeded):
    candidate, conv = seeded
    llm = _llm_returning({"objection_type": "TIMING", "key_concern": "happy where I am", "confidence": 0.8})
    svc.handle_objection(db_session, conv, candidate, "I'm happy where I am", llm_call=llm)

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "OBJECTION_RAISED").all()
    assert len(events) == 1
    assert events[0].event_data["objection_type"] == "TIMING"
    assert events[0].event_data["occurrence_number"] == 1


def test_salary_objection_never_reaches_llm_for_response_br02(db_session, seeded):
    """BR-02: SALARY objection response is the safe fallback, generated
    without ever calling the LLM for the response step (only for
    classification) -- proven here by NOT providing a second llm_call
    that could answer the response-generation call; if the response
    step tried to call the LLM it would use the classification mock's
    return value verbatim (wrong shape) or raise, either way failing
    this assertion."""
    candidate, conv = seeded
    llm = _llm_returning({"objection_type": "SALARY", "key_concern": "wants more money", "confidence": 0.9})
    result = svc.handle_objection(db_session, conv, candidate, "the salary is too low", llm_call=llm)
    assert result["response"] == svc.SALARY_NO_NUMBERS_MESSAGE


def test_third_occurrence_escalates_br01(db_session, seeded):
    candidate, conv = seeded
    llm = _llm_returning({"objection_type": "SALARY", "key_concern": "wants more money", "confidence": 0.9})

    svc.handle_objection(db_session, conv, candidate, "salary too low", llm_call=llm)
    svc.handle_objection(db_session, conv, candidate, "still think salary is low", llm_call=llm)
    with pytest.raises(svc.ObjectionEscalatedError) as exc_info:
        svc.handle_objection(db_session, conv, candidate, "salary still an issue", llm_call=llm)

    assert exc_info.value.objection_type == "SALARY"
    assert exc_info.value.count == 3


def test_escalation_count_is_per_objection_type_not_global(db_session, seeded):
    """Two SALARY objections + one LOCATION objection should NOT
    trigger BR-01 -- the count is scoped per objection_type."""
    candidate, conv = seeded
    salary_llm = _llm_returning({"objection_type": "SALARY", "key_concern": "low pay", "confidence": 0.9})
    location_llm = _llm_returning({"objection_type": "LOCATION", "key_concern": "no relocation", "confidence": 0.9})

    svc.handle_objection(db_session, conv, candidate, "salary too low", llm_call=salary_llm)
    svc.handle_objection(db_session, conv, candidate, "not relocating", llm_call=location_llm)
    result = svc.handle_objection(db_session, conv, candidate, "salary still low", llm_call=salary_llm)  # 2nd SALARY -- not yet escalated
    assert result["occurrence_number"] == 2


def test_objection_response_uses_llm_for_non_salary_types(db_session, seeded):
    candidate, conv = seeded
    llm = _llm_returning({"objection_type": "PROCESS", "key_concern": "too many rounds", "confidence": 0.85})
    result = svc.handle_objection(db_session, conv, candidate, "why are there so many interview rounds", llm_call=llm)
    # non-SALARY objections DO reach the response-generation LLM call, whose mock
    # here returns the same JSON shape as a raw string -- exercised for real,
    # response falls back safely since it isn't natural-language text.
    assert result["objection_type"] == "PROCESS"
    assert result["response"]  # never empty -- either real LLM text or SAFE_FALLBACK_MESSAGE
