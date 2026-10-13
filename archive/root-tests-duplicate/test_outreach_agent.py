"""
HRMS-1104 -- Automated Outreach Agent.

Proves: BR-1104-03 (consent checked before composition, hard gate),
BR-1104-01/AC-5 (every send goes through sendThunderMessage(), recorded
as sent_via), BR-1104-02/AC-3 (R-08 lock halts the sequence without an
automatic channel switch), BR-1104-04/AC-4 (3-touch cap), AC-6 (business
hours deferral, not drop), the 24h debounce, and the Orchestration
Router hand-off.

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
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.client import Client
from app.models.consent import ConsentRecord
from app.models.demand import Demand
from app.models.notification import Notification
from app.models.outreach import OutreachSequence
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.ai_conversation_service import AI_AGENT_NAME
import app.services.whatsapp_routing_service as routing
from app.services.outreach_agent_service import (
    OutreachDebounced,
    advance_outreach_sequence,
    start_outreach_sequence,
)


@pytest.fixture(autouse=True)
def _default_whatsapp_number(monkeypatch):
    monkeypatch.setattr(routing, "DEFAULT_WHATSAPP_NUMBER", "+10005550000")


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Users.__table__, Client.__table__, Demand.__table__,
        Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        CandidateAIAssignment.__table__, ConsentRecord.__table__, OutreachSequence.__table__,
        Notification.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


# A Wednesday, 12:00 IST -- squarely inside 08:00-20:00.
BUSINESS_HOURS_UTC = datetime(2026, 4, 1, 6, 30)
# 22:00 IST -- outside 08:00-20:00.
AFTER_HOURS_UTC = datetime(2026, 4, 1, 16, 30)


@pytest.fixture()
def setup(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    client = Client(company_name="Acme Carrier", tenant_id=tenant.id)
    db_session.add(client)
    db_session.commit()

    demand = Demand(
        tenant_id=tenant.id, client_id=client.id, job_title="Senior PC Developer",
        required_skills='["Guidewire PolicyCenter"]', min_experience_years=5,
        work_location="REMOTE", status="OPEN",
    )
    db_session.add(demand)
    db_session.commit()

    candidate = Candidate(
        candidateID="C-OUT", candidateEmail="out@example.com", candidatePassword="h",
        candidateMobile="+19995551234", timezone="Asia/Kolkata",
    )
    db_session.add(candidate)
    db_session.commit()

    return candidate, demand, tenant


def _compose_ok(payload):
    return {"message_text": "Hi! Saw your PolicyCenter background, are you open to a new role?"}


def _grant_consent(db, candidate_id):
    db.add(ConsentRecord(subject_type="candidate", subject_id=candidate_id, consent_type="whatsapp_outreach", consent_given=True))
    db.commit()


# ---------------------------------------------------------------------------
# BR-1104-03 -- consent is a hard gate, checked before composition
# ---------------------------------------------------------------------------

def test_no_consent_blocks_before_composition(db_session, setup):
    candidate, demand, tenant = setup

    composer_called = []

    def tracking_composer(payload):
        composer_called.append(payload)
        return {"message_text": "should never be reached"}

    sequence = start_outreach_sequence(
        db_session, candidate, demand, message_composer=tracking_composer,
        whatsapp_client=lambda *a: True, now=BUSINESS_HOURS_UTC,
    )
    db_session.commit()

    assert composer_called == []
    assert sequence.message_text is None
    assert sequence.status == "QUEUED"
    assert sequence.touch_count == 0
    assert db_session.query(ConversationEvent).count() == 0


# ---------------------------------------------------------------------------
# BR-1104-01/AC-5 -- send goes through sendThunderMessage only
# ---------------------------------------------------------------------------

def test_successful_send_records_sent_via_and_touch_count(db_session, setup):
    candidate, demand, tenant = setup
    _grant_consent(db_session, candidate.candidateID)

    sequence = start_outreach_sequence(
        db_session, candidate, demand, message_composer=_compose_ok,
        whatsapp_client=lambda *a: True, now=BUSINESS_HOURS_UTC,
    )
    db_session.commit()

    assert sequence.status == "SENT"
    assert sequence.sent_via == "sendThunderMessage"
    assert sequence.touch_count == 1
    assert sequence.last_touch_sent_at == BUSINESS_HOURS_UTC


# ---------------------------------------------------------------------------
# Debounce -- 24h per candidate+demand
# ---------------------------------------------------------------------------

def test_second_sequence_for_same_candidate_and_demand_is_debounced(db_session, setup):
    candidate, demand, tenant = setup
    _grant_consent(db_session, candidate.candidateID)

    start_outreach_sequence(
        db_session, candidate, demand, message_composer=_compose_ok,
        whatsapp_client=lambda *a: True, now=BUSINESS_HOURS_UTC,
    )
    db_session.commit()

    with pytest.raises(OutreachDebounced):
        start_outreach_sequence(
            db_session, candidate, demand, message_composer=_compose_ok,
            whatsapp_client=lambda *a: True, now=BUSINESS_HOURS_UTC,
        )


def test_debounce_does_not_apply_to_a_different_demand(db_session, setup):
    candidate, demand, tenant = setup
    _grant_consent(db_session, candidate.candidateID)
    client = db_session.query(Client).first()
    other_demand = Demand(
        tenant_id=tenant.id, client_id=client.id, job_title="Another Role",
        required_skills='["Java"]', min_experience_years=5,
        work_location="REMOTE", status="OPEN",
    )
    db_session.add(other_demand)
    db_session.commit()

    start_outreach_sequence(
        db_session, candidate, demand, message_composer=_compose_ok,
        whatsapp_client=lambda *a: True, now=BUSINESS_HOURS_UTC,
    )
    db_session.commit()

    # Different message text than the first call -- otherwise Thunder's
    # own duplicate-send debounce (a separate, message-content-based
    # concern, not this test's target) would correctly suppress an
    # identical body sent moments apart on the same conversation.
    sequence2 = start_outreach_sequence(
        db_session, candidate, other_demand,
        message_composer=lambda payload: {"message_text": "Hi! We also have a Java-focused role open."},
        whatsapp_client=lambda *a: True, now=BUSINESS_HOURS_UTC,
    )
    db_session.commit()
    assert sequence2.status == "SENT"


# ---------------------------------------------------------------------------
# AC-6 -- outside business hours defers, does not drop
# ---------------------------------------------------------------------------

def test_outside_business_hours_defers_send(db_session, setup):
    candidate, demand, tenant = setup
    _grant_consent(db_session, candidate.candidateID)

    sent = []
    sequence = start_outreach_sequence(
        db_session, candidate, demand, message_composer=_compose_ok,
        whatsapp_client=lambda *a: sent.append(a) or True, now=AFTER_HOURS_UTC,
    )
    db_session.commit()

    assert sequence.status == "QUEUED"
    assert sequence.touch_count == 0
    assert sent == []


def test_p1_emergency_bypasses_business_hours_check(db_session, setup):
    candidate, demand, tenant = setup
    _grant_consent(db_session, candidate.candidateID)
    demand.p1_emergency = True  # not a mapped column in this codebase -- see module docstring

    sequence = start_outreach_sequence(
        db_session, candidate, demand, message_composer=_compose_ok,
        whatsapp_client=lambda *a: True, now=AFTER_HOURS_UTC,
    )
    db_session.commit()

    assert sequence.status == "SENT"


# ---------------------------------------------------------------------------
# BR-1104-02/AC-3 -- R-08 lock halts, no auto channel switch
# ---------------------------------------------------------------------------

def test_r08_lock_blocks_ownership_without_channel_switch(db_session, setup):
    candidate, demand, tenant = setup
    _grant_consent(db_session, candidate.candidateID)

    recruiter = Users(UserID="U-REC", UserRole="Recruiter", UserEmail="rec@blitzenx.com", UserPassword="h")
    db_session.add(recruiter)
    db_session.commit()
    conversation = CandidateConversation(
        tenant_id="U-ORG", candidate_id=candidate.candidateID, status="open",
        owner_type="hr_user", owner_id=recruiter.UserID,
    )
    db_session.add(conversation)
    db_session.commit()

    sequence = start_outreach_sequence(
        db_session, candidate, demand, message_composer=_compose_ok,
        whatsapp_client=lambda *a: True, now=BUSINESS_HOURS_UTC,
    )
    db_session.commit()

    assert sequence.status == "BLOCKED_OWNERSHIP"
    assert sequence.touch_count == 0
    assert sequence.primary_channel == "whatsapp"  # never switched

    # advance_outreach_sequence must not progress a blocked sequence.
    advanced = advance_outreach_sequence(
        db_session, sequence, candidate, demand,
        now=BUSINESS_HOURS_UTC + timedelta(hours=49),
    )
    db_session.commit()
    assert advanced.status == "BLOCKED_OWNERSHIP"


# ---------------------------------------------------------------------------
# Orchestration Router integration
# ---------------------------------------------------------------------------

def test_router_block_prevents_send_and_is_retryable(db_session, setup):
    candidate, demand, tenant = setup
    _grant_consent(db_session, candidate.candidateID)

    def blocking_router(**kwargs):
        raise RuntimeError("ActionBlocked: outreach vs Core-Pull collision")

    sent = []
    sequence = start_outreach_sequence(
        db_session, candidate, demand, message_composer=_compose_ok,
        whatsapp_client=lambda *a: sent.append(a) or True,
        router_evaluate=blocking_router, now=BUSINESS_HOURS_UTC,
    )
    db_session.commit()

    assert sent == []
    assert sequence.touch_count == 0
    assert "blocked" in (sequence.blocked_reason or "").lower()
    assert sequence.status == "QUEUED"  # retryable, not a terminal state


def test_router_evaluate_called_with_correct_kwargs_on_success(db_session, setup):
    candidate, demand, tenant = setup
    _grant_consent(db_session, candidate.candidateID)

    calls = []

    def fake_router(**kwargs):
        calls.append(kwargs)

    start_outreach_sequence(
        db_session, candidate, demand, message_composer=_compose_ok,
        whatsapp_client=lambda *a: True, router_evaluate=fake_router, now=BUSINESS_HOURS_UTC,
    )
    db_session.commit()

    assert len(calls) == 1
    assert calls[0]["agent_id"] == "HRMS-1104"
    assert calls[0]["entity_type"] == "candidate"
    assert calls[0]["action_type"] == "outreach_send"
    assert calls[0]["risk_tier"] == "LOW"


# ---------------------------------------------------------------------------
# BR-1104-04/AC-4 -- 3-touch cap
# ---------------------------------------------------------------------------

def test_touch_cap_prevents_a_fourth_send(db_session, setup):
    candidate, demand, tenant = setup
    _grant_consent(db_session, candidate.candidateID)

    sequence = start_outreach_sequence(
        db_session, candidate, demand, message_composer=_compose_ok,
        whatsapp_client=lambda *a: True, now=BUSINESS_HOURS_UTC,
    )
    db_session.commit()
    assert sequence.touch_count == 1

    sequence.touch_count = 3
    db_session.add(sequence)
    db_session.commit()

    sent = []
    advanced = advance_outreach_sequence(
        db_session, sequence, candidate, demand,
        whatsapp_client=lambda *a: sent.append(a) or True,
        now=BUSINESS_HOURS_UTC + timedelta(hours=49),
    )
    db_session.commit()

    assert advanced.status == "COMPLETE_NO_RESPONSE"
    assert advanced.touch_count == 3
    assert sent == []


# ---------------------------------------------------------------------------
# advance_outreach_sequence -- response detection and timing
# ---------------------------------------------------------------------------

def test_advance_marks_responded_when_candidate_replied(db_session, setup):
    candidate, demand, tenant = setup
    _grant_consent(db_session, candidate.candidateID)

    sequence = start_outreach_sequence(
        db_session, candidate, demand, message_composer=_compose_ok,
        whatsapp_client=lambda *a: True, now=BUSINESS_HOURS_UTC,
    )
    db_session.commit()

    conversation = db_session.query(CandidateConversation).filter(
        CandidateConversation.candidate_id == candidate.candidateID
    ).first()
    db_session.add(ConversationEvent(
        conversation_id=conversation.id, event_type="candidate_reply",
        triggered_by="candidate", event_data={"body": "Yes, interested!"},
        created_at=BUSINESS_HOURS_UTC + timedelta(hours=1),
    ))
    db_session.commit()

    advanced = advance_outreach_sequence(
        db_session, sequence, candidate, demand, now=BUSINESS_HOURS_UTC + timedelta(hours=2),
    )
    db_session.commit()
    assert advanced.status == "RESPONDED"


def test_advance_does_nothing_before_response_wait_elapses(db_session, setup):
    candidate, demand, tenant = setup
    _grant_consent(db_session, candidate.candidateID)

    sequence = start_outreach_sequence(
        db_session, candidate, demand, message_composer=_compose_ok,
        whatsapp_client=lambda *a: True, now=BUSINESS_HOURS_UTC,
    )
    db_session.commit()

    advanced = advance_outreach_sequence(
        db_session, sequence, candidate, demand, now=BUSINESS_HOURS_UTC + timedelta(hours=10),
    )
    db_session.commit()

    assert advanced.status == "SENT"
    assert advanced.touch_count == 1
    assert advanced.primary_channel == "whatsapp"
