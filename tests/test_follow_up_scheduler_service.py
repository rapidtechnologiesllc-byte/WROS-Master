"""
S-041/HRMS-0441 -- Follow-Up Scheduler.

Real architecture under test (see follow_up_scheduler_service module
docstring): no conversation_messages table -- ConversationEvent is the
real message log; no system_configuration table -- SLA hours are env-
var-overridable module constants; whatsapp sends reuse the real, gated
send_thunder_message(); email sends reuse this codebase's existing
ungated EmailService.send_email() convention; BR-01 max 3 follow-ups;
BR-02 cancel-all-pending-on-reply; no formal "event bus" publish on the
3rd follow-up (see module docstring for the cross-story ownership
resolution with S-042).

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
from app.models.candidate_job_score import CandidateJobScore
from app.models.candidate_joining_score import CandidateJoiningScore
from app.models.consent import ConsentRecord
from app.models.employee import Employee
from app.models.follow_up_schedule import FollowUpSchedule
from app.models.interview_pipeline import SubmissionInterview
from app.models.offer_letter import OfferLetter
from app.models.preboarding_document import PreboardingDocument
from app.models.submission import Submission
from app.models.user import Users

import app.services.follow_up_scheduler_service as svc


@pytest.fixture(autouse=True)
def _fake_whatsapp_number(monkeypatch):
    """whatsapp_routing_service.DEFAULT_WHATSAPP_NUMBER is captured once
    at import time from THUNDER_WHATSAPP_NUMBER -- real value depends on
    env state, which is unreliable across a combined test run (same
    precedent as test_qualification_conversation_service.py's own fix
    for this). Every test here that reaches the real whatsapp send path
    needs a number to send from."""
    import app.services.whatsapp_routing_service as wr_svc
    monkeypatch.setattr(wr_svc, "DEFAULT_WHATSAPP_NUMBER", "+15550009999")


# Real 2026-08-04 reconciliation: this scheduler is now INTERVIEW-stage-
# only (see module constant FOLLOWUP_ELIGIBLE_STAGES) -- every test
# fixture candidate here defaults to INTERVIEW so the pre-existing
# tests still exercise the same send/skip logic they always did,
# without each one needing a real Client/Demand/Submission/
# SubmissionInterview chain just to reach that stage naturally. The
# one new stage-scoping test overrides this back to ENGAGED.
@pytest.fixture(autouse=True)
def _default_interview_stage(monkeypatch):
    monkeypatch.setattr(
        "app.services.candidate_journey_service.get_candidate_journey",
        lambda *a, **kw: {"current_stage": "INTERVIEW"},
    )


# A real Monday 10am IST -- inside the business-hours-weekday window,
# so tests aren't flaky depending on when they happen to run.
BUSINESS_HOURS_NOW = datetime(2026, 8, 3, 4, 30, 0)  # 2026-08-03 is a Monday; 04:30 UTC = 10:00 IST


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        FollowUpSchedule.__table__, ConsentRecord.__table__, CandidateGhostingStatus.__table__,
        CandidateJobScore.__table__, CandidateJoiningScore.__table__, Employee.__table__,
        OfferLetter.__table__, PreboardingDocument.__table__, Submission.__table__, SubmissionInterview.__table__,
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

    original = ConversationEvent(conversation_id=conv.id, event_type="ai_message_sent", event_data={"channel": "whatsapp", "body": "Hi, are you interested?"}, triggered_by="ai_agent")
    db_session.add(original)
    db_session.commit()
    return candidate, conv, original


# ── TC-001 / AC-1: schedule creation ────────────────────────────────

def test_schedule_follow_up_creates_pending_record(db_session, seeded):
    candidate, conv, original = seeded
    record = svc.schedule_follow_up(db_session, "C-1", "U-ORG", conv.id, "whatsapp", original.id, 1)
    assert record is not None
    assert record.status == "PENDING"
    assert record.follow_up_number == 1


def test_schedule_follow_up_whatsapp_defaults_to_24h(db_session, seeded):
    candidate, conv, original = seeded
    before = datetime.utcnow()
    record = svc.schedule_follow_up(db_session, "C-1", "U-ORG", conv.id, "whatsapp", original.id, 1)
    delta = record.scheduled_at - before
    assert timedelta(hours=23, minutes=58) <= delta <= timedelta(hours=24, minutes=2)


def test_schedule_follow_up_email_defaults_to_48h(db_session, seeded):
    candidate, conv, original = seeded
    before = datetime.utcnow()
    record = svc.schedule_follow_up(db_session, "C-1", "U-ORG", conv.id, "email", original.id, 1)
    delta = record.scheduled_at - before
    assert timedelta(hours=47, minutes=58) <= delta <= timedelta(hours=48, minutes=2)


def test_schedule_follow_up_dedupes_existing_pending(db_session, seeded):
    candidate, conv, original = seeded
    first = svc.schedule_follow_up(db_session, "C-1", "U-ORG", conv.id, "whatsapp", original.id, 1)
    second = svc.schedule_follow_up(db_session, "C-1", "U-ORG", conv.id, "whatsapp", original.id, 2)
    assert first is not None
    assert second is None
    rows = db_session.query(FollowUpSchedule).filter(FollowUpSchedule.candidate_id == "C-1").all()
    assert len(rows) == 1


# ── BR-01: max 3 follow-ups ──────────────────────────────────────────

def test_schedule_follow_up_refuses_fourth(db_session, seeded):
    candidate, conv, original = seeded
    result = svc.schedule_follow_up(db_session, "C-1", "U-ORG", conv.id, "whatsapp", original.id, 4)
    assert result is None
    assert db_session.query(FollowUpSchedule).count() == 0


# ── TC-005: SLA hours configurable via env var ──────────────────────

def test_followup_hours_configurable_via_env(monkeypatch):
    monkeypatch.setattr(svc, "WHATSAPP_FOLLOWUP_HOURS", 12)
    assert svc.followup_hours_for_channel("whatsapp") == 12


# ── TC-002 / AC-3: execution job sends a due follow-up ──────────────

def test_execution_job_sends_due_followup_and_marks_sent(db_session, seeded, monkeypatch):
    candidate, conv, original = seeded
    record = FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=BUSINESS_HOURS_NOW - timedelta(minutes=5), status="PENDING", follow_up_number=1, triggered_by_message_id=original.id)
    db_session.add(record)
    db_session.commit()

    monkeypatch.setattr("app.services.thunder_service.generate_followup_message_with_fallback", lambda db, cand, num, **kw: ("Just checking in!", False))

    result = svc.run_follow_up_execution_job(db_session, now=BUSINESS_HOURS_NOW)
    assert result["sent"] == 1

    db_session.refresh(record)
    assert record.status == "SENT"
    assert record.sent_at is not None

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "ai_message_sent").all()
    assert any(e.event_data.get("body") == "Just checking in!" for e in events)


def test_execution_job_schedules_next_followup_when_under_max(db_session, seeded, monkeypatch):
    candidate, conv, original = seeded
    record = FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=BUSINESS_HOURS_NOW - timedelta(minutes=5), status="PENDING", follow_up_number=1, triggered_by_message_id=original.id)
    db_session.add(record)
    db_session.commit()
    monkeypatch.setattr("app.services.thunder_service.generate_followup_message_with_fallback", lambda db, cand, num, **kw: ("Just checking in!", False))

    svc.run_follow_up_execution_job(db_session, now=BUSINESS_HOURS_NOW)

    pending = db_session.query(FollowUpSchedule).filter(FollowUpSchedule.candidate_id == "C-1", FollowUpSchedule.status == "PENDING").first()
    assert pending is not None
    assert pending.follow_up_number == 2


# ── TC-004 / AC-5: no 4th follow-up scheduled after the 3rd ─────────

def test_execution_job_does_not_schedule_fourth_after_third(db_session, seeded, monkeypatch):
    candidate, conv, original = seeded
    record = FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=BUSINESS_HOURS_NOW - timedelta(minutes=5), status="PENDING", follow_up_number=3, triggered_by_message_id=original.id)
    db_session.add(record)
    db_session.commit()
    monkeypatch.setattr("app.services.thunder_service.generate_followup_message_with_fallback", lambda db, cand, num, **kw: ("Final check-in!", False))

    svc.run_follow_up_execution_job(db_session, now=BUSINESS_HOURS_NOW)

    remaining_pending = db_session.query(FollowUpSchedule).filter(FollowUpSchedule.candidate_id == "C-1", FollowUpSchedule.status == "PENDING").count()
    assert remaining_pending == 0


# ── TC-003 / AC-4: cancel on reply ──────────────────────────────────

def test_execution_job_cancels_when_candidate_already_replied(db_session, seeded, monkeypatch):
    candidate, conv, original = seeded
    # Explicit created_at, well after `original` -- SQLite's server_default
    # func.now() only has second-level precision, so two rows created in
    # the same wall-clock second would otherwise tie on the strict ">"
    # comparison _has_replied_since() relies on.
    original.created_at = datetime.utcnow() - timedelta(hours=1)
    db_session.add(original)
    record = FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=BUSINESS_HOURS_NOW - timedelta(minutes=5), status="PENDING", follow_up_number=1, triggered_by_message_id=original.id)
    db_session.add(record)
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={"channel": "whatsapp", "body": "yes I'm interested"}, triggered_by="candidate", created_at=datetime.utcnow()))
    db_session.commit()

    result = svc.run_follow_up_execution_job(db_session, now=BUSINESS_HOURS_NOW)
    assert result["cancelled"] == 1
    db_session.refresh(record)
    assert record.status == "CANCELLED"


def test_cancel_pending_follow_ups_cancels_all(db_session, seeded):
    candidate, conv, original = seeded
    db_session.add_all([
        FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=datetime.utcnow() + timedelta(hours=1), status="PENDING", follow_up_number=1),
    ])
    db_session.commit()

    count = svc.cancel_pending_follow_ups(db_session, "C-1", "U-ORG")
    assert count == 1
    row = db_session.query(FollowUpSchedule).filter(FollowUpSchedule.candidate_id == "C-1").first()
    assert row.status == "CANCELLED"


def test_cancel_pending_follow_ups_no_pending_returns_zero(db_session, seeded):
    candidate, conv, original = seeded
    count = svc.cancel_pending_follow_ups(db_session, "C-1", "U-ORG")
    assert count == 0


# ── AC-9: skip if recruiter owns ────────────────────────────────────

def test_execution_job_skips_when_recruiter_owns(db_session, seeded):
    candidate, conv, original = seeded
    conv.owner_type = "hr_user"
    conv.owner_id = "U-RECRUITER"
    db_session.commit()

    record = FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=BUSINESS_HOURS_NOW - timedelta(minutes=5), status="PENDING", follow_up_number=1, triggered_by_message_id=original.id)
    db_session.add(record)
    db_session.commit()

    result = svc.run_follow_up_execution_job(db_session, now=BUSINESS_HOURS_NOW)
    assert result["skipped"] == 1
    db_session.refresh(record)
    assert record.status == "SKIPPED"


def test_execution_job_skips_when_conversation_closed(db_session, seeded):
    candidate, conv, original = seeded
    conv.status = "closed"
    db_session.commit()

    record = FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=BUSINESS_HOURS_NOW - timedelta(minutes=5), status="PENDING", follow_up_number=1, triggered_by_message_id=original.id)
    db_session.add(record)
    db_session.commit()

    result = svc.run_follow_up_execution_job(db_session, now=BUSINESS_HOURS_NOW)
    assert result["skipped"] == 1


def test_execution_job_skips_when_escalated(db_session, seeded):
    candidate, conv, original = seeded
    conv.escalation_state = "escalated"
    db_session.commit()

    record = FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=BUSINESS_HOURS_NOW - timedelta(minutes=5), status="PENDING", follow_up_number=1, triggered_by_message_id=original.id)
    db_session.add(record)
    db_session.commit()

    result = svc.run_follow_up_execution_job(db_session, now=BUSINESS_HOURS_NOW)
    assert result["skipped"] == 1


def test_execution_job_ignores_not_yet_due_followups(db_session, seeded):
    candidate, conv, original = seeded
    record = FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=datetime.utcnow() + timedelta(hours=1), status="PENDING", follow_up_number=1, triggered_by_message_id=original.id)
    db_session.add(record)
    db_session.commit()

    result = svc.run_follow_up_execution_job(db_session, now=BUSINESS_HOURS_NOW)
    assert result["processed"] == 0


def test_execution_job_logs_generation_failed_on_fallback(db_session, seeded, monkeypatch):
    candidate, conv, original = seeded
    record = FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=BUSINESS_HOURS_NOW - timedelta(minutes=5), status="PENDING", follow_up_number=1, triggered_by_message_id=original.id)
    db_session.add(record)
    db_session.commit()
    monkeypatch.setattr("app.services.thunder_service.generate_followup_message_with_fallback", lambda db, cand, num, **kw: (svc.__dict__.get("SAFE_FOLLOWUP_FALLBACK_MESSAGE", "fallback"), True))

    svc.run_follow_up_execution_job(db_session, now=BUSINESS_HOURS_NOW)

    failed_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "FOLLOWUP_GENERATION_FAILED").all()
    assert len(failed_events) == 1


def test_execution_job_never_raises_on_bad_row(db_session, seeded, monkeypatch):
    candidate, conv, original = seeded
    record = FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=BUSINESS_HOURS_NOW - timedelta(minutes=5), status="PENDING", follow_up_number=1, triggered_by_message_id=original.id)
    db_session.add(record)
    db_session.commit()

    def _boom(db, cand, num, **kw):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr("app.services.thunder_service.generate_followup_message_with_fallback", _boom)

    result = svc.run_follow_up_execution_job(db_session, now=BUSINESS_HOURS_NOW)  # should not raise
    assert result["skipped"] == 1


# ── Real 2026-08-04 cadence-by-stage reconciliation ──────────────────

def test_execution_job_skips_non_interview_stage(db_session, seeded, monkeypatch):
    monkeypatch.setattr(
        "app.services.candidate_journey_service.get_candidate_journey",
        lambda *a, **kw: {"current_stage": "ENGAGED"},
    )
    candidate, conv, original = seeded
    record = FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=BUSINESS_HOURS_NOW - timedelta(minutes=5), status="PENDING", follow_up_number=1, triggered_by_message_id=original.id)
    db_session.add(record)
    db_session.commit()

    result = svc.run_follow_up_execution_job(db_session, now=BUSINESS_HOURS_NOW)
    assert result["sent"] == 0
    assert result["skipped"] == 1
    db_session.refresh(record)
    assert record.status == "SKIPPED"


def test_execution_job_reschedules_outside_business_hours(db_session, seeded, monkeypatch):
    """BR: 24 calendar hours, but only sent Mon-Fri 9am-9pm candidate-
    local -- outside that window, the follow-up is rescheduled, not
    lost or sent at 2am."""
    candidate, conv, original = seeded
    record = FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=BUSINESS_HOURS_NOW - timedelta(minutes=5), status="PENDING", follow_up_number=1, triggered_by_message_id=original.id)
    db_session.add(record)
    db_session.commit()

    saturday_2am_ist = datetime(2026, 8, 1, 20, 30, 0)  # 2026-08-01 is a Saturday; 20:30 UTC Fri = 2:00 AM Sat IST
    result = svc.run_follow_up_execution_job(db_session, now=saturday_2am_ist)
    assert result["sent"] == 0
    db_session.refresh(record)
    assert record.status == "PENDING"  # not lost -- rescheduled
    assert record.scheduled_at > saturday_2am_ist
