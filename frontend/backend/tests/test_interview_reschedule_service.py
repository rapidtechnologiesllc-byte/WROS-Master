"""
S-051/HRMS-0451 -- Interview Reschedule Workflow.

Real architecture under test (see interview_reschedule_service module
docstring): ties S-047/S-048/S-049/S-050 together for real (this
story's own job). No INTERVIEW_SCHEDULED/RESCHEDULING conversation
state -- "is a reschedule mid-flight, for which old interview" is
derived from ConversationEvent history (RESCHEDULE_STARTED with no
later INTERVIEW_RESCHEDULED/RESCHEDULE_LIMIT_ESCALATED). BR-03's real
constraint conflict (two SubmissionInterview rows for the same
submission+level) is resolved via the new partial unique index --
superseded_at is set on the old interview in the SAME commit as the
new interview's creation, only on an actual match.

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
from app.models.recruiter_intervention_queue import RecruiterInterventionQueue
from app.models.user import Users

import app.services.interview_reschedule_service as svc
from app.services.interview_availability_service import parse_availability_response
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
        Notification.__table__, ConsentRecord.__table__, RecruiterInterventionQueue.__table__,
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


def _make_confirmed_interview(db, tenant, submission, panel, *, reschedule_count=0, graph_event_id="evt-original"):
    scheduled_at = datetime.now(dt_timezone.utc).replace(microsecond=0) + timedelta(days=3)
    interview = create_interview(db, tenant_id=tenant.id, submission=submission, level="L1", panel=panel, scheduled_at=scheduled_at, reschedule_count=reschedule_count)
    db.commit()
    interview.confirmed_at = datetime.utcnow()
    interview.scheduled_via_graph_event_id = graph_event_id
    db.add(interview)
    db.commit()
    return interview


def _next_weekday(base, target_weekday):
    from datetime import date as date_cls
    days_ahead = (target_weekday - base.weekday()) % 7
    return base + timedelta(days=days_ahead)


# ── AC-1/TC-001: reschedule detected and acknowledged ─────────────────

def test_start_reschedule_cancels_outlook_event_and_reminders(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    interview = _make_confirmed_interview(db_session, tenant, submission, panel)

    reminder = InterviewReminder(tenant_id=tenant.id, interview_id=interview.id, candidate_id="C-1", reminder_type="24H_BEFORE", scheduled_at=datetime.utcnow() + timedelta(days=2))
    db_session.add(reminder)
    db_session.commit()

    deleted = {}
    def graph_delete(email, event_id):
        deleted["email"] = email
        deleted["event_id"] = event_id

    result = svc.start_reschedule(db_session, candidate, conv, "U-ORG", graph_delete_event_call=graph_delete)
    assert result["outcome"] == "reschedule_started"
    assert result["message"] == svc.RESCHEDULE_ACK_MESSAGE
    assert deleted == {"email": "tom@blitzenx.com", "event_id": "evt-original"}

    db_session.refresh(reminder)
    assert reminder.status == "CANCELLED"

    event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "RESCHEDULE_STARTED").first()
    assert event is not None
    assert event.event_data["old_interview_id"] == interview.id


def test_start_reschedule_clears_existing_availability_slots(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    interview = _make_confirmed_interview(db_session, tenant, submission, panel)
    from datetime import time as time_cls
    db_session.add(CandidateAvailabilitySlot(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, slot_date=date.today() + timedelta(days=1), slot_start_time=time_cls(9, 0), slot_end_time=time_cls(10, 0), timezone="America/Chicago"))
    db_session.commit()

    svc.start_reschedule(db_session, candidate, conv, "U-ORG", graph_delete_event_call=lambda e, i: None)
    assert db_session.query(CandidateAvailabilitySlot).filter(CandidateAvailabilitySlot.candidate_id == "C-1").count() == 0


def test_start_reschedule_no_current_interview(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    result = svc.start_reschedule(db_session, candidate, conv, "U-ORG")
    assert result["outcome"] == "no_current_interview"


def test_outlook_delete_failure_does_not_block_flow(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    _make_confirmed_interview(db_session, tenant, submission, panel)

    def _boom(email, event_id):
        raise RuntimeError("simulated Graph 500")

    result = svc.start_reschedule(db_session, candidate, conv, "U-ORG", graph_delete_event_call=_boom)  # should not raise
    assert result["outcome"] == "reschedule_started"

    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1


# ── AC-8/TC-003: escalates at the reschedule cap ──────────────────────

def test_start_reschedule_escalates_at_cap(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    _make_confirmed_interview(db_session, tenant, submission, panel, reschedule_count=2)

    result = svc.start_reschedule(db_session, candidate, conv, "U-ORG")
    assert result["outcome"] == "escalated"
    assert result["message"] == svc.ESCALATION_MESSAGE

    db_session.refresh(conv)
    assert conv.escalation_state == "escalated"
    assert conv.owner_type == "hr_user"

    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1


# ── Full reschedule flow: new availability -> match -> confirm -> reminders ─

def test_full_reschedule_flow_creates_new_interview_and_supersedes_old(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    old_interview = _make_confirmed_interview(db_session, tenant, submission, panel)

    svc.start_reschedule(db_session, candidate, conv, "U-ORG", graph_delete_event_call=lambda e, i: None)

    d1 = _next_weekday(date.today() + timedelta(days=2), 1)
    d2 = _next_weekday(date.today() + timedelta(days=2), 3)
    import json
    llm_call = lambda prompt: json.dumps([
        {"date": d1.isoformat(), "start_time": "14:00", "end_time": "16:00", "timezone": "America/Chicago"},
        {"date": d2.isoformat(), "start_time": "09:00", "end_time": "10:00", "timezone": "America/Chicago"},
    ])
    parse_result = parse_availability_response(db_session, conv, candidate, "U-ORG", "free Tuesday and Thursday", llm_call=llm_call)
    assert parse_result["outcome"] == "slots_sufficient"

    def graph_call(email, window_start, window_end):
        return []  # interviewer fully free

    with patch("app.services.interview_confirmation_service.EmailService.send_email", return_value={"status": "success"}):
        result = svc.complete_reschedule_match_and_confirm(db_session, candidate, conv, "U-ORG", graph_call=graph_call, graph_create_event_call=lambda *a, **kw: "evt-new")

    assert result["outcome"] == "matched_and_confirmed"
    assert result["old_interview_id"] == old_interview.id
    new_interview_id = result["new_interview_id"]
    assert new_interview_id != old_interview.id

    db_session.refresh(old_interview)
    assert old_interview.superseded_at is not None

    new_interview = db_session.query(SubmissionInterview).filter(SubmissionInterview.id == new_interview_id).first()
    assert new_interview.reschedule_count == 1
    assert new_interview.rescheduled_from_interview_id == old_interview.id
    assert new_interview.confirmed_at is not None

    reschedule_event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "INTERVIEW_RESCHEDULED").first()
    assert reschedule_event is not None
    assert reschedule_event.event_data["old_interview_id"] == old_interview.id
    assert reschedule_event.event_data["new_interview_id"] == new_interview_id

    new_reminders = db_session.query(InterviewReminder).filter(InterviewReminder.interview_id == new_interview_id).all()
    assert len(new_reminders) == 2


def test_complete_reschedule_no_active_reschedule_returns_honest_outcome(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    result = svc.complete_reschedule_match_and_confirm(db_session, candidate, conv, "U-ORG")
    assert result["outcome"] == "no_active_reschedule"


def test_no_match_leaves_old_interview_untouched(db_session, seeded):
    tenant, candidate, submission, conv, panel = seeded
    old_interview = _make_confirmed_interview(db_session, tenant, submission, panel)
    svc.start_reschedule(db_session, candidate, conv, "U-ORG", graph_delete_event_call=lambda e, i: None)

    weekday = _next_weekday(date.today() + timedelta(days=1), 1)
    another = _next_weekday(date.today() + timedelta(days=1), 3)
    import json
    llm_call = lambda prompt: json.dumps([
        {"date": weekday.isoformat(), "start_time": "14:00", "end_time": "15:00", "timezone": "America/Chicago"},
        {"date": another.isoformat(), "start_time": "09:00", "end_time": "10:00", "timezone": "America/Chicago"},
    ])
    parse_availability_response(db_session, conv, candidate, "U-ORG", "free times", llm_call=llm_call)

    def graph_call_busy_all_day(email, window_start, window_end):
        return [(window_start, window_end)]  # fully busy -- no possible match

    result = svc.complete_reschedule_match_and_confirm(db_session, candidate, conv, "U-ORG", graph_call=graph_call_busy_all_day)
    assert result["outcome"] == "no_match"

    db_session.refresh(old_interview)
    assert old_interview.superseded_at is None  # untouched -- no orphaning on a failed attempt
