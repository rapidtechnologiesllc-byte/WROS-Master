"""
import logging
Unit tests for Phase 1 Backend Models: Enums, Opportunity, Revenue, Invoice.

Tests cover:
- Opportunity model with service/module/client_type/pricing_model fields
- Revenue model for revenue recognition and P&L attribution
- Invoice model with opportunity_id link
- Enum validations
"""
import pytest
from datetime import datetime, date
from app.models.opportunity import Opportunity, ENGAGEMENT_TYPES
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.revenue import Revenue, REVENUE_SOURCES, BUSINESS_TYPES
from app.models.enums import SERVICE_TYPES, MODULE_TYPES, CLIENT_TYPES, PRICING_MODEL_TYPES

logger = logging.getLogger(__name__)

class TestEnumDefinitions:
    """Test that all enum types are defined and non-empty."""

    def test_service_types_defined(self):
        assert len(SERVICE_TYPES) > 0
        assert "Staff Augmentation" in SERVICE_TYPES
        assert "System Integration" in SERVICE_TYPES
        assert "Consulting & Advisory" in SERVICE_TYPES

    def test_module_types_defined(self):
        assert len(MODULE_TYPES) > 0
        assert "PolicyCenter" in MODULE_TYPES
        assert "ClaimsCenter" in MODULE_TYPES
        assert "Data and Analytics" in MODULE_TYPES

    def test_client_types_defined(self):
        assert len(CLIENT_TYPES) > 0
        assert "Personal lines" in CLIENT_TYPES
        assert "Commercial lines" in CLIENT_TYPES
        assert "Specialty lines" in CLIENT_TYPES

    def test_pricing_model_types_defined(self):
        assert len(PRICING_MODEL_TYPES) > 0
        assert "FTE-based" in PRICING_MODEL_TYPES
        assert "Fixed Bid" in PRICING_MODEL_TYPES
        assert "Time and Material (T&M)" in PRICING_MODEL_TYPES


class TestOpportunityModel:
    """Test Opportunity model with new enum fields."""

    def test_opportunity_has_engagement_type(self):
        """Opportunity should have engagement_type field with default STAFF_AUGMENTATION."""
        opp = Opportunity(
            id="opp_001",
            client_id="client_123",
            revenue_value_usd_cents=100000,
            stage="QUALIFICATION",
        )
        assert opp.engagement_type == "STAFF_AUGMENTATION"

    def test_opportunity_has_service_field(self):
        """Opportunity should have service field."""
        opp = Opportunity(
            id="opp_001",
            client_id="client_123",
            revenue_value_usd_cents=100000,
            stage="QUALIFICATION",
            service="Staff Augmentation",
        )
        assert opp.service == "Staff Augmentation"

    def test_opportunity_has_module_field(self):
        """Opportunity should have module field."""
        opp = Opportunity(
            id="opp_001",
            client_id="client_123",
            revenue_value_usd_cents=100000,
            stage="QUALIFICATION",
            module="PolicyCenter",
        )
        assert opp.module == "PolicyCenter"

    def test_opportunity_has_client_type_field(self):
        """Opportunity should have client_type field."""
        opp = Opportunity(
            id="opp_001",
            client_id="client_123",
            revenue_value_usd_cents=100000,
            stage="QUALIFICATION",
            client_type="Commercial lines",
        )
        assert opp.client_type == "Commercial lines"

    def test_opportunity_has_pricing_model_field(self):
        """Opportunity should have pricing_model field."""
        opp = Opportunity(
            id="opp_001",
            client_id="client_123",
            revenue_value_usd_cents=100000,
            stage="QUALIFICATION",
            pricing_model="FTE-based",
        )
        assert opp.pricing_model == "FTE-based"

    def test_opportunity_all_enum_fields_together(self):
        """Opportunity should support all new enum fields together."""
        opp = Opportunity(
            id="opp_001",
            client_id="client_123",
            revenue_value_usd_cents=100000,
            stage="PROSPECT",
            engagement_type="PROJECT_BASED",
            service="System Integration",
            module="ClaimsCenter",
            client_type="Personal lines",
            pricing_model="Fixed Bid",
            account_manager_id="emp_123",
            client_owner_id="user_456",
        )
        assert opp.engagement_type == "PROJECT_BASED"
        assert opp.service == "System Integration"
        assert opp.module == "ClaimsCenter"
        assert opp.client_type == "Personal lines"
        assert opp.pricing_model == "Fixed Bid"
        assert opp.account_manager_id == "emp_123"
        assert opp.client_owner_id == "user_456"

    def test_opportunity_enum_fields_nullable(self):
        """Service/module/client_type/pricing_model should be nullable."""
        opp = Opportunity(
            id="opp_001",
            client_id="client_123",
            revenue_value_usd_cents=100000,
            stage="QUALIFICATION",
        )
        assert opp.service is None
        assert opp.module is None
        assert opp.client_type is None
        assert opp.pricing_model is None


class TestInvoiceModel:
    """Test Invoice model with opportunity_id link."""

    def test_invoice_has_opportunity_id(self):
        """Invoice should have optional opportunity_id field."""
        invoice = Invoice(
            id="inv_001",
            project_id="proj_123",
            client_id="client_123",
            opportunity_id="opp_456",
            billing_period_start=date(2026, 8, 1),
            billing_period_end=date(2026, 8, 31),
            total_usd_cents=50000,
        )
        assert invoice.opportunity_id == "opp_456"

    def test_invoice_opportunity_id_nullable(self):
        """Invoice opportunity_id should be nullable (not all invoices trace to opportunities)."""
        invoice = Invoice(
            id="inv_001",
            project_id="proj_123",
            client_id="client_123",
            billing_period_start=date(2026, 8, 1),
            billing_period_end=date(2026, 8, 31),
            total_usd_cents=50000,
        )
        assert invoice.opportunity_id is None

    def test_invoice_all_fields(self):
        """Invoice should support all core fields."""
        invoice = Invoice(
            id="inv_001",
            tenant_id=1,
            opportunity_id="opp_123",
            project_id="proj_123",
            client_id="client_123",
            business_unit_id=1,
            billing_period_start=date(2026, 8, 1),
            billing_period_end=date(2026, 8, 31),
            status="DRAFT",
            total_usd_cents=50000,
            currency="USD",
        )
        assert invoice.opportunity_id == "opp_123"
        assert invoice.status == "DRAFT"
        assert invoice.total_usd_cents == 50000


class TestRevenueModel:
    """Test Revenue model for revenue recognition and P&L attribution."""

    def test_revenue_basic_fields(self):
        """Revenue should have all basic P&L tracking fields."""
        revenue = Revenue(
            id="rev_001",
            invoice_id="inv_123",
            opportunity_id="opp_456",
            client_id="client_789",
            revenue_usd_cents=50000,
            currency="USD",
        )
        assert revenue.invoice_id == "inv_123"
        assert revenue.opportunity_id == "opp_456"
        assert revenue.revenue_usd_cents == 50000

    def test_revenue_p_l_attribution(self):
        """Revenue should track Client Owner for P&L attribution."""
        revenue = Revenue(
            id="rev_001",
            invoice_id="inv_123",
            opportunity_id="opp_456",
            client_id="client_789",
            client_owner_id="user_101",
            revenue_usd_cents=50000,
            currency="USD",
        )
        assert revenue.client_owner_id == "user_101"

    def test_revenue_partner_share(self):
        """Revenue should track partner revenue share (Core business only)."""
        revenue = Revenue(
            id="rev_001",
            invoice_id="inv_123",
            opportunity_id="opp_456",
            client_id="client_789",
            partner_id="partner_123",
            partner_revenue_share_pct=20,
            partner_revenue_share_usd_cents=10000,
            revenue_usd_cents=50000,
            currency="USD",
            business_type="CORE",
        )
        assert revenue.partner_id == "partner_123"
        assert revenue.partner_revenue_share_pct == 20
        assert revenue.partner_revenue_share_usd_cents == 10000
        assert revenue.business_type == "CORE"

    def test_revenue_classification_fields(self):
        """Revenue should store business classification (service/module/etc)."""
        revenue = Revenue(
            id="rev_001",
            invoice_id="inv_123",
            opportunity_id="opp_456",
            client_id="client_789",
            revenue_usd_cents=50000,
            currency="USD",
            service="System Integration",
            module="ClaimsCenter",
            client_type="Commercial lines",
            pricing_model="FTE-based",
        )
        assert revenue.service == "System Integration"
        assert revenue.module == "ClaimsCenter"
        assert revenue.client_type == "Commercial lines"
        assert revenue.pricing_model == "FTE-based"

    def test_revenue_gross_margin_tracking(self):
        """Revenue should track cost and margin for P&L reporting."""
        revenue = Revenue(
            id="rev_001",
            invoice_id="inv_123",
            opportunity_id="opp_456",
            client_id="client_789",
            revenue_usd_cents=100000,
            cost_usd_cents=60000,
            gross_margin_usd_cents=40000,
            gross_margin_pct=40,
            currency="USD",
        )
        assert revenue.cost_usd_cents == 60000
        assert revenue.gross_margin_usd_cents == 40000
        assert revenue.gross_margin_pct == 40

    def test_revenue_source_types(self):
        """Revenue should support different sources (INVOICE, MANUAL_ADJUSTMENT, CORRECTION)."""
        revenue_invoice = Revenue(
            id="rev_001",
            invoice_id="inv_123",
            opportunity_id="opp_456",
            client_id="client_789",
            revenue_usd_cents=50000,
            currency="USD",
            source="INVOICE",
        )
        assert revenue_invoice.source == "INVOICE"

        revenue_adjustment = Revenue(
            id="rev_002",
            invoice_id="inv_123",
            opportunity_id="opp_456",
            client_id="client_789",
            revenue_usd_cents=5000,
            currency="USD",
            source="MANUAL_ADJUSTMENT",
        )
        assert revenue_adjustment.source == "MANUAL_ADJUSTMENT"

    def test_revenue_business_type_enum(self):
        """Revenue should support CORE and SPECIALITY business types."""
        revenue_core = Revenue(
            id="rev_001",
            invoice_id="inv_123",
            opportunity_id="opp_456",
            client_id="client_789",
            revenue_usd_cents=50000,
            currency="USD",
            business_type="CORE",
        )
        assert revenue_core.business_type == "CORE"

        revenue_spec = Revenue(
            id="rev_002",
            invoice_id="inv_124",
            opportunity_id="opp_457",
            client_id="client_789",
            revenue_usd_cents=30000,
            currency="USD",
            business_type="SPECIALITY",
        )
        assert revenue_spec.business_type == "SPECIALITY"

    def test_revenue_complete_flow(self):
        """Test complete revenue tracking scenario."""
        revenue = Revenue(
            id="rev_001",
            tenant_id=1,
            invoice_id="inv_123",
            opportunity_id="opp_456",
            project_id="proj_789",
            client_id="client_101",
            business_unit_id=1,
            client_owner_id="user_202",
            revenue_usd_cents=100000,
            currency="USD",
            service="System Integration",
            module="ClaimsCenter",
            client_type="Commercial lines",
            pricing_model="FTE-based",
            business_type="CORE",
            partner_id="partner_303",
            partner_revenue_share_pct=20,
            partner_revenue_share_usd_cents=20000,
            cost_usd_cents=60000,
            gross_margin_usd_cents=40000,
            gross_margin_pct=40,
            source="INVOICE",
        )

        # Verify all fields persisted
        assert revenue.invoice_id == "inv_123"
        assert revenue.opportunity_id == "opp_456"
        assert revenue.client_owner_id == "user_202"
        assert revenue.partner_revenue_share_pct == 20
        assert revenue.gross_margin_pct == 40


class TestPartnerRevenueShareConfiguration:
    """Test partner revenue share configuration in PartnerBUAssignment."""

    def test_partner_bu_assignment_has_core_revenue_share(self):
        """PartnerBUAssignment should have core_revenue_share_pct field."""
        from app.models.org_structure import PartnerBUAssignment

        assignment = PartnerBUAssignment(
            id=1,
            tenant_id=1,
            partner_org_node_id="node_partner_123",
            business_unit_id="bu_456",
            core_revenue_share_pct=20,
        )
        assert assignment.core_revenue_share_pct == 20

    def test_partner_core_revenue_share_nullable(self):
        """core_revenue_share_pct should be nullable with default 0."""
        from app.models.org_structure import PartnerBUAssignment

        assignment = PartnerBUAssignment(
            id=1,
            tenant_id=1,
            partner_org_node_id="node_partner_123",
            business_unit_id="bu_456",
        )
        # Should default to 0 or None depending on implementation
        assert assignment.core_revenue_share_pct is None or assignment.core_revenue_share_pct == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
