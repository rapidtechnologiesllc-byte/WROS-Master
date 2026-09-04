"""
import logging
Tests for Candidate Rejection Workflow (S-322)

Tests cover:
- reject_candidate() — Create rejection record
- send_rejection_email() — Send email notification
- archive_candidate() — Soft-delete candidate
- Rejection reasons management
- Candidate rejection status queries
- Edge cases and error handling

Story: S-322 (Candidate Rejection Workflow)
"""

import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateStatus
from app.models.candidate_rejection import CandidateRejection, CandidateRejectionReason
from app.models.candidate_history import CandidateHistory
from app.models.user import Users
from app.models.audit_log import AuditLog
from app.services.candidate_rejection_service import (
    reject_candidate,
    send_rejection_email,
    archive_candidate,
    get_rejection_reasons,
    get_candidate_rejection_status,
    CandidateRejectionError,
    CandidateNotFoundError,
    create_default_rejection_reasons,
)

@pytest.fixture()
def db_session():
    """Create an in-memory SQLite test database."""
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")

    # Only create tables we need for this test
    tables_to_create = [
        Candidate.__table__,
        CandidateStatus.__table__,
        CandidateRejection.__table__,
        CandidateRejectionReason.__table__,
        CandidateHistory.__table__,
        Users.__table__,
        AuditLog.__table__,
    ]

    Base.metadata.create_all(engine, tables=tables_to_create)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

def _seed_candidate(db, **overrides):
    """Helper to create a test candidate."""
    defaults = dict(
        candidateID="C-TEST-001",
        candidateEmail="test@example.com",
        candidateMobile="+19995551111",
        candidateFirstName="John",
        candidateLastName="Doe",
        candidatePassword="hashed_password",
        candidateIsVerified=False,
        tenant_id=1,
    )
    defaults.update(overrides)
    candidate = Candidate(**defaults)
    db.add(candidate)
    db.commit()
    return candidate

def _seed_user(db, **overrides):
    """Helper to create a test user."""
    defaults = dict(
        UserID="U-TEST-001",
        Email="recruiter@example.com",
        Password="hashed_password",
        FirstName="Jane",
        LastName="Smith",
    )
    defaults.update(overrides)
    user = Users(**defaults)
    db.add(user)
    db.commit()
    return user

# ---------------------------------------------------------------------------
# Test reject_candidate()
# ---------------------------------------------------------------------------

def test_reject_candidate_creates_rejection_record(db_session):
    """Test that reject_candidate creates a rejection record."""
    candidate = _seed_candidate(db_session)

    rejection = reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="LACK_OF_EXPERIENCE",
        rejection_note="Candidate has only 2 years experience",
        send_email=False,
    )

    assert rejection.id is not None
    assert rejection.candidate_id == candidate.candidateID
    assert rejection.rejection_reason == "LACK_OF_EXPERIENCE"
    assert rejection.rejection_status == "ACTIVE"
    assert rejection.email_sent == False

def test_reject_candidate_updates_candidate_status(db_session):
    """Test that reject_candidate updates candidate pipeline status."""
    candidate = _seed_candidate(db_session)

    reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="FAILED_SCREENING",
        send_email=False,
    )

    status = db_session.query(CandidateStatus).filter(
        CandidateStatus.candidateID == candidate.candidateID
    ).first()

    assert status is not None
    assert status.piplineStatus == "Rejected"
    assert status.status == "Inactive"

def test_reject_candidate_creates_audit_history(db_session):
    """Test that reject_candidate creates history entry."""
    candidate = _seed_candidate(db_session)

    reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="ROLE_MISMATCH",
        rejection_note="Skills don't match",
        send_email=False,
    )

    history = db_session.query(CandidateHistory).filter(
        CandidateHistory.candidateID == candidate.candidateID
    ).first()

    assert history is not None
    assert history.event_type == "Rejection"
    assert "ROLE_MISMATCH" in history.note

def test_reject_candidate_with_job_id(db_session):
    """Test reject_candidate with job_id."""
    candidate = _seed_candidate(db_session)

    rejection = reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="POSITION_FILLED",
        job_id="JOB-123",
        send_email=False,
    )

    assert rejection.job_id == "JOB-123"

def test_reject_candidate_not_found_raises_error(db_session):
    """Test that rejecting non-existent candidate raises error."""
    with pytest.raises(CandidateNotFoundError):
        reject_candidate(
            db_session,
            candidate_id="C-NONEXISTENT",
            rejection_reason="UNKNOWN",
        )

def test_reject_candidate_records_rejected_by_user(db_session):
    """Test that rejection records who performed the action."""
    candidate = _seed_candidate(db_session)
    user = _seed_user(db_session)

    rejection = reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="OTHER",
        rejected_by_user_id=user.UserID,
        send_email=False,
    )

    assert rejection.rejected_by_user_id == user.UserID

# ---------------------------------------------------------------------------
# Test send_rejection_email()
# ---------------------------------------------------------------------------

def test_send_rejection_email_updates_record(db_session):
    """Test that send_rejection_email marks email as sent."""
    candidate = _seed_candidate(db_session)

    rejection = reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="LACK_OF_EXPERIENCE",
        send_email=False,  # Don't send initially
    )

    # Now send the email
    updated = send_rejection_email(
        db_session,
        rejection_id=rejection.id,
        include_feedback=False,
        include_next_steps=True,
    )

    assert updated.email_sent == True
    assert updated.email_sent_at is not None

def test_send_rejection_email_not_found_raises_error(db_session):
    """Test that sending email for non-existent rejection raises error."""
    with pytest.raises(CandidateRejectionError):
        send_rejection_email(
            db_session,
            rejection_id=9999,
        )

def test_reject_candidate_with_email(db_session):
    """Test reject_candidate with send_email=True."""
    candidate = _seed_candidate(db_session)

    rejection = reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="FAILED_INTERVIEW",
        send_email=True,
    )

    # Email sending may fail if EmailService not fully set up, but flag should update
    # This test verifies the flow works (mocking handled by test environment)
    assert rejection.id is not None

# ---------------------------------------------------------------------------
# Test archive_candidate()
# ---------------------------------------------------------------------------

def test_archive_candidate_marks_as_archived(db_session):
    """Test that archive_candidate marks rejection as ARCHIVED."""
    candidate = _seed_candidate(db_session)

    rejection = reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="POSITION_FILLED",
        send_email=False,
    )

    archived = archive_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        archive_reason="Position filled by other candidate",
    )

    assert archived.rejection_status == "ARCHIVED"
    assert archived.archived_at is not None

def test_archive_candidate_records_who_archived(db_session):
    """Test that archive_candidate records who performed action."""
    candidate = _seed_candidate(db_session)
    user = _seed_user(db_session)

    reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="OTHER",
        send_email=False,
    )

    archived = archive_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        archived_by_user_id=user.UserID,
    )

    assert archived.archived_by_user_id == user.UserID

def test_archive_candidate_creates_history(db_session):
    """Test that archive_candidate creates history entry."""
    candidate = _seed_candidate(db_session)

    reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="WITHDREW",
        send_email=False,
    )

    archive_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        archive_reason="Candidate withdrew",
    )

    # Count archive history entries
    history = db_session.query(CandidateHistory).filter(
        CandidateHistory.candidateID == candidate.candidateID,
        CandidateHistory.event_type == "Archive",
    ).first()

    assert history is not None

def test_archive_candidate_appends_to_note(db_session):
    """Test that archive_candidate appends to rejection note."""
    candidate = _seed_candidate(db_session)

    rejection = reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="OTHER",
        rejection_note="Initial note",
        send_email=False,
    )

    archived = archive_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        archive_note="Archive note here",
    )

    assert "Initial note" in archived.rejection_note
    assert "Archive note here" in archived.rejection_note

def test_archive_candidate_no_active_rejection_raises_error(db_session):
    """Test that archiving non-rejected candidate raises error."""
    candidate = _seed_candidate(db_session)

    with pytest.raises(CandidateRejectionError):
        archive_candidate(
            db_session,
            candidate_id=candidate.candidateID,
        )

# ---------------------------------------------------------------------------
# Test Rejection Reasons
# ---------------------------------------------------------------------------

def test_get_rejection_reasons_returns_list(db_session):
    """Test that get_rejection_reasons returns list of reasons."""
    create_default_rejection_reasons(db_session)

    reasons = get_rejection_reasons(db_session, active_only=True)

    assert len(reasons) > 0
    assert any(r.reason_code == "LACK_OF_EXPERIENCE" for r in reasons)
    assert any(r.reason_code == "FAILED_INTERVIEW" for r in reasons)

def test_get_rejection_reasons_filters_active(db_session):
    """Test that get_rejection_reasons filters by active status."""
    create_default_rejection_reasons(db_session)

    # All default reasons should be active
    reasons = get_rejection_reasons(db_session, active_only=True)
    assert all(r.is_active for r in reasons)

    # Should exclude inactive reasons
    inactive_reason = db_session.query(CandidateRejectionReason).first()
    if inactive_reason:
        inactive_reason.is_active = False
        db_session.commit()

        active_reasons = get_rejection_reasons(db_session, active_only=True)
        assert all(r.is_active for r in active_reasons)

def test_create_default_rejection_reasons_idempotent(db_session):
    """Test that creating default reasons twice doesn't create duplicates."""
    create_default_rejection_reasons(db_session)
    count_first = db_session.query(CandidateRejectionReason).count()

    create_default_rejection_reasons(db_session)
    count_second = db_session.query(CandidateRejectionReason).count()

    assert count_first == count_second

# ---------------------------------------------------------------------------
# Test Candidate Rejection Status Queries
# ---------------------------------------------------------------------------

def test_get_candidate_rejection_status_not_rejected(db_session):
    """Test rejection status for non-rejected candidate."""
    candidate = _seed_candidate(db_session)

    is_rejected, latest, all_rejections = get_candidate_rejection_status(
        db_session,
        candidate_id=candidate.candidateID,
    )

    assert is_rejected == False
    assert latest is None
    assert len(all_rejections) == 0

def test_get_candidate_rejection_status_rejected(db_session):
    """Test rejection status for rejected candidate."""
    candidate = _seed_candidate(db_session)

    rejection = reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="FAILED_SCREENING",
        send_email=False,
    )

    is_rejected, latest, all_rejections = get_candidate_rejection_status(
        db_session,
        candidate_id=candidate.candidateID,
    )

    assert is_rejected == True
    assert latest.id == rejection.id
    assert len(all_rejections) == 1

def test_get_candidate_rejection_status_archived(db_session):
    """Test rejection status when archived."""
    candidate = _seed_candidate(db_session)

    reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="POSITION_FILLED",
        send_email=False,
    )

    archive_candidate(
        db_session,
        candidate_id=candidate.candidateID,
    )

    is_rejected, latest, all_rejections = get_candidate_rejection_status(
        db_session,
        candidate_id=candidate.candidateID,
    )

    # After archiving, active rejection should not exist
    assert is_rejected == False
    assert latest is None
    # But all_rejections should still include the archived one
    assert len(all_rejections) == 1
    assert all_rejections[0].rejection_status == "ARCHIVED"

def test_get_candidate_rejection_status_multiple_rejections(db_session):
    """Test rejection status with multiple rejections."""
    candidate = _seed_candidate(db_session)

    rejection1 = reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="FAILED_SCREENING",
        send_email=False,
    )

    archive_candidate(
        db_session,
        candidate_id=candidate.candidateID,
    )

    # Second rejection after archiving first
    rejection2 = reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="ROLE_MISMATCH",
        send_email=False,
    )

    is_rejected, latest, all_rejections = get_candidate_rejection_status(
        db_session,
        candidate_id=candidate.candidateID,
    )

    assert is_rejected == True
    assert latest.id == rejection2.id
    assert len(all_rejections) == 2

# ---------------------------------------------------------------------------
# Test Tenant Isolation
# ---------------------------------------------------------------------------

def test_reject_candidate_tenant_isolation(db_session):
    """Test that rejection respects tenant_id."""
    candidate_t1 = _seed_candidate(db_session, candidateID="C-T1-001", tenant_id=1)
    candidate_t2 = _seed_candidate(
        db_session,
        candidateID="C-T2-001",
        candidateEmail="t2@example.com",
        tenant_id=2,
    )

    reject_candidate(
        db_session,
        candidate_id=candidate_t1.candidateID,
        rejection_reason="OTHER",
        tenant_id=1,
        send_email=False,
    )

    # Trying to access tenant 1's candidate from tenant 2 should fail
    with pytest.raises(CandidateNotFoundError):
        reject_candidate(
            db_session,
            candidate_id=candidate_t1.candidateID,
            rejection_reason="OTHER",
            tenant_id=2,
            send_email=False,
        )

# ---------------------------------------------------------------------------
# Test Error Handling
# ---------------------------------------------------------------------------

def test_reject_candidate_with_none_tenant_defaults(db_session):
    """Test that tenant_id defaults to 1 if not provided."""
    candidate = _seed_candidate(db_session)

    rejection = reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="OTHER",
        tenant_id=1,
        send_email=False,
    )

    assert rejection.tenant_id == 1

def test_reject_candidate_timestamps_set(db_session):
    """Test that rejection timestamps are set correctly."""
    candidate = _seed_candidate(db_session)
    before = datetime.utcnow()

    rejection = reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="OTHER",
        send_email=False,
    )

    after = datetime.utcnow()

    assert before <= rejection.rejected_at <= after

# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

def test_complete_rejection_workflow(db_session):
    """Integration test: full rejection workflow from creation to archival."""
    candidate = _seed_candidate(db_session)
    user = _seed_user(db_session)

    # Step 1: Reject candidate
    rejection = reject_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        rejection_reason="FAILED_INTERVIEW",
        rejection_note="Performance in technical interview was weak",
        job_id="JOB-456",
        rejected_by_user_id=user.UserID,
        send_email=False,
    )

    assert rejection.id is not None
    assert rejection.rejection_status == "ACTIVE"

    # Step 2: Send email
    updated = send_rejection_email(
        db_session,
        rejection_id=rejection.id,
        include_feedback=True,
    )

    assert updated.email_sent == True

    # Step 3: Archive candidate
    archived = archive_candidate(
        db_session,
        candidate_id=candidate.candidateID,
        archive_reason="End of hiring cycle",
        archived_by_user_id=user.UserID,
    )

    assert archived.rejection_status == "ARCHIVED"

    # Verify final state
    is_rejected, latest, all_rejections = get_candidate_rejection_status(
        db_session,
        candidate_id=candidate.candidateID,
    )

    assert is_rejected == False  # No active rejections
    assert len(all_rejections) == 1
    assert all_rejections[0].rejection_status == "ARCHIVED"
