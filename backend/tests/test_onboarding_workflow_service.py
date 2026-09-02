"""
import logging
Tests for S-324/HRMS-ONBOARDING-WORKFLOW service layer.

Test coverage for:
- start_onboarding()
- assign_buddy()
- send_welcome_kit()
- schedule_training()
"""
import pytest
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.candidate import Candidate
from app.models.user import Users
from app.models.onboarding_workflow import (
    OnboardingWorkflow,
    OnboardingBuddy,
    WelcomeKit,
    TrainingSession,
    OnboardingTask,
)
from app.services.onboarding_workflow_service import (
    start_onboarding,
    assign_buddy,
    send_welcome_kit,
    schedule_training,
)

logger = logging.getLogger(__name__)

class TestStartOnboarding:
    """Test onboarding workflow initiation."""

    def test_start_onboarding_success(self, db: Session, test_employee):
        """Should create workflow and default tasks."""
        result = start_onboarding(
            db,
            calling_context_tenant_id="test_tenant",
            employee_id=test_employee.id,
            expected_completion_days=30,
        )

        assert result["status"] == "success"
        assert result["workflow_id"] is not None
        assert result["tasks_created"] > 0

        # Verify workflow created
        workflow = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.id == result["workflow_id"]
        ).first()
        assert workflow is not None
        assert workflow.status == "IN_PROGRESS"
        assert workflow.employee_id == test_employee.id

    def test_start_onboarding_employee_not_found(self, db: Session):
        """Should fail when employee doesn't exist."""
        result = start_onboarding(
            db,
            calling_context_tenant_id="test_tenant",
            employee_id="nonexistent_employee",
        )

        assert result["status"] == "error"
        assert result["workflow_id"] is None

    def test_start_onboarding_duplicate_workflow(self, db: Session, test_employee):
        """Should fail when workflow already exists."""
        # Create first workflow
        result1 = start_onboarding(
            db,
            calling_context_tenant_id="test_tenant",
            employee_id=test_employee.id,
        )
        assert result1["status"] == "success"

        # Try to create duplicate
        result2 = start_onboarding(
            db,
            calling_context_tenant_id="test_tenant",
            employee_id=test_employee.id,
        )

        assert result2["status"] == "error"
        assert "already exists" in result2["message"]

    def test_start_onboarding_creates_default_tasks(self, db: Session, test_employee):
        """Should create standard onboarding tasks."""
        result = start_onboarding(
            db,
            calling_context_tenant_id="test_tenant",
            employee_id=test_employee.id,
        )

        workflow_id = result["workflow_id"]
        tasks = db.query(OnboardingTask).filter(
            OnboardingTask.workflow_id == workflow_id
        ).all()

        # Should have default tasks
        assert len(tasks) > 0

        # Check for required task types
        task_types = {t.task_type for t in tasks}
        assert "ORIENTATION" in task_types
        assert "SYSTEM_ACCESS" in task_types

    def test_start_onboarding_with_reporting_manager(self, db: Session, test_employee, test_user):
        """Should link reporting manager when provided."""
        result = start_onboarding(
            db,
            calling_context_tenant_id="test_tenant",
            employee_id=test_employee.id,
            reporting_manager_id=test_user.UserID,
        )

        workflow = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.id == result["workflow_id"]
        ).first()

        assert workflow.reporting_manager_id == test_user.UserID


class TestAssignBuddy:
    """Test buddy assignment."""

    def test_assign_buddy_success(self, db: Session, test_employee, test_user, setup_onboarding):
        """Should assign buddy successfully."""
        workflow_id = setup_onboarding(test_employee.id)

        result = assign_buddy(
            db,
            calling_context_tenant_id="test_tenant",
            workflow_id=workflow_id,
            buddy_user_id=test_user.UserID,
        )

        assert result["status"] == "success"
        assert result["buddy_id"] is not None

        # Verify buddy assigned
        buddy = db.query(OnboardingBuddy).filter(
            OnboardingBuddy.id == result["buddy_id"]
        ).first()
        assert buddy is not None
        assert buddy.buddy_user_id == test_user.UserID
        assert buddy.status == "ASSIGNED"

    def test_assign_buddy_workflow_not_found(self, db: Session, test_user):
        """Should fail when workflow doesn't exist."""
        result = assign_buddy(
            db,
            calling_context_tenant_id="test_tenant",
            workflow_id=99999,
            buddy_user_id=test_user.UserID,
        )

        assert result["status"] == "error"
        assert result["buddy_id"] is None

    def test_assign_buddy_user_not_found(self, db: Session, setup_onboarding, test_employee):
        """Should fail when buddy user doesn't exist."""
        workflow_id = setup_onboarding(test_employee.id)

        result = assign_buddy(
            db,
            calling_context_tenant_id="test_tenant",
            workflow_id=workflow_id,
            buddy_user_id="nonexistent_user",
        )

        assert result["status"] == "error"

    def test_assign_buddy_duplicate_buddy(self, db: Session, test_employee, test_user, setup_onboarding):
        """Should fail when buddy already assigned."""
        workflow_id = setup_onboarding(test_employee.id)

        # Assign buddy first time
        result1 = assign_buddy(
            db,
            calling_context_tenant_id="test_tenant",
            workflow_id=workflow_id,
            buddy_user_id=test_user.UserID,
        )
        assert result1["status"] == "success"

        # Try to assign again
        result2 = assign_buddy(
            db,
            calling_context_tenant_id="test_tenant",
            workflow_id=workflow_id,
            buddy_user_id=test_user.UserID,
        )

        assert result2["status"] == "error"

    def test_assign_buddy_creates_introduction_task(self, db: Session, test_employee, test_user, setup_onboarding):
        """Should create buddy introduction task."""
        workflow_id = setup_onboarding(test_employee.id)

        assign_buddy(
            db,
            calling_context_tenant_id="test_tenant",
            workflow_id=workflow_id,
            buddy_user_id=test_user.UserID,
        )

        # Check for buddy introduction task
        task = db.query(OnboardingTask).filter(
            OnboardingTask.workflow_id == workflow_id,
            OnboardingTask.task_name == "Buddy Introduction",
        ).first()

        assert task is not None
        assert task.assigned_to_user_id == test_user.UserID


class TestSendWelcomeKit:
    """Test welcome kit delivery."""

    def test_send_welcome_kit_success(self, db: Session, test_employee, setup_onboarding):
        """Should send welcome kit successfully."""
        workflow_id = setup_onboarding(test_employee.id)

        kit_contents = ["Welcome Letter", "Company Handbook", "IT Setup Guide"]

        result = send_welcome_kit(
            db,
            calling_context_tenant_id="test_tenant",
            workflow_id=workflow_id,
            kit_type="EMAIL",
            kit_name="Day 1 Welcome Package",
            kit_contents=kit_contents,
            delivery_channel="EMAIL",
        )

        assert result["status"] in ["success", "partial"]
        assert result["kit_id"] is not None

        # Verify kit created
        kit = db.query(WelcomeKit).filter(
            WelcomeKit.id == result["kit_id"]
        ).first()
        assert kit is not None
        assert kit.kit_type == "EMAIL"
        assert kit.kit_name == "Day 1 Welcome Package"
        assert kit.delivery_status in ["SENT", "FAILED"]

    def test_send_welcome_kit_workflow_not_found(self, db: Session):
        """Should fail when workflow doesn't exist."""
        result = send_welcome_kit(
            db,
            calling_context_tenant_id="test_tenant",
            workflow_id=99999,
            kit_type="EMAIL",
            kit_name="Welcome Kit",
        )

        assert result["status"] == "error"
        assert result["kit_id"] is None

    def test_send_welcome_kit_physical_delivery(self, db: Session, test_employee, setup_onboarding):
        """Should handle physical mail delivery."""
        workflow_id = setup_onboarding(test_employee.id)

        result = send_welcome_kit(
            db,
            calling_context_tenant_id="test_tenant",
            workflow_id=workflow_id,
            kit_type="PHYSICAL",
            kit_name="Onboarding Package",
            delivery_channel="PHYSICAL_MAIL",
        )

        assert result["status"] == "success"

        kit = db.query(WelcomeKit).filter(
            WelcomeKit.id == result["kit_id"]
        ).first()
        assert kit.sent_channel == "PHYSICAL_MAIL"

    def test_send_welcome_kit_multiple_deliveries(self, db: Session, test_employee, setup_onboarding):
        """Should send multiple kit types to same employee."""
        workflow_id = setup_onboarding(test_employee.id)

        # Send email kit
        result1 = send_welcome_kit(
            db,
            calling_context_tenant_id="test_tenant",
            workflow_id=workflow_id,
            kit_type="EMAIL",
            kit_name="Digital Resources",
        )
        assert result1["status"] in ["success", "partial"]

        # Send physical kit
        result2 = send_welcome_kit(
            db,
            calling_context_tenant_id="test_tenant",
            workflow_id=workflow_id,
            kit_type="PHYSICAL",
            kit_name="Physical Package",
        )
        assert result2["status"] == "success"

        # Verify both created
        kits = db.query(WelcomeKit).filter(
            WelcomeKit.workflow_id == workflow_id
        ).all()
        assert len(kits) == 2


class TestScheduleTraining:
    """Test training session scheduling."""

    def test_schedule_training_success(self, db: Session, test_employee, setup_onboarding):
        """Should schedule training session successfully."""
        workflow_id = setup_onboarding(test_employee.id)

        scheduled_date = date.today() + timedelta(days=3)

        result = schedule_training(
            db,
            calling_context_tenant_id="test_tenant",
            workflow_id=workflow_id,
            training_name="System Access Setup",
            scheduled_date=scheduled_date,
            scheduled_time="10:00",
            delivery_mode="IN_PERSON",
            duration_minutes=60,
        )

        assert result["status"] == "success"
        assert result["session_id"] is not None

        # Verify training session created
        session = db.query(TrainingSession).filter(
            TrainingSession.id == result["session_id"]
        ).first()
        assert session is not None
        assert session.training_name == "System Access Setup"
        assert session.scheduled_date == scheduled_date
        assert session.status == "SCHEDULED"

    def test_schedule_training_workflow_not_found(self, db: Session):
        """Should fail when workflow doesn't exist."""
        result = schedule_training(
            db,
            calling_context_tenant_id="test_tenant",
            workflow_id=99999,
            training_name="Training",
            scheduled_date=date.today() + timedelta(days=3),
            scheduled_time="10:00",
        )

        assert result["status"] == "error"

    def test_schedule_training_before_joining_date(self, db: Session, test_employee, setup_onboarding):
        """Should fail when training scheduled before joining date."""
        workflow_id = setup_onboarding(test_employee.id)

        # Get workflow to check joining date
        workflow = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.id == workflow_id
        ).first()

        # Schedule training before joining
        scheduled_date = workflow.joining_date - timedelta(days=1)

        result = schedule_training(
            db,
            calling_context_tenant_id="test_tenant",
            workflow_id=workflow_id,
            training_name="Training",
            scheduled_date=scheduled_date,
            scheduled_time="10:00",
        )

        assert result["status"] == "error"

    def test_schedule_training_with_trainer(self, db: Session, test_employee, test_user, setup_onboarding):
        """Should assign trainer when provided."""
        workflow_id = setup_onboarding(test_employee.id)
        scheduled_date = date.today() + timedelta(days=3)

        result = schedule_training(
            db,
            calling_context_tenant_id="test_tenant",
            workflow_id=workflow_id,
            training_name="Role Training",
            scheduled_date=scheduled_date,
            scheduled_time="14:00",
            trainer_user_id=test_user.UserID,
        )

        assert result["status"] == "success"

        session = db.query(TrainingSession).filter(
            TrainingSession.id == result["session_id"]
        ).first()
        assert session.trainer_user_id == test_user.UserID

    def test_schedule_training_virtual_delivery(self, db: Session, test_employee, setup_onboarding):
        """Should handle virtual training delivery."""
        workflow_id = setup_onboarding(test_employee.id)
        scheduled_date = date.today() + timedelta(days=3)

        result = schedule_training(
            db,
            calling_context_tenant_id="test_tenant",
            workflow_id=workflow_id,
            training_name="Online Training",
            scheduled_date=scheduled_date,
            scheduled_time="15:00",
            delivery_mode="VIRTUAL",
            meeting_link="https://zoom.us/j/123456",
        )

        assert result["status"] == "success"

        session = db.query(TrainingSession).filter(
            TrainingSession.id == result["session_id"]
        ).first()
        assert session.delivery_mode == "VIRTUAL"
        assert session.meeting_link == "https://zoom.us/j/123456"

    def test_schedule_training_creates_task(self, db: Session, test_employee, setup_onboarding):
        """Should create onboarding task for training."""
        workflow_id = setup_onboarding(test_employee.id)
        scheduled_date = date.today() + timedelta(days=3)

        schedule_training(
            db,
            calling_context_tenant_id="test_tenant",
            workflow_id=workflow_id,
            training_name="Important Training",
            scheduled_date=scheduled_date,
            scheduled_time="10:00",
            is_mandatory=True,
        )

        # Check for training task
        task = db.query(OnboardingTask).filter(
            OnboardingTask.workflow_id == workflow_id,
            OnboardingTask.task_type == "TRAINING",
        ).first()

        assert task is not None
        assert "Important Training" in task.task_name
        assert task.is_mandatory is True


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def test_employee(db: Session):
    """Create test employee."""
    employee = Employee(
        id="test_employee_001",
        tenant_id="test_tenant",
        first_name="John",
        last_name="Doe",
        email="john.doe@test.com",
        mobile="9876543210",
        joining_date=date.today(),
        status="ACTIVE",
    )
    db.add(employee)
    db.commit()
    return employee


@pytest.fixture
def test_user(db: Session):
    """Create test user."""
    user = Users(
        UserID="test_user_001",
        UserName="Test User",
        UserEmail="test.user@test.com",
        UserRole="HR",
        Department="HR",
        UserPassword="hashed_password",
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def setup_onboarding(db: Session):
    """Fixture to setup onboarding workflow."""
    def _setup(employee_id: str) -> int:
        result = start_onboarding(
            db,
            calling_context_tenant_id="test_tenant",
            employee_id=employee_id,
        )
        return result["workflow_id"]
    return _setup
