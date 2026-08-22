"""
S-026/HRMS-0426 -- Candidate Response Parser.

Real architecture adaptation under test (see response_parser_service
module docstring): normalized values are upserted into
candidate_memory_facts (S-021/S-022), never written to a dedicated
current_ctc/notice_period_days column on Candidate -- those columns
don't exist, and candidateExpectedSalary/candidateCurrentSalary are
plain display strings already used elsewhere, not integer-normalized
fields.

"""
import json
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_memory import CandidateMemory, CandidateMemoryFact
from app.models.user import Users

import app.services.response_parser_service as svc

def db_session():
    engine = create_engine(f"sqlite:///{db_path}")
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
    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="awaiting_candidate", owner_type="ai_agent", owner_id="thunder")
    db_session.add(conv)
    db_session.commit()
    return candidate, conv

# ── Normalization unit tests ────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("30 days", 30), ("2 weeks", 14), ("1 month", 30), ("3 months", 90), ("immediate", 0), ("immediately available", 0),
def test_normalize_notice_period_days(raw, expected):
    assert svc.normalize_notice_period_days(raw) == expected

@pytest.mark.parametrize("raw,expected", [
    ("18 LPA", 1800000 * 100), ("18 lakhs", 1800000 * 100), ("18,00,000", 1800000 * 100),
def test_normalize_salary_inr(raw, expected):
    assert svc.normalize_salary(raw) == expected

def test_normalize_salary_usd():
    assert svc.normalize_salary("$120k") == 120000 * 100

@pytest.mark.parametrize("raw,expected", [
    ("5 years", 5.0), ("3 years 6 months", 3.5), ("5+", 5.0), ("5+ years", 5.0),
def test_normalize_experience_years(raw, expected):
    assert svc.normalize_experience_years(raw) == expected

def test_normalize_value_passthrough_for_unmapped_field():
    assert svc.normalize_value("location", "Chicago") == "Chicago"

# ── parse_field_response() integration tests ────────────────────────

def test_parse_notice_period_success(db_session, seeded):
    candidate, conv = seeded
    llm_response = json.dumps({"value": "30 days", "confidence": 0.9})
    result = svc.parse_field_response(db_session, conv, candidate, "U-ORG", "notice_period_days", "I can leave with 30 days notice", llm_call=lambda p: llm_response)

    assert result["outcome"] == "parsed"
    assert result["normalized_value"] == 30
    assert result["confidence"] >= 0.8

    fact = db_session.query(CandidateMemoryFact).filter(CandidateMemoryFact.candidate_id == "C-1", CandidateMemoryFact.fact_key == "notice_period_days").first()
    assert fact.fact_value == "30"

def test_parse_salary_lpa_success(db_session, seeded):
    candidate, conv = seeded
    llm_response = json.dumps({"value": "18 LPA", "confidence": 0.9})
    result = svc.parse_field_response(db_session, conv, candidate, "U-ORG", "current_ctc", "Currently earning 18 LPA", llm_call=lambda p: llm_response)

    assert result["outcome"] == "parsed"
    assert result["normalized_value"] == 1800000 * 100
    assert result["confidence"] >= 0.8

def test_low_confidence_does_not_write_normalized_value_requests_clarification(db_session, seeded):
    candidate, conv = seeded
    llm_response = json.dumps({"value": "some amount", "confidence": 0.3})
    result = svc.parse_field_response(db_session, conv, candidate, "U-ORG", "current_ctc", "I make decent money", llm_call=lambda p: llm_response)

    assert result["outcome"] == "clarification_requested"
    assert "salary" in result["message"].lower()

    low_conf_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "PARSE_LOW_CONFIDENCE").all()
    assert len(low_conf_events) == 1
    clarification_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "CLARIFICATION_REQUESTED").all()
    assert len(clarification_events) == 1

def test_second_low_confidence_answer_accepted_no_second_clarification(db_session, seeded):
    candidate, conv = seeded
    vague = json.dumps({"value": "decent amount", "confidence": 0.3})

    first = svc.parse_field_response(db_session, conv, candidate, "U-ORG", "current_ctc", "I make decent money", llm_call=lambda p: vague)
    assert first["outcome"] == "clarification_requested"

    second = svc.parse_field_response(db_session, conv, candidate, "U-ORG", "current_ctc", "still can't say exactly", llm_call=lambda p: vague)
    assert second["outcome"] == "accepted_low_confidence"  # BR-03

    clarification_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "CLARIFICATION_REQUESTED").all()
    assert len(clarification_events) == 1  # never a second one

    fact = db_session.query(CandidateMemoryFact).filter(CandidateMemoryFact.candidate_id == "C-1", CandidateMemoryFact.fact_key == "current_ctc").first()
    assert fact.fact_value == "decent amount"
    assert fact.confidence == 0.3

def test_llm_failure_logs_parse_api_failed_no_crash(db_session, seeded):
    candidate, conv = seeded

    def broken_llm(prompt):
        raise RuntimeError("Gemini down")

    result = svc.parse_field_response(db_session, conv, candidate, "U-ORG", "current_ctc", "18 LPA", llm_call=broken_llm)
    assert result["outcome"] == "parse_failed"

    failures = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "PARSE_API_FAILED").all()
    assert len(failures) == 1

    fact = db_session.query(CandidateMemoryFact).filter(CandidateMemoryFact.candidate_id == "C-1").first()
    assert fact is None  # profile/memory untouched

def test_null_value_response_treated_as_low_confidence(db_session, seeded):
    candidate, conv = seeded
    llm_response = json.dumps({"value": None, "confidence": 0.0})
    result = svc.parse_field_response(db_session, conv, candidate, "U-ORG", "current_ctc", "I'd rather not say", llm_call=lambda p: llm_response)
    assert result["outcome"] == "clarification_requested"
