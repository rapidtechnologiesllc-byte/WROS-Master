"""
Proves EPIC-P8 Sub-Vendor Portal's core pipeline: registration/approval
(HRMS-P801), demand request assignment (HRMS-P804, auto-close per
HRMS-P811 BR-0811-01), the FT-only gate (HRMS-P806) and dedup
(HRMS-P807) each independently blocking a submission, recruiter review
(HRMS-P808, always through createCandidateSafe()), sourcing attribution
(HRMS-P816), and the 3/5-strike compliance escalation
(HRMS-P806/P811, SUSPENSION_PENDING requiring explicit Admin
import logging
confirmation, never automatic).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.client import Client
from app.models.demand import Demand, DemandHistory
from app.models.candidate import Candidate
from app.models.consent import ConsentRecord
from app.models.sub_vendor import SubVendorAccount, SubVendorRequest, SubVendorUser
from app.models.sub_vendor_submission import (
    SubVendorSubmission,
    SubVendorViolation,
    SubVendorDedupRejection,
)
from app.models.user import Users

from app.services.sub_vendor_service import (
    register_sub_vendor,
    approve_sub_vendor,
    is_approved_for_submission,
    create_sub_vendor_request,
    close_expired_requests,
    SubVendorNotApproved,
)
from app.services.sub_vendor_submission_service import (
    submit_candidate,
    accept_submission,
    reject_submission,
    request_more_info,
    evaluate_compliance_escalation,
    confirm_suspension,
    InvalidSubmissionReviewTransition,
    SubmissionValidationError,
)


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
        ConsentRecord.__table__,
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
        required_skills="[\"Guidewire\"]", min_experience_years=5.0,
        work_location="REMOTE", status="OPEN",
    )
    db_session.add(demand)
    db_session.commit()

    account = register_sub_vendor(
        db_session, tenant_id=tenant.id, company_name="Vendor Staffing Co", contact_email="ops@vendor.com",
    )
    db_session.commit()
    approve_sub_vendor(db_session, account, approved_by="U-ADMIN")
    db_session.commit()

    request = create_sub_vendor_request(db_session, tenant_id=tenant.id, demand=demand, sub_vendor=account, assigned_by="U-RM")
    db_session.commit()

    return tenant, client, demand, account, request


# ---------------------------------------------------------------------------
# HRMS-P801: registration & approval
# ---------------------------------------------------------------------------

def test_new_account_starts_pending_approval(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    fresh = register_sub_vendor(db_session, tenant_id=tenant.id, company_name="New Vendor", contact_email="new@vendor.com")
    db_session.commit()
    assert fresh.status == "PENDING_APPROVAL"
    assert is_approved_for_submission(fresh) is False


def test_approved_account_can_submit(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    assert is_approved_for_submission(account) is True


def test_request_requires_approved_vendor(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    unapproved = register_sub_vendor(db_session, tenant_id=tenant.id, company_name="Unapproved Co", contact_email="x@x.com")
    db_session.commit()

    with pytest.raises(SubVendorNotApproved):
        create_sub_vendor_request(db_session, tenant_id=tenant.id, demand=demand, sub_vendor=unapproved, assigned_by="U-RM")


# ---------------------------------------------------------------------------
# HRMS-P811 BR-0811-01: deadline auto-close
# ---------------------------------------------------------------------------

def test_close_expired_requests(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    request.deadline = datetime.utcnow() - timedelta(days=1)
    db_session.commit()

    closed = close_expired_requests(db_session)
    db_session.commit()

    assert closed == 1
    assert request.status == "CLOSED"


def test_close_expired_requests_ignores_future_deadline(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    request.deadline = datetime.utcnow() + timedelta(days=1)
    db_session.commit()

    closed = close_expired_requests(db_session)
    assert closed == 0
    assert request.status == "OPEN"


# ---------------------------------------------------------------------------
# HRMS-P806: FT-only gate
# ---------------------------------------------------------------------------

def test_submission_rejected_for_c2c(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    submission = submit_candidate(
        db_session, request=request, sub_vendor=account,
        candidate_name="John Smith", candidate_email="john@example.com",
        employment_type="C2C",
    )
    db_session.commit()

    assert submission.status == "REJECTED"
    violations = db_session.query(SubVendorViolation).filter(SubVendorViolation.sub_vendor_id == account.id).all()
    assert len(violations) == 1
    assert violations[0].violation_type == "C2C_NOT_ACCEPTED"


def test_submission_accepted_gate_passes_for_w2(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    submission = submit_candidate(
        db_session, request=request, sub_vendor=account,
        candidate_name="Jane Doe", candidate_email="jane@example.com",
        employment_type="W2_FULLTIME",
    )
    db_session.commit()
    assert submission.status == "PENDING_REVIEW"


def test_submission_blocked_for_unapproved_vendor(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    unapproved = register_sub_vendor(db_session, tenant_id=tenant.id, company_name="Bad Co", contact_email="bad@x.com")
    db_session.commit()

    with pytest.raises(SubVendorNotApproved):
        submit_candidate(
            db_session, request=request, sub_vendor=unapproved,
            candidate_name="X", candidate_email="x@x.com", employment_type="W2_FULLTIME",
        )


# ---------------------------------------------------------------------------
# HRMS-P807: dedup, tracked separately from FT violations
# ---------------------------------------------------------------------------

def test_submission_rejected_on_email_dedup(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    existing = Candidate(candidateID="C-EXIST", candidateEmail="dupe@example.com", candidatePassword="h")
    db_session.add(existing)
    db_session.commit()

    submission = submit_candidate(
        db_session, request=request, sub_vendor=account,
        candidate_name="Dupe Candidate", candidate_email="dupe@example.com",
        employment_type="W2_FULLTIME",
    )
    db_session.commit()

    assert submission.status == "REJECTED"
    # BR-0807-02: no internal candidate details in the vendor-facing message.
    assert "dupe@example.com" not in submission.feedback_note
    assert existing.candidateID not in submission.feedback_note

    rejections = db_session.query(SubVendorDedupRejection).filter(
        SubVendorDedupRejection.submission_id == submission.id
    ).all()
    assert len(rejections) == 1
    assert rejections[0].matched_candidate_id == existing.candidateID

    # BR-0807-03: dedup rejection does NOT count as an FT-compliance violation.
    violations = db_session.query(SubVendorViolation).filter(SubVendorViolation.sub_vendor_id == account.id).count()
    assert violations == 0


# ---------------------------------------------------------------------------
# HRMS-P808: recruiter review, always through createCandidateSafe()
# ---------------------------------------------------------------------------

def test_accept_submission_creates_real_candidate_with_source_tag(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    submission = submit_candidate(
        db_session, request=request, sub_vendor=account,
        candidate_name="Priya Rao", candidate_email="priya@example.com",
        candidate_phone="+15551112222", employment_type="W2_FULLTIME",
    )
    db_session.commit()

    candidate = accept_submission(db_session, submission)
    db_session.commit()

    assert candidate.candidateEmail == "priya@example.com"
    # HRMS-P816: immutable sourcing attribution.
    assert candidate.source_channel == "SUBVENDOR"
    assert candidate.vendor_id == account.id
    assert submission.status == "ACCEPTED"
    assert submission.created_candidate_id == candidate.candidateID


def test_cannot_accept_already_reviewed_submission(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    submission = submit_candidate(
        db_session, request=request, sub_vendor=account,
        candidate_name="X", candidate_email="x2@example.com", employment_type="W2_FULLTIME",
    )
    db_session.commit()
    accept_submission(db_session, submission)
    db_session.commit()

    with pytest.raises(InvalidSubmissionReviewTransition):
        accept_submission(db_session, submission)


def test_reject_requires_min_20_char_feedback(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    submission = submit_candidate(
        db_session, request=request, sub_vendor=account,
        candidate_name="X", candidate_email="x3@example.com", employment_type="W2_FULLTIME",
    )
    db_session.commit()

    with pytest.raises(SubmissionValidationError):
        reject_submission(db_session, submission, feedback_note="too short")


def test_reject_success(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    submission = submit_candidate(
        db_session, request=request, sub_vendor=account,
        candidate_name="X", candidate_email="x4@example.com", employment_type="W2_FULLTIME",
    )
    db_session.commit()

    reject_submission(db_session, submission, feedback_note="Experience level does not match the role requirements.")
    db_session.commit()
    assert submission.status == "REJECTED"


def test_request_more_info(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    submission = submit_candidate(
        db_session, request=request, sub_vendor=account,
        candidate_name="X", candidate_email="x5@example.com", employment_type="W2_FULLTIME",
    )
    db_session.commit()

    request_more_info(db_session, submission, note="Please provide updated resume.")
    db_session.commit()
    assert submission.status == "MORE_INFO_REQUESTED"


# ---------------------------------------------------------------------------
# HRMS-P806/P811: 3/5-strike compliance escalation
# ---------------------------------------------------------------------------

def _log_c2c_violations(db, request, account, count):
    for i in range(count):
        submit_candidate(
            db, request=request, sub_vendor=account,
            candidate_name=f"C2C {i}", candidate_email=f"c2c{i}@example.com", employment_type="C2C",
        )


def test_three_violations_trigger_under_review(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    _log_c2c_violations(db_session, request, account, 3)
    db_session.commit()

    result = evaluate_compliance_escalation(db_session, account)
    db_session.commit()

    assert result == "UNDER_REVIEW"
    assert account.compliance_status == "UNDER_REVIEW"


def test_five_violations_trigger_suspension_pending_not_suspended(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    _log_c2c_violations(db_session, request, account, 5)
    db_session.commit()

    result = evaluate_compliance_escalation(db_session, account)
    db_session.commit()

    assert result == "SUSPENSION_PENDING"
    assert account.compliance_status == "SUSPENSION_PENDING"
    assert account.compliance_status != "SUSPENDED"  # BR-0811-02: not automatic


def test_confirm_suspension_requires_pending_state(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    with pytest.raises(InvalidSubmissionReviewTransition):
        confirm_suspension(db_session, account)


def test_confirm_suspension_transitions_to_suspended(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    _log_c2c_violations(db_session, request, account, 5)
    db_session.commit()
    evaluate_compliance_escalation(db_session, account)
    db_session.commit()

    confirm_suspension(db_session, account)
    db_session.commit()

    assert account.compliance_status == "SUSPENDED"


def test_under_two_violations_no_escalation(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    _log_c2c_violations(db_session, request, account, 2)
    db_session.commit()

    result = evaluate_compliance_escalation(db_session, account)
    assert result is None
    assert account.compliance_status == "GOOD_STANDING"


def test_suspended_vendor_cannot_submit(db_session, fixtures):
    tenant, client, demand, account, request = fixtures
    _log_c2c_violations(db_session, request, account, 5)
    db_session.commit()
    evaluate_compliance_escalation(db_session, account)
    db_session.commit()

    with pytest.raises(SubVendorNotApproved):
        submit_candidate(
            db_session, request=request, sub_vendor=account,
            candidate_name="X", candidate_email="blocked@example.com", employment_type="W2_FULLTIME",
        )
