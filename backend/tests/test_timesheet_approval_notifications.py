"""
PRIORITY 1: Test timesheet approval notifications.
Verifies that EmailService.notify_timesheet_approved() is properly wired into approve_timesheet().
"""
from datetime import date, datetime
from unittest.mock import patch, MagicMock
import logging
from sqlalchemy.orm import Session

from app.services.timesheet_service import approve_timesheet


def _create_mock_timesheet():
    """Create a mock timesheet object for testing."""
    timesheet = MagicMock()
    timesheet.id = "ts-001"
    timesheet.status = "SUBMITTED"
    timesheet.submitted_at = datetime.utcnow()
    timesheet.week_starting_date = date(2026, 8, 4)
    timesheet.employee_id = "emp-001"
    timesheet.billable_hours = 40.0
    timesheet.total_hours = 40.0
    timesheet.approved_by = None
    timesheet.approved_at = None
    timesheet.entries = []

    # Create mock entries
    for i in range(5):  # Mon-Fri
        entry = MagicMock()
        entry.hours = 8.0
        entry.entry_type = "BILLABLE"
        timesheet.entries.append(entry)

    return timesheet


def _create_mock_employee():
    """Create a mock employee object."""
    employee = MagicMock()
    employee.id = "emp-001"
    employee.email = "employee@test.com"
    employee.first_name = "John"
    employee.last_name = "Doe"
    return employee


def _create_mock_db():
    """Create a mock database session."""
    db = MagicMock(spec=Session)
    return db


def test_approve_timesheet_sends_notification():
    """
    PRIORITY 1 TEST: Verify that approve_timesheet() calls EmailService.notify_timesheet_approved()
    and that the email notification is properly queued.
    """
    # Create mock objects
    db = _create_mock_db()
    timesheet = _create_mock_timesheet()
    employee = _create_mock_employee()

    # Mock the database query for finding the employee
    db.query.return_value.filter.return_value.first.return_value = employee

    with patch("app.services.timesheet_service.EmailService.notify_timesheet_approved") as mock_email:
        # Call approve_timesheet()
        result = approve_timesheet(
            db,
            timesheet,
            approved_by="manager@test.com"
        )

        # Verify timesheet status changed to APPROVED
        assert result.status == "APPROVED"
        assert result.approved_by == "manager@test.com"
        assert result.approved_at is not None

        # Verify EmailService.notify_timesheet_approved() was called
        mock_email.assert_called_once()

        # Verify the call arguments are correct
        call_args = mock_email.call_args
        assert call_args is not None

        # Get keyword arguments - Python 3.8+ compatibility
        if hasattr(call_args, 'kwargs'):
            kwargs = call_args.kwargs
        else:
            kwargs = call_args[1] if len(call_args) > 1 else {}

        # Verify all required parameters were passed
        assert "employee_email" in kwargs
        assert "employee_name" in kwargs
        assert "approver_email" in kwargs
        assert "approver_name" in kwargs
        assert "week_starting_date" in kwargs
        assert "total_hours" in kwargs

        # Verify email values
        assert kwargs["employee_email"] == "employee@test.com"
        assert kwargs["employee_name"] == "John Doe"
        assert kwargs["approver_email"] == "manager@test.com"
        assert kwargs["total_hours"] == 40.0
        assert kwargs["week_starting_date"] == "2026-08-04"


def test_approve_timesheet_notification_failure_does_not_block_approval():
    """
    PRIORITY 1 TEST: Verify that if EmailService.notify_timesheet_approved() fails,
    it does NOT block the approval itself. Notifications should be fire-and-forget.
    """
    # Create mock objects
    db = _create_mock_db()
    timesheet = _create_mock_timesheet()
    employee = _create_mock_employee()

    # Mock the database query for finding the employee
    db.query.return_value.filter.return_value.first.return_value = employee

    with patch("app.services.timesheet_service.EmailService.notify_timesheet_approved") as mock_email:
        # Make the email service raise an exception
        mock_email.side_effect = Exception("Email service unavailable")

        # Call approve_timesheet() - should NOT raise
        result = approve_timesheet(
            db,
            timesheet,
            approved_by="manager@test.com"
        )

        # Verify timesheet was still approved despite email failure
        assert result.status == "APPROVED"
        assert result.approved_by == "manager@test.com"
        assert result.approved_at is not None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
