"""
S-347/HRMS-P117 -- Candidate Desire Intelligence Engine.
Throwaway SQLite -- never the real database.
"""
import json
import os
import logging
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_desire_signal import CandidateDesireSignal
from app.models.user import Users

import app.services.desire_signal_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__,
        ConversationEvent.__table__, CandidateDesireSignal.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def tenant_and_candidate(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    candidate = Candidate(candidateID="C-DESIRE", candidateEmail="desire@example.com", candidatePassword="h")
    db_session.add_all([owner, candidate])
    db_session.commit()
    return owner, candidate


# ---------------------------------------------------------------------------
# Deterministic scoring -- no LLM involved
# ---------------------------------------------------------------------------

def test_objection_signal_maps_to_desire_category_deterministically(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    signal = svc.record_objection_signal(db_session, owner.UserID, candidate.candidateID, "SALARY", "wants more money")

    assert signal.desire_category == "COMPENSATION"
    assert signal.desire_direction == "AWAY_FROM"
    assert signal.processed is True
    assert signal.signal_data["objection_type"] == "SALARY"


def test_objection_signal_with_no_mapping_stays_unprocessed(db_session, tenant_and_candidate):
    """OTHER has no deterministic mapping -- left for the LLM pass."""
    owner, candidate = tenant_and_candidate
    signal = svc.record_objection_signal(db_session, owner.UserID, candidate.candidateID, "OTHER", "unclear concern")

    assert signal.desire_category is None
    assert signal.processed is False


@pytest.mark.parametrize("minutes,expected_strength", [(10, 0.8), (29, 0.8), (60, 0.4), (2900, 0.1)])
def test_response_speed_signal_strength_formula(db_session, tenant_and_candidate, minutes, expected_strength):
    owner, candidate = tenant_and_candidate
    signal = svc.record_response_speed_signal(db_session, owner.UserID, candidate.candidateID, minutes)

    assert signal.desire_strength == expected_strength
    assert signal.processed is True
    assert signal.desire_category is None  # engagement, not a specific desire category


# ---------------------------------------------------------------------------
# minutes_since_last_outbound
# ---------------------------------------------------------------------------

def test_minutes_since_last_outbound_none_when_no_prior_outbound(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    conversation = CandidateConversation(tenant_id=owner.UserID, candidate_id=candidate.candidateID, status="open", owner_type="ai_agent")
    db_session.add(conversation)
    db_session.commit()

    assert svc.minutes_since_last_outbound(db_session, conversation.id) is None


def test_minutes_since_last_outbound_computes_real_gap(db_session, tenant_and_candidate):
    from datetime import datetime, timedelta
    owner, candidate = tenant_and_candidate
    conversation = CandidateConversation(tenant_id=owner.UserID, candidate_id=candidate.candidateID, status="open", owner_type="ai_agent")
    db_session.add(conversation)
    db_session.commit()

    outbound = ConversationEvent(conversation_id=conversation.id, event_type="ai_message_sent", event_data={"channel": "portal", "body": "hi"}, triggered_by="ai_agent")
    db_session.add(outbound)
    db_session.commit()
    outbound.created_at = datetime.utcnow() - timedelta(minutes=20)
    db_session.commit()

    gap = svc.minutes_since_last_outbound(db_session, conversation.id)
    assert 19 <= gap <= 21


# ---------------------------------------------------------------------------
# SignalProcessingJob -- LLM extraction
# ---------------------------------------------------------------------------

def _clear_growth_llm(prompt):
    return json.dumps({
        "desire_category": "CAREER_GROWTH", "desire_direction": "TOWARDS",
        "desire_strength": 0.85, "extracted_insight": "Candidate asked about growth path.",
    })


def _broken_llm(prompt):
    raise RuntimeError("simulated LLM outage")


def test_process_unprocessed_signals_extracts_real_category(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    svc.record_message_signal(db_session, owner.UserID, candidate.candidateID, "CHAT_MESSAGE", "What's the growth path here?")

    result = svc.process_unprocessed_signals(db_session, llm_call=_clear_growth_llm)

    assert result == {"processed": 1, "failed": 0, "batch_size": 1}
    signal = db_session.query(CandidateDesireSignal).first()
    assert signal.desire_category == "CAREER_GROWTH"
    assert signal.desire_direction == "TOWARDS"
    assert signal.desire_strength == 0.85
    assert signal.processed is True
    assert signal.processed_at is not None


def test_process_unprocessed_signals_leaves_failed_signal_for_retry(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    svc.record_message_signal(db_session, owner.UserID, candidate.candidateID, "CHAT_MESSAGE", "hello")

    result = svc.process_unprocessed_signals(db_session, llm_call=_broken_llm)

    assert result == {"processed": 0, "failed": 1, "batch_size": 1}
    signal = db_session.query(CandidateDesireSignal).first()
    assert signal.processed is False  # stays unprocessed -- retried next cycle


def test_process_unprocessed_signals_skips_already_deterministic_ones(db_session, tenant_and_candidate):
    """OBJECTION/RESPONSE_SPEED signals that already got a deterministic
    score (processed=True at insert time) must not be re-picked-up by
    the batch job."""
    owner, candidate = tenant_and_candidate
    svc.record_objection_signal(db_session, owner.UserID, candidate.candidateID, "SALARY", "wants more")
    svc.record_response_speed_signal(db_session, owner.UserID, candidate.candidateID, 10)
    svc.record_message_signal(db_session, owner.UserID, candidate.candidateID, "CHAT_MESSAGE", "hi there")

    result = svc.process_unprocessed_signals(db_session, llm_call=_clear_growth_llm)

    assert result["batch_size"] == 1  # only the raw CHAT_MESSAGE signal


def test_process_unprocessed_signals_ignores_invalid_category_from_llm(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    svc.record_message_signal(db_session, owner.UserID, candidate.candidateID, "CHAT_MESSAGE", "random chatter")

    def _junk_category_llm(prompt):
        return json.dumps({"desire_category": "NOT_A_REAL_CATEGORY", "desire_direction": "SIDEWAYS", "desire_strength": 5.0, "extracted_insight": "n/a"})

    result = svc.process_unprocessed_signals(db_session, llm_call=_junk_category_llm)

    assert result["processed"] == 1
    signal = db_session.query(CandidateDesireSignal).first()
    assert signal.desire_category is None
    assert signal.desire_direction is None
    assert signal.desire_strength == 1.0  # clamped
    assert signal.processed is True  # still marked processed -- a junk-but-parseable response isn't a failure


# ---------------------------------------------------------------------------
# Fail-soft recording
# ---------------------------------------------------------------------------

def test_record_never_raises_on_db_error(db_session, tenant_and_candidate):
    """A NOT NULL violation (candidate_id=None here -- SQLite doesn't
    enforce FKs by default so a bad tenant_id alone wouldn't trigger a
    real failure in this fixture) must not raise into the caller
    (BR-04 fire-and-forget), and must not poison the session for
    whatever the caller does next."""
    owner, candidate = tenant_and_candidate
    result = svc.record_message_signal(db_session, owner.UserID, None, "CHAT_MESSAGE", "hi")

    assert result is None
    # session still usable afterward
    db_session.add(Candidate(candidateID="C-AFTER", candidateEmail="after@example.com", candidatePassword="h"))
    db_session.commit()
