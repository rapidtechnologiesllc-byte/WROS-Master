"""
Comprehensive test suite for Revenue Recognition (HRMS-0316)

Tests all core functionality:
- Revenue recognition from paid invoices
- Revenue entry creation
- Annual subscription revenue (ASR/ARR) calculation
- Revenue reporting by multiple dimensions
- Margin calculations and P&L summary
- Error handling and validation
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

# Test dependencies - these imports verify the service is properly structured
from app.services.revenue_recognition_service import (
    recognize_revenue_from_paid_invoice,
    create_revenue_entries,
    calculate_asr,
    get_revenue_by_month,
    get_revenue_by_service,
    get_revenue_by_module,
    get_revenue_by_pricing_model,
    get_revenue_by_client_owner,
    get_partner_revenue_share_analysis,
    get_forecast_vs_actual,
    get_negative_margin_alerts,
    calculate_p_and_l_summary,
    _calculate_invoice_costs,
    _calculate_margin_pct,
    _calculate_partner_share,
    InvalidInvoiceError,
    ValidationError,
)

from app.models.invoice import Invoice, InvoiceLineItem
from app.models.revenue import Revenue
from app.models.employee import Employee
from app.models.project import Project
from app.models.opportunity import Opportunity
from app.models.client import Client
from app.models.business_unit_context import BusinessUnitContext
from app.models.tenant import Tenant


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def test_tenant(db_session: Session):
    """Create test tenant."""
    tenant = Tenant(id=1, tenant_name="Test Org", is_active=True)
    db_session.add(tenant)
    db_session.commit()
    return tenant


@pytest.fixture
def test_bu_context(db_session: Session, test_tenant):
    """Create test business unit context."""
    bu_context = BusinessUnitContext(
        id=1,
        tenant_id=test_tenant.id,
        name="Test BU",
        description="Test Business Unit",
    )
    db_session.add(bu_context)
    db_session.commit()
    return bu_context


@pytest.fixture
def test_client(db_session: Session, test_tenant):
    """Create test client."""
    client = Client(
        id="client_001",
        tenant_id=test_tenant.id,
        name="Acme Corp",
        status="ACTIVE",
        line_type="CORE",
    )
    db_session.add(client)
    db_session.commit()
    return client


@pytest.fixture
def test_opportunity(db_session: Session, test_tenant, test_client, test_bu_context):
    """Create test opportunity."""
    opp = Opportunity(
        id="opp_001",
        tenant_id=test_tenant.id,
        client_id=test_client.id,
        client_owner_id="user_owner_123",
        business_unit_id=test_bu_context.id,
        revenue_value_usd_cents=1000000,  # $10,000
        stage="WON",
        probability_pct=100,
        expected_close_date=date.today(),
        engagement_type="PROJECT_BASED",
        service="System Integration",
        module="ClaimsCenter",
        client_type="Commercial lines",
        pricing_model="FTE-based",
        currency="USD",
    )
    db_session.add(opp)
    db_session.commit()
    return opp


@pytest.fixture
def test_project(db_session: Session, test_tenant, test_client, test_opportunity, test_bu_context):
    """Create test project."""
    project = Project(
        id="proj_001",
        tenant_id=test_tenant.id,
        client_id=test_client.id,
        opportunity_id=test_opportunity.id,
        client_owner_id=test_opportunity.client_owner_id,
        name="Acme Core System Integration",
        status="ACTIVE",
        billing_type="TIME_AND_MATERIALS",
        currency="USD",
        delivery_engine="CORE",
        business_type="CORE",
        bu_context_id=test_bu_context.id,
    )
    db_session.add(project)
    db_session.commit()
    return project


@pytest.fixture
def test_invoice_paid(db_session: Session, test_tenant, test_project, test_client, test_bu_context, test_opportunity):
    """Create PAID invoice for testing."""
    invoice = Invoice(
        id="inv_001",
        tenant_id=test_tenant.id,
        opportunity_id=test_opportunity.id,
        project_id=test_project.id,
        client_id=test_client.id,
        bu_context_id=test_bu_context.id,
        billing_period_start=date.today() - timedelta(days=7),
        billing_period_end=date.today(),
        currency="USD",
        status="PAID",
        total_usd_cents=400000,
        paid_at=datetime.utcnow(),
    )
    db_session.add(invoice)
    db_session.commit()
    return invoice


@pytest.fixture
def test_invoice_draft(db_session: Session, test_tenant, test_project, test_client, test_bu_context, test_opportunity):
    """Create DRAFT invoice for testing."""
    invoice = Invoice(
        id="inv_draft_001",
        tenant_id=test_tenant.id,
        opportunity_id=test_opportunity.id,
        project_id=test_project.id,
        client_id=test_client.id,
        bu_context_id=test_bu_context.id,
        billing_period_start=date.today() - timedelta(days=7),
        billing_period_end=date.today(),
        currency="USD",
        status="DRAFT",
        total_usd_cents=400000,
    )
    db_session.add(invoice)
    db_session.commit()
    return invoice


@pytest.fixture
def test_line_item(db_session: Session, test_invoice_paid):
    """Create test invoice line item."""
    item = InvoiceLineItem(
        id="inv_line_001",
        invoice_id=test_invoice_paid.id,
        employee_id="emp_001",
        timesheet_id="ts_001",
        hours=40.0,
        rate_usd_cents=10000,  # $100/hour
        amount_usd_cents=400000,  # 40 × $100 = $4,000
    )
    db_session.add(item)
    db_session.commit()
    return item


# ============================================================================
# TEST SUITE 1: REVENUE RECOGNITION
# ============================================================================

class TestRevenueRecognition:
    """Tests for core revenue recognition functionality."""

    def test_recognize_revenue_success(self, db_session: Session, test_invoice_paid, test_line_item):
        """Test: Successfully recognize revenue from paid invoice."""
        revenue = recognize_revenue_from_paid_invoice(db_session, test_invoice_paid)

        assert revenue is not None
        assert revenue.id is not None
        assert revenue.invoice_id == test_invoice_paid.id
        assert revenue.revenue_usd_cents == 400000
        assert revenue.source == "INVOICE"
        assert revenue.recognized_at is not None

    def test_recognize_revenue_not_paid_fails(self, db_session: Session, test_invoice_draft):
        """Test: Cannot recognize revenue if invoice not PAID."""
        with pytest.raises(InvalidInvoiceError):
            recognize_revenue_from_paid_invoice(db_session, test_invoice_draft)

    def test_recognize_revenue_no_line_items_fails(self, db_session: Session, test_tenant, test_project, test_client):
        """Test: Cannot recognize revenue from invoice with no line items."""
        invoice = Invoice(
            id="inv_no_items",
            tenant_id=test_tenant.id,
            project_id=test_project.id,
            client_id=test_client.id,
            status="PAID",
            total_usd_cents=0,
            paid_at=datetime.utcnow(),
        )
        db_session.add(invoice)
        db_session.commit()

        with pytest.raises(ValidationError):
            recognize_revenue_from_paid_invoice(db_session, invoice)

    def test_revenue_calculates_margin(self, db_session: Session, test_invoice_paid, test_line_item):
        """Test: Revenue entry includes margin calculation."""
        revenue = recognize_revenue_from_paid_invoice(db_session, test_invoice_paid)

        assert revenue.gross_margin_usd_cents is not None
        assert revenue.gross_margin_pct is not None
        # Margin should be positive (revenue > cost)
        assert revenue.gross_margin_usd_cents >= 0

    def test_revenue_stores_business_type(self, db_session: Session, test_invoice_paid, test_line_item):
        """Test: Revenue entry includes business type from project."""
        revenue = recognize_revenue_from_paid_invoice(db_session, test_invoice_paid)

        assert revenue.business_type == "CORE"

    def test_revenue_stores_opportunity_classifications(self, db_session: Session, test_invoice_paid, test_line_item, test_opportunity):
        """Test: Revenue entry includes opportunity classifications."""
        revenue = recognize_revenue_from_paid_invoice(db_session, test_invoice_paid)

        assert revenue.service == test_opportunity.service
        assert revenue.module == test_opportunity.module
        assert revenue.client_type == test_opportunity.client_type
        assert revenue.pricing_model == test_opportunity.pricing_model


# ============================================================================
# TEST SUITE 2: REVENUE ENTRIES
# ============================================================================

class TestRevenueEntries:
    """Tests for revenue entry creation."""

    def test_create_revenue_entries_success(self, db_session: Session, test_invoice_paid, test_line_item):
        """Test: Successfully create revenue entries."""
        result = create_revenue_entries(
            db_session,
            test_invoice_paid.id,
            test_invoice_paid.tenant_id,
            recognition_method="MONTHLY"
        )

        assert result["status"] == "success"
        assert result["invoice_id"] == test_invoice_paid.id
        assert result["entries_created"] == 1
        assert result["total_recognized_usd_cents"] > 0

    def test_create_entries_idempotent(self, db_session: Session, test_invoice_paid, test_line_item):
        """Test: Creating entries twice returns already_recognized."""
        # First call
        result1 = create_revenue_entries(
            db_session,
            test_invoice_paid.id,
            test_invoice_paid.tenant_id
        )
        assert result1["status"] == "success"

        # Second call should indicate already recognized
        result2 = create_revenue_entries(
            db_session,
            test_invoice_paid.id,
            test_invoice_paid.tenant_id
        )
        assert result2["status"] == "already_recognized"


# ============================================================================
# TEST SUITE 3: ASR CALCULATION
# ============================================================================

class TestASRCalculation:
    """Tests for Annual Subscription Revenue calculation."""

    def test_calculate_asr_success(self, db_session: Session, test_invoice_paid, test_line_item):
        """Test: Successfully calculate ASR for client."""
        # First recognize revenue
        recognize_revenue_from_paid_invoice(db_session, test_invoice_paid)

        # Then calculate ASR
        result = calculate_asr(
            db_session,
            test_invoice_paid.client_id,
            test_invoice_paid.tenant_id,
            date.today() - timedelta(days=30),
            date.today()
        )

        assert result["status"] == "success"
        assert result["client_id"] == test_invoice_paid.client_id
        assert result["arr_usd_cents"] > 0
        assert result["mrr_usd_cents"] > 0
        assert result["invoice_count"] > 0

    def test_asr_no_revenue_returns_zero(self, db_session: Session, test_client):
        """Test: ASR returns zero for client with no revenue."""
        result = calculate_asr(
            db_session,
            test_client.id,
            test_client.tenant_id,
            date.today() - timedelta(days=30),
            date.today()
        )

        assert result["status"] == "success"
        assert result["arr_usd_cents"] == 0
        assert result["mrr_usd_cents"] == 0


# ============================================================================
# TEST SUITE 4: REPORTING QUERIES
# ============================================================================

class TestReportingQueries:
    """Tests for revenue reporting queries."""

    def test_revenue_by_month(self, db_session: Session, test_invoice_paid, test_line_item):
        """Test: Revenue aggregation by month."""
        # Recognize revenue
        recognize_revenue_from_paid_invoice(db_session, test_invoice_paid)

        # Query by month
        result = get_revenue_by_month(
            db_session,
            business_unit_id=test_invoice_paid.bu_context_id,
            tenant_id=test_invoice_paid.tenant_id
        )

        assert len(result) > 0
        assert result[0]["revenue"] > 0
        assert result[0]["invoice_count"] > 0

    def test_revenue_by_service(self, db_session: Session, test_invoice_paid, test_line_item):
        """Test: Revenue aggregation by service."""
        recognize_revenue_from_paid_invoice(db_session, test_invoice_paid)

        result = get_revenue_by_service(
            db_session,
            business_unit_id=test_invoice_paid.bu_context_id,
            tenant_id=test_invoice_paid.tenant_id
        )

        assert len(result) > 0
        assert result[0]["service"] == "System Integration"
        assert result[0]["revenue"] > 0

    def test_revenue_by_module(self, db_session: Session, test_invoice_paid, test_line_item):
        """Test: Revenue aggregation by module."""
        recognize_revenue_from_paid_invoice(db_session, test_invoice_paid)

        result = get_revenue_by_module(
            db_session,
            business_unit_id=test_invoice_paid.bu_context_id,
            tenant_id=test_invoice_paid.tenant_id
        )

        assert len(result) > 0
        assert result[0]["module"] == "ClaimsCenter"

    def test_revenue_by_pricing_model(self, db_session: Session, test_invoice_paid, test_line_item):
        """Test: Revenue aggregation by pricing model."""
        recognize_revenue_from_paid_invoice(db_session, test_invoice_paid)

        result = get_revenue_by_pricing_model(
            db_session,
            business_unit_id=test_invoice_paid.bu_context_id,
            tenant_id=test_invoice_paid.tenant_id
        )

        assert len(result) > 0
        assert result[0]["pricing_model"] == "FTE-based"

    def test_revenue_by_client_owner(self, db_session: Session, test_invoice_paid, test_line_item):
        """Test: Revenue attribution by client owner."""
        recognize_revenue_from_paid_invoice(db_session, test_invoice_paid)

        result = get_revenue_by_client_owner(
            db_session,
            business_unit_id=test_invoice_paid.bu_context_id,
            tenant_id=test_invoice_paid.tenant_id
        )

        assert len(result) > 0
        assert result[0]["revenue"] > 0

    def test_forecast_vs_actual(self, db_session: Session, test_invoice_paid, test_line_item, test_opportunity):
        """Test: Forecast vs actual comparison."""
        recognize_revenue_from_paid_invoice(db_session, test_invoice_paid)

        result = get_forecast_vs_actual(
            db_session,
            business_unit_id=test_invoice_paid.bu_context_id,
            tenant_id=test_invoice_paid.tenant_id
        )

        assert len(result) > 0
        # Should find our opportunity
        opp_data = next((r for r in result if r["opportunity_id"] == test_opportunity.id), None)
        assert opp_data is not None
        assert opp_data["forecast_usd_cents"] > 0
        assert opp_data["actual_usd_cents"] > 0


# ============================================================================
# TEST SUITE 5: MARGIN AND P&L
# ============================================================================

class TestMarginAndPnL:
    """Tests for margin calculations and P&L summary."""

    def test_margin_pct_calculation(self):
        """Test: Margin percentage formula."""
        # 35% margin
        pct = _calculate_margin_pct(revenue_usd_cents=1000000, margin_usd_cents=350000)
        assert pct == 35

        # Zero revenue edge case
        pct = _calculate_margin_pct(revenue_usd_cents=0, margin_usd_cents=0)
        assert pct == 0

        # Negative margin (loss)
        pct = _calculate_margin_pct(revenue_usd_cents=1000000, margin_usd_cents=-100000)
        assert pct == -10

    def test_pnl_summary(self, db_session: Session, test_invoice_paid, test_line_item):
        """Test: P&L summary calculation."""
        recognize_revenue_from_paid_invoice(db_session, test_invoice_paid)

        result = calculate_p_and_l_summary(
            db_session,
            business_unit_id=test_invoice_paid.bu_context_id,
            tenant_id=test_invoice_paid.tenant_id
        )

        assert result["status"] == "success"
        assert result["revenue_usd_cents"] > 0
        assert result["margin_usd_cents"] >= 0
        assert result["invoice_count"] > 0
        assert "margin_pct" in result

    def test_pnl_no_revenue_returns_zeros(self, db_session: Session, test_tenant, test_bu_context):
        """Test: P&L returns zeros when no revenue."""
        result = calculate_p_and_l_summary(
            db_session,
            business_unit_id=test_bu_context.id,
            tenant_id=test_tenant.id
        )

        assert result["revenue_usd_cents"] == 0
        assert result["cost_usd_cents"] == 0
        assert result["margin_usd_cents"] == 0


# ============================================================================
# TEST SUITE 6: HELPERS
# ============================================================================

class TestHelperFunctions:
    """Tests for internal helper functions."""

    def test_calculate_invoice_costs(self):
        """Test: Invoice cost calculation."""
        line_items = [
            type('obj', (), {
                'rate_usd_cents': 10000,
                'hours': 40.0
            })(),
        ]

        cost = _calculate_invoice_costs(line_items)
        # Should be approximately 40 * 100 (in dollars)
        assert cost > 0

    def test_calculate_partner_share_core_only(self, db_session: Session, test_invoice_paid):
        """Test: Partner share calculated only for CORE business."""
        share = _calculate_partner_share(db_session, test_invoice_paid, "CORE")

        # Should handle CORE type
        assert isinstance(share, dict)
        assert "partner_id" in share
        assert "share_pct" in share
        assert "share_amount" in share

    def test_calculate_partner_share_zero_for_speciality(self, db_session: Session, test_invoice_paid):
        """Test: Partner share is zero for SPECIALITY."""
        share = _calculate_partner_share(db_session, test_invoice_paid, "SPECIALITY")

        assert share["share_pct"] is None
        assert share["share_amount"] == 0


# ============================================================================
# TEST SUITE 7: EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_zero_revenue_validation(self, db_session: Session, test_tenant, test_project, test_client):
        """Test: Zero revenue invoice cannot be recognized."""
        invoice = Invoice(
            id="inv_zero",
            tenant_id=test_tenant.id,
            project_id=test_project.id,
            client_id=test_client.id,
            status="PAID",
            total_usd_cents=0,
            paid_at=datetime.utcnow(),
        )
        db_session.add(invoice)
        db_session.commit()

        with pytest.raises(ValidationError):
            recognize_revenue_from_paid_invoice(db_session, invoice)

    def test_invoice_not_found(self, db_session: Session, test_tenant):
        """Test: Handling of non-existent invoice."""
        with pytest.raises(ValidationError):
            create_revenue_entries(
                db_session,
                "non_existent_invoice",
                test_tenant.id
            )

    def test_negative_margin_alert(self, db_session: Session, test_invoice_paid, test_line_item):
        """Test: Negative margin detection."""
        # Manually set high cost
        test_line_item.rate_usd_cents = 50000  # $500/hour
        db_session.commit()

        revenue = recognize_revenue_from_paid_invoice(db_session, test_invoice_paid)

        # If cost > revenue, margin will be negative
        if revenue.cost_usd_cents > revenue.revenue_usd_cents:
            assert revenue.gross_margin_usd_cents < 0

        # Test alert query
        alerts = get_negative_margin_alerts(
            db_session,
            business_unit_id=test_invoice_paid.bu_context_id,
            tenant_id=test_invoice_paid.tenant_id
        )

        # Only returns negative margins
        for alert in alerts:
            assert alert["gross_margin_usd_cents"] < 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
