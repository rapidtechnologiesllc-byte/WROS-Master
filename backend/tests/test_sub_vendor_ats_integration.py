"""
Proves HRMS-P809 (AI Recruiter Onboarding) + HRMS-P818 (WROS ATS
Integration) -- both are explicitly verification-only stories per their
own "Not In Scope" sections ("no new ATS features... exclusively a
verification and integration-confirmation story"). Rather than leave
that unverified, this asserts functionally that a SUBVENDOR-sourced
candidate is gated by R-01 (experience) and R-05 (L1-before-L2)
identically to a DIRECT candidate -- zero source_channel branching
anywhere in the real pipeline (confirmed by grep: submission_service.py
only carries source/subvendor_id as pass-through data on the Submission
row, never as a conditional; interview_service.py and
import logging
candidate_service.py reference it nowhere at all).

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
from app.models.submission import Submission, SubmissionViolation
from app.models.interview_pipeline import DemandInterviewPanel, SubmissionInterview
from app.models.sub_vendor import SubVendorAccount

from app.services.submission_service import (
    check_experience_eligibility,
    check_market_profile_rule,
    create_submission,
    SubmissionComplianceError,
)
from app.services.interview_service import create_interview, L1NotPassed


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Client.__table__, Demand.__table__, DemandHistory.__table__,
        Candidate.__table__, Employee.__table__, Submission.__table__, SubmissionViolation.__table__,
        DemandInterviewPanel.__table__, SubmissionInterview.__table__, SubVendorAccount.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def tenant_client_demand(db_session):
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
    return tenant, client, demand


# ---------------------------------------------------------------------------
# HRMS-P818 BR-0818-01: R-01 experience gate applies identically
# ---------------------------------------------------------------------------

def test_r01_experience_gate_ignores_source_channel(db_session, tenant_client_demand):
    tenant, client, demand = tenant_client_demand
    vendor = SubVendorAccount(tenant_id=tenant.id, company_name="Vendor Co", contact_email="v@vendor.com")
    db_session.add(vendor)
    db_session.commit()

    direct_candidate = Candidate(
        candidateID="C-DIRECT", candidateEmail="direct@example.com", candidatePassword="h",
        total_experience_months=48, source_channel="DIRECT",
    )
    subvendor_candidate = Candidate(
        candidateID="C-SUBVENDOR", candidateEmail="subvendor@example.com", candidatePassword="h",
        total_experience_months=48, source_channel="SUBVENDOR", vendor_id=vendor.id,
    )
    db_session.add_all([direct_candidate, subvendor_candidate])
    db_session.commit()

    direct_result = check_experience_eligibility(direct_candidate)
    subvendor_result = check_experience_eligibility(subvendor_candidate)

    # Identical outcome regardless of source_channel -- both ineligible,
    # same deficit, no override for vendor-sourced candidates.
    assert direct_result["is_eligible"] == subvendor_result["is_eligible"] == False
    assert direct_result["deficit_months"] == subvendor_result["deficit_months"]


def test_r01_gate_blocks_submission_for_subvendor_sourced_candidate_too(db_session, tenant_client_demand):
    tenant, client, demand = tenant_client_demand
    vendor = SubVendorAccount(tenant_id=tenant.id, company_name="Vendor Co", contact_email="v@vendor.com")
    db_session.add(vendor)
    db_session.commit()
    candidate = Candidate(
        candidateID="C-SV", candidateEmail="sv@example.com", candidatePassword="h",
        total_experience_months=24, employment_type="W2_FULLTIME",
        source_channel="SUBVENDOR", vendor_id=vendor.id,
    )
    db_session.add(candidate)
    db_session.commit()

    with pytest.raises(SubmissionComplianceError) as exc_info:
        create_submission(db_session, tenant_id=tenant.id, demand=demand, candidate=candidate, source="SUBVENDOR", subvendor_id=vendor.id)

    assert any(b["error"] == "EXPERIENCE_INELIGIBLE" for b in exc_info.value.blockers)


# ---------------------------------------------------------------------------
# HRMS-P818 BR-0818-02: pipeline stage tracking (R-05) identical
# ---------------------------------------------------------------------------

def test_r05_l1_before_l2_gate_applies_to_subvendor_sourced_submission(db_session, tenant_client_demand):
    tenant, client, demand = tenant_client_demand
    vendor = SubVendorAccount(tenant_id=tenant.id, company_name="Vendor Co", contact_email="v@vendor.com")
    db_session.add(vendor)
    db_session.commit()

    candidate = Candidate(
        candidateID="C-SV2", candidateEmail="sv2@example.com", candidatePassword="h",
        total_experience_months=72, employment_type="W2_FULLTIME",
        source_channel="SUBVENDOR", vendor_id=vendor.id,
    )
    employee = Employee(
        tenant_id=tenant.id, candidate_id=candidate.candidateID, first_name="X", last_name="Y",
        email="x@blitzenx.com", joining_date=date(2025, 1, 1), status="BENCH",
    )
    db_session.add_all([candidate, employee])
    db_session.commit()

    submission = create_submission(
        db_session, tenant_id=tenant.id, demand=demand, candidate=candidate,
        source="SUBVENDOR", subvendor_id=vendor.id,
    )
    db_session.commit()

    # R-05 applies identically regardless of source_channel -- no L1
    # PASS on file yet, so L2 is blocked exactly as it would be for a
    # directly-sourced candidate.
    with pytest.raises(L1NotPassed):
        create_interview(db_session, tenant_id=tenant.id, submission=submission, level="L2")
