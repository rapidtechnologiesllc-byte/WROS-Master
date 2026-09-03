"""
import logging
S-022/HRMS-0422 -- Candidate Facts Extraction Engine.

Real architecture adaptations under test (see facts_extraction_service
module docstring): no conversation_messages table, no event bus/task
queue (synchronous but non-crashing on LLM failure), real Gemini LLM
(injectable in tests), PROFILE_FIELD_MAP only maps to real Candidate
columns, BR-03's confidence >= 0.5 gate on profile writes.

Throwaway SQLite -- never the real database.
"""
import json
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateJobApplication
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_job_flag import CandidateJobFlag
from app.models.candidate_job_score import CandidateJobScore
from app.models.candidate_memory import CandidateMemory, CandidateMemoryFact
from app.models.user import Jobs, Users

import app.services.facts_extraction_service as svc

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        CandidateMemory.__table__, CandidateMemoryFact.__table__, Jobs.__table__, CandidateJobApplication.__table__,
        CandidateJobScore.__table__, CandidateJobFlag.__table__,
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
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya")
    db_session.add_all([owner, candidate])
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="thunder")
    db_session.add(conv)
    db_session.commit()
    return candidate, conv

def test_extracts_salary_fact_and_upserts_into_memory(db_session, seeded):
    candidate, conv = seeded
    llm_response = json.dumps([{"fact_category": "SALARY", "fact_key": "expected_ctc", "fact_value": "24 LPA", "confidence": 0.9}])

    facts = svc.extract_facts(db_session, candidate, "U-ORG", conv.id, "I am looking for around 24 LPA", llm_call=lambda p: llm_response)

    assert len(facts) == 1
    assert facts[0]["fact_key"] == "expected_ctc"

    stored = db_session.query(CandidateMemoryFact).filter(CandidateMemoryFact.candidate_id == "C-1").all()
    assert len(stored) == 1
    assert stored[0].fact_value == "24 LPA"

def test_extracts_constraint_fact(db_session, seeded):
    candidate, conv = seeded
    llm_response = json.dumps([{"fact_category": "CONSTRAINT", "fact_key": "location_constraint", "fact_value": "Chicago only, no relocation", "confidence": 0.85}])

    facts = svc.extract_facts(db_session, candidate, "U-ORG", conv.id, "I cannot relocate, based in Chicago only", llm_call=lambda p: llm_response)

    assert facts[0]["fact_category"] == "CONSTRAINT"
    assert facts[0]["fact_value"] == "Chicago only, no relocation"

def test_high_confidence_fact_updates_profile_field(db_session, seeded):
    candidate, conv = seeded
    llm_response = json.dumps([{"fact_category": "SALARY", "fact_key": "expected_ctc", "fact_value": "28 LPA", "confidence": 0.8}])

    svc.extract_facts(db_session, candidate, "U-ORG", conv.id, "msg", llm_call=lambda p: llm_response)
    db_session.refresh(candidate)

    assert candidate.candidateExpectedSalary == "28 LPA"

def test_low_confidence_fact_does_not_update_profile(db_session, seeded):
    candidate, conv = seeded
    original = candidate.candidateExpectedSalary
    llm_response = json.dumps([{"fact_category": "SALARY", "fact_key": "expected_ctc", "fact_value": "99 LPA", "confidence": 0.3}])

    svc.extract_facts(db_session, candidate, "U-ORG", conv.id, "msg", llm_call=lambda p: llm_response)
    db_session.refresh(candidate)

    assert candidate.candidateExpectedSalary == original  # BR-03: below 0.5, profile untouched
    stored = db_session.query(CandidateMemoryFact).filter(CandidateMemoryFact.candidate_id == "C-1").first()
    assert stored is not None  # still stored in memory though

def test_unmapped_fact_key_does_not_touch_profile(db_session, seeded):
    candidate, conv = seeded
    llm_response = json.dumps([{"fact_category": "PREFERENCE", "fact_key": "domain_interest", "fact_value": "Healthcare", "confidence": 0.9}])

    svc.extract_facts(db_session, candidate, "U-ORG", conv.id, "msg", llm_call=lambda p: llm_response)

    stored = db_session.query(CandidateMemoryFact).filter(CandidateMemoryFact.candidate_id == "C-1").first()
    assert stored.fact_value == "Healthcare"

def test_llm_failure_returns_empty_list_and_logs_failure_no_crash(db_session, seeded):
    candidate, conv = seeded

    def broken_llm(prompt):
        raise RuntimeError("Gemini 500")

    facts = svc.extract_facts(db_session, candidate, "U-ORG", conv.id, "msg", llm_call=broken_llm)

    assert facts == []
    failures = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "FACTS_EXTRACTION_FAILED").all()
    assert len(failures) == 1

def test_invalid_json_returns_empty_list_and_logs_failure(db_session, seeded):
    candidate, conv = seeded
    facts = svc.extract_facts(db_session, candidate, "U-ORG", conv.id, "msg", llm_call=lambda p: "not valid json{{{")

    assert facts == []
    failures = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "FACTS_EXTRACTION_FAILED").all()
    assert len(failures) == 1

def test_empty_array_response_is_valid_no_facts(db_session, seeded):
    candidate, conv = seeded
    facts = svc.extract_facts(db_session, candidate, "U-ORG", conv.id, "just saying hi", llm_call=lambda p: "[]")
    assert facts == []

def test_facts_extracted_event_logged_with_keys_and_count(db_session, seeded):
    candidate, conv = seeded
    llm_response = json.dumps([
        {"fact_category": "SALARY", "fact_key": "expected_ctc", "fact_value": "24 LPA", "confidence": 0.9},
        {"fact_category": "AVAILABILITY", "fact_key": "notice_period_text", "fact_value": "30 days", "confidence": 0.8},
    ])
    svc.extract_facts(db_session, candidate, "U-ORG", conv.id, "msg", llm_call=lambda p: llm_response)

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "FACTS_EXTRACTED").all()
    assert len(events) == 1
    assert events[0].event_data["facts_count"] == 2
    assert set(events[0].event_data["fact_keys_extracted"]) == {"expected_ctc", "notice_period_text"}

def test_invalid_category_item_is_skipped_not_crashed(db_session, seeded):
    candidate, conv = seeded
    llm_response = json.dumps([
        {"fact_category": "NOT_REAL", "fact_key": "x", "fact_value": "y", "confidence": 0.9},
        {"fact_category": "SKILL", "fact_key": "python_experience", "fact_value": "5 years", "confidence": 0.9},
    ])
    facts = svc.extract_facts(db_session, candidate, "U-ORG", conv.id, "msg", llm_call=lambda p: llm_response)

    assert len(facts) == 1
    assert facts[0]["fact_key"] == "python_experience"
