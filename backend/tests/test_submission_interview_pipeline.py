"""
Proves HRMS-0711 (Client Submission Pipeline) and HRMS-0706 (Interview
Panel Assignment) -- the piece connecting Demand -> Candidate ->
import logging
Employee.

Covers the hard-block compliance gates this session decided to build
for real (R-01 experience, R-02/HRMS-P605 market profile, R-03/HRMS-P606
employment type) and R-05 (L1 must pass before L2). Deliberately does
NOT test the Director+BU Head override workflow or the 3/5-strike
violation-escalation cascade -- neither is built, by design (see
app.services.submission_service's module docstring).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.client import Client
from app.models.demand import Demand, DemandHistory
from app.models.candidate import Candidate
from app.models.employee import Employee
from app.models.user import Users
from app.models.submission import Submission, SubmissionViolation
from app.models.interview_pipeline import DemandInterviewPanel, SubmissionInterview

from app.services.submission_service import (
    check_experience_eligibility,
    check_market_profile_rule,
    check_employment_type_rule,
    create_submission,
    update_client_response,
    SubmissionComplianceError,
    DemandNotOpenForSubmission,
    DuplicateSubmission,
    InvalidSubmissionTransition,
)
from app.services.interview_service import (
    assign_panel_member,
    remove_panel_member,
    get_assigned_interviewer,
    create_interview,
    set_outcome,
    InterviewerNotEligible,
    NoEligibleInterviewer,
    L1NotPassed,
    InvalidOutcomeChange,
)

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
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

@pytest.fixture()
def base_fixtures(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    client = Client(tenant_id=tenant.id, company_name="Acme Insurance")
    db_session.add(client)
    db_session.commit()

    demand = Demand(
        tenant_id=tenant.id, client_id=client.id, job_title="Sr. Guidewire Developer",
        required_skills="[\"Guidewire\"]", min_experience_years=5.0,
        work_location="REMOTE", status="OPEN",
    )
    db_session.add(demand)
    db_session.commit()

    return tenant, client, demand

def _make_candidate(db, tenant, candidate_id="C-001", **overrides):
    defaults = dict(
        candidateID=candidate_id, candidateEmail=f"{candidate_id}@example.com",
        candidatePassword="hashed", tenant_id=tenant.id,
        total_experience_months=72, employment_type="W2_FULLTIME",
    )
    defaults.update(overrides)
    candidate = Candidate(**defaults)
    db.add(candidate)
    db.commit()
    return candidate

def _make_employee(db, tenant, candidate, status="BENCH", **overrides):
    defaults = dict(
        tenant_id=tenant.id, candidate_id=candidate.candidateID,
        first_name="Aisha", last_name="Verma", email="aisha@blitzenx.com",
        joining_date=date(2026, 1, 15), status=status,
    )
    defaults.update(overrides)
    emp = Employee(**defaults)
    db.add(emp)
    db.commit()
    return emp

def _make_eligible_candidate_and_employee(db, tenant, candidate_id="C-001", status="BENCH"):
    candidate = _make_candidate(db, tenant, candidate_id=candidate_id)
    employee = _make_employee(db, tenant, candidate, status=status)
    return candidate, employee

# ---------------------------------------------------------------------------
# checkExperienceEligibility (R-01 / HRMS-P601)
# ---------------------------------------------------------------------------

def test_experience_eligible_at_60_months():
    candidate = Candidate(candidateID="X", candidateEmail="x@x.com", candidatePassword="h", total_experience_months=60)
    result = check_experience_eligibility(candidate)
    assert result["is_eligible"] is True

def test_experience_ineligible_below_60_months():
    candidate = Candidate(candidateID="X", candidateEmail="x@x.com", candidatePassword="h", total_experience_months=48)
    result = check_experience_eligibility(candidate)
    assert result["is_eligible"] is False
    assert result["deficit_months"] == 12

def test_experience_null_is_ineligible_not_exempt():
    candidate = Candidate(candidateID="X", candidateEmail="x@x.com", candidatePassword="h", total_experience_months=None)
    result = check_experience_eligibility(candidate)
    assert result["is_eligible"] is False

# ---------------------------------------------------------------------------
# checkMarketProfileRule (R-02 / HRMS-P605)
# ---------------------------------------------------------------------------

def test_market_profile_blocked_with_no_employee_record(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    candidate = _make_candidate(db_session, tenant)

    result = check_market_profile_rule(db_session, candidate.candidateID)
    assert result["allowed"] is False
    assert result["candidate_status"] == "NO_EMPLOYEE_RECORD"

def test_market_profile_blocked_for_disallowed_employee_status(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    candidate, employee = _make_eligible_candidate_and_employee(db_session, tenant, status="PRE_JOINING")

    result = check_market_profile_rule(db_session, candidate.candidateID)
    assert result["allowed"] is False
    assert result["candidate_status"] == "PRE_JOINING"

@pytest.mark.parametrize("status", ["BENCH", "ACTIVE", "ALLOCATED"])
def test_market_profile_allowed_for_bench_active_allocated(db_session, base_fixtures, status):
    tenant, client, demand = base_fixtures
    candidate, employee = _make_eligible_candidate_and_employee(db_session, tenant, status=status)

    result = check_market_profile_rule(db_session, candidate.candidateID)
    assert result["allowed"] is True

# ---------------------------------------------------------------------------
# checkEmploymentTypeRule (R-03 / HRMS-P606)
# ---------------------------------------------------------------------------

def test_employment_type_c2c_blocked():
    candidate = Candidate(candidateID="X", candidateEmail="x@x.com", candidatePassword="h", employment_type="C2C")
    result = check_employment_type_rule(candidate)
    assert result["allowed"] is False

def test_employment_type_unknown_blocked_same_as_c2c():
    candidate = Candidate(candidateID="X", candidateEmail="x@x.com", candidatePassword="h", employment_type="UNKNOWN")
    result = check_employment_type_rule(candidate)
    assert result["allowed"] is False

def test_employment_type_w2_fulltime_allowed():
    candidate = Candidate(candidateID="X", candidateEmail="x@x.com", candidatePassword="h", employment_type="W2_FULLTIME")
    result = check_employment_type_rule(candidate)
    assert result["allowed"] is True

# ---------------------------------------------------------------------------
# create_submission -- BR-01: all violations returned together
# ---------------------------------------------------------------------------

def test_all_three_gate_failures_reported_together(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    candidate = _make_candidate(
        db_session, tenant, total_experience_months=48, employment_type="C2C",
    )
    # no linked Employee record at all -> market profile also fails

    with pytest.raises(SubmissionComplianceError) as exc_info:
        create_submission(db_session, tenant_id=tenant.id, demand=demand, candidate=candidate)

    errors = {b["error"] for b in exc_info.value.blockers}
    assert errors == {"EXPERIENCE_INELIGIBLE", "MARKET_PROFILE_SUBMISSION_BLOCKED", "C2C_NOT_ACCEPTED"}

    violations = db_session.query(SubmissionViolation).filter(
        SubmissionViolation.candidate_id == candidate.candidateID
    ).all()
    assert len(violations) == 3

def test_eligible_candidate_submission_succeeds_and_opens_demand(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    candidate, employee = _make_eligible_candidate_and_employee(db_session, tenant)
    assert demand.status == "OPEN"

    submission = create_submission(
        db_session, tenant_id=tenant.id, demand=demand, candidate=candidate,
        submitted_by_user_id="U1",
    )
    db_session.commit()

    assert submission.status == "SUBMITTED"
    assert demand.status == "IN_PROGRESS"

    no_violations = db_session.query(SubmissionViolation).filter(
        SubmissionViolation.candidate_id == candidate.candidateID
    ).count()
    assert no_violations == 0

def test_submission_blocked_when_demand_not_open(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    demand.status = "FILLED"
    candidate, employee = _make_eligible_candidate_and_employee(db_session, tenant)

    with pytest.raises(DemandNotOpenForSubmission):
        create_submission(db_session, tenant_id=tenant.id, demand=demand, candidate=candidate)

def test_duplicate_submission_rejected(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    candidate, employee = _make_eligible_candidate_and_employee(db_session, tenant)

    create_submission(db_session, tenant_id=tenant.id, demand=demand, candidate=candidate)
    db_session.commit()

    with pytest.raises(DuplicateSubmission):
        create_submission(db_session, tenant_id=tenant.id, demand=demand, candidate=candidate)

# ---------------------------------------------------------------------------
# update_client_response -- status machine + record_placement wiring
# ---------------------------------------------------------------------------

def test_client_response_valid_transition(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    candidate, employee = _make_eligible_candidate_and_employee(db_session, tenant)
    submission = create_submission(db_session, tenant_id=tenant.id, demand=demand, candidate=candidate)
    db_session.commit()

    update_client_response(db_session, submission, "SHORTLISTED", client_feedback="Strong profile")
    db_session.commit()

    assert submission.status == "SHORTLISTED"
    assert submission.client_feedback == "Strong profile"
    assert submission.client_response_at is not None

def test_client_response_invalid_transition_rejected(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    candidate, employee = _make_eligible_candidate_and_employee(db_session, tenant)
    submission = create_submission(db_session, tenant_id=tenant.id, demand=demand, candidate=candidate)
    db_session.commit()

    with pytest.raises(InvalidSubmissionTransition):
        update_client_response(db_session, submission, "PLACED")  # can't skip straight to PLACED

def test_placed_status_increments_demand_positions_filled(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    demand.headcount = 1
    candidate, employee = _make_eligible_candidate_and_employee(db_session, tenant)
    submission = create_submission(db_session, tenant_id=tenant.id, demand=demand, candidate=candidate)
    db_session.commit()

    update_client_response(db_session, submission, "CLIENT_INTERVIEW_REQUESTED")
    update_client_response(db_session, submission, "OFFER_EXTENDED")
    update_client_response(db_session, submission, "PLACED")
    db_session.commit()

    assert demand.positions_filled == 1
    assert demand.status == "FILLED"

# ---------------------------------------------------------------------------
# Interview panel assignment (HRMS-0706, BR-01)
# ---------------------------------------------------------------------------

def _make_interviewer(db, tenant, email, wros_user_id="U-INT-1", status="ACTIVE"):
    user = Users(UserID=wros_user_id, UserRole="RECRUITER", UserEmail=f"{wros_user_id}@blitzenx.com", UserPassword="h")
    db.add(user)
    db.commit()
    emp = Employee(
        tenant_id=tenant.id, first_name="Tom", last_name="Kumar", email=email,
        joining_date=date(2025, 1, 1), status=status, wros_user_id=wros_user_id,
    )
    db.add(emp)
    db.commit()
    return emp

def test_assign_panel_member_requires_active_employee_with_wros_access(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    inactive_interviewer = Employee(
        tenant_id=tenant.id, first_name="Bob", last_name="Lee", email="bob@blitzenx.com",
        joining_date=date(2025, 1, 1), status="EXITED",
    )
    db_session.add(inactive_interviewer)
    db_session.commit()

    with pytest.raises(InterviewerNotEligible):
        assign_panel_member(
            db_session, tenant_id=tenant.id, demand_id=demand.id,
            employee=inactive_interviewer, interview_level="L1",
        )

def test_assign_panel_member_succeeds_for_active_wros_employee(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    interviewer = _make_interviewer(db_session, tenant, "tom@blitzenx.com")

    panel = assign_panel_member(
        db_session, tenant_id=tenant.id, demand_id=demand.id,
        employee=interviewer, interview_level="L1",
    )
    db_session.commit()
    assert panel.is_active is True

def test_get_assigned_interviewer_picks_least_loaded(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    interviewer_a = _make_interviewer(db_session, tenant, "a@blitzenx.com", wros_user_id="U-A")
    interviewer_b = _make_interviewer(db_session, tenant, "b@blitzenx.com", wros_user_id="U-B")

    panel_a = assign_panel_member(db_session, tenant_id=tenant.id, demand_id=demand.id, employee=interviewer_a, interview_level="L1")
    panel_b = assign_panel_member(db_session, tenant_id=tenant.id, demand_id=demand.id, employee=interviewer_b, interview_level="L1")
    db_session.commit()

    candidate, employee = _make_eligible_candidate_and_employee(db_session, tenant)
    submission = create_submission(db_session, tenant_id=tenant.id, demand=demand, candidate=candidate)
    db_session.commit()

    # Load interviewer A up with a pending interview first.
    other_candidate = _make_candidate(db_session, tenant, candidate_id="C-002")
    _make_employee(db_session, tenant, other_candidate, status="BENCH")
    other_submission = create_submission(db_session, tenant_id=tenant.id, demand=demand, candidate=other_candidate)
    db_session.commit()
    create_interview(db_session, tenant_id=tenant.id, submission=other_submission, level="L1", panel=panel_a)
    db_session.commit()

    assigned = get_assigned_interviewer(db_session, demand_id=demand.id, interview_level="L1", tenant_id=tenant.id)
    assert assigned.id == panel_b.id  # B has 0 pending vs A's 1

def test_remove_panel_member_soft_deletes(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    interviewer = _make_interviewer(db_session, tenant, "tom@blitzenx.com")
    panel = assign_panel_member(db_session, tenant_id=tenant.id, demand_id=demand.id, employee=interviewer, interview_level="L1")
    db_session.commit()

    remove_panel_member(db_session, panel)
    db_session.commit()
    assert panel.is_active is False

    assigned = get_assigned_interviewer(db_session, demand_id=demand.id, interview_level="L1", tenant_id=tenant.id)
    assert assigned is None

# ---------------------------------------------------------------------------
# R-05: L1 must pass before L2
# ---------------------------------------------------------------------------

def _submission_with_panel(db, tenant, demand):
    candidate, employee = _make_eligible_candidate_and_employee(db, tenant)
    submission = create_submission(db, tenant_id=tenant.id, demand=demand, candidate=candidate)
    db.commit()
    interviewer = _make_interviewer(db, tenant, "panel@blitzenx.com")
    panel = assign_panel_member(db, tenant_id=tenant.id, demand_id=demand.id, employee=interviewer, interview_level="L1")
    db.commit()
    return submission, panel

def test_l2_interview_blocked_without_prior_l1_pass(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    submission, panel = _submission_with_panel(db_session, tenant, demand)

    with pytest.raises(L1NotPassed):
        create_interview(db_session, tenant_id=tenant.id, submission=submission, level="L2", panel=panel)

def test_l2_interview_blocked_when_l1_still_pending(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    submission, panel = _submission_with_panel(db_session, tenant, demand)
    create_interview(db_session, tenant_id=tenant.id, submission=submission, level="L1", panel=panel)
    db_session.commit()

    with pytest.raises(L1NotPassed):
        create_interview(db_session, tenant_id=tenant.id, submission=submission, level="L2", panel=panel)

def test_l2_interview_allowed_after_l1_pass(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    submission, panel = _submission_with_panel(db_session, tenant, demand)
    l1 = create_interview(db_session, tenant_id=tenant.id, submission=submission, level="L1", panel=panel)
    db_session.commit()

    set_outcome(db_session, l1, "PASS")
    db_session.commit()

    l2 = create_interview(db_session, tenant_id=tenant.id, submission=submission, level="L2", panel=panel)
    db_session.commit()
    assert l2.level == "L2"

def test_no_eligible_interviewer_raises(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    candidate, employee = _make_eligible_candidate_and_employee(db_session, tenant)
    submission = create_submission(db_session, tenant_id=tenant.id, demand=demand, candidate=candidate)
    db_session.commit()

    with pytest.raises(NoEligibleInterviewer):
        create_interview(db_session, tenant_id=tenant.id, submission=submission, level="L1")

def test_outcome_settable_only_once(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    submission, panel = _submission_with_panel(db_session, tenant, demand)
    l1 = create_interview(db_session, tenant_id=tenant.id, submission=submission, level="L1", panel=panel)
    db_session.commit()

    set_outcome(db_session, l1, "FAIL")
    db_session.commit()

    with pytest.raises(InvalidOutcomeChange):
        set_outcome(db_session, l1, "PASS")
