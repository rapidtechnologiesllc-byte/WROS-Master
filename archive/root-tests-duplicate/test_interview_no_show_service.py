"""
S-052/HRMS-0452 -- Interview No-Show Handling.

Real architecture under test (see interview_no_show_service module
docstring): no interviews.status literal values -- 4 new
timestamp-presence columns on SubmissionInterview instead. BR-01's
30-min cutoff is enforced as elapsed time since scheduled_at_utc, not
elapsed time since check-in. BR-02: nothing here ever
auto-disqualifies -- no_show_no_response_at is observability only.
Step 4 routes a reply to interview_reschedule_service.start_reschedule()
directly (this story's own spec says to).

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
from app.models.candidate_availability_slot import CandidateAvailabilitySlot
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

import app.services.interview_no_show_service as svc
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
        CandidateAvailabilitySlot.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
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
    interviewer_user = Users(UserID="U-INT-1", UserRole="Employee", UserEmail="tom@blitzenx.com", UserPassword="h", tenant_id=tenant.id, timezone="America/Chicago")
    db_session.add(interviewer_user)
    db_session.commit()
    panel = assign_panel_member(db_session, tenant_id=tenant.id, demand_id=demand.id, employee=interviewer_employee, interview_level="L1")
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp")
    db_session.add(conv)
    db_session.add(ConsentRecord(subject_type="candidate", subject_id="C-1", consent_type="whatsapp_outreach", consent_given=True, captured_by="candidate_self_service"))
    db_session.commit()

    return tenant, candidate, submission, conv, panel


def _make_confirmed_interview(db, tenant, submission, panel, minutes_ago):
    scheduled_at = datetime.now(dt_timezone.utc).replace(microsecond=0, tzinfo=None) - timedelta(minutes=minutes_ago)
    interview = create_interview(db, tenant_id=tenant.id, submission=submission, level="L1", panel=panel, scheduled_at=scheduled_at)
    db.commit()
    interview.confirmed_at = datetime.utcnow()
    db.add(interview)
    db.commit()
    return interview


# ── AC-1/TC-001: check-in sent at 15 min ──────────────────────────────

def test_check_in_sent_at_15_minutes(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    interview = _make_confirmed_interview(db_session, tenant, submission, panel, minutes_ago=16)

    with patch.object(svc.EmailService, "send_email", return_value={"status": "success"}) as mock_send:
        result = svc.run_no_show_detection_job(db_session)

    assert result["check_in_sent"] == 1
    mock_send.assert_called_once()

    db_session.refresh(interview)
    assert interview.no_show_check_in_at is not None
    assert interview.no_show_confirmed_at is None


def test_check_in_not_sent_before_15_minutes(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    interview = _make_confirmed_interview(db_session, tenant, submission, panel, minutes_ago=5)

    result = svc.run_no_show_detection_job(db_session)
    assert result["check_in_sent"] == 0

    db_session.refresh(interview)
    assert interview.no_show_check_in_at is None


# ── AC-3/TC-002: candidate reply prevents no-show ─────────────────────

def test_candidate_reply_after_scheduled_time_prevents_check_in(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    interview = _make_confirmed_interview(db_session, tenant, submission, panel, minutes_ago=20)
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={"body": "sorry, joining now!"}, triggered_by="candidate", created_at=datetime.utcnow() - timedelta(minutes=2)))
    db_session.commit()

    result = svc.run_no_show_detection_job(db_session)
    assert result["check_in_sent"] == 0

    db_session.refresh(interview)
    assert interview.no_show_check_in_at is None


def test_candidate_reply_after_check_in_prevents_no_show_confirmation(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    interview = _make_confirmed_interview(db_session, tenant, submission, panel, minutes_ago=31)
    interview.no_show_check_in_at = datetime.utcnow() - timedelta(minutes=10)
    db_session.commit()
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={"body": "here now"}, triggered_by="candidate", created_at=datetime.utcnow() - timedelta(minutes=1)))
    db_session.commit()

    result = svc.run_no_show_detection_job(db_session)
    assert result["no_show_confirmed"] == 0

    db_session.refresh(interview)
    assert interview.no_show_confirmed_at is None


# ── AC-4/TC-003: no-show confirmed at 30 min, both parties notified ───

def test_no_show_confirmed_after_30_minutes_notifies_both_parties(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    interview = _make_confirmed_interview(db_session, tenant, submission, panel, minutes_ago=31)
    interview.no_show_check_in_at = datetime.utcnow() - timedelta(minutes=16)
    db_session.commit()

    with patch.object(svc.EmailService, "send_email", return_value={"status": "success"}) as mock_send:
        result = svc.run_no_show_detection_job(db_session)

    assert result["no_show_confirmed"] == 1
    mock_send.assert_called_once()  # interviewer email

    db_session.refresh(interview)
    assert interview.no_show_confirmed_at is not None

    event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "INTERVIEW_NO_SHOW").first()
    assert event is not None

    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1


def test_no_show_not_confirmed_before_30_minutes(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    interview = _make_confirmed_interview(db_session, tenant, submission, panel, minutes_ago=20)
    interview.no_show_check_in_at = datetime.utcnow() - timedelta(minutes=5)
    db_session.commit()

    result = svc.run_no_show_detection_job(db_session)
    assert result["no_show_confirmed"] == 0


def test_never_raises_on_missing_candidate(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    interview = _make_confirmed_interview(db_session, tenant, submission, panel, minutes_ago=16)
    interview.candidate_id = "NOPE"
    db_session.commit()

    result = svc.run_no_show_detection_job(db_session)  # should not raise
    assert result["check_in_sent"] == 0


# ── AC-7: reschedule offer 2h after no-show ────────────────────────────

def test_reschedule_offer_sent_2_hours_after_no_show(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    interview = _make_confirmed_interview(db_session, tenant, submission, panel, minutes_ago=200)
    interview.no_show_confirmed_at = datetime.utcnow() - timedelta(hours=2, minutes=5)
    db_session.commit()

    result = svc.run_no_show_followup_job(db_session)
    assert result["offer_sent"] == 1

    db_session.refresh(interview)
    assert interview.no_show_reschedule_offer_sent_at is not None


def test_reschedule_offer_not_sent_before_2_hours(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    interview = _make_confirmed_interview(db_session, tenant, submission, panel, minutes_ago=200)
    interview.no_show_confirmed_at = datetime.utcnow() - timedelta(minutes=30)
    db_session.commit()

    result = svc.run_no_show_followup_job(db_session)
    assert result["offer_sent"] == 0


# ── Step 4(b): reply to offer routes to reschedule ────────────────────

def test_reply_to_reschedule_offer_routes_to_reschedule_flow(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    interview = _make_confirmed_interview(db_session, tenant, submission, panel, minutes_ago=300)
    interview.no_show_confirmed_at = datetime.utcnow() - timedelta(hours=5)
    interview.no_show_reschedule_offer_sent_at = datetime.utcnow() - timedelta(hours=3)
    interview.scheduled_via_graph_event_id = "evt-original"
    db_session.commit()
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={"body": "yes please reschedule"}, triggered_by="candidate", created_at=datetime.utcnow() - timedelta(hours=1)))
    db_session.commit()

    result = svc.run_no_show_followup_job(db_session, )
    assert result["rescheduled"] == 1

    reschedule_event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "RESCHEDULE_STARTED").first()
    assert reschedule_event is not None
    assert reschedule_event.event_data["old_interview_id"] == interview.id


# ── Step 4(c)/BR-02: 48h no reply -> observability marker only ────────

def test_no_reply_after_48h_marks_no_response_without_disqualifying(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    interview = _make_confirmed_interview(db_session, tenant, submission, panel, minutes_ago=4000)
    interview.no_show_confirmed_at = datetime.utcnow() - timedelta(hours=52)
    interview.no_show_reschedule_offer_sent_at = datetime.utcnow() - timedelta(hours=49)
    db_session.commit()

    result = svc.run_no_show_followup_job(db_session)
    assert result["no_response"] == 1

    db_session.refresh(interview)
    assert interview.no_show_no_response_at is not None

    # BR-02: never auto-disqualifies -- submission status untouched.
    db_session.refresh(submission)
    assert submission.status == "SUBMITTED"


def test_no_response_not_marked_before_48h(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    interview = _make_confirmed_interview(db_session, tenant, submission, panel, minutes_ago=300)
    interview.no_show_confirmed_at = datetime.utcnow() - timedelta(hours=5)
    interview.no_show_reschedule_offer_sent_at = datetime.utcnow() - timedelta(hours=10)
    db_session.commit()

    result = svc.run_no_show_followup_job(db_session)
    assert result["no_response"] == 0
