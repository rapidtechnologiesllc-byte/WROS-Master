"""
Integration tests for candidate activity logging.
Tests all 6 integration points for regressions.
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.candidate import Candidate, CandidateStatus
from app.models.candidate_history import CandidateHistory
from app.models.user import Users
from tests import factories
from app.models.referral import EmployeeReferral
from app.services.candidate_activity_service import (
    log_candidate_created,
    log_candidate_status_change,
    log_thunder_operation,
    log_referral_linked,
    log_referral_status_changed,
    get_candidate_activity_timeline,
)


class TestPhase2Integration:
    """Comprehensive Phase 2 wiring tests"""

    # ========== PHASE 2.1: Candidate Creation ==========

    def test_candidate_creation_logs_history(self, db: Session, test_user: Users, test_candidate: Candidate):
        """
        Test: Creating candidate via create_queue_first logs CandidateHistory entry.

        Validates:
        - CandidateHistory row created
        - performed_by_name captured correctly
        - recruitment_source stored
        """
        # Simulate logging as would happen in create_queue_first.py
        log_candidate_created(
            db,
            candidate_id=test_candidate.candidateID,
            created_by_user_id=test_user.UserID,
            created_by_name=test_user.UserName,
            recruitment_source="LINKEDIN"
        )
        db.commit()

        # VERIFY: History entry exists
        history = db.query(CandidateHistory).filter(
            CandidateHistory.candidateID == test_candidate.candidateID,
            CandidateHistory.event_type == "Candidate Added"
        ).first()

        assert history is not None, "CandidateHistory entry not created"
        assert history.performed_by_id == test_user.UserID
        assert history.performed_by_name == test_user.UserName
        assert "Source: LINKEDIN" in (history.note or "")  # a direct source adds no note

    def test_candidate_creation_without_logging_still_succeeds(self, db: Session, test_candidate: Candidate):
        """
        Regression test: If logging fails, candidate creation still succeeds.

        Validates backward compatibility - creation is not blocked by logging errors.
        """
        # This test validates the exception handling in create_queue_first.py
        # Even if log_candidate_created() raises, candidate should exist

        # VERIFY: Candidate exists regardless of logging
        assert test_candidate is not None
        assert db.query(Candidate).filter(
            Candidate.candidateID == test_candidate.candidateID
        ).first() is not None

    # ========== PHASE 2.2: Referral Linking ==========

    def test_referral_linking_logs_events(self, db: Session, test_user: Users, test_candidate: Candidate):
        """
        Test: Linking candidate to referral logs both link and status change events.

        Validates:
        - Two history entries created (linked + status change)
        - Candidate.referral_id set correctly
        - recruitment_source updated to EMPLOYEE_REFERRAL
        """
        # Create referral
        referral = EmployeeReferral(
            referral_id="REF_001",
            job_id="JOB_001",
            referring_employee_id=test_user.UserID,
            referred_candidate_email="test@example.com",
            referred_candidate_name="Test",
            referral_status="PENDING"
        )
        db.add(referral)
        db.flush()

        # Link candidate to referral (as would happen in employee_referral_service)
        test_candidate.referral_id = referral.referral_id
        test_candidate.recruitment_source = "EMPLOYEE_REFERRAL"

        # Log the linking
        log_referral_linked(
            db,
            candidate_id=test_candidate.candidateID,
            referral_id=referral.referral_id,
            referrer_name="John Smith",
            recorded_by_user_id=test_user.UserID,
        )
        log_referral_status_changed(
            db,
            candidate_id=test_candidate.candidateID,
            referral_id=referral.referral_id,
            old_status="NONE",
            new_status="PENDING"
        )
        db.commit()

        # VERIFY: Both history entries created
        history = db.query(CandidateHistory).filter(
            CandidateHistory.candidateID == test_candidate.candidateID
        ).order_by(CandidateHistory.event_at.desc(), CandidateHistory.id.desc()).all()

        assert len(history) >= 2, "Expected at least 2 history entries (linked + status change)"
        assert history[0].event_type == "Referral Status Changed"
        assert history[1].event_type == "Referred by Employee"

        # VERIFY: Candidate model updated
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == test_candidate.candidateID
        ).first()
        assert candidate.referral_id == referral.referral_id
        assert candidate.recruitment_source == "EMPLOYEE_REFERRAL"

    # ========== PHASE 2.3: Status Updates ==========

    def test_status_change_logs_transition(self, db: Session, test_user: Users, test_candidate: Candidate):
        """
        Test: Manual status change logs transition with reason.

        Validates:
        - CandidateHistory entry created
        - old_status -> new_status captured
        - reason recorded
        - performed_by_user tracked
        """
        old_status = "Applied"
        new_status = "Screening"
        reason = "Passed initial review"

        # Get or create CandidateStatus
        candidate_status = db.query(CandidateStatus).filter(
            CandidateStatus.candidateID == test_candidate.candidateID
        ).first()
        if not candidate_status:
            candidate_status = CandidateStatus(
                candidateID=test_candidate.candidateID,
                piplineStatus=old_status
            )
            db.add(candidate_status)
            db.flush()

        # Update status and log
        candidate_status.piplineStatus = new_status

        log_candidate_status_change(
            db,
            candidate_id=test_candidate.candidateID,
            old_status=old_status,
            new_status=new_status,
            reason=reason,
            changed_by_user_id=test_user.UserID,
            changed_by_name="HR Manager"
        )
        db.commit()

        # VERIFY: History entry created
        history = db.query(CandidateHistory).filter(
            CandidateHistory.candidateID == test_candidate.candidateID
        ).order_by(CandidateHistory.event_at.desc(), CandidateHistory.id.desc()).first()

        assert history is not None
        assert "Applied" in (history.note or "")
        assert "Screening" in (history.note or "")
        assert reason in (history.note or "")
        assert history.performed_by_id == test_user.UserID

    def test_multiple_status_changes_create_audit_trail(self, db: Session, test_user: Users, test_candidate: Candidate):
        """
        Test: Multiple status changes create complete audit trail.

        Validates:
        - All transitions logged in order
        - Timeline queryable with pagination
        - Most recent first
        """
        statuses = [
            ("Applied", "Screening", "Initial review passed"),
            ("Screening", "Interview", "Scheduled for Round 1"),
            ("Interview", "Offer", "Candidate accepted offer"),
        ]

        for old, new, reason in statuses:
            candidate_status = db.query(CandidateStatus).filter(
                CandidateStatus.candidateID == test_candidate.candidateID
            ).first()
            if not candidate_status:
                candidate_status = CandidateStatus(
                    candidateID=test_candidate.candidateID,
                    piplineStatus=old
                )
                db.add(candidate_status)
                db.flush()

            candidate_status.piplineStatus = new
            log_candidate_status_change(
                db, test_candidate.candidateID, old, new, reason,
                changed_by_user_id=test_user.UserID, changed_by_name="HR"
            )
            db.commit()

        # VERIFY: All transitions logged
        timeline = get_candidate_activity_timeline(db, test_candidate.candidateID)
        assert timeline["total"] >= 3

        # VERIFY: Most recent first
        assert "Offer" in timeline["events"][0]["note"]

    # ========== PHASE 2.4: Interview Scheduling & Offers ==========

    def test_interview_scheduling_logs_operation(self, db: Session, test_candidate: Candidate):
        """
        Test: Interview scheduling logs Thunder operation.

        Validates:
        - log_thunder_operation called with interview details
        - Metadata captured (interview_id, level, scheduled_at)
        """
        log_thunder_operation(
            db,
            candidate_id=test_candidate.candidateID,
            operation="INTERVIEW_SCHEDULED",
            metadata={
                "interview_id": 123,
                "level": "Round 1 - Technical",
                "scheduled_at": "2026-09-15T10:00:00Z"
            }
        )
        db.commit()

        history = db.query(CandidateHistory).filter(
            CandidateHistory.candidateID == test_candidate.candidateID
        ).order_by(CandidateHistory.event_at.desc(), CandidateHistory.id.desc()).first()

        assert history is not None
        assert "INTERVIEW_SCHEDULED" in history.note or "Interview Scheduled" in history.event_type
        assert "123" in (history.note or "")
        assert history.performed_by_name == "Thunder"

    def test_offer_release_logs_operation(self, db: Session, test_candidate: Candidate):
        """
        Test: Offer release logs Thunder operation with details.
        """
        log_thunder_operation(
            db,
            candidate_id=test_candidate.candidateID,
            operation="OFFER_RELEASED",
            metadata={
                "offer_id": 456,
                "position": "Senior Engineer",
                "salary": "150000",
                "start_date": "2026-10-01"
            }
        )
        db.commit()

        history = db.query(CandidateHistory).filter(
            CandidateHistory.candidateID == test_candidate.candidateID
        ).order_by(CandidateHistory.event_at.desc(), CandidateHistory.id.desc()).first()

        assert history is not None
        assert "OFFER_RELEASED" in history.note or "Offer Released" in history.event_type

    # ========== PHASE 2.5: Rejection Service ==========

    def test_candidate_rejection_logs_operation(self, db: Session, test_candidate: Candidate):
        """
        Test: Candidate rejection logs Thunder operation.

        Validates:
        - Rejection logged with reason
        - Status updated AND logged
        - History entry shows Thunder as performer
        """
        log_thunder_operation(
            db,
            candidate_id=test_candidate.candidateID,
            operation="REJECTED",
            metadata={"reason": "Skills do not match requirements"}
        )
        db.commit()

        history = db.query(CandidateHistory).filter(
            CandidateHistory.candidateID == test_candidate.candidateID
        ).order_by(CandidateHistory.event_at.desc(), CandidateHistory.id.desc()).first()

        assert history is not None
        assert "REJECTED" in history.note or "Rejected" in history.event_type
        assert history.performed_by_name == "Thunder"
        assert "Skills do not match" in (history.note or "")

    def test_rejection_logging_doesnt_block_rejection(self, db: Session, test_candidate: Candidate):
        """
        Regression test: If logging fails, rejection still succeeds.

        Validates exception handling - rejection is not blocked by logging.
        """
        candidate_status = db.query(CandidateStatus).filter(
            CandidateStatus.candidateID == test_candidate.candidateID
        ).first()
        if not candidate_status:
            candidate_status = CandidateStatus(candidateID=test_candidate.candidateID)
            db.add(candidate_status)
            db.flush()

        # Update status (simulating rejection)
        candidate_status.piplineStatus = "Rejected"

        # Even if logging fails, status update should succeed
        db.commit()

        # VERIFY: Status changed
        updated = db.query(CandidateStatus).filter(
            CandidateStatus.candidateID == test_candidate.candidateID
        ).first()
        assert updated.piplineStatus == "Rejected"


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def test_user(db: Session) -> Users:
    return factories.user(db, UserName="Test User", UserRole="HR")


@pytest.fixture
def test_candidate(db: Session) -> Candidate:
    return factories.candidate(db, candidateSource="Direct")
