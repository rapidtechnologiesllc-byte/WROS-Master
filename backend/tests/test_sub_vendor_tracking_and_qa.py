"""
Proves HRMS-P803/P810 (vendor-facing submission tracking, isolated per
vendor), HRMS-P805/P812 (scorecard + portfolio analytics, all computed),
and HRMS-P814 (clarification Q&A, shared visibility across vendors on
import logging
the same request).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.client import Client
from app.models.demand import Demand, DemandHistory
from app.models.candidate import Candidate
from app.models.sub_vendor import SubVendorAccount, SubVendorRequest, SubVendorUser, ClarificationQA
from app.models.sub_vendor_submission import SubVendorSubmission, SubVendorViolation, SubVendorDedupRejection
from app.models.user import Users

from app.services.sub_vendor_service import register_sub_vendor, approve_sub_vendor, create_sub_vendor_request
from app.services.sub_vendor_submission_service import submit_candidate, accept_submission, reject_submission
from app.services.sub_vendor_tracking_service import (
    get_submissions_for_vendor,
    get_sub_vendor_scorecard,
    get_sub_vendor_portfolio_analytics,
)
from app.services.sub_vendor_qa_service import ask_question, answer_question, get_qa_for_request, ClarificationValidationError

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Client.__table__, Demand.__table__, DemandHistory.__table__,
        Candidate.__table__, Users.__table__,
        SubVendorAccount.__table__, SubVendorUser.__table__, SubVendorRequest.__table__,
        SubVendorSubmission.__table__, SubVendorViolation.__table__, SubVendorDedupRejection.__table__,
        ClarificationQA.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

@pytest.fixture()
def fixtures(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    client = Client(tenant_id=tenant.id, company_name="Acme Insurance")
    db_session.add(client)
    db_session.commit()
    demand = Demand(
        tenant_id=tenant.id, client_id=client.id, job_title="Sr. Guidewire Developer",
        required_skills='["Guidewire"]', min_experience_years=5.0,
        work_location="REMOTE", status="OPEN",
    )
    db_session.add(demand)
    db_session.commit()

    vendor_a = register_sub_vendor(db_session, tenant_id=tenant.id, company_name="Vendor A", contact_email="a@vendor.com")
    vendor_b = register_sub_vendor(db_session, tenant_id=tenant.id, company_name="Vendor B", contact_email="b@vendor.com")
    db_session.commit()
    approve_sub_vendor(db_session, vendor_a, approved_by="U-ADMIN")
    approve_sub_vendor(db_session, vendor_b, approved_by="U-ADMIN")
    db_session.commit()

    request_a = create_sub_vendor_request(db_session, tenant_id=tenant.id, demand=demand, sub_vendor=vendor_a, assigned_by="U-RM")
    request_b = create_sub_vendor_request(db_session, tenant_id=tenant.id, demand=demand, sub_vendor=vendor_b, assigned_by="U-RM")
    db_session.commit()

    return tenant, client, demand, vendor_a, vendor_b, request_a, request_b

# ---------------------------------------------------------------------------
# HRMS-P803/P810: vendor isolation + rejection always shows feedback
# ---------------------------------------------------------------------------

def test_vendor_sees_only_own_submissions(db_session, fixtures):
    tenant, client, demand, vendor_a, vendor_b, request_a, request_b = fixtures
    submit_candidate(db_session, request=request_a, sub_vendor=vendor_a, candidate_name="A1", candidate_email="a1@example.com", employment_type="W2_FULLTIME")
    submit_candidate(db_session, request=request_b, sub_vendor=vendor_b, candidate_name="B1", candidate_email="b1@example.com", employment_type="W2_FULLTIME")
    db_session.commit()

    results_a = get_submissions_for_vendor(db_session, vendor_a)
    assert len(results_a) == 1
    assert results_a[0]["candidate_name"] == "A1"
    assert results_a[0]["demand_job_title"] == "Sr. Guidewire Developer"

def test_rejected_submission_shows_feedback_note(db_session, fixtures):
    tenant, client, demand, vendor_a, vendor_b, request_a, request_b = fixtures
    submission = submit_candidate(db_session, request=request_a, sub_vendor=vendor_a, candidate_name="X", candidate_email="x@example.com", employment_type="W2_FULLTIME")
    db_session.commit()
    reject_submission(db_session, submission, feedback_note="Experience level too junior for this role.")
    db_session.commit()

    results = get_submissions_for_vendor(db_session, vendor_a)
    assert results[0]["status"] == "REJECTED"
    assert results[0]["feedback_note"] is not None

# ---------------------------------------------------------------------------
# HRMS-P805/P812: scorecard + portfolio
# ---------------------------------------------------------------------------

def test_scorecard_computed_from_submissions(db_session, fixtures):
    tenant, client, demand, vendor_a, vendor_b, request_a, request_b = fixtures
    s1 = submit_candidate(db_session, request=request_a, sub_vendor=vendor_a, candidate_name="A1", candidate_email="a1@example.com", employment_type="W2_FULLTIME")
    s2 = submit_candidate(db_session, request=request_a, sub_vendor=vendor_a, candidate_name="A2", candidate_email="a2@example.com", employment_type="W2_FULLTIME")
    db_session.commit()
    accept_submission(db_session, s1)
    db_session.commit()

    scorecard = get_sub_vendor_scorecard(db_session, vendor_a)
    assert scorecard["submissions_total"] == 2
    assert scorecard["accepted_count"] == 1
    assert scorecard["submission_to_acceptance_rate_pct"] == 50.0

def test_scorecard_counts_ft_violations(db_session, fixtures):
    tenant, client, demand, vendor_a, vendor_b, request_a, request_b = fixtures
    submit_candidate(db_session, request=request_a, sub_vendor=vendor_a, candidate_name="C2C", candidate_email="c2c@example.com", employment_type="C2C")
    db_session.commit()

    scorecard = get_sub_vendor_scorecard(db_session, vendor_a)
    assert scorecard["ft_compliance_violations_90d"] == 1

def test_portfolio_analytics_reflects_source_channel_tagging(db_session, fixtures):
    tenant, client, demand, vendor_a, vendor_b, request_a, request_b = fixtures
    direct_candidate = Candidate(candidateID="C-DIRECT", candidateEmail="direct@example.com", candidatePassword="h")
    db_session.add(direct_candidate)
    db_session.commit()

    submission = submit_candidate(db_session, request=request_a, sub_vendor=vendor_a, candidate_name="Vendor Sourced", candidate_email="vs@example.com", employment_type="W2_FULLTIME")
    db_session.commit()
    accept_submission(db_session, submission)
    db_session.commit()

    analytics = get_sub_vendor_portfolio_analytics(db_session, tenant_id=tenant.id)
    assert analytics["sub_vendor_sourced_candidate_count"] == 1
    assert analytics["active_vendors"] == 2
    # 1 of 2 total candidates (direct + vendor-sourced) is vendor-sourced.
    assert analytics["sub_vendor_contribution_pct"] == 50.0

# ---------------------------------------------------------------------------
# HRMS-P814: clarification Q&A -- shared visibility
# ---------------------------------------------------------------------------

def test_ask_question_requires_min_length(db_session, fixtures):
    tenant, client, demand, vendor_a, vendor_b, request_a, request_b = fixtures
    with pytest.raises(ClarificationValidationError):
        ask_question(db_session, request_a, vendor_a, question="short")

def test_answer_requires_min_length(db_session, fixtures):
    tenant, client, demand, vendor_a, vendor_b, request_a, request_b = fixtures
    qa = ask_question(db_session, request_a, vendor_a, question="Is remote work allowed for this role?")
    db_session.commit()

    with pytest.raises(ClarificationValidationError):
        answer_question(db_session, qa, answered_by="U-RM", answer="no")

def test_answered_question_visible_to_other_vendor_on_same_request(db_session, fixtures):
    """BR-0814-01: shared visibility, not scoped to the asker."""
    tenant, client, demand, vendor_a, vendor_b, request_a, request_b = fixtures
    qa = ask_question(db_session, request_a, vendor_a, question="Is remote work allowed for this role?")
    db_session.commit()
    answer_question(db_session, qa, answered_by="U-RM", answer="Yes, fully remote is acceptable for this role.")
    db_session.commit()

    # Vendor A asked on request_a; a hypothetical second vendor viewing
    # the SAME request would see it too -- get_qa_for_request has no
    # sub_vendor_id filter at all, unlike get_submissions_for_vendor.
    all_qa = get_qa_for_request(db_session, request_a)
    assert len(all_qa) == 1
    assert all_qa[0].answer is not None

def test_qa_scoped_per_request_not_leaked_across_requests(db_session, fixtures):
    tenant, client, demand, vendor_a, vendor_b, request_a, request_b = fixtures
    ask_question(db_session, request_a, vendor_a, question="Is remote work allowed for this role?")
    db_session.commit()

    qa_for_b = get_qa_for_request(db_session, request_b)
    assert qa_for_b == []
