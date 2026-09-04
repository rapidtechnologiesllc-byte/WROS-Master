"""
S-349/HRMS-P119 -- Proactive Motivation Engine.
Throwaway SQLite -- never the real database.
"""
import os
import tempfile
import logging
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_desire_profile import CandidateDesireProfile
from app.models.consent import ConsentRecord
from app.models.event_log import EventLog
from app.models.motivation import MotivationContentLibrary, MotivationOutcome
from app.models.offer_letter import OfferLetter
from app.models.user import Users

import app.services.motivation_engine_service as svc

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        CandidateDesireProfile.__table__, EventLog.__table__, OfferLetter.__table__,
        MotivationContentLibrary.__table__, MotivationOutcome.__table__, ConsentRecord.__table__,
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
    candidate = Candidate(candidateID="C-MOT", candidateEmail="mot@example.com", candidatePassword="h", candidateFirstName="Sam")
    db_session.add_all([owner, candidate])
    db_session.commit()
    return owner, candidate

@pytest.fixture()
def conversation(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    conv = CandidateConversation(
        tenant_id=owner.UserID, candidate_id=candidate.candidateID, status="open",
        owner_type="ai_agent", channel_preference="email",
    )
    db_session.add(conv)
    db_session.commit()
    return conv

def _profile(db, owner, candidate, **overrides):
    defaults = dict(
        tenant_id=owner.UserID, candidate_id=candidate.candidateID,
        top_desire_category="CAREER_GROWTH", top_desire_score=0.8,
        desire_ranking=[{"category": "CAREER_GROWTH", "score": 0.8, "signal_count": 3, "direction": "TOWARDS"}],
        engagement_level="WARM", has_competing_offer=False, decision_urgency="NORMAL",
        profile_updated_at=datetime.utcnow(),
    )
    defaults.update(overrides)
    row = CandidateDesireProfile(**defaults)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def _offer(db, candidate, **overrides):
    defaults = dict(
        candidate_id=candidate.candidateID, position="Guidewire Dev", salary="20 LPA",
        joining_date=date.today() + timedelta(days=30), offer_expire_date=date.today() + timedelta(days=10),
        offer_status="Released", released_at=datetime.utcnow(),
    )
    defaults.update(overrides)
    row = OfferLetter(**defaults)
    db.add(row)
    db.commit()
    return row

# ---------------------------------------------------------------------------
# Trigger detection
# ---------------------------------------------------------------------------

def test_no_trigger_when_nothing_fires(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _profile(db_session, owner, candidate, engagement_level="HOT")
    assert svc.detect_trigger(db_session, owner.UserID, candidate.candidateID) is None

def test_competing_offer_trigger_bypasses_48h_cap(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _offer(db_session, candidate)
    _profile(db_session, owner, candidate, has_competing_offer=True)
    db_session.add(MotivationOutcome(
        tenant_id=owner.UserID, candidate_id=candidate.candidateID, trigger_type="SCHEDULED_NURTURE",
        message_sent="x", sent_at=datetime.utcnow() - timedelta(hours=1),
    ))
    db_session.commit()

    assert svc.detect_trigger(db_session, owner.UserID, candidate.candidateID) == "COMPETING_OFFER"

def test_offer_pending_trigger_fires_after_2_days(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _offer(db_session, candidate, released_at=datetime.utcnow() - timedelta(days=3))
    _profile(db_session, owner, candidate)

    assert svc.detect_trigger(db_session, owner.UserID, candidate.candidateID) == "OFFER_PENDING_RESPONSE"

def test_offer_pending_trigger_not_yet_at_1_day(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _offer(db_session, candidate, released_at=datetime.utcnow() - timedelta(days=1))
    _profile(db_session, owner, candidate)

    assert svc.detect_trigger(db_session, owner.UserID, candidate.candidateID) is None

def test_cooling_engagement_trigger_fires_on_real_event(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _profile(db_session, owner, candidate, engagement_level="COOL")
    db_session.add(EventLog(tenant_id=owner.UserID, candidate_id=candidate.candidateID, event_type="candidate.engagement_cooled", payload={}))
    db_session.commit()

    assert svc.detect_trigger(db_session, owner.UserID, candidate.candidateID) == "COOLING_ENGAGEMENT"

def test_desire_shift_trigger_fires_on_real_event(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _profile(db_session, owner, candidate)
    db_session.add(EventLog(tenant_id=owner.UserID, candidate_id=candidate.candidateID, event_type="candidate.desire_shift_detected", payload={}))
    db_session.commit()

    assert svc.detect_trigger(db_session, owner.UserID, candidate.candidateID) == "DESIRE_SHIFT"

def test_cooling_beats_desire_shift_in_priority(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _profile(db_session, owner, candidate, engagement_level="COOL")
    db_session.add(EventLog(tenant_id=owner.UserID, candidate_id=candidate.candidateID, event_type="candidate.engagement_cooled", payload={}))
    db_session.add(EventLog(tenant_id=owner.UserID, candidate_id=candidate.candidateID, event_type="candidate.desire_shift_detected", payload={}))
    db_session.commit()

    assert svc.detect_trigger(db_session, owner.UserID, candidate.candidateID) == "COOLING_ENGAGEMENT"

def test_48h_cap_blocks_lower_priority_triggers(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _profile(db_session, owner, candidate, engagement_level="COOL")
    db_session.add(EventLog(tenant_id=owner.UserID, candidate_id=candidate.candidateID, event_type="candidate.engagement_cooled", payload={}))
    db_session.add(MotivationOutcome(
        tenant_id=owner.UserID, candidate_id=candidate.candidateID, trigger_type="SCHEDULED_NURTURE",
        message_sent="x", sent_at=datetime.utcnow() - timedelta(hours=2),
    ))
    db_session.commit()

    assert svc.detect_trigger(db_session, owner.UserID, candidate.candidateID) is None

def test_scheduled_nurture_requires_warm_and_correct_stage(db_session, tenant_and_candidate, monkeypatch):
    owner, candidate = tenant_and_candidate
    _profile(db_session, owner, candidate, engagement_level="WARM")

    monkeypatch.setattr(
        "app.services.candidate_journey_service.get_candidate_journey",
        lambda db, cid, tid: {"current_stage": "SCREENED"},
    )
    assert svc.detect_trigger(db_session, owner.UserID, candidate.candidateID) == "SCHEDULED_NURTURE"

# ---------------------------------------------------------------------------
# Message generation
# ---------------------------------------------------------------------------

def test_generate_message_without_profile_is_generic_nurture(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    message, category = svc.generate_motivation_message(db_session, owner.UserID, candidate, None, "SCHEDULED_NURTURE")
    assert message == svc.GENERIC_NURTURE_MESSAGE
    assert category is None

def test_generate_message_validated_against_library(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    profile = _profile(db_session, owner, candidate)
    fact = svc.DEFAULT_CONTENT_LIBRARY["CAREER_GROWTH"][0]

    llm_call = lambda p: f"Hi Sam, {fact} Would that matter to you?"
    message, category = svc.generate_motivation_message(db_session, owner.UserID, candidate, profile, "SCHEDULED_NURTURE", llm_call=llm_call)

    assert fact in message
    assert category == "CAREER_GROWTH"

def test_generate_message_falls_back_when_llm_invents_facts(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    profile = _profile(db_session, owner, candidate)

    llm_call = lambda p: "We pay 200% above market rate guaranteed!"  # never in the library
    message, category = svc.generate_motivation_message(db_session, owner.UserID, candidate, profile, "SCHEDULED_NURTURE", llm_call=llm_call)

    assert svc.DEFAULT_CONTENT_LIBRARY["CAREER_GROWTH"][0] in message
    assert category == "CAREER_GROWTH"

def test_generate_message_uses_tenant_content_library_over_default(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    profile = _profile(db_session, owner, candidate)
    db_session.add(MotivationContentLibrary(tenant_id=owner.UserID, desire_category="CAREER_GROWTH", content_items=["Custom tenant fact about growth"]))
    db_session.commit()

    llm_call = lambda p: "Hi Sam, Custom tenant fact about growth -- interested?"
    message, category = svc.generate_motivation_message(db_session, owner.UserID, candidate, profile, "SCHEDULED_NURTURE", llm_call=llm_call)

    assert "Custom tenant fact about growth" in message

# ---------------------------------------------------------------------------
# Send + outcome
# ---------------------------------------------------------------------------

def test_send_motivation_message_records_outcome_via_email(db_session, tenant_and_candidate, conversation, monkeypatch):
    owner, candidate = tenant_and_candidate
    _profile(db_session, owner, candidate)

    monkeypatch.setattr("app.services.email_service.EmailService.send_email", lambda *a, **k: None)

    outcome = svc.send_motivation_message(db_session, candidate, "SCHEDULED_NURTURE", llm_call=lambda p: f"Hi Sam, {svc.DEFAULT_CONTENT_LIBRARY['CAREER_GROWTH'][0]} Interested?")

    assert outcome is not None
    assert outcome.trigger_type == "SCHEDULED_NURTURE"
    assert outcome.desire_category_targeted == "CAREER_GROWTH"
    assert outcome.engagement_before == "WARM"

    sent_event = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "ai_message_sent").first()
    assert sent_event is not None
    assert sent_event.event_data["channel"] == "email"

def test_send_motivation_message_no_conversation_returns_none(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _profile(db_session, owner, candidate)
    assert svc.send_motivation_message(db_session, candidate, "SCHEDULED_NURTURE") is None

# ---------------------------------------------------------------------------
# run_motivation_job
# ---------------------------------------------------------------------------

def test_run_motivation_job_sends_for_due_candidate(db_session, tenant_and_candidate, conversation, monkeypatch):
    owner, candidate = tenant_and_candidate
    _profile(db_session, owner, candidate, engagement_level="COOL")
    db_session.add(EventLog(tenant_id=owner.UserID, candidate_id=candidate.candidateID, event_type="candidate.engagement_cooled", payload={}))
    db_session.commit()
    monkeypatch.setattr("app.services.email_service.EmailService.send_email", lambda *a, **k: None)

    result = svc.run_motivation_job(db_session, llm_call=lambda p: f"Hi Sam, {svc.DEFAULT_CONTENT_LIBRARY['CAREER_GROWTH'][0]} Interested?")

    assert result["sent"] == 1
    assert db_session.query(MotivationOutcome).count() == 1

def test_run_motivation_job_skips_when_no_trigger(db_session, tenant_and_candidate, conversation):
    owner, candidate = tenant_and_candidate
    _profile(db_session, owner, candidate, engagement_level="HOT")

    result = svc.run_motivation_job(db_session)

    assert result["sent"] == 0
    assert result["skipped"] == 1
