"""
import logging
S-048/HRMS-0448 -- Calendar Matching Engine.

Real architecture under test (see calendar_matching_service module
docstring): writes into the existing SubmissionInterview (not a new
`interviews` table); BR-02's 15-min buffer is applied at free/busy
INVERSION time (reconciling the spec's own TC-001/TC-002); BR-03
weekends are enforced by construction (business-hour windows are never
generated for a weekend interviewer-local date); holiday-checking is
explicitly NOT built (no holiday data source anywhere in this
codebase, same gap S-039 already flagged); submission resolution picks
the candidate's most relevant open Submission by status priority
(a real, flagged simplification since no submission_id thread exists
from the availability-collection conversation); Graph calendar reads
are injected via graph_call so no test ever hits a real external API.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date, datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_availability_slot import CandidateAvailabilitySlot
from app.models.client import Client
from app.models.demand import Demand, DemandHistory
from app.models.employee import Employee
from app.models.interview_pipeline import DemandInterviewPanel, SubmissionInterview
from app.models.notification import Notification
from app.models.submission import Submission, SubmissionViolation
from app.models.tenant import Tenant
from app.models.user import Users

import app.services.calendar_matching_service as svc
from app.services.interview_service import assign_panel_member
from app.services.submission_service import create_submission


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Client.__table__, Demand.__table__, DemandHistory.__table__,
        Candidate.__table__, Employee.__table__, Users.__table__,
        Submission.__table__, SubmissionViolation.__table__,
        DemandInterviewPanel.__table__, SubmissionInterview.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__,
        CandidateAvailabilitySlot.__table__, Notification.__table__,
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

    demand = Demand(
        tenant_id=tenant.id, client_id=client.id, job_title="Sr. Guidewire Developer",
        required_skills="[\"Guidewire\"]", min_experience_years=5.0, work_location="REMOTE", status="OPEN",
    )
    db_session.add(demand)
    db_session.commit()

    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h", tenant_id=None)
    recruiter = Users(UserID="U-RECRUITER", UserRole="Recruiter", UserEmail="recruiter@blitzenx.com", UserPassword="h", tenant_id=tenant.id)
    db_session.add_all([owner, recruiter])
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

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="awaiting_candidate", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp")
    db_session.add(conv)
    db_session.commit()

    return tenant, client, demand, candidate, submission, conv


def _make_interviewer(db, tenant, wros_user_id="U-INT-1", tz="America/Chicago"):
    user = Users(UserID=wros_user_id, UserRole="Employee", UserEmail=f"{wros_user_id.lower()}@blitzenx.com", UserPassword="h", tenant_id=tenant.id, timezone=tz)
    db.add(user)
    db.commit()
    emp = Employee(tenant_id=tenant.id, first_name="Tom", last_name="Kumar", email=f"{wros_user_id.lower()}@blitzenx.com", joining_date=date(2025, 1, 1), status="ACTIVE", wros_user_id=wros_user_id)
    db.add(emp)
    db.commit()
    return emp, user


def _assign_interviewer(db, tenant, demand, employee, level="L1"):
    panel = assign_panel_member(db, tenant_id=tenant.id, demand_id=demand.id, employee=employee, interview_level=level)
    db.commit()
    return panel


def _add_slot(db, candidate_id, conversation_id, tz_tenant_id, slot_date, start_h, end_h, tz="America/Chicago"):
    from datetime import time as time_cls
    slot = CandidateAvailabilitySlot(
        tenant_id=tz_tenant_id, candidate_id=candidate_id, conversation_id=conversation_id,
        slot_date=slot_date, slot_start_time=time_cls(start_h, 0), slot_end_time=time_cls(end_h, 0), timezone=tz,
    )
    db.add(slot)
    db.commit()
    return slot


def _next_weekday(base, target_weekday):
    days_ahead = (target_weekday - base.weekday()) % 7
    return base + timedelta(days=days_ahead)


def _chicago_busy(day, start_h, start_m, end_h, end_m):
    tz = ZoneInfo("America/Chicago")
    start = datetime(day.year, day.month, day.day, start_h, start_m, tzinfo=tz).astimezone(dt_timezone.utc)
    end = datetime(day.year, day.month, day.day, end_h, end_m, tzinfo=tz).astimezone(dt_timezone.utc)
    return (start, end)


# ── Pure-function unit tests: TC-001/TC-002 from the spec itself ────

def test_tc001_buffer_already_reflected_in_free_period_matches_at_boundary():
    tz = ZoneInfo("America/Chicago")
    day = date(2026, 8, 11)  # a Tuesday
    window_start = datetime(2026, 8, 11, 9, 0, tzinfo=tz).astimezone(dt_timezone.utc)
    window_end = datetime(2026, 8, 11, 17, 0, tzinfo=tz).astimezone(dt_timezone.utc)
    busy = [_chicago_busy(day, 12, 0, 14, 15)]  # busy until 2:15pm -> free starts 2:30pm after 15-min buffer

    free = svc.invert_busy_to_free(busy, window_start, window_end)
    candidate_slot_start = datetime(2026, 8, 11, 14, 0, tzinfo=tz).astimezone(dt_timezone.utc)
    candidate_slot_end = datetime(2026, 8, 11, 16, 0, tzinfo=tz).astimezone(dt_timezone.utc)

    match_start = None
    for free_start, free_end in free:
        candidate_match = max(candidate_slot_start, free_start)
        if candidate_match + timedelta(minutes=60) <= min(candidate_slot_end, free_end):
            match_start = candidate_match
            break

    assert match_start == datetime(2026, 8, 11, 14, 30, tzinfo=tz).astimezone(dt_timezone.utc)


def test_tc002_buffer_pushes_match_past_naive_busy_end():
    tz = ZoneInfo("America/Chicago")
    day = date(2026, 8, 11)
    window_start = datetime(2026, 8, 11, 9, 0, tzinfo=tz).astimezone(dt_timezone.utc)
    window_end = datetime(2026, 8, 11, 17, 0, tzinfo=tz).astimezone(dt_timezone.utc)
    busy = [_chicago_busy(day, 9, 0, 14, 0)]  # busy until 2:00pm exactly

    free = svc.invert_busy_to_free(busy, window_start, window_end)
    candidate_slot_start = datetime(2026, 8, 11, 14, 0, tzinfo=tz).astimezone(dt_timezone.utc)
    candidate_slot_end = datetime(2026, 8, 11, 17, 0, tzinfo=tz).astimezone(dt_timezone.utc)

    match_start = None
    for free_start, free_end in free:
        candidate_match = max(candidate_slot_start, free_start)
        if candidate_match + timedelta(minutes=60) <= min(candidate_slot_end, free_end):
            match_start = candidate_match
            break

    expected_2pm = datetime(2026, 8, 11, 14, 0, tzinfo=tz).astimezone(dt_timezone.utc)
    expected_215pm = datetime(2026, 8, 11, 14, 15, tzinfo=tz).astimezone(dt_timezone.utc)
    assert match_start != expected_2pm  # AC-3/TC-002: NOT matched at 2:00, no buffer
    assert match_start == expected_215pm


# ── attempt_calendar_match: full integration ──────────────────────────

def test_matches_and_creates_scheduled_interview(db_session, seeded):
    tenant, client, demand, candidate, submission, conv = seeded
    employee, interviewer_user = _make_interviewer(db_session, tenant)
    _assign_interviewer(db_session, tenant, demand, employee)

    day = _next_weekday(date.today() + timedelta(days=1), 1)  # Tuesday
    slot1 = _add_slot(db_session, "C-1", conv.id, "U-ORG", day, 14, 16)
    slot2 = _add_slot(db_session, "C-1", conv.id, "U-ORG", day, 9, 10)

    def graph_call(email, window_start, window_end):
        return [_chicago_busy(day, 9, 0, 14, 15)]  # busy 9am-2:15pm -> free from 2:30pm

    result = svc.attempt_calendar_match(db_session, candidate, conv, "U-ORG", graph_call=graph_call)

    assert result["outcome"] == "matched"
    interview = db_session.query(SubmissionInterview).filter(SubmissionInterview.id == result["interview_id"]).first()
    assert interview is not None
    assert interview.outcome == "PENDING"
    assert interview.scheduled_at is not None
    assert interview.submission_id == submission.id
    assert interview.level == "L1"

    db_session.refresh(slot1)
    assert slot1.is_confirmed is True

    event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "calendar_match_succeeded").first()
    assert event is not None


def test_returns_both_local_times_cross_timezone(db_session, seeded):
    tenant, client, demand, candidate, submission, conv = seeded
    # America/Los_Angeles (not Asia/Kolkata) so the two parties' 9-5
    # business hours actually overlap in real UTC terms -- Chicago and
    # Kolkata are ~10.5 hours apart, so their respective 9am-5pm
    # windows never overlap at all on any calendar day, which would
    # make this a genuinely unmatchable (not buggy) scenario.
    employee, interviewer_user = _make_interviewer(db_session, tenant, tz="America/Los_Angeles")
    _assign_interviewer(db_session, tenant, demand, employee)

    day = _next_weekday(date.today() + timedelta(days=1), 1)
    _add_slot(db_session, "C-1", conv.id, "U-ORG", day, 14, 16)  # 2-4pm Chicago
    _add_slot(db_session, "C-1", conv.id, "U-ORG", day, 9, 10)

    def graph_call(email, window_start, window_end):
        return []  # interviewer fully free

    result = svc.attempt_calendar_match(db_session, candidate, conv, "U-ORG", graph_call=graph_call)
    assert result["outcome"] == "matched"
    assert result["candidate_local_time"].tzinfo is not None
    assert result["interviewer_local_time"].tzinfo is not None
    assert result["candidate_local_time"].utcoffset() != result["interviewer_local_time"].utcoffset()


# ── No-match handling ──────────────────────────────────────────────

def test_no_overlap_deletes_slots_and_notifies_recruiter(db_session, seeded):
    tenant, client, demand, candidate, submission, conv = seeded
    employee, interviewer_user = _make_interviewer(db_session, tenant)
    _assign_interviewer(db_session, tenant, demand, employee)

    day = _next_weekday(date.today() + timedelta(days=1), 1)
    _add_slot(db_session, "C-1", conv.id, "U-ORG", day, 14, 15)
    _add_slot(db_session, "C-1", conv.id, "U-ORG", day, 9, 10)

    def graph_call(email, window_start, window_end):
        return [_chicago_busy(day, 9, 0, 17, 0)]  # busy all day

    result = svc.attempt_calendar_match(db_session, candidate, conv, "U-ORG", graph_call=graph_call)

    assert result["outcome"] == "no_match"
    assert db_session.query(CandidateAvailabilitySlot).filter(CandidateAvailabilitySlot.candidate_id == "C-1").count() == 0

    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1

    event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "calendar_match_failed").first()
    assert event is not None


def test_insufficient_slots_short_circuits(db_session, seeded):
    tenant, client, demand, candidate, submission, conv = seeded
    day = _next_weekday(date.today() + timedelta(days=1), 1)
    _add_slot(db_session, "C-1", conv.id, "U-ORG", day, 14, 16)  # only 1 slot

    result = svc.attempt_calendar_match(db_session, candidate, conv, "U-ORG")
    assert result["outcome"] == "insufficient_slots"


def test_no_open_submission(db_session, seeded):
    tenant, client, demand, candidate, submission, conv = seeded
    submission.status = "PLACED"  # terminal, not interview-eligible
    db_session.commit()

    day = _next_weekday(date.today() + timedelta(days=1), 1)
    _add_slot(db_session, "C-1", conv.id, "U-ORG", day, 14, 16)
    _add_slot(db_session, "C-1", conv.id, "U-ORG", day, 9, 10)

    result = svc.attempt_calendar_match(db_session, candidate, conv, "U-ORG")
    assert result["outcome"] == "no_open_submission"


def test_no_interviewer_assigned_notifies_recruiter(db_session, seeded):
    tenant, client, demand, candidate, submission, conv = seeded
    day = _next_weekday(date.today() + timedelta(days=1), 1)
    _add_slot(db_session, "C-1", conv.id, "U-ORG", day, 14, 16)
    _add_slot(db_session, "C-1", conv.id, "U-ORG", day, 9, 10)

    result = svc.attempt_calendar_match(db_session, candidate, conv, "U-ORG")
    assert result["outcome"] == "no_interviewer_assigned"

    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1


def test_calendar_check_failed_never_raises(db_session, seeded):
    tenant, client, demand, candidate, submission, conv = seeded
    employee, interviewer_user = _make_interviewer(db_session, tenant)
    _assign_interviewer(db_session, tenant, demand, employee)

    day = _next_weekday(date.today() + timedelta(days=1), 1)
    _add_slot(db_session, "C-1", conv.id, "U-ORG", day, 14, 16)
    _add_slot(db_session, "C-1", conv.id, "U-ORG", day, 9, 10)

    def _boom(email, window_start, window_end):
        raise RuntimeError("simulated Graph failure")

    result = svc.attempt_calendar_match(db_session, candidate, conv, "U-ORG", graph_call=_boom)  # should not raise
    assert result["outcome"] == "calendar_check_failed"

    # Slots are NOT deleted -- this isn't a real no-match, we just couldn't check.
    assert db_session.query(CandidateAvailabilitySlot).filter(CandidateAvailabilitySlot.candidate_id == "C-1").count() == 2


# ── BR-03: weekend enforcement by construction ────────────────────────

def test_weekend_slot_never_matched_even_if_interviewer_fully_free(db_session, seeded):
    tenant, client, demand, candidate, submission, conv = seeded
    employee, interviewer_user = _make_interviewer(db_session, tenant)
    _assign_interviewer(db_session, tenant, demand, employee)

    saturday = _next_weekday(date.today() + timedelta(days=1), 5)
    # Bypasses S-047's own weekend guard by writing the row directly --
    # a real, standalone test of THIS story's BR-03 enforcement.
    _add_slot(db_session, "C-1", conv.id, "U-ORG", saturday, 14, 16)
    another = _next_weekday(date.today() + timedelta(days=1), 6)
    _add_slot(db_session, "C-1", conv.id, "U-ORG", another, 9, 10)

    def graph_call(email, window_start, window_end):
        return []  # interviewer fully free, but both slots are weekend dates

    result = svc.attempt_calendar_match(db_session, candidate, conv, "U-ORG", graph_call=graph_call)
    assert result["outcome"] == "no_match"


# ── Submission resolution priority ──────────────────────────────────

def test_resolves_client_interview_requested_over_submitted(db_session, seeded):
    tenant, client, demand, candidate, submission, conv = seeded
    submission.status = "SUBMITTED"
    db_session.commit()

    demand2 = Demand(tenant_id=tenant.id, client_id=client.id, job_title="Jr. Dev", required_skills="[]", min_experience_years=1.0, work_location="REMOTE", status="OPEN")
    db_session.add(demand2)
    db_session.commit()
    submission2 = create_submission(db_session, tenant_id=tenant.id, demand=demand2, candidate=candidate, submitted_by_user_id="U-RECRUITER")
    submission2.status = "CLIENT_INTERVIEW_REQUESTED"
    db_session.commit()

    employee, interviewer_user = _make_interviewer(db_session, tenant)
    _assign_interviewer(db_session, tenant, demand2, employee)

    day = _next_weekday(date.today() + timedelta(days=1), 1)
    _add_slot(db_session, "C-1", conv.id, "U-ORG", day, 14, 16)
    _add_slot(db_session, "C-1", conv.id, "U-ORG", day, 9, 10)

    def graph_call(email, window_start, window_end):
        return []

    result = svc.attempt_calendar_match(db_session, candidate, conv, "U-ORG", graph_call=graph_call)
    assert result["outcome"] == "matched"
    interview = db_session.query(SubmissionInterview).filter(SubmissionInterview.id == result["interview_id"]).first()
    assert interview.submission_id == submission2.id  # the CLIENT_INTERVIEW_REQUESTED one, not the SUBMITTED one
