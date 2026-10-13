"""
S-045/HRMS-0445 -- Reactivation Campaign.

Real architecture under test (see reactivation_campaign_service module
docstring for the full rationale): this is a REAL, EXPLICIT SPEC
OVERRIDE from Avinash -- the literal spec archives a candidate after
one failed reactivation campaign; Avinash's direct instruction was
"keep trying till I succeed -- no candidate should ever be left."
There is no archive/terminal state anywhere in this module, and
reactivation_attempt_count is observability-only, never a cutoff.
These tests assert that override behavior explicitly (see the
"no archive, ever" section below), not just its absence.

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

import app.services.reactivation_campaign_service as svc


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

    ghosting_status = CandidateGhostingStatus(
        tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id,
        ghosted_at=datetime.utcnow() - timedelta(days=14),
        reactivation_scheduled_at=datetime.utcnow() - timedelta(minutes=5),
    )
    db_session.add(ghosting_status)
    db_session.commit()
    return candidate, conv, ghosting_status


def _fake_generate(msg="It's been a while -- still interested?"):
    return lambda db, cand, days, **kw: (msg, False)


# ── Step 2 / AC: due reactivation is sent ────────────────────────────

def test_job_sends_due_reactivation_and_starts_campaign(db_session, seeded, monkeypatch):
    candidate, conv, status_row = seeded
    monkeypatch.setattr("app.services.thunder_service.generate_reactivation_message_with_fallback", _fake_generate())

    result = svc.run_reactivation_job(db_session)
    assert result["sent"] == 1

    db_session.refresh(status_row)
    assert status_row.reactivation_attempt_count == 1
    assert status_row.last_reactivation_sent_at is not None
    assert status_row.reactivation_scheduled_at is None  # in flight via the campaign now

    campaign = db_session.query(OutreachCampaign).filter(OutreachCampaign.candidate_id == "C-1", OutreachCampaign.campaign_type == "REACTIVATION_CAMPAIGN").first()
    assert campaign is not None
    assert campaign.status == "ACTIVE"

    sent_event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "REACTIVATION_SENT").first()
    assert sent_event is not None


def test_job_ignores_not_yet_due_reactivations(db_session, seeded):
    candidate, conv, status_row = seeded
    status_row.reactivation_scheduled_at = datetime.utcnow() + timedelta(days=1)
    db_session.commit()

    result = svc.run_reactivation_job(db_session)
    assert result["processed"] == 0


def test_job_ignores_rows_with_no_scheduled_reactivation(db_session, seeded):
    candidate, conv, status_row = seeded
    status_row.reactivation_scheduled_at = None
    db_session.commit()

    result = svc.run_reactivation_job(db_session)
    assert result["processed"] == 0


def test_job_skips_already_reactivated_candidate(db_session, seeded):
    candidate, conv, status_row = seeded
    status_row.is_reactivated = True
    db_session.commit()

    result = svc.run_reactivation_job(db_session)
    assert result["processed"] == 0


# ── Reply mid-cycle self-reactivates, does not archive ───────────────

def test_job_reactivates_instead_of_sending_if_candidate_already_replied(db_session, seeded, monkeypatch):
    candidate, conv, status_row = seeded
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={"channel": "whatsapp", "body": "yes still interested!"}, triggered_by="candidate", created_at=datetime.utcnow()))
    db_session.commit()

    called = {"generate": False}
    def _boom(db, cand, days, **kw):
        called["generate"] = True
        return ("should not be sent", False)
    monkeypatch.setattr("app.services.thunder_service.generate_reactivation_message_with_fallback", _boom)

    result = svc.run_reactivation_job(db_session)
    assert result["skipped"] == 1
    assert called["generate"] is False

    db_session.refresh(status_row)
    assert status_row.is_reactivated is True


# ── Consistency guards (ownership/closed/escalated) ──────────────────

def test_job_skips_when_recruiter_owns(db_session, seeded):
    candidate, conv, status_row = seeded
    conv.owner_type = "hr_user"
    conv.owner_id = "U-RECRUITER"
    db_session.commit()

    result = svc.run_reactivation_job(db_session)
    assert result["skipped"] == 1


def test_job_skips_when_conversation_closed(db_session, seeded):
    candidate, conv, status_row = seeded
    conv.status = "closed"
    db_session.commit()

    result = svc.run_reactivation_job(db_session)
    assert result["skipped"] == 1


def test_job_logs_generation_failed_on_fallback(db_session, seeded, monkeypatch):
    candidate, conv, status_row = seeded
    monkeypatch.setattr("app.services.thunder_service.generate_reactivation_message_with_fallback", lambda db, cand, days, **kw: ("fallback text", True))

    svc.run_reactivation_job(db_session)

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "REACTIVATION_GENERATION_FAILED").all()
    assert len(events) == 1


def test_job_never_raises_on_bad_row(db_session, seeded, monkeypatch):
    candidate, conv, status_row = seeded

    def _boom(db, cand, days, **kw):
        raise RuntimeError("simulated failure")
    monkeypatch.setattr("app.services.thunder_service.generate_reactivation_message_with_fallback", _boom)

    result = svc.run_reactivation_job(db_session)  # should not raise
    assert result["skipped"] == 1


# ── "No archive, ever" -- the explicit S-045 override ────────────────

def test_no_response_after_campaign_reschedules_instead_of_archiving(db_session, seeded):
    candidate, conv, status_row = seeded
    status_row.reactivation_scheduled_at = None  # already sent, campaign now running
    campaign = OutreachCampaign(
        tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, campaign_type="REACTIVATION_CAMPAIGN",
        status="COMPLETED", stop_reason="CAMPAIGN_COMPLETED_NO_RESPONSE",
        started_at=datetime.utcnow() - timedelta(days=10), completed_at=datetime.utcnow(),
    )
    db_session.add(campaign)
    db_session.commit()

    result = svc.run_reactivation_reschedule_job(db_session)
    assert result["rescheduled"] == 1

    db_session.refresh(status_row)
    assert status_row.is_reactivated is False  # not archived -- still active, just waiting
    assert status_row.reactivation_scheduled_at is not None
    assert status_row.reactivation_scheduled_at > datetime.utcnow() + timedelta(days=1)

    # No archive event of any kind was ever logged.
    archive_events = db_session.query(ConversationEvent).filter(ConversationEvent.event_type.like("%ARCHIV%")).all()
    assert archive_events == []


def test_reschedule_job_does_not_double_schedule_already_pending(db_session, seeded):
    candidate, conv, status_row = seeded
    status_row.reactivation_scheduled_at = datetime.utcnow() + timedelta(days=5)  # already has a next attempt queued
    campaign = OutreachCampaign(
        tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, campaign_type="REACTIVATION_CAMPAIGN",
        status="COMPLETED", stop_reason="CAMPAIGN_COMPLETED_NO_RESPONSE",
        started_at=datetime.utcnow() - timedelta(days=10), completed_at=datetime.utcnow(),
    )
    db_session.add(campaign)
    db_session.commit()
    original_scheduled_at = status_row.reactivation_scheduled_at

    result = svc.run_reactivation_reschedule_job(db_session)
    assert result["rescheduled"] == 0

    db_session.refresh(status_row)
    assert status_row.reactivation_scheduled_at == original_scheduled_at


def test_reschedule_job_skips_already_reactivated_candidate(db_session, seeded):
    candidate, conv, status_row = seeded
    status_row.is_reactivated = True
    status_row.reactivation_scheduled_at = None
    campaign = OutreachCampaign(
        tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, campaign_type="REACTIVATION_CAMPAIGN",
        status="COMPLETED", stop_reason="CAMPAIGN_COMPLETED_NO_RESPONSE",
        started_at=datetime.utcnow() - timedelta(days=10), completed_at=datetime.utcnow(),
    )
    db_session.add(campaign)
    db_session.commit()

    result = svc.run_reactivation_reschedule_job(db_session)
    assert result["rescheduled"] == 0


def test_repeated_cycles_keep_retrying_indefinitely(db_session, seeded, monkeypatch):
    """Simulate 3 full send -> campaign-exhaustion -> reschedule cycles.
    Asserts the candidate is still active (never archived, never capped)
    after every cycle -- the core claim of the S-045 override."""
    candidate, conv, status_row = seeded

    for cycle in range(3):
        db_session.refresh(status_row)
        status_row.reactivation_scheduled_at = datetime.utcnow() - timedelta(minutes=5)
        db_session.commit()

        # Distinct message text per cycle -- send_thunder_message's own
        # debounce guard suppresses an identical body sent within 60s,
        # which would otherwise mask this test's real intent.
        monkeypatch.setattr("app.services.thunder_service.generate_reactivation_message_with_fallback", _fake_generate(f"Reactivation attempt #{cycle + 1} -- still interested?"))

        send_result = svc.run_reactivation_job(db_session)
        assert send_result["sent"] == 1

        campaign = db_session.query(OutreachCampaign).filter(OutreachCampaign.candidate_id == "C-1", OutreachCampaign.campaign_type == "REACTIVATION_CAMPAIGN", OutreachCampaign.status == "ACTIVE").first()
        assert campaign is not None
        campaign.status = "COMPLETED"
        campaign.stop_reason = "CAMPAIGN_COMPLETED_NO_RESPONSE"
        campaign.completed_at = datetime.utcnow()
        db_session.commit()

        reschedule_result = svc.run_reactivation_reschedule_job(db_session)
        assert reschedule_result["rescheduled"] == 1

        db_session.refresh(status_row)
        assert status_row.is_reactivated is False
        assert status_row.reactivation_scheduled_at is not None  # queued for another attempt, never archived

    db_session.refresh(status_row)
    assert status_row.reactivation_attempt_count == 3  # observability only -- no cap enforced despite 3 full cycles
