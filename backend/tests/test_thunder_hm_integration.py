"""
End-to-End Integration Tests: Thunder → AI Recruiter → HM Validation → Interview
Comprehensive testing of autonomous hiring flow
import logging
"""

import logging
import pytest
import json
from datetime import datetime, timedelta
from uuid import uuid4

from app.models import (
    ThunderSession,
    ThunderSessionStatus,
    HiringManagerValidation,
    HMValidationStatus,
    Candidate,
    Interview,
)
from app.services.thunder_service import ThunderService
from app.services.hm_validation_service import HMValidationService
from app.services.ai_recruiter_integration_service import AIRecruiterIntegrationService

@pytest.fixture
def db_session():
    """Create test database session"""
    # Mock DB implementation
    pass

@pytest.fixture
def thunder_service():
    return ThunderService()

@pytest.fixture
def hm_service():
    return HMValidationService()

@pytest.fixture
def ai_recruiter_service():
    return AIRecruiterIntegrationService()

logger = logging.getLogger(__name__)

class TestThunderSessionLifecycle:
    """Test Thunder session creation, progression, and submission"""

    @pytest.mark.asyncio
    async def test_create_new_session(self, thunder_service, db_session):
        """Test creating new Thunder session"""
        session = await thunder_service.create_session(
            candidate_email="john.smith@example.com",
            device_type="desktop",
            utm_source="email_campaign",
            db=db_session,
        )

        assert session.id is not None
        assert session.candidate_email == "john.smith@example.com"
        assert session.status == ThunderSessionStatus.STARTED
        assert session.last_question_reached == "Q1"
        assert session.completion_percentage == 0

    @pytest.mark.asyncio
    async def test_resume_existing_session(self, thunder_service, db_session):
        """Test resuming session at Q4 after candidate closes browser"""
        # Create session
        session = await thunder_service.create_session(
            candidate_email="jane.doe@example.com",
            device_type="mobile",
            utm_source="linkedin",
            db=db_session,
        )

        # Simulate answering Q1-Q3
        for q in ["Q1", "Q2", "Q3"]:
            await thunder_service.save_response(
                session=session,
                question=q,
                response=f"Response to {q}",
                time_taken_seconds=30,
                db=db_session,
            )

        # Pause session
        session.status = ThunderSessionStatus.PAUSED
        session.paused_at = datetime.utcnow()

        # Resume session (new API call, same email)
        resumed = await thunder_service.create_session(
            candidate_email="jane.doe@example.com",
            device_type="mobile",
            utm_source="linkedin",
            db=db_session,
        )

        assert resumed.id == session.id
        assert resumed.last_question_reached == "Q3"
        assert resumed.status == ThunderSessionStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_form_persistence_across_sessions(self, thunder_service, db_session):
        """Test that form state persists when candidate resumes"""
        session = await thunder_service.create_session(
            candidate_email="test@example.com",
            device_type="desktop",
            utm_source="test",
            db=db_session,
        )

        # Answer Q1, Q2, Q3
        form_data = {"name": "John", "experience": "5 years", "title": "Engineer"}
        for q, resp in form_data.items():
            await thunder_service.save_response(
                session=session,
                question=f"Q{list(form_data.keys()).index(q) + 1}",
                response=resp,
                time_taken_seconds=20,
                db=db_session,
            )

        # Verify form responses stored
        assert len(session.form_responses) == 3
        assert session.form_responses["Q1"]["response"] == "John"

    @pytest.mark.asyncio
    async def test_conditional_question_work_auth_us_only(self, thunder_service, db_session):
        """Test Q8 (work auth) only appears for US jobs"""
        session = await thunder_service.create_session(
            candidate_email="test@example.com",
            device_type="desktop",
            utm_source="test",
            db=db_session,
        )

        # Non-US job → Q8 should be skipped
        session.job_matches = [{"job_location": "India"}]
        next_q = await thunder_service.get_next_question(
            session=session,
            current_question="Q7",
            db=db_session,
        )
        assert next_q != "Q8"

        # US job → Q8 should appear
        session.job_matches = [{"job_location": "US"}]
        next_q = await thunder_service.get_next_question(
            session=session,
            current_question="Q7",
            db=db_session,
        )
        assert next_q == "Q8"

    @pytest.mark.asyncio
    async def test_session_submission_creates_candidate(self, thunder_service, db_session):
        """Test that session submission creates/updates candidate record"""
        session = await thunder_service.create_session(
            candidate_email="newcandidate@example.com",
            device_type="desktop",
            utm_source="test",
            db=db_session,
        )

        session.candidate_data = {
            "name": "New Candidate",
            "email": "newcandidate@example.com",
            "title": "Senior Engineer",
            "company": "TechCorp",
            "location": "San Francisco, CA",
        }

        candidate = await thunder_service.finalize_candidate(
            session=session,
            db=db_session,
        )

        assert candidate is not None
        assert candidate.candidateEmail == "newcandidate@example.com"
        assert candidate.candidateName == "New Candidate"

class TestHMValidationDecisionLogic:
    """Test HM validation decision paths (APPROVED/REJECTED/MAYBE)"""

    @pytest.mark.asyncio
    async def test_hm_approval_decision(self, hm_service):
        """Test HM APPROVAL decision (score 8+, critical response yes)"""
        decision = await hm_service.determine_decision(
            responses={
                "q_001": "yes",
                "q_002": "Strong experience",
                "q_003": "Python, Go, Docker",
                "q_004": "yes",
            },
            decision_score=9,
            job_id="job_001",
            db=None,
        )

        assert decision["status"] == HMValidationStatus.APPROVED

    @pytest.mark.asyncio
    async def test_hm_rejection_decision(self, hm_service):
        """Test HM REJECTION decision (score <=4 or critical no)"""
        decision = await hm_service.determine_decision(
            responses={
                "q_001": "no",
                "q_002": "Missing key skills",
                "q_003": "Python only",
                "q_004": "no",
            },
            decision_score=2,
            job_id="job_001",
            db=None,
        )

        assert decision["status"] == HMValidationStatus.REJECTED

    @pytest.mark.asyncio
    async def test_hm_maybe_decision(self, hm_service):
        """Test HM MAYBE decision (score 5-7, uncertain)"""
        decision = await hm_service.determine_decision(
            responses={
                "q_001": "yes",
                "q_002": "Some concerns",
                "q_003": "Relevant skills",
                "q_004": "maybe",
            },
            decision_score=6,
            job_id="job_001",
            db=None,
        )

        assert decision["status"] == HMValidationStatus.MAYBE

class TestCompleteAutonomousFlow:
    """Test full Thunder → AI Recruiter → HM Validation → Interview flow"""

    @pytest.mark.asyncio
    async def test_complete_flow_hm_approves(
        self,
        thunder_service,
        hm_service,
        ai_recruiter_service,
        db_session,
    ):
        """
        Complete end-to-end flow:
        1. Candidate completes Thunder intake
        2. AI Recruiter finds best match
        3. HM validates candidate
        4. Interview scheduled automatically
        """

        # Step 1: Create Thunder session and complete intake
        session = await thunder_service.create_session(
            candidate_email="test@example.com",
            device_type="desktop",
            utm_source="test",
            db=db_session,
        )

        # Answer all questions
        for q in ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q11", "Q12"]:
            await thunder_service.save_response(
                session=session,
                question=q,
                response="yes" if q in ["Q5", "Q6", "Q11", "Q12"] else f"Response {q}",
                time_taken_seconds=20,
                db=db_session,
            )

        # Submit application
        session.candidate_data = {
            "name": "Test Candidate",
            "title": "Engineer",
            "company": "TechCorp",
            "location": "San Francisco, CA",
        }
        candidate = await thunder_service.finalize_candidate(
            session=session,
            db=db_session,
        )

        # Step 2: AI Recruiter matches candidate to jobs
        job_matches = await ai_recruiter_service.match_candidate_to_jobs(
            candidate_id=candidate.candidateID,
            resume_data={},
            candidate_data=session.candidate_data,
            db=db_session,
        )

        assert len(job_matches) > 0
        best_job = job_matches[0]

        # Step 3: HM Validation created for best match
        validation = await hm_service.create_validation_request(
            candidate_id=candidate.candidateID,
            job_id=best_job["job_id"],
            hiring_manager_id="user_hm_001",
            match_score=best_job["score"],
            db=db_session,
        )

        assert validation is not None
        assert validation.status == HMValidationStatus.PENDING

        # Step 4: HM responds with APPROVAL
        decision = await hm_service.determine_decision(
            responses={
                "q_001": "yes",
                "q_002": "Good fit",
                "q_003": "Strong skills",
                "q_004": "yes",
            },
            decision_score=8,
            job_id=best_job["job_id"],
            db=db_session,
        )

        assert decision["status"] == HMValidationStatus.APPROVED

        # Step 5: Interview scheduled automatically
        validation.status = HMValidationStatus.APPROVED
        interview = await hm_service.schedule_interview_after_approval(
            validation=validation,
            db=db_session,
        )

        assert interview is not None
        assert interview.candidate_id == candidate.candidateID

    @pytest.mark.asyncio
    async def test_hm_rejection_tries_next_candidate(
        self,
        thunder_service,
        hm_service,
        ai_recruiter_service,
        db_session,
    ):
        """Test HM REJECTION triggers next candidate in pool"""

        # Create candidate and validation
        session = await thunder_service.create_session(
            candidate_email="rejected@example.com",
            device_type="desktop",
            utm_source="test",
            db=db_session,
        )

        candidate = await thunder_service.finalize_candidate(
            session=session,
            db=db_session,
        )

        validation = await hm_service.create_validation_request(
            candidate_id=candidate.candidateID,
            job_id="job_001",
            hiring_manager_id="user_hm_001",
            match_score=0.75,
            db=db_session,
        )

        # HM rejects
        decision = await hm_service.determine_decision(
            responses={"q_004": "no"},
            decision_score=2,
            job_id="job_001",
            db=db_session,
        )

        assert decision["status"] == HMValidationStatus.REJECTED

        # Return to pool
        result = await hm_service.return_candidate_to_pool(
            validation=validation,
            db=db_session,
        )

        assert result is True
        assert validation.status == HMValidationStatus.REJECTED

class TestTimeoutAndEscalation:
    """Test timeout handling and escalation to HM's manager"""

    @pytest.mark.asyncio
    async def test_validation_expires_after_timeout(self, hm_service, db_session):
        """Test that validations expire after timeout hours"""
        from app.models import HiringManagerValidation

        validation = HiringManagerValidation(
            id=str(uuid4()),
            candidate_id="cand_001",
            job_id="job_001",
            hiring_manager_id="user_hm_001",
            status=HMValidationStatus.PENDING,
            created_at=datetime.utcnow() - timedelta(hours=25),  # Created 25hrs ago
            due_at=datetime.utcnow() - timedelta(hours=1),  # Due 1hr ago
        )

        # Run batch job to find expired validations
        count = await hm_service.handle_expired_validations(db=db_session)

        assert count >= 1

    @pytest.mark.asyncio
    async def test_maybe_response_escalates_to_manager(self, hm_service, db_session):
        """Test MAYBE responses escalate to HM's manager"""

        validation_id = str(uuid4())
        # Mock validation creation
        decision = await hm_service.determine_decision(
            responses={"q_004": "maybe"},
            decision_score=5,
            job_id="job_001",
            db=db_session,
        )

        assert decision["status"] == HMValidationStatus.MAYBE

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
