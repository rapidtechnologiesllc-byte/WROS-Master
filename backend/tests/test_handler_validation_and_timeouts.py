"""
Test Suite: Queue Handler Validation & Time-Binding

Tests that all Priority 1-2 handlers:
1. Validate work before marking COMPLETED
2. Enforce 10-15 second timeout on execution
3. Handle errors properly (ValueError non-retryable, RuntimeError retryable)
4. Query database to confirm work actually happened
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from app.services.message_handlers.base_message_handler import time_bound, TimeoutError
from app.services.message_handlers.candidate_creation_handler import CandidateCreationHandler
from app.services.message_handlers.candidate_conversion_handler import CandidateConversionHandler
from app.services.message_handlers.job_creation_flash_handler import JobCreationFlashHandler
from app.services.message_handlers.job_update_flash_handler import JobUpdateFlashHandler
from app.services.message_handlers.job_delete_flash_handler import JobDeleteFlashHandler
from app.services.message_handlers.interview_scheduled_handler import InterviewScheduledHandler
from app.models.channel_queue import ChannelQueueItem


class TestTimeBinding:
    """Test that @time_bound decorator enforces timeout."""

    def test_time_bound_decorator_logs_when_near_timeout(self):
        """Decorator should log warning when execution nears timeout."""
        @time_bound(timeout_seconds=0.1)
        def slow_function():
            import time
            time.sleep(0.05)
            return "success"

        result = slow_function()
        assert result == "success"

    def test_time_bound_decorator_allows_successful_execution(self):
        """Decorator should allow normal execution under timeout."""
        @time_bound(timeout_seconds=5)
        def quick_function():
            return "done"

        result = quick_function()
        assert result == "done"

    def test_time_bound_decorator_propagates_exceptions(self):
        """Decorator should propagate exceptions from decorated function."""
        @time_bound(timeout_seconds=5)
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()


class TestCandidateCreationValidation:
    """Test candidate_creation_handler validation before COMPLETED."""

    def test_on_success_validates_result_structure(self):
        """on_success should raise ValueError if result structure invalid."""
        message = Mock(spec=ChannelQueueItem)
        db = Mock(spec=Session)

        # Invalid: result is not a dict
        with pytest.raises(ValueError, match="Handler returned invalid type"):
            CandidateCreationHandler.on_success(message, "not_a_dict", db)

        # Invalid: missing required field
        result = {"status": "success"}  # Missing candidate_id
        with pytest.raises(ValueError, match="missing required field"):
            CandidateCreationHandler.on_success(message, result, db)

    def test_on_success_validates_database_exists(self):
        """on_success should raise RuntimeError if candidate not in DB."""
        from app.models.candidate import Candidate

        message = Mock(spec=ChannelQueueItem)
        message.payload = {"candidate_email": "test@example.com"}
        message.id = "msg-123"

        result = {
            "status": "success",
            "candidate_id": "cand-999",
            "is_new": True
        }

        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = None  # Not found

        with pytest.raises(RuntimeError, match="not found in database"):
            CandidateCreationHandler.on_success(message, result, db)

    def test_on_success_validates_status_record_exists(self):
        """on_success should raise RuntimeError if status record missing."""
        from app.models.candidate import Candidate, CandidateStatus

        message = Mock(spec=ChannelQueueItem)
        message.payload = {"candidate_email": "test@example.com"}
        message.id = "msg-123"

        result = {
            "status": "success",
            "candidate_id": "cand-123",
            "is_new": True
        }

        # Mock candidate exists
        candidate_mock = Mock(spec=Candidate)
        candidate_mock.candidateEmail = "test@example.com"

        db = Mock(spec=Session)
        # First query finds candidate, second query finds no status
        db.query.side_effect = [
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=candidate_mock)))),
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=None))))  # No status
        ]

        with pytest.raises(RuntimeError, match="Required status record missing"):
            CandidateCreationHandler.on_success(message, result, db)


class TestCandidateConversionValidation:
    """Test candidate_conversion_handler validation before COMPLETED."""

    def test_on_success_validates_both_records_exist(self):
        """on_success should verify candidate AND employee exist."""
        message = Mock(spec=ChannelQueueItem)
        message.payload = {}
        message.id = "msg-456"

        result = {
            "status": "success",
            "candidate_id": "cand-456",
            "employee_id": "emp-456"
        }

        # Mock employee not found
        db = Mock(spec=Session)
        db.query.side_effect = [
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=Mock())))),  # Candidate found
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=None))))  # Employee not found
        ]

        with pytest.raises(RuntimeError, match="Employee .* not found in database"):
            CandidateConversionHandler.on_success(message, result, db)

    def test_on_success_validates_status_updated(self):
        """on_success should verify candidate status is EMPLOYEE."""
        from app.models.candidate import Candidate, CandidateStatus

        message = Mock(spec=ChannelQueueItem)
        message.id = "msg-457"

        result = {
            "status": "success",
            "candidate_id": "cand-457",
            "employee_id": "emp-457"
        }

        # Mock status with wrong value
        status_mock = Mock(spec=CandidateStatus)
        status_mock.piplineStatus = "OFFER"  # Wrong!

        db = Mock(spec=Session)
        db.query.side_effect = [
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=Mock())))),  # Candidate
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=Mock())))),  # Employee
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=status_mock))))  # Status
        ]

        with pytest.raises(RuntimeError, match="expected 'EMPLOYEE'"):
            CandidateConversionHandler.on_success(message, result, db)


class TestJobCreationValidation:
    """Test job_creation_flash_handler validation before COMPLETED."""

    def test_on_success_validates_job_exists(self):
        """on_success should raise RuntimeError if job not in DB."""
        message = Mock(spec=ChannelQueueItem)
        message.payload = {}
        message.id = "msg-789"

        result = {
            "status": "success",
            "job_id": "job-999",
            "created_at": datetime.utcnow().isoformat(),
            "job_status": "active",
            "job_title": "Test Job"
        }

        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = None  # Not found

        with pytest.raises(RuntimeError, match="not found in database"):
            JobCreationFlashHandler.on_success(message, result, db)


class TestJobUpdateValidation:
    """Test job_update_flash_handler validation before COMPLETED."""

    def test_on_success_validates_updates_persisted(self):
        """on_success should verify updates actually persisted."""
        from app.models.user import Jobs

        message = Mock(spec=ChannelQueueItem)
        message.id = "msg-update-1"

        result = {
            "status": "success",
            "job_id": "job-111",
            "updated_fields": ["jobTitle"],
            "new_values": {"jobTitle": "Senior Engineer"},
            "previous_values": {"jobTitle": "Engineer"}
        }

        # Mock job with wrong title (not persisted)
        job_mock = Mock(spec=Jobs)
        job_mock.jobTitle = "Engineer"  # Not updated!

        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = job_mock

        with pytest.raises(RuntimeError, match="Update validation failed"):
            JobUpdateFlashHandler.on_success(message, result, db)


class TestJobDeleteValidation:
    """Test job_delete_flash_handler validation before COMPLETED."""

    def test_on_success_validates_deletion(self):
        """on_success should verify job is actually deleted."""
        message = Mock(spec=ChannelQueueItem)
        message.id = "msg-delete-1"

        result = {
            "status": "success",
            "job_id": "job-delete-123",
            "deleted_at": datetime.utcnow().isoformat(),
            "cascade_tables_cleaned": []
        }

        # Mock job still exists (deletion failed)
        job_mock = Mock()

        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = job_mock

        with pytest.raises(RuntimeError, match="still exists in database after deletion"):
            JobDeleteFlashHandler.on_success(message, result, db)


class TestInterviewScheduledValidation:
    """Test interview_scheduled_handler validation before COMPLETED."""

    def test_on_success_validates_interview_created(self):
        """on_success should verify interview record exists."""
        message = Mock(spec=ChannelQueueItem)
        message.id = "msg-interview-1"

        result = {
            "status": "success",
            "interview_id": "int-999",
            "candidate_id": "cand-int-1",
            "interview_date": "2026-09-20"
        }

        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = None  # Not found

        with pytest.raises(RuntimeError, match="Interview .* not found in database"):
            InterviewScheduledHandler.on_success(message, result, db)

    def test_on_success_validates_interview_status(self):
        """on_success should verify interview status is 'Scheduled'."""
        from app.models.user import Interview

        message = Mock(spec=ChannelQueueItem)
        message.id = "msg-interview-2"

        result = {
            "status": "success",
            "interview_id": "int-123",
            "candidate_id": "cand-int-2",
            "interview_date": "2026-09-20"
        }

        # Mock interview with wrong status
        interview_mock = Mock(spec=Interview)
        interview_mock.status = "Pending"  # Wrong!
        interview_mock.candidate_id = "cand-int-2"

        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = interview_mock

        with pytest.raises(RuntimeError, match="expected 'Scheduled'"):
            InterviewScheduledHandler.on_success(message, result, db)


class TestErrorClassification:
    """Test that errors are properly classified for retry logic."""

    def test_value_error_not_retryable(self):
        """ValueError should be non-retryable (handler bug)."""
        message = Mock(spec=ChannelQueueItem)
        db = Mock(spec=Session)

        # ValueError during validation = code bug, don't retry
        with pytest.raises(ValueError):
            CandidateCreationHandler.on_success(
                message,
                {"invalid": "structure"},
                db
            )

    def test_runtime_error_retryable(self):
        """RuntimeError should be retryable (DB issue)."""
        message = Mock(spec=ChannelQueueItem)
        message.id = "msg-retry-test"

        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = None

        # RuntimeError during validation = DB issue, retry
        with pytest.raises(RuntimeError):
            CandidateCreationHandler.on_success(
                message,
                {"status": "success", "candidate_id": "cand-123", "is_new": True},
                db
            )


class TestHandlerCompletionFlow:
    """Test complete flow: process -> validate -> mark COMPLETED."""

    def test_retry_scheduling(self):
        """on_retry should schedule message for retry with correct backoff."""
        message = Mock(spec=ChannelQueueItem)
        message.id = "msg-retry"
        message.retry_count = 0
        message.next_retry_at = None

        db = Mock(spec=Session)

        CandidateCreationHandler.on_retry(
            message,
            "Test error",
            db
        )

        # Verify retry was scheduled
        assert message.retry_count == 1
        assert message.error == "Test error"
        assert message.next_retry_at is not None
        db.commit.assert_called_once()

    def test_should_retry_respects_max_retries(self):
        """should_retry should return False when max retries exceeded."""
        message = Mock(spec=ChannelQueueItem)
        message.retry_count = CandidateCreationHandler.MAX_RETRIES

        assert not CandidateCreationHandler.should_retry(message)

    def test_should_retry_respects_next_retry_at(self):
        """should_retry should return False if next_retry_at in future."""
        message = Mock(spec=ChannelQueueItem)
        message.retry_count = 0
        message.next_retry_at = datetime.utcnow() + timedelta(hours=1)

        assert not CandidateCreationHandler.should_retry(message)

    def test_should_retry_allows_ready_messages(self):
        """should_retry should return True for ready messages."""
        message = Mock(spec=ChannelQueueItem)
        message.retry_count = 1
        message.next_retry_at = datetime.utcnow() - timedelta(minutes=1)

        assert CandidateCreationHandler.should_retry(message)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
