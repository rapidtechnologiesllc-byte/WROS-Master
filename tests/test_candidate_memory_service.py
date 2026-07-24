"""
S-021/HRMS-0421 -- Candidate Memory Store.

Real architecture adaptations under test (see candidate_memory.py and
candidate_memory_service.py module docstrings): Integer PKs, real
tenant_id=UserID convention, source_message_id FKs into
ConversationEvent, BR-02's versioning enforced at the application
layer (not a DB unique constraint), 200-500 WORD summary validation
(not chars), LLM is injectable Gemini.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_memory import CandidateMemory, CandidateMemoryFact
from app.models.user import Users

import app.services.candidate_memory_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        CandidateMemory.__table__, CandidateMemoryFact.__table__,
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
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya", candidateLastName="Sharma")
    db_session.add_all([owner, candidate])
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="thunder")
    db_session.add(conv)
    db_session.commit()
    return candidate, conv


def test_upsert_fact_creates_memory_row_on_first_insertion(db_session, seeded):
    candidate, conv = seeded
    assert db_session.query(CandidateMemory).filter(CandidateMemory.candidate_id == "C-1").first() is None

    svc.upsert_fact(db_session, "C-1", "U-ORG", "SALARY", "expected_ctc", "24 LPA", confidence=0.9)
    db_session.commit()

    memory = db_session.query(CandidateMemory).filter(CandidateMemory.candidate_id == "C-1").first()
    assert memory is not None


def test_upsert_fact_inserts_new_fact_with_all_fields(db_session, seeded):
    candidate, conv = seeded
    fact = svc.upsert_fact(db_session, "C-1", "U-ORG", "SALARY", "expected_ctc", "24 LPA", confidence=0.9)
    db_session.commit()

    assert fact.fact_category == "SALARY"
    assert fact.fact_key == "expected_ctc"
    assert fact.fact_value == "24 LPA"
    assert fact.confidence == 0.9
    assert fact.is_active is True


def test_upsert_fact_rejects_invalid_category(db_session, seeded):
    candidate, conv = seeded
    with pytest.raises(svc.InvalidFactCategory):
        svc.upsert_fact(db_session, "C-1", "U-ORG", "NOT_A_REAL_CATEGORY", "key", "value")


def test_upsert_fact_versions_on_changed_value(db_session, seeded):
    candidate, conv = seeded
    first = svc.upsert_fact(db_session, "C-1", "U-ORG", "SALARY", "expected_ctc", "24 LPA", confidence=0.9)
    db_session.commit()
    second = svc.upsert_fact(db_session, "C-1", "U-ORG", "SALARY", "expected_ctc", "28 LPA", confidence=0.95)
    db_session.commit()

    db_session.refresh(first)
    assert first.is_active is False  # BR-02: old record deactivated
    assert second.is_active is True
    assert second.fact_value == "28 LPA"

    all_rows = db_session.query(CandidateMemoryFact).filter(CandidateMemoryFact.candidate_id == "C-1").all()
    assert len(all_rows) == 2  # history preserved, not overwritten


def test_upsert_fact_same_value_refreshes_in_place_no_history_churn(db_session, seeded):
    candidate, conv = seeded
    svc.upsert_fact(db_session, "C-1", "U-ORG", "SALARY", "expected_ctc", "24 LPA", confidence=0.7)
    db_session.commit()
    svc.upsert_fact(db_session, "C-1", "U-ORG", "SALARY", "expected_ctc", "24 LPA", confidence=0.95)
    db_session.commit()

    all_rows = db_session.query(CandidateMemoryFact).filter(CandidateMemoryFact.candidate_id == "C-1").all()
    assert len(all_rows) == 1
    assert all_rows[0].confidence == 0.95


def test_get_memory_returns_all_active_facts(db_session, seeded):
    candidate, conv = seeded
    svc.upsert_fact(db_session, "C-1", "U-ORG", "SALARY", "expected_ctc", "24 LPA")
    svc.upsert_fact(db_session, "C-1", "U-ORG", "PREFERENCE", "domain", "Healthcare")
    svc.upsert_fact(db_session, "C-1", "U-ORG", "CONSTRAINT", "relocation", "Cannot relocate to Austin")
    db_session.commit()

    memory = svc.get_memory(db_session, "C-1", "U-ORG")
    assert len(memory["facts"]) == 3
    keys = {f["key"] for f in memory["facts"]}
    assert keys == {"expected_ctc", "domain", "relocation"}


def test_get_memory_returns_null_summary_when_none_generated(db_session, seeded):
    candidate, conv = seeded
    svc.upsert_fact(db_session, "C-1", "U-ORG", "SALARY", "expected_ctc", "24 LPA")
    db_session.commit()

    memory = svc.get_memory(db_session, "C-1", "U-ORG")
    assert memory["summary"] is None


def test_get_memory_no_facts_returns_empty(db_session, seeded):
    candidate, conv = seeded
    memory = svc.get_memory(db_session, "C-1", "U-ORG")
    assert memory == {"summary": None, "last_updated": None, "facts": []}


def test_get_memory_flags_low_confidence_facts(db_session, seeded):
    candidate, conv = seeded
    svc.upsert_fact(db_session, "C-1", "U-ORG", "SALARY", "expected_ctc", "24 LPA", confidence=0.5)
    db_session.commit()

    memory = svc.get_memory(db_session, "C-1", "U-ORG")
    assert memory["facts"][0]["is_low_confidence"] is True  # BR-03


def _valid_summary_text(word_count=250):
    return " ".join(["word"] * word_count)


def test_update_memory_summary_success_stores_summary(db_session, seeded):
    candidate, conv = seeded
    svc.upsert_fact(db_session, "C-1", "U-ORG", "SALARY", "expected_ctc", "24 LPA", confidence=0.9)
    db_session.commit()

    summary_text = _valid_summary_text(300)
    result = svc.update_memory_summary(db_session, "C-1", "U-ORG", llm_call=lambda p: summary_text)

    assert result == summary_text
    memory = db_session.query(CandidateMemory).filter(CandidateMemory.candidate_id == "C-1").first()
    assert memory.summary == summary_text
    assert memory.last_updated is not None
    assert memory.version == 2


def test_update_memory_summary_out_of_range_keeps_previous_and_logs_failure(db_session, seeded):
    candidate, conv = seeded
    svc.upsert_fact(db_session, "C-1", "U-ORG", "SALARY", "expected_ctc", "24 LPA")
    db_session.commit()

    good_summary = _valid_summary_text(300)
    svc.update_memory_summary(db_session, "C-1", "U-ORG", llm_call=lambda p: good_summary)

    too_short = "way too short"
    result = svc.update_memory_summary(db_session, "C-1", "U-ORG", llm_call=lambda p: too_short)

    assert result is None
    memory = db_session.query(CandidateMemory).filter(CandidateMemory.candidate_id == "C-1").first()
    assert memory.summary == good_summary  # unchanged

    failures = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "MEMORY_SUMMARY_FAILED").all()
    assert len(failures) == 1


def test_update_memory_summary_llm_error_keeps_previous_no_crash(db_session, seeded):
    candidate, conv = seeded
    svc.upsert_fact(db_session, "C-1", "U-ORG", "SALARY", "expected_ctc", "24 LPA")
    db_session.commit()

    def broken_llm(prompt):
        raise RuntimeError("Gemini down")

    result = svc.update_memory_summary(db_session, "C-1", "U-ORG", llm_call=broken_llm)
    assert result is None

    failures = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "MEMORY_SUMMARY_FAILED").all()
    assert len(failures) == 1


def test_should_update_summary_true_when_no_memory_yet(db_session, seeded):
    candidate, conv = seeded
    assert svc.should_update_summary(db_session, "C-1", "U-ORG") is True


def test_should_update_summary_true_after_5_new_facts(db_session, seeded):
    candidate, conv = seeded
    summary_text = _valid_summary_text(300)
    svc.upsert_fact(db_session, "C-1", "U-ORG", "SALARY", "expected_ctc", "24 LPA")
    db_session.commit()
    svc.update_memory_summary(db_session, "C-1", "U-ORG", llm_call=lambda p: summary_text)

    for i in range(4):
        svc.upsert_fact(db_session, "C-1", "U-ORG", "SKILL", f"skill_{i}", f"value_{i}")
    db_session.commit()
    assert svc.should_update_summary(db_session, "C-1", "U-ORG") is False

    svc.upsert_fact(db_session, "C-1", "U-ORG", "SKILL", "skill_5", "value_5")
    db_session.commit()
    assert svc.should_update_summary(db_session, "C-1", "U-ORG") is True


def test_should_update_summary_true_after_a_day(db_session, seeded):
    candidate, conv = seeded
    summary_text = _valid_summary_text(300)
    svc.upsert_fact(db_session, "C-1", "U-ORG", "SALARY", "expected_ctc", "24 LPA")
    db_session.commit()
    svc.update_memory_summary(db_session, "C-1", "U-ORG", llm_call=lambda p: summary_text)

    memory = db_session.query(CandidateMemory).filter(CandidateMemory.candidate_id == "C-1").first()
    memory.last_updated = datetime.utcnow() - timedelta(days=2)
    db_session.commit()

    assert svc.should_update_summary(db_session, "C-1", "U-ORG") is True
