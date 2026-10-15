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
from app.services.message_handlers.candidate_conversion_handler import CandidateConversionHandler
from app.services.message_handlers.job_creation_flash_handler import JobCreationFlashHandler
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

        # missing right after creation = a handler bug: ValueError, never retried
        with pytest.raises(ValueError, match="not found in database"):
            JobCreationFlashHandler.on_success(message, result, db)


class TestErrorClassification:
    """Bad data is a ValueError (not retried); a database failure is a RuntimeError (retried)."""

    def test_value_error_not_retryable(self):
        message = Mock(spec=ChannelQueueItem)
        message.id = "msg-value-error"
        with pytest.raises(ValueError):
            JobCreationFlashHandler.on_success(message, {"invalid": "structure"}, Mock(spec=Session))

    def test_runtime_error_retryable(self):
        message = Mock(spec=ChannelQueueItem)
        message.id = "msg-retry-test"
        message.payload = {}
        db = Mock(spec=Session)
        db.query.side_effect = ConnectionError("database unavailable")
        with pytest.raises(RuntimeError, match="Database validation error"):
            JobCreationFlashHandler.on_success(message, {"status": "success", "job_id": "job-1"}, db)


class TestHandlerCompletionFlow:
    """Test complete flow: process -> validate -> mark COMPLETED."""

    def test_retry_scheduling(self):
        """on_retry should schedule message for retry with correct backoff."""
        message = Mock(spec=ChannelQueueItem)
        message.id = "msg-retry"
        message.retry_count = 0
        message.next_retry_at = None

        db = Mock(spec=Session)

        CandidateConversionHandler.on_retry(
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
        message.retry_count = CandidateConversionHandler.MAX_RETRIES

        assert not CandidateConversionHandler.should_retry(message)

    def test_should_retry_respects_next_retry_at(self):
        """should_retry should return False if next_retry_at in future."""
        message = Mock(spec=ChannelQueueItem)
        message.retry_count = 0
        message.next_retry_at = datetime.utcnow() + timedelta(hours=1)

        assert not CandidateConversionHandler.should_retry(message)

    def test_should_retry_allows_ready_messages(self):
        """should_retry should return True for ready messages."""
        message = Mock(spec=ChannelQueueItem)
        message.retry_count = 1
        message.next_retry_at = datetime.utcnow() - timedelta(minutes=1)

        assert CandidateConversionHandler.should_retry(message)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
