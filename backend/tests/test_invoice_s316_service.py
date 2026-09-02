"""
HRMS-0316 -- Invoice Service Tests
Comprehensive test coverage for invoice generation, calculation, sending, and payment tracking.
import logging
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceLineItem
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.employee import Employee
from app.models.project import Project
from app.models.client import Client
from app.models.employee_allocation import EmployeeAllocation
from app.models.business_unit_context import BusinessUnitContext
from app.services.invoice_s316_service import (
    InvoiceS316Service,
    InvoiceError,
    UnapprovedTimesheetBlocksInvoice,
    OpenDisputeBlocksInvoice,
    InvalidInvoiceTransition,
    InvoicePaymentError,
)


@pytest.fixture
def service():
    """Fixture for InvoiceS316Service."""
    return InvoiceS316Service()


@pytest.fixture
def bu_context(db: Session):
    """Create a business unit context."""
    bu = BusinessUnitContext(
        bu_code="NA",
        bu_name="North America",
        tenant_id=1,
    )
    db.add(bu)
    db.commit()
    return bu


@pytest.fixture
def client(db: Session, bu_context):
    """Create a test client."""
    c = Client(
        id="client-test-001",
        tenant_id=1,
        company_name="Test Client Inc.",
        billing_currency="USD",
        bu_context_id=bu_context.id,
    )
    db.add(c)
    db.commit()
    return c


@pytest.fixture
def project(db: Session, client):
    """Create a test project."""
    p = Project(
        id="proj-test-001",
        tenant_id=1,
        client_id=client.id,
        project_name="Test Project",
        project_status="ACTIVE",
        start_date=date.today(),
    )
    db.add(p)
    db.commit()
    return p


@pytest.fixture
def employee(db: Session, bu_context):
    """Create a test employee."""
    e = Employee(
        id="emp-test-001",
        tenant_id=1,
        first_name="John",
        last_name="Doe",
        employee_status="ACTIVE",
        delivery_engine="CORE",
        bu_context_id=bu_context.id,
    )
    db.add(e)
    db.commit()
    return e


@pytest.fixture
def allocation(db: Session, employee, project):
    """Create an employee allocation."""
    a = EmployeeAllocation(
        id="alloc-test-001",
        tenant_id=1,
        employee_id=employee.id,
        project_id=project.id,
        allocation_status="ACTIVE",
        bill_rate_usd_cents=50_00,  # $50/hour
        start_date=date.today() - timedelta(days=30),
    )
    db.add(a)
    db.commit()
    return a


@pytest.fixture
def approved_timesheet(db: Session, employee, allocation, bu_context):
    """Create an approved timesheet."""
    # Get Monday of current week
    today = date.today()
    monday = today - timedelta(days=today.weekday())

    ts = Timesheet(
        id="ts-test-001",
        tenant_id=1,
        employee_id=employee.id,
        allocation_id=allocation.id,
        bu_context_id=bu_context.id,
        week_starting_date=monday,
        total_hours=40,
        billable_hours=40,
        non_billable_hours=0,
        status="APPROVED",
        submitted_at=datetime.utcnow(),
        approved_at=datetime.utcnow(),
        approved_by="user-001",
    )
    db.add(ts)
    db.commit()

    # Add timesheet entries
    for i in range(5):  # Mon-Fri
        entry_date = monday + timedelta(days=i)
        entry = TimesheetEntry(
            id=f"ts-entry-{i}",
            timesheet_id=ts.id,
            entry_date=entry_date,
            hours=8,
            entry_type="BILLABLE",
        )
        db.add(entry)
    db.commit()
    return ts


# ============================================================================
# TEST: generate_invoice()
# ============================================================================
logger = logging.getLogger(__name__)

class TestGenerateInvoice:
    """Test invoice generation from approved timesheets."""

    def test_generate_invoice_success(
        self, service, db, project, client, approved_timesheet, allocation
    ):
        """Test successful invoice generation."""
        period_start = approved_timesheet.week_starting_date
        period_end = period_start + timedelta(days=6)

        invoice = service.generate_invoice(
            db,
            tenant_id=1,
            project_id=project.id,
            client_id=client.id,
            billing_period_start=period_start,
            billing_period_end=period_end,
        )

        assert invoice.status == "DRAFT"
        assert invoice.project_id == project.id
        assert invoice.client_id == client.id
        assert invoice.billing_period_start == period_start
        assert invoice.billing_period_end == period_end

        # Check line items
        line_items = db.query(InvoiceLineItem).filter(
            InvoiceLineItem.invoice_id == invoice.id
        ).all()
        assert len(line_items) == 1
        assert line_items[0].hours == 40
        assert line_items[0].rate_usd_cents == 50_00

        # Check total calculation
        expected_total = int(40 * 50_00)
        assert invoice.total_usd_cents == expected_total

    def test_generate_invoice_unapproved_timesheet_blocks(
        self, service, db, employee, allocation, bu_context
    ):
        """Test R-10: Unapproved timesheet blocks invoice generation."""
        # Create a DRAFT timesheet
        today = date.today()
        monday = today - timedelta(days=today.weekday())

        ts = Timesheet(
            id="ts-draft-001",
            tenant_id=1,
            employee_id=employee.id,
            allocation_id=allocation.id,
            bu_context_id=bu_context.id,
            week_starting_date=monday,
            total_hours=40,
            billable_hours=40,
            status="DRAFT",
        )
        db.add(ts)
        db.commit()

        period_start = monday
        period_end = monday + timedelta(days=6)

        with pytest.raises(UnapprovedTimesheetBlocksInvoice):
            service.generate_invoice(
                db,
                tenant_id=1,
                project_id=allocation.project_id,
                client_id="client-test-001",
                billing_period_start=period_start,
                billing_period_end=period_end,
            )

    def test_generate_invoice_no_timesheets(self, service, db, project, client):
        """Test invoice generation with no timesheets in period."""
        period_start = date.today()
        period_end = period_start + timedelta(days=7)

        with pytest.raises(InvoiceError, match="No approved timesheets found"):
            service.generate_invoice(
                db,
                tenant_id=1,
                project_id=project.id,
                client_id=client.id,
                billing_period_start=period_start,
                billing_period_end=period_end,
            )

    def test_generate_invoice_project_not_found(self, service, db, client):
        """Test invoice generation with non-existent project."""
        with pytest.raises(InvoiceError, match="Project .* not found"):
            service.generate_invoice(
                db,
                tenant_id=1,
                project_id="nonexistent-proj",
                client_id=client.id,
                billing_period_start=date.today(),
                billing_period_end=date.today() + timedelta(days=7),
            )

    def test_generate_invoice_client_not_found(self, service, db, project):
        """Test invoice generation with non-existent client."""
        with pytest.raises(InvoiceError, match="Client .* not found"):
            service.generate_invoice(
                db,
                tenant_id=1,
                project_id=project.id,
                client_id="nonexistent-client",
                billing_period_start=date.today(),
                billing_period_end=date.today() + timedelta(days=7),
            )


# ============================================================================
# TEST: calculate_bill_amount()
# ============================================================================

class TestCalculateBillAmount:
    """Test bill amount calculation."""

    def test_calculate_bill_amount(
        self, service, db, project, client, approved_timesheet, allocation
    ):
        """Test calculating bill amount for an invoice."""
        # Generate invoice first
        period_start = approved_timesheet.week_starting_date
        period_end = period_start + timedelta(days=6)

        invoice = service.generate_invoice(
            db,
            tenant_id=1,
            project_id=project.id,
            client_id=client.id,
            billing_period_start=period_start,
            billing_period_end=period_end,
        )
        db.commit()

        # Calculate bill amount
        result = service.calculate_bill_amount(
            db,
            invoice_id=invoice.id,
            tenant_id=1,
        )

        assert result["invoice_id"] == invoice.id
        assert result["subtotal_usd_cents"] == 200_000  # 40 hours * $50/hr
        assert result["total_usd_cents"] == 200_000  # No tax for now
        assert result["line_item_count"] == 1
        assert result["billable_hours"] == 40.0

    def test_calculate_bill_amount_invoice_not_found(self, service, db):
        """Test calculating bill amount for non-existent invoice."""
        with pytest.raises(InvoiceError, match="Invoice .* not found"):
            service.calculate_bill_amount(
                db,
                invoice_id="nonexistent-inv",
                tenant_id=1,
            )


# ============================================================================
# TEST: send_invoice()
# ============================================================================

class TestSendInvoice:
    """Test invoice sending and approval."""

    def test_send_invoice_success(
        self, service, db, project, client, approved_timesheet
    ):
        """Test successful invoice send."""
        # Generate invoice first
        period_start = approved_timesheet.week_starting_date
        period_end = period_start + timedelta(days=6)

        invoice = service.generate_invoice(
            db,
            tenant_id=1,
            project_id=project.id,
            client_id=client.id,
            billing_period_start=period_start,
            billing_period_end=period_end,
        )
        db.commit()

        # Send invoice
        result = service.send_invoice(
            db,
            invoice_id=invoice.id,
            tenant_id=1,
            approved_by="user-finance-001",
            sent_by="user-admin-001",
            client_email="billing@client.com",
        )

        assert result.status == "SENT"
        assert result.approved_by == "user-finance-001"
        assert result.approved_at is not None
        assert result.sent_at is not None

    def test_send_invoice_not_draft_fails(
        self, service, db, project, client, approved_timesheet
    ):
        """Test sending invoice that's not in DRAFT status."""
        # Generate and send invoice
        period_start = approved_timesheet.week_starting_date
        period_end = period_start + timedelta(days=6)

        invoice = service.generate_invoice(
            db,
            tenant_id=1,
            project_id=project.id,
            client_id=client.id,
            billing_period_start=period_start,
            billing_period_end=period_end,
        )
        db.commit()

        # First send succeeds
        service.send_invoice(
            db,
            invoice_id=invoice.id,
            tenant_id=1,
            approved_by="user-finance-001",
            sent_by="user-admin-001",
            client_email="billing@client.com",
        )
        db.commit()

        # Second send fails
        with pytest.raises(InvalidInvoiceTransition):
            service.send_invoice(
                db,
                invoice_id=invoice.id,
                tenant_id=1,
                approved_by="user-finance-001",
                sent_by="user-admin-001",
                client_email="billing@client.com",
            )


# ============================================================================
# TEST: track_payment()
# ============================================================================

class TestTrackPayment:
    """Test payment tracking."""

    def test_track_payment_full_payment(
        self, service, db, project, client, approved_timesheet
    ):
        """Test recording a full payment."""
        # Generate and send invoice
        period_start = approved_timesheet.week_starting_date
        period_end = period_start + timedelta(days=6)

        invoice = service.generate_invoice(
            db,
            tenant_id=1,
            project_id=project.id,
            client_id=client.id,
            billing_period_start=period_start,
            billing_period_end=period_end,
        )
        db.commit()

        # Send invoice
        service.send_invoice(
            db,
            invoice_id=invoice.id,
            tenant_id=1,
            approved_by="user-finance-001",
            sent_by="user-admin-001",
            client_email="billing@client.com",
        )
        db.commit()

        # Record full payment
        result = service.track_payment(
            db,
            invoice_id=invoice.id,
            tenant_id=1,
            amount_received_usd_cents=200_000,
            payment_date=datetime.utcnow(),
            payment_method="wire",
            reference_number="WIRE-001",
        )

        assert result["invoice_id"] == invoice.id
        assert result["amount_received_usd_cents"] == 200_000
        assert result["total_paid_usd_cents"] == 200_000
        assert result["remaining_usd_cents"] == 0
        assert result["status"] == "PAID"
        assert result["is_fully_paid"] is True

    def test_track_payment_partial_payment(
        self, service, db, project, client, approved_timesheet
    ):
        """Test recording a partial payment."""
        # Generate and send invoice
        period_start = approved_timesheet.week_starting_date
        period_end = period_start + timedelta(days=6)

        invoice = service.generate_invoice(
            db,
            tenant_id=1,
            project_id=project.id,
            client_id=client.id,
            billing_period_start=period_start,
            billing_period_end=period_end,
        )
        db.commit()

        service.send_invoice(
            db,
            invoice_id=invoice.id,
            tenant_id=1,
            approved_by="user-finance-001",
            sent_by="user-admin-001",
            client_email="billing@client.com",
        )
        db.commit()

        # Record partial payment
        result = service.track_payment(
            db,
            invoice_id=invoice.id,
            tenant_id=1,
            amount_received_usd_cents=100_000,  # 50% payment
            payment_date=datetime.utcnow(),
            payment_method="check",
            reference_number="CHK-001",
        )

        assert result["amount_received_usd_cents"] == 100_000
        assert result["total_paid_usd_cents"] == 100_000
        assert result["remaining_usd_cents"] == 100_000
        assert result["status"] == "SENT"  # Still SENT for partial payment
        assert result["is_fully_paid"] is False

    def test_track_payment_invalid_amount(
        self, service, db, project, client, approved_timesheet
    ):
        """Test tracking payment with invalid amount."""
        # Generate and send invoice
        period_start = approved_timesheet.week_starting_date
        period_end = period_start + timedelta(days=6)

        invoice = service.generate_invoice(
            db,
            tenant_id=1,
            project_id=project.id,
            client_id=client.id,
            billing_period_start=period_start,
            billing_period_end=period_end,
        )
        db.commit()

        service.send_invoice(
            db,
            invoice_id=invoice.id,
            tenant_id=1,
            approved_by="user-finance-001",
            sent_by="user-admin-001",
            client_email="billing@client.com",
        )
        db.commit()

        # Try to record payment with 0 amount
        with pytest.raises(InvoicePaymentError, match="must be positive"):
            service.track_payment(
                db,
                invoice_id=invoice.id,
                tenant_id=1,
                amount_received_usd_cents=0,
                payment_date=datetime.utcnow(),
                payment_method="wire",
            )

        # Try with negative amount
        with pytest.raises(InvoicePaymentError, match="must be positive"):
            service.track_payment(
                db,
                invoice_id=invoice.id,
                tenant_id=1,
                amount_received_usd_cents=-100,
                payment_date=datetime.utcnow(),
                payment_method="wire",
            )


# ============================================================================
# TEST: Helper methods
# ============================================================================

class TestHelperMethods:
    """Test helper methods."""

    def test_get_invoices_by_status(
        self, service, db, project, client, approved_timesheet
    ):
        """Test getting invoices by status."""
        period_start = approved_timesheet.week_starting_date
        period_end = period_start + timedelta(days=6)

        # Create invoice (DRAFT)
        invoice = service.generate_invoice(
            db,
            tenant_id=1,
            project_id=project.id,
            client_id=client.id,
            billing_period_start=period_start,
            billing_period_end=period_end,
        )
        db.commit()

        # Get DRAFT invoices
        drafts = service.get_invoices_by_status(
            db,
            tenant_id=1,
            status="DRAFT",
        )
        assert len(drafts) >= 1
        assert any(inv.id == invoice.id for inv in drafts)

    def test_get_invoices_by_client(
        self, service, db, project, client, approved_timesheet
    ):
        """Test getting invoices by client."""
        period_start = approved_timesheet.week_starting_date
        period_end = period_start + timedelta(days=6)

        invoice = service.generate_invoice(
            db,
            tenant_id=1,
            project_id=project.id,
            client_id=client.id,
            billing_period_start=period_start,
            billing_period_end=period_end,
        )
        db.commit()

        # Get invoices for this client
        invoices = service.get_invoices_by_client(
            db,
            tenant_id=1,
            client_id=client.id,
        )
        assert len(invoices) >= 1
        assert any(inv.id == invoice.id for inv in invoices)
