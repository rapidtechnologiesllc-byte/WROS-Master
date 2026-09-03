"""
HRMS-0316 -- Invoice REST API Endpoint Tests
Integration tests for invoice generation, sending, and payment endpoints.
import logging
"""

import logging
import pytest
from datetime import datetime, date, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.employee import Employee
from app.models.project import Project
from app.models.client import Client, ClientContact
from app.models.employee_allocation import EmployeeAllocation
from app.models.business_unit_context import BusinessUnitContext
from app.models.user import Users

client = TestClient(app)


@pytest.fixture
def db():
    """Get database session."""
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def auth_headers(db):
    """Create authenticated user and return headers."""
    # Create a test user
    user = Users(
        UserID="user-test-001",
        user_email="test@example.com",
        user_name="Test User",
        user_password_hash="dummy-hash",
        tenant_id=1,
        is_active=True,
    )
    db.add(user)
    db.commit()

    # Return auth headers (in real app, would be JWT token)
    return {"X-User-ID": "user-test-001", "X-Tenant-ID": "1"}


@pytest.fixture
def setup_data(db):
    """Set up test data: client, project, employee, allocation, timesheet."""
    # Create BU context
    bu = BusinessUnitContext(
        bu_code="NA",
        bu_name="North America",
        tenant_id=1,
    )
    db.add(bu)
    db.flush()

    # Create client
    client_obj = Client(
        id="client-test-001",
        tenant_id=1,
        company_name="Test Client Inc.",
        billing_currency="USD",
        bu_context_id=bu.id,
    )
    db.add(client_obj)
    db.flush()

    # Create client contact
    contact = ClientContact(
        id="contact-test-001",
        tenant_id=1,
        client_id=client_obj.id,
        name="John Billing",
        email="billing@client.com",
        role_type="ACCOUNTS",
        is_primary=True,
    )
    db.add(contact)
    db.flush()

    # Create project
    project = Project(
        id="proj-test-001",
        tenant_id=1,
        client_id=client_obj.id,
        project_name="Test Project",
        project_status="ACTIVE",
        start_date=date.today(),
    )
    db.add(project)
    db.flush()

    # Create employee
    employee = Employee(
        id="emp-test-001",
        tenant_id=1,
        first_name="John",
        last_name="Doe",
        employee_status="ACTIVE",
        delivery_engine="CORE",
        bu_context_id=bu.id,
    )
    db.add(employee)
    db.flush()

    # Create allocation
    allocation = EmployeeAllocation(
        id="alloc-test-001",
        tenant_id=1,
        employee_id=employee.id,
        project_id=project.id,
        allocation_status="ACTIVE",
        bill_rate_usd_cents=50_00,  # $50/hour
        start_date=date.today() - timedelta(days=30),
    )
    db.add(allocation)
    db.flush()

    # Create approved timesheet
    today = date.today()
    monday = today - timedelta(days=today.weekday())

    timesheet = Timesheet(
        id="ts-test-001",
        tenant_id=1,
        employee_id=employee.id,
        allocation_id=allocation.id,
        bu_context_id=bu.id,
        week_starting_date=monday,
        total_hours=40,
        billable_hours=40,
        non_billable_hours=0,
        status="APPROVED",
        submitted_at=datetime.utcnow(),
        approved_at=datetime.utcnow(),
        approved_by="user-001",
    )
    db.add(timesheet)
    db.flush()

    # Add timesheet entries
    for i in range(5):
        entry_date = monday + timedelta(days=i)
        entry = TimesheetEntry(
            id=f"ts-entry-{i}",
            timesheet_id=timesheet.id,
            entry_date=entry_date,
            hours=8,
            entry_type="BILLABLE",
        )
        db.add(entry)

    db.commit()

    return {
        "bu": bu,
        "client": client_obj,
        "contact": contact,
        "project": project,
        "employee": employee,
        "allocation": allocation,
        "timesheet": timesheet,
    }


# ============================================================================
# TEST: POST /invoices/generate
# ============================================================================
logger = logging.getLogger(__name__)

class TestGenerateInvoiceEndpoint:
    """Test invoice generation endpoint."""

    def test_generate_invoice_success(self, auth_headers, setup_data, db):
        """Test successful invoice generation."""
        data = setup_data
        timesheet = data["timesheet"]
        project = data["project"]
        client = data["client"]

        period_start = timesheet.week_starting_date
        period_end = period_start + timedelta(days=6)

        response = client.post(
            "/api/v1/invoices/generate",
            json={
                "project_id": project.id,
                "client_id": client.id,
                "billing_period_start": period_start.isoformat(),
                "billing_period_end": period_end.isoformat(),
                "currency": "USD",
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "DRAFT"
        assert data["project_id"] == project.id
        assert data["client_id"] == client.id
        assert data["line_item_count"] == 1
        assert data["billable_hours"] == 40.0
        assert data["total_usd_cents"] == 200_000

    def test_generate_invoice_invalid_dates(self, auth_headers, setup_data):
        """Test invoice generation with invalid date range."""
        data = setup_data
        project = data["project"]
        client = data["client"]

        today = date.today()

        response = client.post(
            "/api/v1/invoices/generate",
            json={
                "project_id": project.id,
                "client_id": client.id,
                "billing_period_start": today.isoformat(),
                "billing_period_end": (today - timedelta(days=1)).isoformat(),  # End before start
                "currency": "USD",
            },
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error

    def test_generate_invoice_project_not_found(self, auth_headers, setup_data):
        """Test invoice generation with non-existent project."""
        data = setup_data
        client = data["client"]

        response = client.post(
            "/api/v1/invoices/generate",
            json={
                "project_id": "nonexistent",
                "client_id": client.id,
                "billing_period_start": date.today().isoformat(),
                "billing_period_end": (date.today() + timedelta(days=7)).isoformat(),
            },
            headers=auth_headers,
        )

        assert response.status_code in (400, 404)


# ============================================================================
# TEST: GET /invoices/{id}/calculate
# ============================================================================

class TestCalculateBillAmountEndpoint:
    """Test bill amount calculation endpoint."""

    def test_calculate_bill_amount(self, auth_headers, setup_data, db):
        """Test calculating bill amount for invoice."""
        data = setup_data
        timesheet = data["timesheet"]
        project = data["project"]
        client = data["client"]

        # First generate invoice
        period_start = timesheet.week_starting_date
        period_end = period_start + timedelta(days=6)

        gen_response = client.post(
            "/api/v1/invoices/generate",
            json={
                "project_id": project.id,
                "client_id": client.id,
                "billing_period_start": period_start.isoformat(),
                "billing_period_end": period_end.isoformat(),
            },
            headers=auth_headers,
        )
        assert gen_response.status_code == 201
        invoice_id = gen_response.json()["invoice_id"]

        # Calculate bill amount
        calc_response = client.get(
            f"/api/v1/invoices/{invoice_id}/calculate",
            headers=auth_headers,
        )

        assert calc_response.status_code == 200
        calc_data = calc_response.json()
        assert calc_data["invoice_id"] == invoice_id
        assert calc_data["subtotal_usd_cents"] == 200_000
        assert calc_data["total_usd_cents"] == 200_000
        assert calc_data["line_item_count"] == 1
        assert calc_data["billable_hours"] == 40.0


# ============================================================================
# TEST: POST /invoices/{id}/send
# ============================================================================

class TestSendInvoiceEndpoint:
    """Test invoice sending endpoint."""

    def test_send_invoice_success(self, auth_headers, setup_data, db):
        """Test successful invoice send."""
        data = setup_data
        timesheet = data["timesheet"]
        project = data["project"]
        client = data["client"]

        # Generate invoice
        period_start = timesheet.week_starting_date
        period_end = period_start + timedelta(days=6)

        gen_response = client.post(
            "/api/v1/invoices/generate",
            json={
                "project_id": project.id,
                "client_id": client.id,
                "billing_period_start": period_start.isoformat(),
                "billing_period_end": period_end.isoformat(),
            },
            headers=auth_headers,
        )
        invoice_id = gen_response.json()["invoice_id"]

        # Send invoice
        send_response = client.post(
            f"/api/v1/invoices/{invoice_id}/send",
            json={
                "approved_by": "user-finance-001",
                "sent_by": "user-admin-001",
                "client_email": "billing@client.com",
            },
            headers=auth_headers,
        )

        assert send_response.status_code == 200
        send_data = send_response.json()
        assert send_data["status"] == "SENT"
        assert send_data["approved_by"] == "user-finance-001"
        assert send_data["client_email"] == "billing@client.com"


# ============================================================================
# TEST: POST /invoices/{id}/pay
# ============================================================================

class TestTrackPaymentEndpoint:
    """Test payment tracking endpoint."""

    def test_track_payment_success(self, auth_headers, setup_data, db):
        """Test recording payment."""
        data = setup_data
        timesheet = data["timesheet"]
        project = data["project"]
        client = data["client"]

        # Generate invoice
        period_start = timesheet.week_starting_date
        period_end = period_start + timedelta(days=6)

        gen_response = client.post(
            "/api/v1/invoices/generate",
            json={
                "project_id": project.id,
                "client_id": client.id,
                "billing_period_start": period_start.isoformat(),
                "billing_period_end": period_end.isoformat(),
            },
            headers=auth_headers,
        )
        invoice_id = gen_response.json()["invoice_id"]

        # Send invoice
        client.post(
            f"/api/v1/invoices/{invoice_id}/send",
            json={
                "approved_by": "user-finance-001",
                "sent_by": "user-admin-001",
            },
            headers=auth_headers,
        )

        # Record payment
        pay_response = client.post(
            f"/api/v1/invoices/{invoice_id}/pay",
            json={
                "amount_received_usd_cents": 200_000,
                "payment_date": datetime.utcnow().isoformat(),
                "payment_method": "wire",
                "reference_number": "WIRE-001",
            },
            headers=auth_headers,
        )

        assert pay_response.status_code == 200
        pay_data = pay_response.json()
        assert pay_data["amount_received_usd_cents"] == 200_000
        assert pay_data["is_fully_paid"] is True
        assert pay_data["status"] == "PAID"


# ============================================================================
# TEST: GET /invoices/{id}
# ============================================================================

class TestGetInvoiceEndpoint:
    """Test get invoice endpoint."""

    def test_get_invoice_details(self, auth_headers, setup_data, db):
        """Test getting invoice details."""
        data = setup_data
        timesheet = data["timesheet"]
        project = data["project"]
        client = data["client"]

        # Generate invoice
        period_start = timesheet.week_starting_date
        period_end = period_start + timedelta(days=6)

        gen_response = client.post(
            "/api/v1/invoices/generate",
            json={
                "project_id": project.id,
                "client_id": client.id,
                "billing_period_start": period_start.isoformat(),
                "billing_period_end": period_end.isoformat(),
            },
            headers=auth_headers,
        )
        invoice_id = gen_response.json()["invoice_id"]

        # Get invoice
        get_response = client.get(
            f"/api/v1/invoices/{invoice_id}",
            headers=auth_headers,
        )

        assert get_response.status_code == 200
        inv_data = get_response.json()
        assert inv_data["id"] == invoice_id
        assert inv_data["status"] == "DRAFT"
        assert len(inv_data["line_items"]) == 1


# ============================================================================
# TEST: GET /invoices
# ============================================================================

class TestListInvoicesEndpoint:
    """Test list invoices endpoint."""

    def test_list_invoices(self, auth_headers, setup_data, db):
        """Test listing invoices."""
        data = setup_data
        timesheet = data["timesheet"]
        project = data["project"]
        client = data["client"]

        # Generate invoice
        period_start = timesheet.week_starting_date
        period_end = period_start + timedelta(days=6)

        client.post(
            "/api/v1/invoices/generate",
            json={
                "project_id": project.id,
                "client_id": client.id,
                "billing_period_start": period_start.isoformat(),
                "billing_period_end": period_end.isoformat(),
            },
            headers=auth_headers,
        )

        # List invoices
        list_response = client.get(
            "/api/v1/invoices",
            headers=auth_headers,
        )

        assert list_response.status_code == 200
        list_data = list_response.json()
        assert "invoices" in list_data
        assert list_data["total_count"] >= 1

    def test_list_invoices_filter_by_status(self, auth_headers, setup_data, db):
        """Test filtering invoices by status."""
        data = setup_data
        timesheet = data["timesheet"]
        project = data["project"]
        client_obj = data["client"]

        # Generate invoice
        period_start = timesheet.week_starting_date
        period_end = period_start + timedelta(days=6)

        client.post(
            "/api/v1/invoices/generate",
            json={
                "project_id": project.id,
                "client_id": client_obj.id,
                "billing_period_start": period_start.isoformat(),
                "billing_period_end": period_end.isoformat(),
            },
            headers=auth_headers,
        )

        # List DRAFT invoices
        list_response = client.get(
            "/api/v1/invoices?status=DRAFT",
            headers=auth_headers,
        )

        assert list_response.status_code == 200
        list_data = list_response.json()
        assert all(inv["status"] == "DRAFT" for inv in list_data["invoices"])
