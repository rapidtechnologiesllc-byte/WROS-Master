"""
S-044/HRMS-0444 -- Multi-Touch Outreach Campaign.

Real architecture under test (see outreach_campaign_service module
docstring): start_campaign() is called unconditionally right after
Day-0 first contact (Step 4/TC-001 resolution of the spec's own
"triggered by no-response detection" vs "called after first messages
sent" inconsistency); no conversation_messages table -- ConversationEvent
is the real message log; no event bus -- cancel-on-reply wired into the
same 3 real inbound entry points S-041/S-043 already hook, and campaign
completion is a real durable row, not a fabricated publish into
ghosting detection; BR-01 cancel-on-reply; BR-02 fixed code-constant
sequence; BR-03 idempotent, one ACTIVE campaign per candidate; every
send additionally gated on is_ai_owner()/is_candidate_ghosted() for
consistency with every other outbound path this round.

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
from app.models.candidate_ghosting_status import CandidateGhostingStatus
from app.models.consent import ConsentRecord
from app.models.outreach_campaign import CampaignTouchpoint, OutreachCampaign
from app.models.user import Users

import app.services.outreach_campaign_service as svc


@pytest.fixture(autouse=True)
def _fake_whatsapp_number(monkeypatch):
    """See test_follow_up_scheduler_service.py's identical fixture for
    why this is necessary -- DEFAULT_WHATSAPP_NUMBER is captured once at
    import time from env state that's unreliable across a combined run."""
    import app.services.whatsapp_routing_service as wr_svc
    monkeypatch.setattr(wr_svc, "DEFAULT_WHATSAPP_NUMBER", "+15550009999")


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        OutreachCampaign.__table__, CampaignTouchpoint.__table__, CandidateGhostingStatus.__table__, ConsentRecord.__table__,
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
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya", candidateMobile="+919876543210")
    db_session.add_all([owner, candidate])
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp")
    db_session.add(conv)
    db_session.add(ConsentRecord(subject_type="candidate", subject_id="C-1", consent_type="whatsapp_outreach", consent_given=True, captured_by="candidate_self_service"))
    db_session.commit()
    return candidate, conv


# ── TC-001 / AC-1: campaign creation ────────────────────────────────

def test_start_campaign_creates_active_campaign(db_session, seeded):
    candidate, conv = seeded
    campaign = svc.start_campaign(db_session, "C-1", "U-ORG", conv.id)
    assert campaign.status == "ACTIVE"
    assert campaign.started_at is not None


def test_start_campaign_creates_three_pending_touchpoints_at_correct_offsets(db_session, seeded):
    candidate, conv = seeded
    before = datetime.utcnow()
    campaign = svc.start_campaign(db_session, "C-1", "U-ORG", conv.id)

    touchpoints = db_session.query(CampaignTouchpoint).filter(CampaignTouchpoint.campaign_id == campaign.id).order_by(CampaignTouchpoint.touchpoint_number).all()
    assert len(touchpoints) == 3
    assert [t.touchpoint_number for t in touchpoints] == [1, 2, 3]
    assert [t.channel for t in touchpoints] == ["email", "whatsapp", "email"]
    assert all(t.status == "PENDING" for t in touchpoints)

    expected_days = [1, 3, 7]
    for touchpoint, day in zip(touchpoints, expected_days):
        delta = touchpoint.scheduled_at - before
        assert timedelta(days=day, hours=-1) <= delta <= timedelta(days=day, hours=1)


# ── TC-003 / BR-03: idempotent ───────────────────────────────────────

def test_start_campaign_is_idempotent(db_session, seeded):
    candidate, conv = seeded
    first = svc.start_campaign(db_session, "C-1", "U-ORG", conv.id)
    second = svc.start_campaign(db_session, "C-1", "U-ORG", conv.id)

    assert first.id == second.id
    campaigns = db_session.query(OutreachCampaign).filter(OutreachCampaign.candidate_id == "C-1").all()
    assert len(campaigns) == 1
    touchpoints = db_session.query(CampaignTouchpoint).filter(CampaignTouchpoint.campaign_id == first.id).all()
    assert len(touchpoints) == 3  # not duplicated


def test_new_campaign_allowed_after_previous_completed(db_session, seeded):
    candidate, conv = seeded
    first = svc.start_campaign(db_session, "C-1", "U-ORG", conv.id)
    first.status = "COMPLETED"
    db_session.commit()

    second = svc.start_campaign(db_session, "C-1", "U-ORG", conv.id)
    assert second.id != first.id


# ── TC-002 / BR-01: cancel on reply ──────────────────────────────────

def test_cancel_campaign_on_reply_cancels_all_pending(db_session, seeded):
    candidate, conv = seeded
    campaign = svc.start_campaign(db_session, "C-1", "U-ORG", conv.id)

    cancelled = svc.cancel_campaign_on_reply(db_session, "C-1", "U-ORG")
    assert cancelled is True

    db_session.refresh(campaign)
    assert campaign.status == "COMPLETED"
    assert campaign.stop_reason == "CANDIDATE_REPLIED"

    touchpoints = db_session.query(CampaignTouchpoint).filter(CampaignTouchpoint.campaign_id == campaign.id).all()
    assert all(t.status == "CANCELLED" for t in touchpoints)


def test_cancel_campaign_on_reply_no_op_when_no_active_campaign(db_session, seeded):
    candidate, conv = seeded
    result = svc.cancel_campaign_on_reply(db_session, "C-1", "U-ORG")
    assert result is False


def test_execution_job_cancels_when_candidate_already_replied(db_session, seeded):
    candidate, conv = seeded
    campaign = svc.start_campaign(db_session, "C-1", "U-ORG", conv.id)
    campaign.started_at = datetime.utcnow() - timedelta(hours=1)
    db_session.commit()

    touchpoint = db_session.query(CampaignTouchpoint).filter(CampaignTouchpoint.campaign_id == campaign.id, CampaignTouchpoint.touchpoint_number == 1).first()
    touchpoint.scheduled_at = datetime.utcnow() - timedelta(minutes=5)
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={"channel": "whatsapp", "body": "yes!"}, triggered_by="candidate", created_at=datetime.utcnow()))
    db_session.commit()

    result = svc.run_campaign_execution_job(db_session)
    assert result["cancelled"] == 1

    db_session.refresh(campaign)
    assert campaign.status == "COMPLETED"
    assert campaign.stop_reason == "CANDIDATE_REPLIED"


# ── TC-002 (send) / AC: due touchpoint sent ──────────────────────────

def test_execution_job_sends_due_touchpoint(db_session, seeded, monkeypatch):
    candidate, conv = seeded
    campaign = svc.start_campaign(db_session, "C-1", "U-ORG", conv.id)
    touchpoint = db_session.query(CampaignTouchpoint).filter(CampaignTouchpoint.campaign_id == campaign.id, CampaignTouchpoint.touchpoint_number == 1).first()
    touchpoint.scheduled_at = datetime.utcnow() - timedelta(minutes=5)
    db_session.commit()

    monkeypatch.setattr("app.services.thunder_service.generate_followup_message_with_fallback", lambda db, cand, num, **kw: ("Following up on your application!", False))

    result = svc.run_campaign_execution_job(db_session)
    assert result["sent"] == 1

    db_session.refresh(touchpoint)
    assert touchpoint.status == "SENT"
    assert touchpoint.sent_at is not None


def test_execution_job_marks_campaign_completed_after_last_touchpoint(db_session, seeded, monkeypatch):
    candidate, conv = seeded
    campaign = svc.start_campaign(db_session, "C-1", "U-ORG", conv.id)
    touchpoints = db_session.query(CampaignTouchpoint).filter(CampaignTouchpoint.campaign_id == campaign.id).all()
    for t in touchpoints:
        t.status = "SENT"
        t.sent_at = datetime.utcnow()
    db_session.commit()

    last = max(touchpoints, key=lambda t: t.touchpoint_number)
    last.status = "PENDING"
    last.scheduled_at = datetime.utcnow() - timedelta(minutes=5)
    db_session.commit()

    monkeypatch.setattr("app.services.thunder_service.generate_followup_message_with_fallback", lambda db, cand, num, **kw: ("Final check-in!", False))

    svc.run_campaign_execution_job(db_session)

    db_session.refresh(campaign)
    assert campaign.status == "COMPLETED"
    assert campaign.stop_reason == "CAMPAIGN_COMPLETED_NO_RESPONSE"


def test_execution_job_ignores_not_yet_due_touchpoints(db_session, seeded):
    candidate, conv = seeded
    svc.start_campaign(db_session, "C-1", "U-ORG", conv.id)
    result = svc.run_campaign_execution_job(db_session)
    assert result["processed"] == 0


# ── consistency guards (not explicit in spec, added for parity) ─────

def test_execution_job_skips_when_recruiter_owns(db_session, seeded, monkeypatch):
    candidate, conv = seeded
    campaign = svc.start_campaign(db_session, "C-1", "U-ORG", conv.id)
    touchpoint = db_session.query(CampaignTouchpoint).filter(CampaignTouchpoint.campaign_id == campaign.id, CampaignTouchpoint.touchpoint_number == 1).first()
    touchpoint.scheduled_at = datetime.utcnow() - timedelta(minutes=5)
    conv.owner_type = "hr_user"
    conv.owner_id = "U-RECRUITER"
    db_session.commit()

    result = svc.run_campaign_execution_job(db_session)
    assert result["skipped"] == 1
    db_session.refresh(touchpoint)
    assert touchpoint.status == "SKIPPED"


def test_execution_job_skips_when_candidate_ghosted(db_session, seeded, monkeypatch):
    candidate, conv = seeded
    campaign = svc.start_campaign(db_session, "C-1", "U-ORG", conv.id)
    touchpoint = db_session.query(CampaignTouchpoint).filter(CampaignTouchpoint.campaign_id == campaign.id, CampaignTouchpoint.touchpoint_number == 1).first()
    touchpoint.scheduled_at = datetime.utcnow() - timedelta(minutes=5)
    db_session.add(CandidateGhostingStatus(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, ghosted_at=datetime.utcnow()))
    db_session.commit()

    result = svc.run_campaign_execution_job(db_session)
    assert result["skipped"] == 1


def test_execution_job_logs_touchpoint_send_failed_on_fallback(db_session, seeded, monkeypatch):
    candidate, conv = seeded
    campaign = svc.start_campaign(db_session, "C-1", "U-ORG", conv.id)
    touchpoint = db_session.query(CampaignTouchpoint).filter(CampaignTouchpoint.campaign_id == campaign.id, CampaignTouchpoint.touchpoint_number == 1).first()
    touchpoint.scheduled_at = datetime.utcnow() - timedelta(minutes=5)
    db_session.commit()

    monkeypatch.setattr("app.services.thunder_service.generate_followup_message_with_fallback", lambda db, cand, num, **kw: ("fallback message here", True))

    svc.run_campaign_execution_job(db_session)

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "TOUCHPOINT_SEND_FAILED").all()
    assert len(events) == 1


def test_execution_job_never_raises_on_bad_touchpoint(db_session, seeded, monkeypatch):
    candidate, conv = seeded
    campaign = svc.start_campaign(db_session, "C-1", "U-ORG", conv.id)
    touchpoint = db_session.query(CampaignTouchpoint).filter(CampaignTouchpoint.campaign_id == campaign.id, CampaignTouchpoint.touchpoint_number == 1).first()
    touchpoint.scheduled_at = datetime.utcnow() - timedelta(minutes=5)
    db_session.commit()

    def _boom(db, cand, num, **kw):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr("app.services.thunder_service.generate_followup_message_with_fallback", _boom)

    result = svc.run_campaign_execution_job(db_session)  # should not raise
    assert result["skipped"] == 1
