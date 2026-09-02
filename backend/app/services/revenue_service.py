"""
import logging
Revenue Recognition & P&L Attribution Service.

Handles:
- Revenue recognition when Invoice.status = PAID
- Revenue attribution to Client Owner (opportunity owner at creation)
- Partner revenue share calculation (Core business only)
- Gross margin tracking
- Revenue rollup by service/module/client_type/pricing_model
"""
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from app.models.revenue import Revenue, REVENUE_SOURCES
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.opportunity import Opportunity
from app.models.project import Project
from app.models.org_structure import PartnerBUAssignment
from app.models.client import Client
from app.models.employee import Employee

logger = logging.getLogger(__name__)

class RevenueRecognitionError(Exception):
    pass


def recognize_invoice_revenue(db: Session, invoice: Invoice) -> Revenue:
    """
    Recognize revenue when invoice transitions to PAID status.

    Business logic:
    - Revenue amount = invoice.total_usd_cents
    - All revenue flows to Client Owner (from opportunity if traced, else null)
    - Partner revenue share applies to Core business only
    - Cost is derived from employee rates + hours in invoice line items
    - Gross margin = revenue - cost
    - Revenue recognition timestamp = now

    Args:
        db: Database session
        invoice: Invoice object that was just marked PAID

    Returns:
        Revenue object that was created/updated

    Raises:
        RevenueRecognitionError: If invoice not PAID or missing critical data
    """
    if invoice.status != "PAID":
        raise RevenueRecognitionError(
            f"Cannot recognize revenue for invoice {invoice.id} -- status is '{invoice.status}', must be PAID"
        )

    # Get opportunity for classification and client owner attribution
    opportunity = None
    if invoice.opportunity_id:
        opportunity = db.query(Opportunity).filter(Opportunity.id == invoice.opportunity_id).first()

    # Get project for business unit context
    project = db.query(Project).filter(Project.id == invoice.project_id).first() if invoice.project_id else None

    # Calculate cost from invoice line items (employee rates * hours)
    line_items = db.query(InvoiceLineItem).filter(InvoiceLineItem.invoice_id == invoice.id).all()
    total_cost_usd_cents = sum(item.rate_usd_cents * int(item.hours * 100) for item in line_items)  # cents * hours

    # Calculate gross margin
    gross_margin_usd_cents = invoice.total_usd_cents - total_cost_usd_cents
    gross_margin_pct = int((gross_margin_usd_cents / invoice.total_usd_cents * 100)) if invoice.total_usd_cents > 0 else 0

    # Determine business type and partner share
    business_type = project.business_type if project else None
    partner_revenue_share_pct = None
    partner_revenue_share_usd_cents = None
    partner_id = None

    # Partner revenue share: Core business only
    if business_type == "CORE" and invoice.business_unit_id:
        partner_assignment = db.query(PartnerBUAssignment).filter(
            PartnerBUAssignment.business_unit_id == invoice.business_unit_id,
            PartnerBUAssignment.active == True
        ).first()

        if partner_assignment and partner_assignment.core_revenue_share_pct:
            partner_revenue_share_pct = partner_assignment.core_revenue_share_pct
            # Calculate partner's share as % of gross revenue (not net)
            partner_revenue_share_usd_cents = int(
                invoice.total_usd_cents * partner_revenue_share_pct / 100
            )
            partner_id = partner_assignment.partner_org_node_id

    # Create or update revenue record
    existing_revenue = db.query(Revenue).filter(Revenue.invoice_id == invoice.id).first()
    if existing_revenue:
        # Update existing (handles case of invoice status changes)
        revenue = existing_revenue
    else:
        revenue = Revenue(
            invoice_id=invoice.id,
            tenant_id=invoice.tenant_id,
        )

    # Populate all fields
    revenue.opportunity_id = invoice.opportunity_id
    revenue.project_id = invoice.project_id
    revenue.client_id = invoice.client_id
    revenue.business_unit_id = invoice.business_unit_id
    revenue.client_owner_id = opportunity.client_owner_id if opportunity else None

    revenue.revenue_usd_cents = invoice.total_usd_cents
    revenue.currency = invoice.currency
    revenue.cost_usd_cents = total_cost_usd_cents
    revenue.gross_margin_usd_cents = gross_margin_usd_cents
    revenue.gross_margin_pct = gross_margin_pct

    # Classification from opportunity
    if opportunity:
        revenue.service = opportunity.service
        revenue.module = opportunity.module
        revenue.client_type = opportunity.client_type
        revenue.pricing_model = opportunity.pricing_model

    revenue.business_type = business_type
    revenue.partner_id = partner_id
    revenue.partner_revenue_share_pct = partner_revenue_share_pct
    revenue.partner_revenue_share_usd_cents = partner_revenue_share_usd_cents

    revenue.source = REVENUE_SOURCES[0]  # "INVOICE"
    revenue.recognized_at = datetime.utcnow()

    db.add(revenue)
    return revenue


def calculate_partner_share(revenue_usd_cents: int, share_pct: int) -> int:
    """Calculate partner's revenue share in USD cents."""
    if share_pct is None or share_pct <= 0:
        return 0
    return int(revenue_usd_cents * share_pct / 100)


def get_revenue_by_opportunity(db: Session, opportunity_id: str) -> List[Revenue]:
    """Get all revenue records linked to an opportunity."""
    return db.query(Revenue).filter(Revenue.opportunity_id == opportunity_id).all()


def get_revenue_by_client_owner(db: Session, client_owner_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Revenue]:
    """
    Get all revenue for a Client Owner (P&L tracking by account manager).

    Args:
        db: Database session
        client_owner_id: Client Owner (account manager) ID
        start_date: Filter revenues recognized after this date
        end_date: Filter revenues recognized before this date

    Returns:
        List of revenue records attributed to this client owner
    """
    query = db.query(Revenue).filter(Revenue.client_owner_id == client_owner_id)

    if start_date:
        query = query.filter(Revenue.recognized_at >= start_date)
    if end_date:
        query = query.filter(Revenue.recognized_at <= end_date)

    return query.all()


def get_revenue_by_business_unit(db: Session, business_unit_id: int, business_type: Optional[str] = None) -> List[Revenue]:
    """
    Get revenue for a Business Unit (partner P&L).

    Args:
        db: Database session
        business_unit_id: Business unit ID
        business_type: Filter by business type (CORE, SPECIALITY)

    Returns:
        List of revenue records for this BU
    """
    query = db.query(Revenue).filter(Revenue.business_unit_id == business_unit_id)

    if business_type:
        query = query.filter(Revenue.business_type == business_type)

    return query.all()


def get_revenue_breakdown_by_service(db: Session, business_unit_id: int) -> Dict[str, int]:
    """
    Get revenue breakdown by service type for Partner ROI reporting.

    Returns:
        Dictionary: {service_name: total_revenue_usd_cents, ...}
    """
    revenues = get_revenue_by_business_unit(db, business_unit_id)

    breakdown = {}
    for revenue in revenues:
        service = revenue.service or "Unknown"
        breakdown[service] = breakdown.get(service, 0) + revenue.revenue_usd_cents

    return breakdown


def get_revenue_breakdown_by_module(db: Session, business_unit_id: int) -> Dict[str, int]:
    """Get revenue breakdown by Guidewire module type."""
    revenues = get_revenue_by_business_unit(db, business_unit_id)

    breakdown = {}
    for revenue in revenues:
        module = revenue.module or "Unknown"
        breakdown[module] = breakdown.get(module, 0) + revenue.revenue_usd_cents

    return breakdown


def get_revenue_breakdown_by_pricing(db: Session, business_unit_id: int) -> Dict[str, int]:
    """Get revenue breakdown by pricing model."""
    revenues = get_revenue_by_business_unit(db, business_unit_id)

    breakdown = {}
    for revenue in revenues:
        pricing = revenue.pricing_model or "Unknown"
        breakdown[pricing] = breakdown.get(pricing, 0) + revenue.revenue_usd_cents

    return breakdown


def get_gross_margin_analysis(db: Session, business_unit_id: int) -> Dict:
    """
    Calculate gross margin analytics for P&L reporting.

    Returns:
        {
            'total_revenue': int,
            'total_cost': int,
            'total_margin': int,
            'margin_pct': int,
        }
    """
    revenues = get_revenue_by_business_unit(db, business_unit_id)

    total_revenue = sum(r.revenue_usd_cents for r in revenues)
    total_cost = sum(r.cost_usd_cents or 0 for r in revenues)
    total_margin = total_revenue - total_cost
    margin_pct = int((total_margin / total_revenue * 100)) if total_revenue > 0 else 0

    return {
        'total_revenue': total_revenue,
        'total_cost': total_cost,
        'total_margin': total_margin,
        'margin_pct': margin_pct,
    }


def get_partner_revenue_share_analysis(db: Session, business_unit_id: int) -> Dict:
    """
    Calculate partner revenue share (Core business only).

    Returns:
        {
            'core_revenue': int,
            'partner_share_pct': int,
            'partner_share_amount': int,
            'company_retains': int,
        }
    """
    revenues = db.query(Revenue).filter(
        Revenue.business_unit_id == business_unit_id,
        Revenue.business_type == "CORE"
    ).all()

    total_core_revenue = sum(r.revenue_usd_cents for r in revenues)
    total_partner_share = sum(r.partner_revenue_share_usd_cents or 0 for r in revenues)
    partner_share_pct = int((total_partner_share / total_core_revenue * 100)) if total_core_revenue > 0 else 0
    company_retains = total_core_revenue - total_partner_share

    return {
        'core_revenue': total_core_revenue,
        'partner_share_pct': partner_share_pct,
        'partner_share_amount': total_partner_share,
        'company_retains': company_retains,
    }
