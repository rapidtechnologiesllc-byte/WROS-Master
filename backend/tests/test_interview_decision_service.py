"""
S-311: Interview Decision Engine — Unit Tests
Complete test coverage for interview decision service methods.
"""
import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.models.base import Base
from app.models.user import Users, Jobs, Interview
from app.models.candidate import Candidate
from app.models.interview import InterviewFeedback, InterviewDecisionLog
from app.services.interview_decision_service import InterviewDecisionService


# ────────────────────────────────────────────────────────────────────────────
# Test Fixtures
# ────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def test_db():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()


@pytest.fixture
def service():
    """Create InterviewDecisionService instance."""
    return InterviewDecisionService()


def create_test_user(db: Session, user_id: str, email: str) -> Users:
    """Helper to create test user."""
    user = Users(
        UserID=user_id,
        UserRole="Admin",
        UserName=f"Test User {user_id}",
        UserEmail=email,
        UserPassword="hashed_password",
        tenant_id=1
    )
    db.add(user)
    db.commit()
    return user


def create_test_candidate(db: Session, candidate_id: str) -> Candidate:
    """Helper to create test candidate."""
    candidate = Candidate(
        candidateID=candidate_id,
        candidateName="Test Candidate",
        candidateEmail="candidate@test.com",
        candidatePhone="+1234567890",
        candidateStatus="ACTIVE",
        recruiterID="R001",
        tenant_id=1
    )
    db.add(candidate)
    db.commit()
    return candidate


def create_test_job(db: Session, job_id: str) -> Jobs:
    """Helper to create test job."""
    job = Jobs(
        jobID=job_id,
        jobTitle="Senior Software Engineer",
        jobDescription="A great job",
        jobSkills="Python, JavaScript",
        jobExperience="5 years",
        jobLocation="Remote",
        recurierID="R001",
        tenant_id=1
    )
    db.add(job)
    db.commit()
    return job


def create_test_interview(db: Session, interview_id: int, candidate_id: str) -> Interview:
    """Helper to create test interview."""
    interview = Interview(
        id=interview_id,
        interviewID=f"INT_{interview_id}",
        candidate_id=candidate_id,
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow() + timedelta(hours=1),
        status="Completed",
        feedback_status="Completed"
    )
    db.add(interview)
    db.commit()
    return interview


def create_test_feedback(
    db: Session,
    interview_id: int,
    interviewer_id: str,
    recommendation: str,
    tech_score: int = 4,
    comm_score: int = 4,
    prob_score: int = 4,
    culture_score: int = 4
) -> InterviewFeedback:
    """Helper to create test interview feedback."""
    feedback = InterviewFeedback(
        interview_id=interview_id,
        interviewer_id=interviewer_id,
        technical_score=tech_score,
        communication_score=comm_score,
        problem_solving_score=prob_score,
        culture_fit_score=culture_score,
        recommendation=recommendation,
        submitted_at=datetime.utcnow()
    )
    db.add(feedback)
    db.commit()
    return feedback


# ────────────────────────────────────────────────────────────────────────────
# Test: get_interview_status
# ────────────────────────────────────────────────────────────────────────────

class TestGetInterviewStatus:
    """Tests for get_interview_status method."""

    def test_get_interview_status_success(self, test_db, service):
        """Test retrieving interview status successfully."""
        # Setup
        candidate = create_test_candidate(test_db, "C001")
        interviewer = create_test_user(test_db, "U001", "interviewer@test.com")
        interview = create_test_interview(test_db, 1, "C001")
        feedback = create_test_feedback(test_db, 1, "U001", "YES")

        # Execute
        result = service.get_interview_status(test_db, 1, 1)

        # Assert
        assert result is not None
        assert result["interview_id"] == 1
        assert result["candidate_id"] == "C001"
        assert result["status"] == "Completed"
        assert result["feedback_received"] == 1
        assert len(result["feedbacks"]) == 1
        assert result["feedbacks"][0]["interviewer_id"] == "U001"

    def test_get_interview_status_no_feedback(self, test_db, service):
        """Test retrieving interview status with no feedback."""
        # Setup
        candidate = create_test_candidate(test_db, "C002")
        interview = create_test_interview(test_db, 2, "C002")

        # Execute
        result = service.get_interview_status(test_db, 2, 1)

        # Assert
        assert result is not None
        assert result["feedback_received"] == 0
        assert len(result["feedbacks"]) == 0

    def test_get_interview_status_not_found(self, test_db, service):
        """Test retrieving non-existent interview."""
        # Execute
        result = service.get_interview_status(test_db, 999, 1)

        # Assert
        assert result is None

    def test_get_interview_status_multiple_feedback(self, test_db, service):
        """Test retrieving interview with multiple feedback entries."""
        # Setup
        candidate = create_test_candidate(test_db, "C003")
        interview = create_test_interview(test_db, 3, "C003")
        u1 = create_test_user(test_db, "U001", "u1@test.com")
        u2 = create_test_user(test_db, "U002", "u2@test.com")
        u3 = create_test_user(test_db, "U003", "u3@test.com")

        create_test_feedback(test_db, 3, "U001", "STRONG_YES", 5, 5, 5, 5)
        create_test_feedback(test_db, 3, "U002", "YES", 4, 4, 4, 4)
        create_test_feedback(test_db, 3, "U003", "YES", 4, 5, 4, 5)

        # Execute
        result = service.get_interview_status(test_db, 3, 1)

        # Assert
        assert result["feedback_received"] == 3
        assert len(result["feedbacks"]) == 3


# ────────────────────────────────────────────────────────────────────────────
# Test: calculate_panel_decision
# ────────────────────────────────────────────────────────────────────────────

class TestCalculatePanelDecision:
    """Tests for calculate_panel_decision method."""

    def test_panel_decision_all_strong_yes(self, test_db, service):
        """Test decision when all panelists vote STRONG_YES."""
        # Setup
        candidate = create_test_candidate(test_db, "C004")
        interview = create_test_interview(test_db, 4, "C004")
        create_test_user(test_db, "U001", "u1@test.com")
        create_test_user(test_db, "U002", "u2@test.com")
        create_test_user(test_db, "U003", "u3@test.com")

        create_test_feedback(test_db, 4, "U001", "STRONG_YES")
        create_test_feedback(test_db, 4, "U002", "STRONG_YES")
        create_test_feedback(test_db, 4, "U003", "STRONG_YES")

        # Execute
        result = service.calculate_panel_decision(test_db, 4, 1)

        # Assert
        assert result["decision"] == "APPROVED"
        assert result["voting"]["strong_yes"] == 3
        assert result["voting"]["total_panelists"] == 3

    def test_panel_decision_majority_yes(self, test_db, service):
        """Test decision when majority vote YES."""
        # Setup
        candidate = create_test_candidate(test_db, "C005")
        interview = create_test_interview(test_db, 5, "C005")
        create_test_user(test_db, "U001", "u1@test.com")
        create_test_user(test_db, "U002", "u2@test.com")
        create_test_user(test_db, "U003", "u3@test.com")

        create_test_feedback(test_db, 5, "U001", "STRONG_YES")
        create_test_feedback(test_db, 5, "U002", "YES")
        create_test_feedback(test_db, 5, "U003", "NO")

        # Execute
        result = service.calculate_panel_decision(test_db, 5, 1)

        # Assert
        assert result["decision"] == "APPROVED"
        assert result["voting"]["strong_yes"] == 1
        assert result["voting"]["yes"] == 1
        assert result["voting"]["no"] == 1
        assert result["voting"]["total_panelists"] == 3

    def test_panel_decision_all_no(self, test_db, service):
        """Test decision when all vote NO."""
        # Setup
        candidate = create_test_candidate(test_db, "C006")
        interview = create_test_interview(test_db, 6, "C006")
        create_test_user(test_db, "U001", "u1@test.com")
        create_test_user(test_db, "U002", "u2@test.com")

        create_test_feedback(test_db, 6, "U001", "NO")
        create_test_feedback(test_db, 6, "U002", "STRONG_NO")

        # Execute
        result = service.calculate_panel_decision(test_db, 6, 1)

        # Assert
        assert result["decision"] == "REJECTED"

    def test_panel_decision_no_feedback(self, test_db, service):
        """Test decision when no feedback exists."""
        # Setup
        candidate = create_test_candidate(test_db, "C007")
        interview = create_test_interview(test_db, 7, "C007")

        # Execute
        result = service.calculate_panel_decision(test_db, 7, 1)

        # Assert
        assert result["decision"] == "PENDING"
        assert result["voting"]["total_panelists"] == 0

    def test_panel_decision_tied_vote(self, test_db, service):
        """Test decision with tied votes."""
        # Setup
        candidate = create_test_candidate(test_db, "C008")
        interview = create_test_interview(test_db, 8, "C008")
        create_test_user(test_db, "U001", "u1@test.com")
        create_test_user(test_db, "U002", "u2@test.com")

        create_test_feedback(test_db, 8, "U001", "YES")
        create_test_feedback(test_db, 8, "U002", "NO")

        # Execute
        result = service.calculate_panel_decision(test_db, 8, 1)

        # Assert
        assert result["decision"] == "PENDING_REVIEW"

    def test_panel_decision_average_scores(self, test_db, service):
        """Test that average scores are calculated correctly."""
        # Setup
        candidate = create_test_candidate(test_db, "C009")
        interview = create_test_interview(test_db, 9, "C009")
        create_test_user(test_db, "U001", "u1@test.com")
        create_test_user(test_db, "U002", "u2@test.com")

        create_test_feedback(test_db, 9, "U001", "YES", 5, 5, 5, 5)
        create_test_feedback(test_db, 9, "U002", "YES", 3, 3, 3, 3)

        # Execute
        result = service.calculate_panel_decision(test_db, 9, 1)

        # Assert
        assert result["average_scores"]["technical"] == 4.0
        assert result["average_scores"]["communication"] == 4.0
        assert result["average_scores"]["problem_solving"] == 4.0
        assert result["average_scores"]["culture_fit"] == 4.0


# ────────────────────────────────────────────────────────────────────────────
# Test: move_to_offer
# ────────────────────────────────────────────────────────────────────────────

class TestMoveToOffer:
    """Tests for move_to_offer method."""

    def test_move_to_offer_success(self, test_db, service):
        """Test creating offer for approved interview."""
        # Setup
        candidate = create_test_candidate(test_db, "C010")
        job = create_test_job(test_db, "J001")
        recruiter = create_test_user(test_db, "R001", "recruiter@test.com")
        interview = create_test_interview(test_db, 10, "C010")
        create_test_user(test_db, "U001", "u1@test.com")
        create_test_user(test_db, "U002", "u2@test.com")
        create_test_user(test_db, "U003", "u3@test.com")

        # Make interview approved
        create_test_feedback(test_db, 10, "U001", "STRONG_YES")
        create_test_feedback(test_db, 10, "U002", "STRONG_YES")
        create_test_feedback(test_db, 10, "U003", "YES")

        # Execute
        result = service.move_to_offer(
            test_db,
            interview_id=10,
            candidate_id="C010",
            job_id="J001",
            tenant_id=1,
            approved_salary_usd_cents=10000000,
            position_title="Senior Software Engineer",
            start_date=datetime.utcnow() + timedelta(days=30),
            created_by_user_id="R001"
        )

        # Assert
        assert result["status"] == "success"
        assert result["offer_id"] is not None
        assert result["candidate_id"] == "C010"
        assert result["salary_usd_cents"] == 10000000

    def test_move_to_offer_interview_not_found(self, test_db, service):
        """Test offer creation for non-existent interview."""
        # Execute
        result = service.move_to_offer(
            test_db,
            interview_id=999,
            candidate_id="C999",
            job_id="J999",
            tenant_id=1,
            approved_salary_usd_cents=10000000,
            position_title="Position",
            start_date=datetime.utcnow() + timedelta(days=30),
            created_by_user_id="R001"
        )

        # Assert
        assert result["status"] == "error"
        assert "Interview not found" in result["message"]

    def test_move_to_offer_not_approved(self, test_db, service):
        """Test offer creation for rejected interview."""
        # Setup
        candidate = create_test_candidate(test_db, "C011")
        interview = create_test_interview(test_db, 11, "C011")
        create_test_user(test_db, "U001", "u1@test.com")
        create_test_user(test_db, "U002", "u2@test.com")

        # Make interview rejected
        create_test_feedback(test_db, 11, "U001", "NO")
        create_test_feedback(test_db, 11, "U002", "STRONG_NO")

        # Execute
        result = service.move_to_offer(
            test_db,
            interview_id=11,
            candidate_id="C011",
            job_id="J001",
            tenant_id=1,
            approved_salary_usd_cents=10000000,
            position_title="Position",
            start_date=datetime.utcnow() + timedelta(days=30),
            created_by_user_id="R001"
        )

        # Assert
        assert result["status"] == "error"
        assert "not approved for offer" in result["message"]


# ────────────────────────────────────────────────────────────────────────────
# Test: reject_candidate
# ────────────────────────────────────────────────────────────────────────────

class TestRejectCandidate:
    """Tests for reject_candidate method."""

    def test_reject_candidate_success(self, test_db, service):
        """Test successfully rejecting a candidate."""
        # Setup
        candidate = create_test_candidate(test_db, "C012")
        interview = create_test_interview(test_db, 12, "C012")
        recruiter = create_test_user(test_db, "R001", "recruiter@test.com")

        # Execute
        result = service.reject_candidate(
            test_db,
            interview_id=12,
            tenant_id=1,
            rejection_reason="Did not meet technical requirements",
            rejected_by_user_id="R001"
        )

        # Assert
        assert result["status"] == "success"
        assert result["interview_id"] == 12
        assert result["candidate_id"] == "C012"
        assert result["rejection_reason"] == "Did not meet technical requirements"

    def test_reject_candidate_interview_not_found(self, test_db, service):
        """Test rejecting a candidate for non-existent interview."""
        # Execute
        result = service.reject_candidate(
            test_db,
            interview_id=999,
            tenant_id=1,
            rejection_reason="Interview not found",
            rejected_by_user_id="R001"
        )

        # Assert
        assert result["status"] == "error"
        assert "Interview not found" in result["message"]

    def test_reject_candidate_updates_interview_status(self, test_db, service):
        """Test that rejection updates interview status."""
        # Setup
        candidate = create_test_candidate(test_db, "C013")
        interview = create_test_interview(test_db, 13, "C013")
        recruiter = create_test_user(test_db, "R001", "recruiter@test.com")

        # Execute
        result = service.reject_candidate(
            test_db,
            interview_id=13,
            tenant_id=1,
            rejection_reason="Test rejection",
            rejected_by_user_id="R001"
        )

        # Verify
        updated_interview = test_db.query(Interview).filter(
            Interview.id == 13
        ).first()

        assert result["status"] == "success"
        assert updated_interview.status == "REJECTED"


# ────────────────────────────────────────────────────────────────────────────
# Integration Tests
# ────────────────────────────────────────────────────────────────────────────

class TestIntegrationWorkflow:
    """Integration tests for complete interview decision workflow."""

    def test_full_workflow_approval_and_offer(self, test_db, service):
        """Test complete workflow: interview → feedback → decision → offer."""
        # Setup
        candidate = create_test_candidate(test_db, "C014")
        job = create_test_job(test_db, "J001")
        recruiter = create_test_user(test_db, "R001", "recruiter@test.com")
        interview = create_test_interview(test_db, 14, "C014")
        create_test_user(test_db, "U001", "u1@test.com")
        create_test_user(test_db, "U002", "u2@test.com")

        # Step 1: Collect feedback
        create_test_feedback(test_db, 14, "U001", "STRONG_YES", 5, 5, 5, 5)
        create_test_feedback(test_db, 14, "U002", "YES", 4, 4, 4, 4)

        # Step 2: Check interview status
        status = service.get_interview_status(test_db, 14, 1)
        assert status["feedback_received"] == 2

        # Step 3: Calculate decision
        decision = service.calculate_panel_decision(test_db, 14, 1)
        assert decision["decision"] == "APPROVED"

        # Step 4: Move to offer
        offer = service.move_to_offer(
            test_db,
            interview_id=14,
            candidate_id="C014",
            job_id="J001",
            tenant_id=1,
            approved_salary_usd_cents=12000000,
            position_title="Senior Engineer",
            start_date=datetime.utcnow() + timedelta(days=30),
            created_by_user_id="R001"
        )
        assert offer["status"] == "success"

    def test_full_workflow_rejection(self, test_db, service):
        """Test complete workflow: interview → feedback → decision → rejection."""
        # Setup
        candidate = create_test_candidate(test_db, "C015")
        job = create_test_job(test_db, "J001")
        recruiter = create_test_user(test_db, "R001", "recruiter@test.com")
        interview = create_test_interview(test_db, 15, "C015")
        create_test_user(test_db, "U001", "u1@test.com")
        create_test_user(test_db, "U002", "u2@test.com")

        # Step 1: Collect feedback
        create_test_feedback(test_db, 15, "U001", "NO")
        create_test_feedback(test_db, 15, "U002", "STRONG_NO")

        # Step 2: Calculate decision
        decision = service.calculate_panel_decision(test_db, 15, 1)
        assert decision["decision"] == "REJECTED"

        # Step 3: Reject candidate
        result = service.reject_candidate(
            test_db,
            interview_id=15,
            tenant_id=1,
            rejection_reason="Did not meet requirements",
            rejected_by_user_id="R001"
        )
        assert result["status"] == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
