"""
import logging
S-053/HRMS-0453 -- Offer Readiness Check.

Real architecture under test (see offer_readiness_service module
docstring): SubmissionInterview (not the legacy Interview model) is
the real L1/L2 PASS/FAIL data source; Submission.status (not a
nonexistent Candidate.status value) is the real withdrawn/rejected
signal; check_experience_eligibility() (HRMS-P601) is reused directly
for BR-02; COMPLIANCE_BLOCK is read honestly even though no story ever
produces one yet; a no-show'd interview (S-052) is treated as "not
completed."

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_job_flag import CandidateJobFlag
from app.models.client import Client
from app.models.demand import Demand, DemandHistory
from app.models.employee import Employee
from app.models.interview_pipeline import DemandInterviewPanel, SubmissionInterview
from app.models.submission import Submission, SubmissionViolation
from app.models.tenant import Tenant
from app.models.user import Users

import app.services.offer_readiness_service as svc
from app.services.interview_service import assign_panel_member, create_interview
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
        CandidateJobFlag.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
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

    candidate = Candidate(
        candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya",
        tenant_id=tenant.id, timezone="America/Chicago", total_experience_months=72, employment_type="W2_FULLTIME",
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

    return tenant, candidate, submission, panel

def _make_interview(db, tenant, submission, panel, level, outcome):
    interview = create_interview(db, tenant_id=tenant.id, submission=submission, level=level, panel=panel, scheduled_at=datetime.utcnow() - timedelta(days=1))
    db.commit()
    if outcome != "PENDING":
        interview.outcome = outcome
        db.add(interview)
        db.commit()
    return interview

# ── TC-001: missing L1 ────────────────────────────────────────────────

def test_missing_l1_interview_blocks(db_session, seeded):
    tenant, candidate, submission, panel = seeded
    result = svc.check_offer_readiness(db_session, "C-1", "JOB-1", "U-ORG")
    assert result["is_ready"] is False
    assert "L1 interview not completed." in result["blockers"]

# ── TC-002: L2 failed ──────────────────────────────────────────────────

def test_l1_pass_l2_fail_blocks(db_session, seeded):
    tenant, candidate, submission, panel = seeded
    _make_interview(db_session, tenant, submission, panel, "L1", "PASS")
    _make_interview(db_session, tenant, submission, panel, "L2", "FAIL")

    result = svc.check_offer_readiness(db_session, "C-1", "JOB-1", "U-ORG")
    assert result["is_ready"] is False
    assert "Candidate failed L2 interview." in result["blockers"]

def test_l2_not_yet_done_blocks(db_session, seeded):
    tenant, candidate, submission, panel = seeded
    _make_interview(db_session, tenant, submission, panel, "L1", "PASS")

    result = svc.check_offer_readiness(db_session, "C-1", "JOB-1", "U-ORG")
    assert result["is_ready"] is False
    assert "L2 interview not completed." in result["blockers"]

# ── TC-003: all clear ──────────────────────────────────────────────────

def test_all_passed_no_flags_is_ready(db_session, seeded):
    tenant, candidate, submission, panel = seeded
    _make_interview(db_session, tenant, submission, panel, "L1", "PASS")
    _make_interview(db_session, tenant, submission, panel, "L2", "PASS")

    result = svc.check_offer_readiness(db_session, "C-1", "JOB-1", "U-ORG")
    assert result["is_ready"] is True
    assert result["blockers"] == []
    assert result["warnings"] == []

# ── TC-004: compensation mismatch is a warning, not a blocker (BR-03) ──

def test_compensation_mismatch_is_warning_not_blocker(db_session, seeded):
    tenant, candidate, submission, panel = seeded
    _make_interview(db_session, tenant, submission, panel, "L1", "PASS")
    _make_interview(db_session, tenant, submission, panel, "L2", "PASS")
    db_session.add(CandidateJobFlag(tenant_id="U-ORG", candidate_id="C-1", job_id="JOB-1", flag_type="COMPENSATION_MISMATCH", message="over budget"))
    db_session.commit()

    result = svc.check_offer_readiness(db_session, "C-1", "JOB-1", "U-ORG")
    assert result["is_ready"] is True
    assert result["blockers"] == []
    assert "Compensation mismatch flagged -- review before offering." in result["warnings"]

def test_resolved_compensation_flag_does_not_warn(db_session, seeded):
    tenant, candidate, submission, panel = seeded
    _make_interview(db_session, tenant, submission, panel, "L1", "PASS")
    _make_interview(db_session, tenant, submission, panel, "L2", "PASS")
    db_session.add(CandidateJobFlag(tenant_id="U-ORG", candidate_id="C-1", job_id="JOB-1", flag_type="COMPENSATION_MISMATCH", message="over budget", is_resolved=True))
    db_session.commit()

    result = svc.check_offer_readiness(db_session, "C-1", "JOB-1", "U-ORG")
    assert result["warnings"] == []

# ── BR-02: experience re-validation ────────────────────────────────────

def test_below_experience_threshold_blocks(db_session, seeded):
    tenant, candidate, submission, panel = seeded
    candidate.total_experience_months = 48
    db_session.commit()
    _make_interview(db_session, tenant, submission, panel, "L1", "PASS")
    _make_interview(db_session, tenant, submission, panel, "L2", "PASS")

    result = svc.check_offer_readiness(db_session, "C-1", "JOB-1", "U-ORG")
    assert result["is_ready"] is False
    assert "Candidate does not meet 5-year experience requirement." in result["blockers"]

# ── Check 1: withdrawn/rejected submission blocks ─────────────────────

def test_withdrawn_submission_blocks(db_session, seeded):
    tenant, candidate, submission, panel = seeded
    submission.status = "WITHDRAWN"
    db_session.commit()

    result = svc.check_offer_readiness(db_session, "C-1", "JOB-1", "U-ORG")
    assert result["is_ready"] is False
    assert "Candidate has withdrawn or been rejected." in result["blockers"]

def test_rejected_by_client_submission_blocks(db_session, seeded):
    tenant, candidate, submission, panel = seeded
    submission.status = "REJECTED_BY_CLIENT"
    db_session.commit()

    result = svc.check_offer_readiness(db_session, "C-1", "JOB-1", "U-ORG")
    assert result["is_ready"] is False
    assert "Candidate has withdrawn or been rejected." in result["blockers"]

# ── Check 6: compliance block is a hard blocker ───────────────────────

def test_compliance_block_flag_blocks(db_session, seeded):
    tenant, candidate, submission, panel = seeded
    _make_interview(db_session, tenant, submission, panel, "L1", "PASS")
    _make_interview(db_session, tenant, submission, panel, "L2", "PASS")
    db_session.add(CandidateJobFlag(tenant_id="U-ORG", candidate_id="C-1", job_id="JOB-1", flag_type="COMPLIANCE_BLOCK", message="background check pending"))
    db_session.commit()

    result = svc.check_offer_readiness(db_session, "C-1", "JOB-1", "U-ORG")
    assert result["is_ready"] is False
    assert "Outstanding compliance flag(s) must be resolved before offering." in result["blockers"]

# ── S-052 bridge: a no-show'd interview is not "completed" ─────────────

def test_no_show_interview_blocks_as_not_completed(db_session, seeded):
    tenant, candidate, submission, panel = seeded
    interview = _make_interview(db_session, tenant, submission, panel, "L1", "PENDING")
    interview.no_show_confirmed_at = datetime.utcnow()
    db_session.commit()

    result = svc.check_offer_readiness(db_session, "C-1", "JOB-1", "U-ORG")
    assert result["is_ready"] is False
    assert "Candidate did not join their L1 interview (no-show)." in result["blockers"]

# ── Superseded (rescheduled-away) interviews are ignored ──────────────

def test_superseded_interview_ignored_current_one_used(db_session, seeded):
    tenant, candidate, submission, panel = seeded
    old = _make_interview(db_session, tenant, submission, panel, "L1", "FAIL")
    old.superseded_at = datetime.utcnow()
    db_session.commit()
    _make_interview(db_session, tenant, submission, panel, "L1", "PASS")
    _make_interview(db_session, tenant, submission, panel, "L2", "PASS")

    result = svc.check_offer_readiness(db_session, "C-1", "JOB-1", "U-ORG")
    assert result["is_ready"] is True  # the superseded FAIL doesn't count

def test_candidate_not_found(db_session, seeded):
    result = svc.check_offer_readiness(db_session, "NOPE", "JOB-1", "U-ORG")
    assert result["is_ready"] is False
    assert result["blockers"] == ["Candidate not found."]

# ── Step 4: OFFER_READINESS_CHECKED logged ────────────────────────────

def test_logs_offer_readiness_checked_event(db_session, seeded):
    tenant, candidate, submission, panel = seeded
    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp")
    db_session.add(conv)
    db_session.commit()

    svc.check_offer_readiness(db_session, "C-1", "JOB-1", "U-ORG")

    event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "OFFER_READINESS_CHECKED").first()
    assert event is not None
    assert event.event_data["candidate_id"] == "C-1"
    assert event.event_data["job_id"] == "JOB-1"
