"""
Unit Tests for Hiring Manager Validation Service (HRMS-1104 / S-319)
Focused on business logic without database setup
import logging
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, MagicMock, patch

from app.services.hiring_manager_validation_service import HiringManagerValidationService


@pytest.fixture
def service():
    """Create service instance"""
    return HiringManagerValidationService()

logger = logging.getLogger(__name__)

class TestDetermineDecision:
    """Test decision determination logic (most important business logic)"""

    def test_decision_from_q4_yes(self, service):
        """Test: q_004=yes → APPROVED → schedule_interview"""
        result = service.determine_decision(
            responses={"q_001": "yes", "q_004": "yes"},
            decision_score=None,
            job_id="job_1",
            db=None
        )
        assert result["status"].value == "APPROVED"
        assert result["next_step"] == "schedule_interview"

    def test_decision_from_q4_no(self, service):
        """Test: q_004=no → REJECTED → return_to_pool"""
        result = service.determine_decision(
            responses={"q_004": "no"},
            decision_score=None,
            job_id="job_1",
            db=None
        )
        assert result["status"].value == "REJECTED"
        assert result["next_step"] == "return_to_pool"

    def test_decision_from_q4_maybe(self, service):
        """Test: q_004=maybe → MAYBE → escalate_for_review"""
        result = service.determine_decision(
            responses={"q_004": "maybe"},
            decision_score=None,
            job_id="job_1",
            db=None
        )
        assert result["status"].value == "MAYBE"
        assert result["next_step"] == "escalate_for_review"

    def test_decision_from_high_score_9(self, service):
        """Test: score=9 → APPROVED"""
        result = service.determine_decision(
            responses={"q_001": "yes"},
            decision_score=9,
            job_id="job_1",
            db=None
        )
        assert result["status"].value == "APPROVED"

    def test_decision_from_high_score_8(self, service):
        """Test: score=8 (boundary) → APPROVED"""
        result = service.determine_decision(
            responses={},
            decision_score=8,
            job_id="job_1",
            db=None
        )
        assert result["status"].value == "APPROVED"

    def test_decision_from_low_score_2(self, service):
        """Test: score=2 → REJECTED"""
        result = service.determine_decision(
            responses={},
            decision_score=2,
            job_id="job_1",
            db=None
        )
        assert result["status"].value == "REJECTED"

    def test_decision_from_low_score_4(self, service):
        """Test: score=4 (boundary) → REJECTED"""
        result = service.determine_decision(
            responses={},
            decision_score=4,
            job_id="job_1",
            db=None
        )
        assert result["status"].value == "REJECTED"

    def test_decision_from_medium_score_5(self, service):
        """Test: score=5 (middle) → MAYBE"""
        result = service.determine_decision(
            responses={},
            decision_score=5,
            job_id="job_1",
            db=None
        )
        assert result["status"].value == "MAYBE"

    def test_decision_from_medium_score_6(self, service):
        """Test: score=6 → MAYBE"""
        result = service.determine_decision(
            responses={},
            decision_score=6,
            job_id="job_1",
            db=None
        )
        assert result["status"].value == "MAYBE"

    def test_decision_from_medium_score_7(self, service):
        """Test: score=7 → MAYBE"""
        result = service.determine_decision(
            responses={},
            decision_score=7,
            job_id="job_1",
            db=None
        )
        assert result["status"].value == "MAYBE"

    def test_decision_q4_takes_precedence_over_score(self, service):
        """Test: q_004 takes precedence over score"""
        # q_004=no should override high score
        result = service.determine_decision(
            responses={"q_004": "no"},
            decision_score=9,
            job_id="job_1",
            db=None
        )
        assert result["status"].value == "REJECTED"

    def test_decision_various_yes_spellings(self, service):
        """Test: handles various yes spellings"""
        for yes_variant in ["yes", "YES", "Yes", "approved", "APPROVED", "true", "TRUE", "1", "approve"]:
            result = service.determine_decision(
                responses={"q_004": yes_variant},
                decision_score=None,
                job_id="job_1",
                db=None
            )
            assert result["status"].value == "APPROVED", f"Failed for: {yes_variant}"

    def test_decision_various_no_spellings(self, service):
        """Test: handles various no spellings"""
        for no_variant in ["no", "NO", "No", "rejected", "REJECTED", "false", "FALSE", "0", "reject"]:
            result = service.determine_decision(
                responses={"q_004": no_variant},
                decision_score=None,
                job_id="job_1",
                db=None
            )
            assert result["status"].value == "REJECTED", f"Failed for: {no_variant}"

    def test_decision_various_maybe_spellings(self, service):
        """Test: handles various maybe spellings"""
        for maybe_variant in ["maybe", "MAYBE", "Maybe", "uncertain", "UNCERTAIN", "escalate", "2"]:
            result = service.determine_decision(
                responses={"q_004": maybe_variant},
                decision_score=None,
                job_id="job_1",
                db=None
            )
            assert result["status"].value == "MAYBE", f"Failed for: {maybe_variant}"

    def test_decision_no_q4_falls_back_to_score(self, service):
        """Test: without q_004, uses score"""
        result = service.determine_decision(
            responses={"q_001": "yes", "q_002": "Some concern"},
            decision_score=8,
            job_id="job_1",
            db=None
        )
        assert result["status"].value == "APPROVED"

    def test_decision_no_q4_no_score_defaults_to_escalation(self, service):
        """Test: without q_004 or score, defaults to MAYBE"""
        result = service.determine_decision(
            responses={"q_001": "yes"},
            decision_score=None,
            job_id="job_1",
            db=None
        )
        assert result["status"].value == "MAYBE"


class TestCreateValidationQuestions:
    """Test create_validation_questions service method"""

    @patch('app.services.hiring_manager_validation_service.logger')
    def test_success_minimal_questions(self, mock_logger, service):
        """Test successful creation with minimal question data"""
        mock_db = MagicMock()
        mock_job = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job

        questions = [
            {"question_id": "q_001", "question_text": "Experience match?"}
        ]

        result = service.create_validation_questions(
            db=mock_db,
            job_id="job_1",
            tenant_id=1,
            questions=questions,
            timeout_hours=24,
            auto_schedule=True
        )

        assert result["status"] == "success"
        assert result["job_id"] == "job_1"
        assert result["question_count"] == 1
        assert result["timeout_hours"] == 24
        assert result["auto_schedule_after_approval"] is True
        assert "question_ids" in result
        assert "created_at" in result

    @patch('app.services.hiring_manager_validation_service.logger')
    def test_success_maximum_questions(self, mock_logger, service):
        """Test successful creation with 10 questions (max)"""
        mock_db = MagicMock()
        mock_job = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job

        questions = [
            {"question_id": f"q_{i:03d}", "question_text": f"Question {i}"}
            for i in range(1, 11)
        ]

        result = service.create_validation_questions(
            db=mock_db,
            job_id="job_1",
            tenant_id=1,
            questions=questions
        )

        assert result["status"] == "success"
        assert result["question_count"] == 10

    def test_error_job_not_found(self, service):
        """Test error when job not found"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="Job .* not found"):
            service.create_validation_questions(
                db=mock_db,
                job_id="nonexistent",
                tenant_id=1,
                questions=[{"question_id": "q_001", "question_text": "Test"}]
            )
        mock_db.rollback.assert_called()

    def test_error_empty_questions(self, service):
        """Test error when no questions provided"""
        mock_db = MagicMock()
        mock_job = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job

        with pytest.raises(ValueError, match="At least one question is required"):
            service.create_validation_questions(
                db=mock_db,
                job_id="job_1",
                tenant_id=1,
                questions=[]
            )

    def test_error_too_many_questions(self, service):
        """Test error when more than 10 questions"""
        mock_db = MagicMock()
        mock_job = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job

        questions = [
            {"question_id": f"q_{i:03d}", "question_text": f"Question {i}"}
            for i in range(1, 12)  # 11 questions
        ]

        with pytest.raises(ValueError, match="Maximum 10 questions allowed"):
            service.create_validation_questions(
                db=mock_db,
                job_id="job_1",
                tenant_id=1,
                questions=questions
            )

    def test_error_missing_question_id(self, service):
        """Test error when question_id missing"""
        mock_db = MagicMock()
        mock_job = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job

        questions = [
            {"question_text": "No ID provided"}  # Missing question_id
        ]

        with pytest.raises(ValueError, match="Each question must have"):
            service.create_validation_questions(
                db=mock_db,
                job_id="job_1",
                tenant_id=1,
                questions=questions
            )

    def test_error_missing_question_text(self, service):
        """Test error when question_text missing"""
        mock_db = MagicMock()
        mock_job = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job

        questions = [
            {"question_id": "q_001"}  # Missing question_text
        ]

        with pytest.raises(ValueError, match="Each question must have"):
            service.create_validation_questions(
                db=mock_db,
                job_id="job_1",
                tenant_id=1,
                questions=questions
            )

    @patch('app.services.hiring_manager_validation_service.logger')
    def test_custom_timeout_hours(self, mock_logger, service):
        """Test setting custom timeout hours"""
        mock_db = MagicMock()
        mock_job = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job

        result = service.create_validation_questions(
            db=mock_db,
            job_id="job_1",
            tenant_id=1,
            questions=[{"question_id": "q_001", "question_text": "Test"}],
            timeout_hours=48
        )

        assert result["timeout_hours"] == 48

    @patch('app.services.hiring_manager_validation_service.logger')
    def test_auto_schedule_disabled(self, mock_logger, service):
        """Test disabling auto-schedule"""
        mock_db = MagicMock()
        mock_job = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job

        result = service.create_validation_questions(
            db=mock_db,
            job_id="job_1",
            tenant_id=1,
            questions=[{"question_id": "q_001", "question_text": "Test"}],
            auto_schedule=False
        )

        assert result["auto_schedule_after_approval"] is False


class TestRecordHMResponse:
    """Test record_hm_response service method"""

    def test_success_with_all_fields(self, service):
        """Test successful response recording with all fields"""
        mock_db = MagicMock()
        validation = Mock()
        validation.id = "val_1"
        validation.status = Mock(value="PENDING")
        validation.created_at = datetime.utcnow() - timedelta(hours=2)
        validation.candidate_id = "cand_1"
        validation.job_id = "job_1"

        mock_db.query.return_value.filter.return_value.first.return_value = validation

        # Make status enum comparable
        from app.models import HMValidationStatus
        validation.status = HMValidationStatus.PENDING

        responses = {
            "q_001": "yes",
            "q_002": "No red flags",
            "q_004": "yes"
        }

        result = service.record_hm_response(
            db=mock_db,
            validation_id="val_1",
            tenant_id=1,
            responses=responses,
            decision_comment="Great candidate",
            decision_score=9
        )

        assert result["status"] == "success"
        assert result["validation_id"] == "val_1"
        assert result["decision"] == "APPROVED"
        assert result["next_step"] == "schedule_interview"
        assert result["decision_comment"] == "Great candidate"
        assert result["decision_score"] == 9

    def test_error_validation_not_found(self, service):
        """Test error when validation not found"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="not found"):
            service.record_hm_response(
                db=mock_db,
                validation_id="nonexistent",
                tenant_id=1,
                responses={"q_001": "yes"}
            )
        mock_db.rollback.assert_called()

    def test_error_already_responded(self, service):
        """Test error when validation already responded"""
        from app.models import HMValidationStatus

        mock_db = MagicMock()
        validation = Mock()
        validation.status = HMValidationStatus.APPROVED

        mock_db.query.return_value.filter.return_value.first.return_value = validation

        with pytest.raises(ValueError, match="already responded"):
            service.record_hm_response(
                db=mock_db,
                validation_id="val_1",
                tenant_id=1,
                responses={"q_001": "yes"}
            )

    def test_error_no_responses(self, service):
        """Test error when no responses provided"""
        from app.models import HMValidationStatus

        mock_db = MagicMock()
        validation = Mock()
        validation.status = HMValidationStatus.PENDING

        mock_db.query.return_value.filter.return_value.first.return_value = validation

        with pytest.raises(ValueError, match="At least one response is required"):
            service.record_hm_response(
                db=mock_db,
                validation_id="val_1",
                tenant_id=1,
                responses={}
            )

    def test_response_time_calculation(self, service):
        """Test response time is calculated correctly"""
        from app.models import HMValidationStatus

        mock_db = MagicMock()
        validation = Mock()
        validation.id = "val_1"
        validation.status = HMValidationStatus.PENDING
        validation.created_at = datetime.utcnow() - timedelta(hours=3)

        mock_db.query.return_value.filter.return_value.first.return_value = validation

        result = service.record_hm_response(
            db=mock_db,
            validation_id="val_1",
            tenant_id=1,
            responses={"q_001": "yes", "q_004": "yes"}
        )

        # Response time should be approximately 3 hours
        assert result["response_time_hours"] >= 3

    def test_decision_rejected(self, service):
        """Test decision logic when q_004=no"""
        from app.models import HMValidationStatus

        mock_db = MagicMock()
        validation = Mock()
        validation.id = "val_1"
        validation.status = HMValidationStatus.PENDING
        validation.created_at = datetime.utcnow()

        mock_db.query.return_value.filter.return_value.first.return_value = validation

        result = service.record_hm_response(
            db=mock_db,
            validation_id="val_1",
            tenant_id=1,
            responses={"q_001": "yes", "q_004": "no"}
        )

        assert result["decision"] == "REJECTED"
        assert result["next_step"] == "return_to_pool"

    def test_decision_escalated(self, service):
        """Test decision logic when q_004=maybe"""
        from app.models import HMValidationStatus

        mock_db = MagicMock()
        validation = Mock()
        validation.id = "val_1"
        validation.status = HMValidationStatus.PENDING
        validation.created_at = datetime.utcnow()

        mock_db.query.return_value.filter.return_value.first.return_value = validation

        result = service.record_hm_response(
            db=mock_db,
            validation_id="val_1",
            tenant_id=1,
            responses={"q_001": "yes", "q_004": "maybe"}
        )

        assert result["decision"] == "MAYBE"
        assert result["next_step"] == "escalate_for_review"
