"""
S-036/HRMS-0436 -- Candidate Sentiment Analysis.

Real architecture under test (see sentiment_analysis_service module
docstring): callLLM()/getContextForPrompt() are S-031/S-032's real,
already-tested functions, scoped to just the single message being
classified; BR-01/BR-03 collapse LLM failure/invalid JSON/unknown
sentiment value to {sentiment: NEUTRAL, confidence: 0.0}, never raises;
every call persists a CandidateSentimentLog row regardless of outcome;
has_negative_sentiment_trend() is a plain DB read used directly by
S-035's escalation_detection_service Rule #3, not a fabricated event.

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
from app.models.candidate_sentiment_log import CandidateSentimentLog
from app.models.prompt_execution_log import PromptExecutionLog
from app.models.sla_breach import CandidateSLABreach
from app.models.user import Jobs, Users

import app.services.sentiment_analysis_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateInfoForm.__table__, Jobs.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__, CandidateFieldSkip.__table__,
        CandidateMemory.__table__, CandidateMemoryFact.__table__, CandidateSLABreach.__table__,
        PromptExecutionLog.__table__, CandidateSentimentLog.__table__,
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


# ── TC-001: neutral classification ────────────────────────────────────

def test_neutral_classification(db_session, seeded):
    candidate, conv = seeded
    result = svc.analyze_sentiment(
        db_session, "U-ORG", "C-1", "Ok, sounds good.",
        conversation_id=conv.id, llm_call=_llm_returning({"sentiment": "NEUTRAL", "confidence": 0.75}),
    )
    assert result["sentiment"] == "NEUTRAL"
    assert result["confidence"] > 0.6


def test_positive_classification(db_session, seeded):
    candidate, conv = seeded
    result = svc.analyze_sentiment(
        db_session, "U-ORG", "C-1", "This sounds amazing, I'm really excited!",
        conversation_id=conv.id, llm_call=_llm_returning({"sentiment": "POSITIVE", "confidence": 0.9}),
    )
    assert result["sentiment"] == "POSITIVE"


# ── TC-002: negative classification ────────────────────────────────────

def test_negative_classification(db_session, seeded):
    candidate, conv = seeded
    result = svc.analyze_sentiment(
        db_session, "U-ORG", "C-1", "This is really frustrating, whatever.",
        conversation_id=conv.id, llm_call=_llm_returning({"sentiment": "NEGATIVE", "confidence": 0.85}),
    )
    assert result["sentiment"] == "NEGATIVE"
    assert result["confidence"] > 0.7


# ── AC: each sentiment stored with message_id ──────────────────────────

def test_sentiment_persisted_with_message_event_id(db_session, seeded):
    candidate, conv = seeded
    svc.analyze_sentiment(
        db_session, "U-ORG", "C-1", "Fine, I guess.",
        conversation_id=conv.id, message_event_id=99, llm_call=_llm_returning({"sentiment": "NEUTRAL", "confidence": 0.5}),
    )
    rows = db_session.query(CandidateSentimentLog).filter(CandidateSentimentLog.candidate_id == "C-1").all()
    assert len(rows) == 1
    assert rows[0].message_event_id == 99
    assert rows[0].conversation_id == conv.id
    assert rows[0].tenant_id == "U-ORG"


# ── TC-004 / BR-01/BR-03: LLM failure -> safe NEUTRAL, no exception ────

def test_llm_failure_stores_safe_neutral_never_raises(db_session, seeded):
    candidate, conv = seeded
    result = svc.analyze_sentiment(db_session, "U-ORG", "C-1", "Some message", conversation_id=conv.id, llm_call=_llm_raising(RuntimeError("Gemini down")))
    assert result == {"sentiment": "NEUTRAL", "confidence": 0.0, "raw_response": None}
    rows = db_session.query(CandidateSentimentLog).filter(CandidateSentimentLog.candidate_id == "C-1").all()
    assert len(rows) == 1
    assert rows[0].sentiment == "NEUTRAL"


def test_invalid_json_stores_safe_neutral(db_session, seeded):
    candidate, conv = seeded
    result = svc.analyze_sentiment(db_session, "U-ORG", "C-1", "Some message", conversation_id=conv.id, llm_call=lambda sp, up, mt, t: "not json")
    assert result["sentiment"] == "NEUTRAL"
    assert result["confidence"] == 0.0


def test_unknown_sentiment_value_mapped_to_neutral(db_session, seeded):
    candidate, conv = seeded
    result = svc.analyze_sentiment(
        db_session, "U-ORG", "C-1", "Some message", conversation_id=conv.id,
        llm_call=_llm_returning({"sentiment": "VERY_ANGRY", "confidence": 0.9}),
    )
    assert result["sentiment"] == "NEUTRAL"


def test_confidence_out_of_range_is_clamped(db_session, seeded):
    candidate, conv = seeded
    result = svc.analyze_sentiment(
        db_session, "U-ORG", "C-1", "Some message", conversation_id=conv.id,
        llm_call=_llm_returning({"sentiment": "POSITIVE", "confidence": 5.0}),
    )
    assert result["confidence"] == 1.0


# ── get_recent_sentiment_trend() / TC-003 negative trend ────────────────

def test_get_recent_sentiment_trend_most_recent_first(db_session, seeded):
    candidate, conv = seeded
    for sentiment in ("POSITIVE", "NEUTRAL", "NEGATIVE"):
        db_session.add(CandidateSentimentLog(tenant_id="U-ORG", candidate_id="C-1", sentiment=sentiment, confidence=0.8))
        db_session.commit()

    trend = svc.get_recent_sentiment_trend(db_session, "C-1")
    assert trend == ["NEGATIVE", "NEUTRAL", "POSITIVE"]


def test_has_negative_sentiment_trend_true_after_3_consecutive(db_session, seeded):
    candidate, conv = seeded
    for _ in range(3):
        db_session.add(CandidateSentimentLog(tenant_id="U-ORG", candidate_id="C-1", sentiment="NEGATIVE", confidence=0.8))
    db_session.commit()

    assert svc.has_negative_sentiment_trend(db_session, "C-1") is True


def test_has_negative_sentiment_trend_false_with_fewer_than_3(db_session, seeded):
    candidate, conv = seeded
    for _ in range(2):
        db_session.add(CandidateSentimentLog(tenant_id="U-ORG", candidate_id="C-1", sentiment="NEGATIVE", confidence=0.8))
    db_session.commit()

    assert svc.has_negative_sentiment_trend(db_session, "C-1") is False


def test_has_negative_sentiment_trend_false_when_trend_broken(db_session, seeded):
    candidate, conv = seeded
    for sentiment in ("NEGATIVE", "NEGATIVE", "POSITIVE"):
        db_session.add(CandidateSentimentLog(tenant_id="U-ORG", candidate_id="C-1", sentiment=sentiment, confidence=0.8))
        db_session.commit()

    assert svc.has_negative_sentiment_trend(db_session, "C-1") is False
