"""
Tests for Hiring Manager Validation Service (HRMS-1104 / S-319)
Tests for create_validation_questions, send_to_hm, record_hm_response
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch

from sqlalchemy.orm import Session
from app.models import (
    HiringManagerValidation,
    HMValidationResponse,
    HMValidationStatus,
    Demand,
    Candidate,
    Users,
)
from app.services.hiring_manager_validation_service import HiringManagerValidationService

@pytest.fixture
def hm_service():
    """Create service instance for testing"""
    return HiringManagerValidationService()

@pytest.fixture
def mock_db():
    """Create mock database session"""
    return Mock(spec=Session)

@pytest.fixture
def sample_job():
    """Create sample job/demand for testing"""
    return Demand(
        id=str(uuid4()),
        tenant_id=1,
        hm_validation_required=False,
        hm_validation_questions=None,
        hm_validation_timeout_hours=24,
        auto_schedule_after_approval=True
    )

@pytest.fixture
def sample_candidate():
    """Create sample candidate for testing"""
    return Candidate(
        candidateID=str(uuid4()),
        tenant_id=1,
        candidateName="John Doe",
        email="john@example.com",
        phone="+1234567890"
    )

@pytest.fixture
def sample_hiring_manager():
    """Create sample hiring manager user"""
    return Users(
        UserID=str(uuid4()),
        user_email="manager@example.com",
        user_name="Manager Name"
    )

class TestCreateValidationQuestions:
    """Tests for create_validation_questions method"""

    def test_create_validation_questions_success(self, hm_service, mock_db, sample_job):
        """Test successful creation of validation questions"""
        # Setup
        questions = [
            {
                "question_id": "q_001",
                "question_text": "Does candidate experience match requirements?",
                "question_type": "yes_no",
                "required": True
            },
            {
                "question_id": "q_002",
                "question_text": "Any red flags?",
                "question_type": "text",
                "required": False
            },
            {
                "question_id": "q_004",
                "question_text": "Should we move forward?",
                "question_type": "yes_no_maybe",
                "required": True,
                "determine_flow": True
            }

        mock_db.query.return_value.filter.return_value.first.return_value = sample_job

        # Execute
        result = hm_service.create_validation_questions(
            db=mock_db,
            job_id=sample_job.id,
            tenant_id=1,
            questions=questions,
            timeout_hours=24,
            auto_schedule=True
        )

        # Assert
        assert result["status"] == "success"
        assert result["job_id"] == sample_job.id
        assert result["question_count"] == 3
        assert len(result["question_ids"]) == 3
        assert result["timeout_hours"] == 24
        assert result["auto_schedule_after_approval"] is True
        assert "created_at" in result

    def test_create_validation_questions_job_not_found(self, hm_service, mock_db):
        """Test error when job not found"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        questions = [{"question_id": "q_001", "question_text": "Test question"}]

        with pytest.raises(ValueError, match="Job .* not found"):
            hm_service.create_validation_questions(
                db=mock_db,
                job_id="nonexistent",
                tenant_id=1,
                questions=questions
            )

    def test_create_validation_questions_no_questions(self, hm_service, mock_db, sample_job):
        """Test error when no questions provided"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_job

        with pytest.raises(ValueError, match="At least one question is required"):
            hm_service.create_validation_questions(
                db=mock_db,
                job_id=sample_job.id,
                tenant_id=1,
                questions=[]
            )

    def test_create_validation_questions_too_many_questions(self, hm_service, mock_db, sample_job):
        """Test error when more than 10 questions"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_job

        questions = [
            {"question_id": f"q_{i:03d}", "question_text": f"Question {i}"}
            for i in range(11)

        with pytest.raises(ValueError, match="Maximum 10 questions allowed"):
            hm_service.create_validation_questions(
                db=mock_db,
                job_id=sample_job.id,
                tenant_id=1,
                questions=questions
            )

    def test_create_validation_questions_missing_required_fields(self, hm_service, mock_db, sample_job):
        """Test error when question missing required fields"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_job

        # Missing question_text
        questions = [{"question_id": "q_001"}]

        with pytest.raises(ValueError, match="Each question must have"):
            hm_service.create_validation_questions(
                db=mock_db,
                job_id=sample_job.id,
                tenant_id=1,
                questions=questions
            )

    def test_create_validation_questions_with_custom_timeout(self, hm_service, mock_db, sample_job):
        """Test creating questions with custom timeout"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_job

        questions = [{"question_id": "q_001", "question_text": "Test question"}]

        result = hm_service.create_validation_questions(
            db=mock_db,
            job_id=sample_job.id,
            tenant_id=1,
            questions=questions,
            timeout_hours=48
        )

        assert result["timeout_hours"] == 48

    def test_create_validation_questions_disables_auto_schedule(self, hm_service, mock_db, sample_job):
        """Test creating questions with auto_schedule disabled"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_job

        questions = [{"question_id": "q_001", "question_text": "Test question"}]

        result = hm_service.create_validation_questions(
            db=mock_db,
            job_id=sample_job.id,
            tenant_id=1,
            questions=questions,
            auto_schedule=False
        )

        assert result["auto_schedule_after_approval"] is False

class TestSendToHM:
    """Tests for send_to_hm method"""

    def test_send_to_hm_success(self, hm_service, mock_db, sample_job, sample_candidate, sample_hiring_manager):
        """Test successful sending of validation to HM"""
        # Setup query to return different models
        query_mock = Mock()
        query_mock.filter.return_value.first.side_effect = [
            sample_job,  # First call for job
            sample_candidate,  # Second call for candidate
            sample_hiring_manager,  # Third call for HM
            None  # Fourth call for existing validation
        mock_db.query.return_value = query_mock

        # Execute
        result = hm_service.send_to_hm(
            db=mock_db,
            job_id=sample_job.id,
            candidate_id=sample_candidate.candidateID,
            hiring_manager_id=sample_hiring_manager.UserID,
            tenant_id=1
        )

        # Assert
        assert result["status"] == "success"
        assert "validation_id" in result
        assert result["job_id"] == sample_job.id
        assert result["candidate_id"] == sample_candidate.candidateID
        assert result["sent_to"] == sample_hiring_manager.user_email
        assert result["expires_in_hours"] == 24
        assert "dashboard_link" in result

    def test_send_to_hm_job_not_found(self, hm_service, mock_db):
        """Test error when job not found"""
        query_mock = Mock()
        query_mock.filter.return_value.first.return_value = None
        mock_db.query.return_value = query_mock

        with pytest.raises(ValueError, match="Job .* not found"):
            hm_service.send_to_hm(
                db=mock_db,
                job_id="nonexistent",
                candidate_id="candidate_id",
                hiring_manager_id="hm_id",
                tenant_id=1
            )

    def test_send_to_hm_job_no_questions(self, hm_service, mock_db, sample_job):
        """Test error when job has no validation questions configured"""
        sample_job.hm_validation_required = False
        sample_job.hm_validation_questions = None

        query_mock = Mock()
        query_mock.filter.return_value.first.return_value = sample_job
        mock_db.query.return_value = query_mock

        with pytest.raises(ValueError, match="does not have validation questions"):
            hm_service.send_to_hm(
                db=mock_db,
                job_id=sample_job.id,
                candidate_id="candidate_id",
                hiring_manager_id="hm_id",
                tenant_id=1
            )

    def test_send_to_hm_candidate_not_found(self, hm_service, mock_db, sample_job):
        """Test error when candidate not found"""
        sample_job.hm_validation_required = True
        sample_job.hm_validation_questions = [{"question_id": "q_001"}]

        query_mock = Mock()
        query_mock.filter.return_value.first.side_effect = [
            sample_job,  # Job found
            None  # Candidate not found
        mock_db.query.return_value = query_mock

        with pytest.raises(ValueError, match="Candidate .* not found"):
            hm_service.send_to_hm(
                db=mock_db,
                job_id=sample_job.id,
                candidate_id="nonexistent",
                hiring_manager_id="hm_id",
                tenant_id=1
            )

    def test_send_to_hm_hm_not_found(self, hm_service, mock_db, sample_job, sample_candidate):
        """Test error when hiring manager not found"""
        sample_job.hm_validation_required = True
        sample_job.hm_validation_questions = [{"question_id": "q_001"}]

        query_mock = Mock()
        query_mock.filter.return_value.first.side_effect = [
            sample_job,  # Job found
            sample_candidate,  # Candidate found
            None  # HM not found
        mock_db.query.return_value = query_mock

        with pytest.raises(ValueError, match="Hiring manager .* not found"):
            hm_service.send_to_hm(
                db=mock_db,
                job_id=sample_job.id,
                candidate_id=sample_candidate.candidateID,
                hiring_manager_id="nonexistent",
                tenant_id=1
            )

    def test_send_to_hm_validation_already_exists(self, hm_service, mock_db, sample_job, sample_candidate, sample_hiring_manager):
        """Test when validation already exists for candidate/job"""
        sample_job.hm_validation_required = True
        sample_job.hm_validation_questions = [{"question_id": "q_001"}]

        existing_validation = HiringManagerValidation(
            id="existing_validation_id",
            candidate_id=sample_candidate.candidateID,
            job_id=sample_job.id,
            status=HMValidationStatus.PENDING,
            email_sent_at=datetime.utcnow()
        )

        query_mock = Mock()
        query_mock.filter.return_value.first.side_effect = [
            sample_job,  # Job found
            sample_candidate,  # Candidate found
            sample_hiring_manager,  # HM found
            existing_validation  # Existing validation found
        mock_db.query.return_value = query_mock

        result = hm_service.send_to_hm(
            db=mock_db,
            job_id=sample_job.id,
            candidate_id=sample_candidate.candidateID,
            hiring_manager_id=sample_hiring_manager.UserID,
            tenant_id=1
        )

        assert result["status"] == "already_exists"
        assert result["validation_id"] == "existing_validation_id"

class TestRecordHMResponse:
    """Tests for record_hm_response method"""

    def test_record_hm_response_approved(self, hm_service, mock_db):
        """Test recording HM response with approval"""
        validation_id = str(uuid4())
        validation = HiringManagerValidation(
            id=validation_id,
            status=HMValidationStatus.PENDING,
            created_at=datetime.utcnow()
        )

        query_mock = Mock()
        query_mock.filter.return_value.first.return_value = validation
        mock_db.query.return_value = query_mock

        responses = {
            "q_001": "yes",
            "q_002": "No red flags",
            "q_004": "yes"
        }

        result = hm_service.record_hm_response(
            db=mock_db,
            validation_id=validation_id,
            tenant_id=1,
            responses=responses,
            decision_comment="Excellent candidate",
            decision_score=9
        )

        assert result["status"] == "success"
        assert result["validation_id"] == validation_id
        assert result["decision"] == "APPROVED"
        assert result["next_step"] == "schedule_interview"
        assert result["decision_score"] == 9
        assert result["response_time_hours"] >= 0

    def test_record_hm_response_rejected(self, hm_service, mock_db):
        """Test recording HM response with rejection"""
        validation_id = str(uuid4())
        validation = HiringManagerValidation(
            id=validation_id,
            status=HMValidationStatus.PENDING,
            created_at=datetime.utcnow()
        )

        query_mock = Mock()
        query_mock.filter.return_value.first.return_value = validation
        mock_db.query.return_value = query_mock

        responses = {
            "q_001": "no",
            "q_002": "Experience gap",
            "q_004": "no"
        }

        result = hm_service.record_hm_response(
            db=mock_db,
            validation_id=validation_id,
            tenant_id=1,
            responses=responses,
            decision_comment="Not ready",
            decision_score=3
        )

        assert result["status"] == "success"
        assert result["decision"] == "REJECTED"
        assert result["next_step"] == "return_to_pool"

    def test_record_hm_response_maybe(self, hm_service, mock_db):
        """Test recording HM response with maybe/uncertain"""
        validation_id = str(uuid4())
        validation = HiringManagerValidation(
            id=validation_id,
            status=HMValidationStatus.PENDING,
            created_at=datetime.utcnow()
        )

        query_mock = Mock()
        query_mock.filter.return_value.first.return_value = validation
        mock_db.query.return_value = query_mock

        responses = {
            "q_001": "maybe",
            "q_002": "Some concerns",
            "q_004": "maybe"
        }

        result = hm_service.record_hm_response(
            db=mock_db,
            validation_id=validation_id,
            tenant_id=1,
            responses=responses,
            decision_comment="Needs discussion",
            decision_score=5
        )

        assert result["status"] == "success"
        assert result["decision"] == "MAYBE"
        assert result["next_step"] == "escalate_for_review"

    def test_record_hm_response_validation_not_found(self, hm_service, mock_db):
        """Test error when validation not found"""
        query_mock = Mock()
        query_mock.filter.return_value.first.return_value = None
        mock_db.query.return_value = query_mock

        with pytest.raises(ValueError, match="not found"):
            hm_service.record_hm_response(
                db=mock_db,
                validation_id="nonexistent",
                tenant_id=1,
                responses={"q_001": "yes"}
            )

    def test_record_hm_response_already_responded(self, hm_service, mock_db):
        """Test error when validation already responded"""
        validation = HiringManagerValidation(
            id="validation_id",
            status=HMValidationStatus.APPROVED,  # Already responded
            created_at=datetime.utcnow()
        )

        query_mock = Mock()
        query_mock.filter.return_value.first.return_value = validation
        mock_db.query.return_value = query_mock

        with pytest.raises(ValueError, match="already responded"):
            hm_service.record_hm_response(
                db=mock_db,
                validation_id="validation_id",
                tenant_id=1,
                responses={"q_001": "yes"}
            )

    def test_record_hm_response_no_responses(self, hm_service, mock_db):
        """Test error when no responses provided"""
        validation = HiringManagerValidation(
            id="validation_id",
            status=HMValidationStatus.PENDING,
            created_at=datetime.utcnow()
        )

        query_mock = Mock()
        query_mock.filter.return_value.first.return_value = validation
        mock_db.query.return_value = query_mock

        with pytest.raises(ValueError, match="At least one response is required"):
            hm_service.record_hm_response(
                db=mock_db,
                validation_id="validation_id",
                tenant_id=1,
                responses={}
            )

    def test_record_hm_response_response_time_calculation(self, hm_service, mock_db):
        """Test response time calculation"""
        created_at = datetime.utcnow() - timedelta(hours=2)
        validation = HiringManagerValidation(
            id="validation_id",
            status=HMValidationStatus.PENDING,
            created_at=created_at
        )

        query_mock = Mock()
        query_mock.filter.return_value.first.return_value = validation
        mock_db.query.return_value = query_mock

        responses = {"q_001": "yes", "q_004": "yes"}

        result = hm_service.record_hm_response(
            db=mock_db,
            validation_id="validation_id",
            tenant_id=1,
            responses=responses
        )

        assert result["response_time_hours"] >= 2

class TestDetermineDecision:
    """Tests for decision determination logic"""

    def test_determine_decision_from_q4_yes(self, hm_service):
        """Test decision logic with q_004 = yes"""
        result = hm_service.determine_decision(
            responses={"q_001": "yes", "q_004": "yes"},
            decision_score=None,
            job_id="job_id",
            db=None
        )

        assert result["status"] == HMValidationStatus.APPROVED
        assert result["next_step"] == "schedule_interview"

    def test_determine_decision_from_q4_no(self, hm_service):
        """Test decision logic with q_004 = no"""
        result = hm_service.determine_decision(
            responses={"q_001": "yes", "q_004": "no"},
            decision_score=None,
            job_id="job_id",
            db=None
        )

        assert result["status"] == HMValidationStatus.REJECTED
        assert result["next_step"] == "return_to_pool"

    def test_determine_decision_from_q4_maybe(self, hm_service):
        """Test decision logic with q_004 = maybe"""
        result = hm_service.determine_decision(
            responses={"q_001": "yes", "q_004": "maybe"},
            decision_score=None,
            job_id="job_id",
            db=None
        )

        assert result["status"] == HMValidationStatus.MAYBE
        assert result["next_step"] == "escalate_for_review"

    def test_determine_decision_from_score_high(self, hm_service):
        """Test decision logic with high score"""
        result = hm_service.determine_decision(
            responses={"q_001": "yes"},
            decision_score=9,
            job_id="job_id",
            db=None
        )

        assert result["status"] == HMValidationStatus.APPROVED
        assert result["next_step"] == "schedule_interview"

    def test_determine_decision_from_score_low(self, hm_service):
        """Test decision logic with low score"""
        result = hm_service.determine_decision(
            responses={"q_001": "yes"},
            decision_score=2,
            job_id="job_id",
            db=None
        )

        assert result["status"] == HMValidationStatus.REJECTED
        assert result["next_step"] == "return_to_pool"

    def test_determine_decision_from_score_medium(self, hm_service):
        """Test decision logic with medium score"""
        result = hm_service.determine_decision(
            responses={"q_001": "yes"},
            decision_score=5,
            job_id="job_id",
            db=None
        )

        assert result["status"] == HMValidationStatus.MAYBE
        assert result["next_step"] == "escalate_for_review"

    def test_determine_decision_defaults_to_escalation(self, hm_service):
        """Test that unclear decisions default to escalation"""
        result = hm_service.determine_decision(
            responses={"q_001": "yes"},
            decision_score=None,
            job_id="job_id",
            db=None
        )

        assert result["status"] == HMValidationStatus.MAYBE
        assert result["next_step"] == "escalate_for_review"

class TestIntegrationScenarios:
    """Integration tests for complete workflows"""

    def test_complete_validation_workflow_approved(self, hm_service, mock_db, sample_job, sample_candidate, sample_hiring_manager):
        """Test complete workflow: create questions -> send to HM -> record approval"""
        # Step 1: Create questions
        questions = [
            {"question_id": "q_001", "question_text": "Experience match?"},
            {"question_id": "q_004", "question_text": "Move forward?", "determine_flow": True}

        query_mock = Mock()
        query_mock.filter.return_value.first.return_value = sample_job
        mock_db.query.return_value = query_mock

        create_result = hm_service.create_validation_questions(
            db=mock_db,
            job_id=sample_job.id,
            tenant_id=1,
            questions=questions
        )

        assert create_result["status"] == "success"
        assert create_result["question_count"] == 2

        # Step 2: Send to HM (reset mocks)
        sample_job.hm_validation_required = True
        sample_job.hm_validation_questions = questions

        query_mock.filter.return_value.first.side_effect = [
            sample_job,
            sample_candidate,
            sample_hiring_manager,
            None

        send_result = hm_service.send_to_hm(
            db=mock_db,
            job_id=sample_job.id,
            candidate_id=sample_candidate.candidateID,
            hiring_manager_id=sample_hiring_manager.UserID,
            tenant_id=1
        )

        assert send_result["status"] == "success"
        validation_id = send_result["validation_id"]

        # Step 3: Record approval response
        validation = HiringManagerValidation(
            id=validation_id,
            status=HMValidationStatus.PENDING,
            created_at=datetime.utcnow()
        )

        query_mock.filter.return_value.first.return_value = validation

        record_result = hm_service.record_hm_response(
            db=mock_db,
            validation_id=validation_id,
            tenant_id=1,
            responses={"q_001": "yes", "q_004": "yes"},
            decision_score=9
        )

        assert record_result["status"] == "success"
        assert record_result["decision"] == "APPROVED"
        assert record_result["next_step"] == "schedule_interview"
