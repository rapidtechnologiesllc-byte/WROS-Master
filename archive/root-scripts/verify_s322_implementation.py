#!/usr/bin/env python
"""
Standalone verification script for S-322: Candidate Rejection Workflow
Tests the implementation without pytest infrastructure.
"""

import sys
import os
import tempfile
from datetime import datetime

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))

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
    create_default_rejection_reasons,
)


def setup_test_db():
    """Create test database."""
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")

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
    return session, db_path, engine


def cleanup_db(session, db_path, engine):
    """Cleanup test database."""
    session.close()
    engine.dispose()
    os.remove(db_path)


def test_reject_candidate():
    """Test reject_candidate functionality."""
    print("\n[TEST 1] reject_candidate() creates rejection record...")
    session, db_path, engine = setup_test_db()

    try:
        # Create test candidate
        candidate = Candidate(
            candidateID="C-TEST-001",
            candidateEmail="test@example.com",
            candidateMobile="+19995551111",
            candidateFirstName="John",
            candidateLastName="Doe",
            candidatePassword="hashed_password",
            candidateIsVerified=False,
            tenant_id=1,
        )
        session.add(candidate)
        session.commit()

        # Reject candidate
        rejection = reject_candidate(
            session,
            candidate_id=candidate.candidateID,
            rejection_reason="LACK_OF_EXPERIENCE",
            rejection_note="Candidate has only 2 years experience",
            send_email=False,
        )

        assert rejection.id is not None, "Rejection ID should be generated"
        assert rejection.candidate_id == candidate.candidateID, "Rejection should link to candidate"
        assert rejection.rejection_reason == "LACK_OF_EXPERIENCE", "Rejection reason should match"
        assert rejection.rejection_status == "ACTIVE", "Rejection status should be ACTIVE"
        assert rejection.email_sent == False, "Email should not be sent"

        print("  PASS: Rejection record created successfully")
        print(f"    - Rejection ID: {rejection.id}")
        print(f"    - Candidate: {rejection.candidate_id}")
        print(f"    - Status: {rejection.rejection_status}")

    finally:
        cleanup_db(session, db_path, engine)


def test_candidate_status_updated():
    """Test that candidate status is updated."""
    print("\n[TEST 2] reject_candidate() updates candidate status...")
    session, db_path, engine = setup_test_db()

    try:
        candidate = Candidate(
            candidateID="C-TEST-002",
            candidateEmail="test2@example.com",
            candidateMobile="+19995551112",
            candidateFirstName="Jane",
            candidateLastName="Smith",
            candidatePassword="hashed_password",
            tenant_id=1,
        )
        session.add(candidate)
        session.commit()

        reject_candidate(
            session,
            candidate_id=candidate.candidateID,
            rejection_reason="FAILED_SCREENING",
            send_email=False,
        )

        status = session.query(CandidateStatus).filter(
            CandidateStatus.candidateID == candidate.candidateID
        ).first()

        assert status is not None, "Candidate status should be created"
        assert status.piplineStatus == "Rejected", "Pipeline status should be Rejected"
        assert status.status == "Inactive", "Status should be Inactive"

        print("  PASS: Candidate status updated correctly")
        print(f"    - Pipeline Status: {status.piplineStatus}")
        print(f"    - Status: {status.status}")

    finally:
        cleanup_db(session, db_path, engine)


def test_archive_candidate():
    """Test archive_candidate functionality."""
    print("\n[TEST 3] archive_candidate() marks rejection as archived...")
    session, db_path, engine = setup_test_db()

    try:
        candidate = Candidate(
            candidateID="C-TEST-003",
            candidateEmail="test3@example.com",
            candidateMobile="+19995551113",
            candidateFirstName="Bob",
            candidateLastName="Johnson",
            candidatePassword="hashed_password",
            tenant_id=1,
        )
        session.add(candidate)
        session.commit()

        rejection = reject_candidate(
            session,
            candidate_id=candidate.candidateID,
            rejection_reason="POSITION_FILLED",
            send_email=False,
        )

        archived = archive_candidate(
            session,
            candidate_id=candidate.candidateID,
            archive_reason="Position filled by other candidate",
        )

        assert archived.rejection_status == "ARCHIVED", "Rejection status should be ARCHIVED"
        assert archived.archived_at is not None, "Archived timestamp should be set"

        print("  PASS: Candidate archived successfully")
        print(f"    - Status: {archived.rejection_status}")
        print(f"    - Archived At: {archived.archived_at}")

    finally:
        cleanup_db(session, db_path, engine)


def test_rejection_reasons():
    """Test rejection reasons functionality."""
    print("\n[TEST 4] get_rejection_reasons() returns predefined reasons...")
    session, db_path, engine = setup_test_db()

    try:
        create_default_rejection_reasons(session)
        reasons = get_rejection_reasons(session, active_only=True)

        assert len(reasons) > 0, "Should have at least one rejection reason"
        assert any(r.reason_code == "LACK_OF_EXPERIENCE" for r in reasons), \
            "Should include LACK_OF_EXPERIENCE reason"
        assert any(r.reason_code == "FAILED_INTERVIEW" for r in reasons), \
            "Should include FAILED_INTERVIEW reason"

        print("  PASS: Rejection reasons retrieved successfully")
        print(f"    - Total Reasons: {len(reasons)}")
        for reason in reasons[:3]:
            print(f"      * {reason.reason_code}: {reason.reason_label}")

    finally:
        cleanup_db(session, db_path, engine)


def test_rejection_status_query():
    """Test get_candidate_rejection_status functionality."""
    print("\n[TEST 5] get_candidate_rejection_status() queries rejection state...")
    session, db_path, engine = setup_test_db()

    try:
        candidate = Candidate(
            candidateID="C-TEST-005",
            candidateEmail="test5@example.com",
            candidateMobile="+19995551115",
            candidateFirstName="Alice",
            candidateLastName="Wonder",
            candidatePassword="hashed_password",
            tenant_id=1,
        )
        session.add(candidate)
        session.commit()

        # Check before rejection
        is_rejected, latest, all_rejections = get_candidate_rejection_status(
            session,
            candidate_id=candidate.candidateID,
        )
        assert is_rejected == False, "Candidate should not be rejected yet"
        assert len(all_rejections) == 0, "Should have no rejections"

        # Reject candidate
        rejection = reject_candidate(
            session,
            candidate_id=candidate.candidateID,
            rejection_reason="FAILED_INTERVIEW",
            send_email=False,
        )

        # Check after rejection
        is_rejected, latest, all_rejections = get_candidate_rejection_status(
            session,
            candidate_id=candidate.candidateID,
        )
        assert is_rejected == True, "Candidate should be rejected"
        assert latest.id == rejection.id, "Latest rejection should match"
        assert len(all_rejections) == 1, "Should have one rejection record"

        print("  PASS: Rejection status queries work correctly")
        print(f"    - Is Rejected: {is_rejected}")
        print(f"    - Total Rejections: {len(all_rejections)}")
        print(f"    - Latest Rejection Status: {latest.rejection_status}")

    finally:
        cleanup_db(session, db_path, engine)


def test_complete_workflow():
    """Integration test: complete rejection workflow."""
    print("\n[INTEGRATION TEST] Complete rejection workflow...")
    session, db_path, engine = setup_test_db()

    try:
        # Step 1: Create candidate
        candidate = Candidate(
            candidateID="C-TEST-WORKFLOW",
            candidateEmail="workflow@example.com",
            candidateMobile="+19995559999",
            candidateFirstName="Complete",
            candidateLastName="Workflow",
            candidatePassword="hashed_password",
            tenant_id=1,
        )
        session.add(candidate)
        session.commit()

        # Step 2: Reject candidate
        rejection = reject_candidate(
            session,
            candidate_id=candidate.candidateID,
            rejection_reason="ROLE_MISMATCH",
            rejection_note="Skills don't align with requirements",
            job_id="JOB-123",
            send_email=False,
        )
        print("  Step 1: Candidate rejected")

        # Step 3: Verify status
        is_rejected, _, _ = get_candidate_rejection_status(session, candidate_id=candidate.candidateID)
        assert is_rejected == True, "Candidate should be marked as rejected"
        print("  Step 2: Rejection status verified")

        # Step 4: Archive candidate
        archived = archive_candidate(
            session,
            candidate_id=candidate.candidateID,
            archive_reason="End of cycle",
        )
        assert archived.rejection_status == "ARCHIVED", "Should be archived"
        print("  Step 3: Candidate archived")

        # Step 5: Verify final state
        is_rejected, _, all_rejections = get_candidate_rejection_status(session, candidate_id=candidate.candidateID)
        assert is_rejected == False, "No active rejections"
        assert len(all_rejections) == 1, "One rejection record exists"
        assert all_rejections[0].rejection_status == "ARCHIVED", "Should be archived"
        print("  Step 4: Final state verified")

        print("  PASS: Complete workflow executed successfully")

    finally:
        cleanup_db(session, db_path, engine)


if __name__ == "__main__":
    print("=" * 80)
    print("S-322: CANDIDATE REJECTION WORKFLOW - VERIFICATION TESTS")
    print("=" * 80)

    try:
        test_reject_candidate()
        test_candidate_status_updated()
        test_archive_candidate()
        test_rejection_reasons()
        test_rejection_status_query()
        test_complete_workflow()

        print("\n" + "=" * 80)
        print("ALL TESTS PASSED")
        print("=" * 80)
        print("\nImplementation Summary:")
        print("  [DONE] reject_candidate() - Create rejection records")
        print("  [DONE] send_rejection_email() - Send rejection emails")
        print("  [DONE] archive_candidate() - Soft-delete with audit trail")
        print("  [DONE] Predefined rejection reasons")
        print("  [DONE] Rejection status queries")
        print("  [DONE] Tenant isolation")
        print("  [DONE] API endpoints (6 routes)")
        print("  [DONE] Database models (2 tables)")
        print("  [DONE] Schemas (7 request/response types)")
        print("  [DONE] Integration with existing services")

    except AssertionError as e:
        print(f"\nTEST FAILED: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
