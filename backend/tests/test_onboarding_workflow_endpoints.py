"""
import logging
Tests for S-324/HRMS-ONBOARDING-WORKFLOW REST API endpoints.

Test coverage for:
- POST /onboarding-workflow/start
- POST /onboarding-workflow/assign-buddy
- POST /onboarding-workflow/send-welcome-kit
- POST /onboarding-workflow/schedule-training
- GET /onboarding-workflow/{workflow_id}
- GET /onboarding-workflow/employee/{employee_id}
"""
import logging
import pytest
import json
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.models.employee import Employee
from app.models.user import Users
from app.models.onboarding_workflow import OnboardingWorkflow

client = TestClient(app)

logger = logging.getLogger(__name__)

class TestStartOnboardingEndpoint:
    """Test POST /onboarding-workflow/start endpoint."""

    def test_start_onboarding_endpoint_success(self, db_session, test_auth_headers, test_employee):
        """Should start onboarding via REST API."""
        payload = {
            "employee_id": test_employee.id,
            "expected_completion_days": 30,
        }

        response = client.post(
            "/api/v1/onboarding-workflow/start",
            json=payload,
            headers=test_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["workflow_id"] is not None
        assert data["tasks_created"] > 0

    def test_start_onboarding_endpoint_invalid_employee(self, test_auth_headers):
        """Should return 400 for invalid employee."""
        payload = {
            "employee_id": "nonexistent_employee",
        }

        response = client.post(
            "/api/v1/onboarding-workflow/start",
            json=payload,
            headers=test_auth_headers,
        )

        assert response.status_code == 400

    def test_start_onboarding_endpoint_with_reporting_manager(self, db_session, test_auth_headers, test_employee, test_user):
        """Should accept reporting manager parameter."""
        payload = {
            "employee_id": test_employee.id,
            "reporting_manager_id": test_user.UserID,
        }

        response = client.post(
            "/api/v1/onboarding-workflow/start",
            json=payload,
            headers=test_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

class TestAssignBuddyEndpoint:
    """Test POST /onboarding-workflow/assign-buddy endpoint."""

    def test_assign_buddy_endpoint_success(self, db_session, test_auth_headers, test_employee, test_user, setup_workflow):
        """Should assign buddy via REST API."""
        workflow_id = setup_workflow(test_employee.id)

        payload = {
            "workflow_id": workflow_id,
            "buddy_user_id": test_user.UserID,
        }

        response = client.post(
            "/api/v1/onboarding-workflow/assign-buddy",
            json=payload,
            headers=test_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["buddy_id"] is not None

    def test_assign_buddy_endpoint_invalid_workflow(self, test_auth_headers, test_user):
        """Should return 400 for invalid workflow."""
        payload = {
            "workflow_id": 99999,
            "buddy_user_id": test_user.UserID,
        }

        response = client.post(
            "/api/v1/onboarding-workflow/assign-buddy",
            json=payload,
            headers=test_auth_headers,
        )

        assert response.status_code == 400

    def test_assign_buddy_endpoint_with_activation_date(self, db_session, test_auth_headers, test_employee, test_user, setup_workflow):
        """Should accept activation date parameter."""
        workflow_id = setup_workflow(test_employee.id)
        activation_date = (date.today() + timedelta(days=1)).isoformat()

        payload = {
            "workflow_id": workflow_id,
            "buddy_user_id": test_user.UserID,
            "activation_date": activation_date,
        }

        response = client.post(
            "/api/v1/onboarding-workflow/assign-buddy",
            json=payload,
            headers=test_auth_headers,
        )

        assert response.status_code == 200

class TestSendWelcomeKitEndpoint:
    """Test POST /onboarding-workflow/send-welcome-kit endpoint."""

    def test_send_welcome_kit_endpoint_success(self, db_session, test_auth_headers, test_employee, setup_workflow):
        """Should send welcome kit via REST API."""
        workflow_id = setup_workflow(test_employee.id)

        payload = {
            "workflow_id": workflow_id,
            "kit_type": "EMAIL",
            "kit_name": "Day 1 Welcome Package",
            "kit_contents": ["Letter", "Handbook", "Setup Guide"],
            "delivery_channel": "EMAIL",
        }

        response = client.post(
            "/api/v1/onboarding-workflow/send-welcome-kit",
            json=payload,
            headers=test_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["success", "partial"]
        assert data["kit_id"] is not None

    def test_send_welcome_kit_endpoint_physical_delivery(self, db_session, test_auth_headers, test_employee, setup_workflow):
        """Should handle physical delivery."""
        workflow_id = setup_workflow(test_employee.id)

        payload = {
            "workflow_id": workflow_id,
            "kit_type": "PHYSICAL",
            "kit_name": "Physical Welcome Package",
            "delivery_channel": "PHYSICAL_MAIL",
        }

        response = client.post(
            "/api/v1/onboarding-workflow/send-welcome-kit",
            json=payload,
            headers=test_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_send_welcome_kit_endpoint_invalid_workflow(self, test_auth_headers):
        """Should return 400 for invalid workflow."""
        payload = {
            "workflow_id": 99999,
            "kit_type": "EMAIL",
            "kit_name": "Kit",
        }

        response = client.post(
            "/api/v1/onboarding-workflow/send-welcome-kit",
            json=payload,
            headers=test_auth_headers,
        )

        assert response.status_code == 400

class TestScheduleTrainingEndpoint:
    """Test POST /onboarding-workflow/schedule-training endpoint."""

    def test_schedule_training_endpoint_success(self, db_session, test_auth_headers, test_employee, setup_workflow):
        """Should schedule training via REST API."""
        workflow_id = setup_workflow(test_employee.id)
        scheduled_date = (date.today() + timedelta(days=3)).isoformat()

        payload = {
            "workflow_id": workflow_id,
            "training_name": "System Access Setup",
            "scheduled_date": scheduled_date,
            "scheduled_time": "10:00",
            "delivery_mode": "IN_PERSON",
            "duration_minutes": 60,
        }

        response = client.post(
            "/api/v1/onboarding-workflow/schedule-training",
            json=payload,
            headers=test_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["session_id"] is not None

    def test_schedule_training_endpoint_virtual(self, db_session, test_auth_headers, test_employee, setup_workflow):
        """Should handle virtual training."""
        workflow_id = setup_workflow(test_employee.id)
        scheduled_date = (date.today() + timedelta(days=3)).isoformat()

        payload = {
            "workflow_id": workflow_id,
            "training_name": "Online Training",
            "scheduled_date": scheduled_date,
            "scheduled_time": "14:00",
            "delivery_mode": "VIRTUAL",
            "meeting_link": "https://zoom.us/j/123456",
        }

        response = client.post(
            "/api/v1/onboarding-workflow/schedule-training",
            json=payload,
            headers=test_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_schedule_training_endpoint_invalid_workflow(self, test_auth_headers):
        """Should return 400 for invalid workflow."""
        scheduled_date = (date.today() + timedelta(days=3)).isoformat()

        payload = {
            "workflow_id": 99999,
            "training_name": "Training",
            "scheduled_date": scheduled_date,
            "scheduled_time": "10:00",
        }

        response = client.post(
            "/api/v1/onboarding-workflow/schedule-training",
            json=payload,
            headers=test_auth_headers,
        )

        assert response.status_code == 400

class TestGetWorkflowEndpoint:
    """Test GET /onboarding-workflow/{workflow_id} endpoint."""

    def test_get_workflow_success(self, db_session, test_auth_headers, test_employee, setup_workflow):
        """Should retrieve workflow details."""
        workflow_id = setup_workflow(test_employee.id)

        response = client.get(
            f"/api/v1/onboarding-workflow/{workflow_id}",
            headers=test_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == workflow_id
        assert data["employee_id"] == test_employee.id
        assert data["status"] == "IN_PROGRESS"

    def test_get_workflow_not_found(self, test_auth_headers):
        """Should return 404 for nonexistent workflow."""
        response = client.get(
            "/api/v1/onboarding-workflow/99999",
            headers=test_auth_headers,
        )

        assert response.status_code == 404

class TestGetWorkflowByEmployeeEndpoint:
    """Test GET /onboarding-workflow/employee/{employee_id} endpoint."""

    def test_get_workflow_by_employee_success(self, db_session, test_auth_headers, test_employee, setup_workflow):
        """Should retrieve workflow by employee ID."""
        workflow_id = setup_workflow(test_employee.id)

        response = client.get(
            f"/api/v1/onboarding-workflow/employee/{test_employee.id}",
            headers=test_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["workflow"]["employee_id"] == test_employee.id
        assert data["workflow"]["workflow_id"] == workflow_id

    def test_get_workflow_by_employee_not_found(self, test_auth_headers):
        """Should return 404 for nonexistent employee."""
        response = client.get(
            "/api/v1/onboarding-workflow/employee/nonexistent",
            headers=test_auth_headers,
        )

        assert response.status_code == 404

class TestGetWorkflowTasksEndpoint:
    """Test GET /onboarding-workflow/{workflow_id}/tasks endpoint."""

    def test_get_workflow_tasks_success(self, db_session, test_auth_headers, test_employee, setup_workflow):
        """Should retrieve all tasks for workflow."""
        workflow_id = setup_workflow(test_employee.id)

        response = client.get(
            f"/api/v1/onboarding-workflow/{workflow_id}/tasks",
            headers=test_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == workflow_id
        assert data["total_tasks"] > 0
        assert len(data["tasks"]) > 0

    def test_get_workflow_tasks_with_status_filter(self, db_session, test_auth_headers, test_employee, setup_workflow):
        """Should filter tasks by status."""
        workflow_id = setup_workflow(test_employee.id)

        response = client.get(
            f"/api/v1/onboarding-workflow/{workflow_id}/tasks?status=PENDING",
            headers=test_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert all(t["status"] == "PENDING" for t in data["tasks"])

class TestGetWorkflowTrainingEndpoint:
    """Test GET /onboarding-workflow/{workflow_id}/training endpoint."""

    def test_get_workflow_training_success(self, db_session, test_auth_headers, test_employee, setup_workflow, setup_training):
        """Should retrieve training sessions for workflow."""
        workflow_id = setup_workflow(test_employee.id)
        setup_training(workflow_id)

        response = client.get(
            f"/api/v1/onboarding-workflow/{workflow_id}/training",
            headers=test_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == workflow_id
        assert data["total_sessions"] > 0

    def test_get_workflow_training_empty(self, db_session, test_auth_headers, test_employee, setup_workflow):
        """Should return empty list when no training scheduled."""
        workflow_id = setup_workflow(test_employee.id)

        response = client.get(
            f"/api/v1/onboarding-workflow/{workflow_id}/training",
            headers=test_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_sessions"] == 0
        assert len(data["training_sessions"]) == 0

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def test_auth_headers(test_user):
    """Create auth headers for test requests."""
    return {
        "Authorization": f"Bearer test_token",
        "X-Tenant-ID": "test_tenant",
    }

@pytest.fixture
def test_employee(db_session):
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
    db_session.add(employee)
    db_session.commit()
    return employee

@pytest.fixture
def test_user(db_session):
    """Create test user."""
    user = Users(
        UserID="test_user_001",
        UserName="Test User",
        UserEmail="test.user@test.com",
        UserRole="HR",
        Department="HR",
        UserPassword="hashed_password",
    )
    db_session.add(user)
    db_session.commit()
    return user

@pytest.fixture
def setup_workflow(db_session):
    """Fixture to setup onboarding workflow."""
    from app.services.onboarding_workflow_service import start_onboarding

    def _setup(employee_id: str) -> int:
        result = start_onboarding(
            db_session,
            calling_context_tenant_id="test_tenant",
            employee_id=employee_id,
        )
        return result["workflow_id"]
    return _setup

@pytest.fixture
def setup_training(db_session):
    """Fixture to schedule training."""
    from app.services.onboarding_workflow_service import schedule_training

    def _setup(workflow_id: int):
        scheduled_date = date.today() + timedelta(days=3)
        result = schedule_training(
            db_session,
            calling_context_tenant_id="test_tenant",
            workflow_id=workflow_id,
            training_name="Test Training",
            scheduled_date=scheduled_date,
            scheduled_time="10:00",
        )
        return result["session_id"]
    return _setup
