"""
S-050/HRMS-0450 -- Interview Reminder Engine.

Real architecture under test (see interview_reminder_service module
docstring): no interview.confirmed event bus -- schedule_reminders_for_interview()
is a real, directly-callable function; BR-03's "interview.status=CONFIRMED"
check maps to confirmed_at is not None (no RESCHEDULED/CANCELLED status
exists since HRMS-0451 doesn't exist yet); BR-02 escalates to
REMINDER_SEND_FAILED + recruiter notification only when BOTH channels
fail, per the spec's own integrations table.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.client import Client
from app.models.consent import ConsentRecord
from app.models.demand import Demand, DemandHistory
from app.models.employee import Employee
from app.models.interview_pipeline import DemandInterviewPanel, SubmissionInterview
from app.models.interview_reminder import InterviewReminder
from app.models.notification import Notification
from app.models.submission import Submission, SubmissionViolation
from app.models.tenant import Tenant
from app.models.user import Users

import app.services.interview_reminder_service as svc
from app.services.interview_service import assign_panel_member, create_interview
from app.services.submission_service import create_submission


@pytest.fixture(autouse=True)
def _fake_whatsapp_number(monkeypatch):
    import app.services.whatsapp_routing_service as wr_svc
    monkeypatch.setattr(wr_svc, "DEFAULT_WHATSAPP_NUMBER", "+15550009999")


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Client.__table__, Demand.__table__, DemandHistory.__table__,
        Candidate.__table__, Employee.__table__, Users.__table__,
        Submission.__table__, SubmissionViolation.__table__,
        DemandInterviewPanel.__table__, SubmissionInterview.__table__, InterviewReminder.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__,
        Notification.__table__, ConsentRecord.__table__,
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
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    client = Client(tenant_id=tenant.id, company_name="Acme Insurance")
    db_session.add(client)
    db_session.commit()

    demand = Demand(tenant_id=tenant.id, client_id=client.id, job_title="Sr. Guidewire Developer", required_skills="[]", min_experience_years=5.0, work_location="REMOTE", status="OPEN")
    db_session.add(demand)
    db_session.commit()

    recruiter = Users(UserID="U-RECRUITER", UserRole="Recruiter", UserEmail="recruiter@blitzenx.com", UserPassword="h", tenant_id=tenant.id)
    db_session.add(recruiter)
    db_session.commit()

    candidate = Candidate(
        candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya",
        candidateMobile="+919876543210", tenant_id=tenant.id, timezone="America/Chicago",
        total_experience_months=72, employment_type="W2_FULLTIME",
    )
    db_session.add(candidate)
    db_session.commit()

    employee = Employee(tenant_id=tenant.id, candidate_id="C-1", first_name="Priya", last_name="S", email="c1@example.com", joining_date=date(2026, 1, 1), status="BENCH")
    db_session.add(employee)
    db_session.commit()

    submission = create_submission(db_session, tenant_id=tenant.id, demand=demand, candidate=candidate, submitted_by_user_id="U-RECRUITER")
    db_session.commit()

    interviewer_employee = Employee(tenant_id=tenant.id, first_name="Tom", last_name="Kumar", email="tom@blitzenx.com", joining_date=date(2025, 1, 1), status="ACTIVE", wros_user_id="U-INT-1")
    db_session.add(interviewer_employee)
    db_session.commit()
    panel = assign_panel_member(db_session, tenant_id=tenant.id, demand_id=demand.id, employee=interviewer_employee, interview_level="L1")
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp")
    db_session.add(conv)
    db_session.add(ConsentRecord(subject_type="candidate", subject_id="C-1", consent_type="whatsapp_outreach", consent_given=True, captured_by="candidate_self_service"))
    db_session.commit()

    return tenant, candidate, submission, conv, panel


def _make_interview(db, tenant, submission, panel, scheduled_at, confirmed=True):
    interview = create_interview(db, tenant_id=tenant.id, submission=submission, level="L1", panel=panel, scheduled_at=scheduled_at)
    db.commit()
    if confirmed:
        interview.confirmed_at = datetime.utcnow()
        db.add(interview)
        db.commit()
    return interview


# ── AC-1/TC-001: reminders created for a far-future interview ─────────

def test_schedules_both_reminders_for_interview_days_away(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    now = datetime.now(dt_timezone.utc)
    scheduled_at = now + timedelta(days=3)
    interview = _make_interview(db_session, tenant, submission, panel, scheduled_at)

    result = svc.schedule_reminders_for_interview(db_session, interview.id, now=now)
    assert result["outcome"] == "scheduled"
    assert set(result["reminders_created"]) == {"24H_BEFORE", "1H_BEFORE"}

    reminders = db_session.query(InterviewReminder).filter(InterviewReminder.interview_id == interview.id).all()
    assert len(reminders) == 2
    by_type = {r.reminder_type: r for r in reminders}
    assert abs((by_type["24H_BEFORE"].scheduled_at.replace(tzinfo=dt_timezone.utc) - (scheduled_at - timedelta(hours=24))).total_seconds()) < 2
    assert abs((by_type["1H_BEFORE"].scheduled_at.replace(tzinfo=dt_timezone.utc) - (scheduled_at - timedelta(hours=1))).total_seconds()) < 2
    assert all(r.status == "PENDING" for r in reminders)


# ── AC-6/TC-004: short-notice interview skips the 24H reminder ────────

def test_short_notice_interview_skips_24h_reminder(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    now = datetime.now(dt_timezone.utc)
    scheduled_at = now + timedelta(hours=15)  # < 25h away
    interview = _make_interview(db_session, tenant, submission, panel, scheduled_at)

    result = svc.schedule_reminders_for_interview(db_session, interview.id, now=now)
    assert result["reminders_created"] == ["1H_BEFORE"]

    reminders = db_session.query(InterviewReminder).filter(InterviewReminder.interview_id == interview.id).all()
    assert len(reminders) == 1
    assert reminders[0].reminder_type == "1H_BEFORE"


def test_very_short_notice_skips_both_reminders(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    now = datetime.now(dt_timezone.utc)
    scheduled_at = now + timedelta(minutes=30)  # < 70min away
    interview = _make_interview(db_session, tenant, submission, panel, scheduled_at)

    result = svc.schedule_reminders_for_interview(db_session, interview.id, now=now)
    assert result["reminders_created"] == []
    assert db_session.query(InterviewReminder).filter(InterviewReminder.interview_id == interview.id).count() == 0


def test_interview_not_found_returns_honest_outcome(db_session, seeded):
    result = svc.schedule_reminders_for_interview(db_session, "nonexistent")
    assert result["outcome"] == "interview_not_found"


# ── AC-2/TC-002: execution job sends due reminders via both channels ──

def test_execution_job_sends_due_reminder_via_both_channels(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    scheduled_at = datetime.now(dt_timezone.utc) + timedelta(days=1)
    interview = _make_interview(db_session, tenant, submission, panel, scheduled_at)

    reminder = InterviewReminder(tenant_id=tenant.id, interview_id=interview.id, candidate_id="C-1", reminder_type="24H_BEFORE", scheduled_at=datetime.now(dt_timezone.utc) - timedelta(minutes=5))
    db_session.add(reminder)
    db_session.commit()

    with patch.object(svc.EmailService, "send_email", return_value={"status": "success"}) as mock_send:
        result = svc.run_reminder_execution_job(db_session)

    assert result["sent"] == 1
    mock_send.assert_called_once()

    db_session.refresh(reminder)
    assert reminder.status == "SENT"
    assert reminder.sent_at is not None

    email_event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "ai_message_sent").first()
    assert email_event is not None


def test_execution_job_ignores_not_yet_due_reminders(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    scheduled_at = datetime.now(dt_timezone.utc) + timedelta(days=1)
    interview = _make_interview(db_session, tenant, submission, panel, scheduled_at)

    reminder = InterviewReminder(tenant_id=tenant.id, interview_id=interview.id, candidate_id="C-1", reminder_type="24H_BEFORE", scheduled_at=datetime.now(dt_timezone.utc) + timedelta(hours=1))
    db_session.add(reminder)
    db_session.commit()

    result = svc.run_reminder_execution_job(db_session)
    assert result["processed"] == 0


# ── BR-03/AC-4/TC-003: cancelled when interview isn't confirmed ──────

def test_execution_job_cancels_reminder_when_interview_not_confirmed(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    scheduled_at = datetime.now(dt_timezone.utc) + timedelta(days=1)
    interview = _make_interview(db_session, tenant, submission, panel, scheduled_at, confirmed=False)  # never confirmed

    reminder = InterviewReminder(tenant_id=tenant.id, interview_id=interview.id, candidate_id="C-1", reminder_type="24H_BEFORE", scheduled_at=datetime.now(dt_timezone.utc) - timedelta(minutes=5))
    db_session.add(reminder)
    db_session.commit()

    result = svc.run_reminder_execution_job(db_session)
    assert result["cancelled"] == 1

    db_session.refresh(reminder)
    assert reminder.status == "CANCELLED"


def test_cancel_pending_reminders_for_interview(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    scheduled_at = datetime.now(dt_timezone.utc) + timedelta(days=3)
    interview = _make_interview(db_session, tenant, submission, panel, scheduled_at)
    svc.schedule_reminders_for_interview(db_session, interview.id)

    cancelled_count = svc.cancel_pending_reminders_for_interview(db_session, interview.id)
    assert cancelled_count == 2

    reminders = db_session.query(InterviewReminder).filter(InterviewReminder.interview_id == interview.id).all()
    assert all(r.status == "CANCELLED" for r in reminders)


# ── BR-02: both channels fail -> REMINDER_SEND_FAILED + recruiter notified ─

def test_both_channels_failing_escalates_and_notifies_recruiter(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    scheduled_at = datetime.now(dt_timezone.utc) + timedelta(days=1)
    interview = _make_interview(db_session, tenant, submission, panel, scheduled_at)

    # Make WhatsApp fail too, by using an owner_type of hr_user (R-08 blocks Thunder).
    conv.owner_type = "hr_user"
    conv.owner_id = "U-RECRUITER"
    db_session.commit()

    reminder = InterviewReminder(tenant_id=tenant.id, interview_id=interview.id, candidate_id="C-1", reminder_type="1H_BEFORE", scheduled_at=datetime.now(dt_timezone.utc) - timedelta(minutes=5))
    db_session.add(reminder)
    db_session.commit()

    with patch.object(svc.EmailService, "send_email", side_effect=RuntimeError("simulated outage")):
        result = svc.run_reminder_execution_job(db_session)

    assert result["skipped"] == 1
    db_session.refresh(reminder)
    assert reminder.status == "CANCELLED"

    failed_event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "REMINDER_SEND_FAILED").first()
    assert failed_event is not None

    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1


def test_execution_job_never_raises_on_bad_row(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    scheduled_at = datetime.now(dt_timezone.utc) + timedelta(days=1)
    interview = _make_interview(db_session, tenant, submission, panel, scheduled_at)

    reminder = InterviewReminder(tenant_id=tenant.id, interview_id=interview.id, candidate_id="NOPE", reminder_type="1H_BEFORE", scheduled_at=datetime.now(dt_timezone.utc) - timedelta(minutes=5))
    db_session.add(reminder)
    db_session.commit()

    result = svc.run_reminder_execution_job(db_session)  # should not raise -- candidate not found -> cancelled
    assert result["cancelled"] == 1
