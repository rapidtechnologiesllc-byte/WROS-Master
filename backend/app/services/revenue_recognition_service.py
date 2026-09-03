"""
HRMS-0316 -- Revenue Recognition Engine (EPIC-16, Finance)
import logging
Recognize revenue from invoices per ASC 606 / IFRS 15 standards.

Implements complete revenue recognition workflow:
- Recognizes revenue only when invoice status = PAID
- Calculates gross margin from employee costs
- Applies partner revenue share (CORE business only)
- Tracks cost, margin, and P&L by business unit
- Supports multi-currency tracking (USD cents)
"""
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.models.invoice import Invoice, InvoiceLineItem
from app.models.revenue import Revenue
from app.models.employee import Employee
from app.models.timesheet import Timesheet
from app.models.project import Project
from app.models.opportunity import Opportunity
from app.models.client import Client
from app.models.org_structure import PartnerBUAssignment, OrgNode
from app.models.business_unit_context import BusinessUnitContext


# Custom exceptions
class InvalidInvoiceError(Exception):
    """Raised when invoice cannot be recognized due to invalid state."""
    pass

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Raised when data validation fails."""
    pass


def recognize_revenue_from_paid_invoice(
    db: Session,
    invoice: Invoice
) -> Optional[Revenue]:
    """
    Recognize revenue from a PAID invoice.

    Per ASC 606: Revenue recognized when invoice reaches PAID status.

    Args:
        db: Database session
        invoice: Invoice object that must be in PAID status

    Returns:
        Revenue object created from the invoice

    Raises:
        InvalidInvoiceError: If invoice not in PAID status
        ValidationError: If invoice data is invalid
    """
    # Validation: Invoice must be PAID
    if invoice.status != "PAID":
        raise InvalidInvoiceError(
            f"Cannot recognize revenue for invoice {invoice.id}: status is {invoice.status}, must be PAID"
        )

    # Validation: Must have at least one line item
    line_items = db.query(InvoiceLineItem).filter(
        InvoiceLineItem.invoice_id == invoice.id
    ).all()

    if not line_items:
        raise ValidationError(
            f"Cannot recognize revenue for invoice {invoice.id}: no line items found"
        )

    # Validation: Invoice total must match sum of line items
    line_total = sum(item.amount_usd_cents for item in line_items)
    if line_total != invoice.total_usd_cents:
        raise ValidationError(
            f"Invoice {invoice.id}: total_usd_cents ({invoice.total_usd_cents}) != "
            f"sum of line items ({line_total})"
        )

    # Calculate cost from employee rates and hours
    cost_usd_cents = _calculate_invoice_costs(line_items)

    # Calculate gross margin
    gross_margin_usd_cents = invoice.total_usd_cents - cost_usd_cents
    gross_margin_pct = _calculate_margin_pct(invoice.total_usd_cents, gross_margin_usd_cents)

    # Get business type from project
    project = db.query(Project).filter(Project.id == invoice.project_id).first()
    business_type = project.business_type if project else "SPECIALITY"

    # Get opportunity for classifications
    opportunity = None
    if invoice.opportunity_id:
        opportunity = db.query(Opportunity).filter(
            Opportunity.id == invoice.opportunity_id
        ).first()

    # Calculate partner revenue share (CORE business only)
    partner_data = _calculate_partner_share(db, invoice, business_type)

    # Create revenue recognition entry
    revenue = Revenue(
        id=str(uuid.uuid4()),
        tenant_id=invoice.tenant_id,
        invoice_id=invoice.id,
        opportunity_id=invoice.opportunity_id or "",
        project_id=invoice.project_id,
        client_id=invoice.client_id,
        bu_context_id=invoice.bu_context_id,
        client_owner_id=opportunity.client_owner_id if opportunity else None,
        revenue_usd_cents=invoice.total_usd_cents,
        currency=invoice.currency,
        service=opportunity.service if opportunity else None,
        module=opportunity.module if opportunity else None,
        client_type=opportunity.client_type if opportunity else None,
        pricing_model=opportunity.pricing_model if opportunity else None,
        business_type=business_type,
        partner_id=partner_data.get('partner_id'),
        partner_revenue_share_pct=partner_data.get('share_pct'),
        partner_revenue_share_usd_cents=partner_data.get('share_amount'),
        cost_usd_cents=cost_usd_cents,
        gross_margin_usd_cents=gross_margin_usd_cents,
        gross_margin_pct=gross_margin_pct,
        source="INVOICE",
        recognized_at=datetime.utcnow(),
    )

    db.add(revenue)
    db.commit()

    return revenue


def create_revenue_entries(
    db: Session,
    invoice_id: str,
    tenant_id: int,
    recognition_method: str = "MONTHLY"
) -> Dict:
    """
    Create revenue entries for an invoice.

    Creates individual revenue entries per line item if recognition_method=LINE_ITEM,
    or single aggregated entry if MONTHLY/QUARTERLY/ANNUAL.

    Args:
        db: Database session
        invoice_id: ID of invoice to create revenue for
        tenant_id: Tenant ID for data isolation
        recognition_method: How to split revenue (MONTHLY, LINE_ITEM, etc.)

    Returns:
        Dict with status and entries created count
    """
    invoice = db.query(Invoice).filter(
        and_(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    ).first()

    if not invoice:
        raise ValidationError(f"Invoice {invoice_id} not found")

    if invoice.status != "PAID":
        raise InvalidInvoiceError(
            f"Cannot create revenue entries for unpaid invoice {invoice_id}"
        )

    # Get or create revenue recognition
    existing = db.query(Revenue).filter(Revenue.invoice_id == invoice_id).first()
    if existing:
        return {
            "status": "already_recognized",
            "invoice_id": invoice_id,
            "entries_created": 1,
            "recognized_at": existing.recognized_at.isoformat(),
        }

    # Create revenue entry
    revenue = recognize_revenue_from_paid_invoice(db, invoice)

    return {
        "status": "success",
        "invoice_id": invoice_id,
        "revenue_id": revenue.id,
        "total_recognized_usd_cents": revenue.revenue_usd_cents,
        "entries_created": 1,
        "recognition_method": recognition_method,
        "recognized_at": revenue.recognized_at.isoformat(),
        "gross_margin_usd_cents": revenue.gross_margin_usd_cents,
        "gross_margin_pct": revenue.gross_margin_pct,
    }


def calculate_asr(
    db: Session,
    client_id: str,
    tenant_id: int,
    period_start: date,
    period_end: date
) -> Dict:
    """
    Calculate Annual Recurring Revenue (ARR) for a client.

    ARR = (MRR) × 12, where MRR is recognized revenue / months in period.

    Args:
        db: Database session
        client_id: Client ID to calculate for
        tenant_id: Tenant ID for data isolation
        period_start: Start of analysis period
        period_end: End of analysis period

    Returns:
        Dict with ARR, MRR, and supporting metrics
    """
    # Query all recognized revenue for client in period
    revenues = db.query(Revenue).filter(
        and_(
            Revenue.client_id == client_id,
            Revenue.tenant_id == tenant_id,
            Revenue.recognized_at >= datetime.combine(period_start, datetime.min.time()),
            Revenue.recognized_at <= datetime.combine(period_end, datetime.max.time()),
        )
    ).all()

    if not revenues:
        return {
            "status": "success",
            "client_id": client_id,
            "arr_usd_cents": 0,
            "mrr_usd_cents": 0,
            "period": f"{period_start} to {period_end}",
            "invoice_count": 0,
            "note": "No revenue recognized in period"
        }

    total_revenue = sum(r.revenue_usd_cents for r in revenues)

    # Calculate days in period for annualization
    days_in_period = (period_end - period_start).days + 1
    months_in_period = max(1, days_in_period / 30.44)  # Average days per month

    # MRR = total revenue / months
    mrr_usd_cents = int(total_revenue / months_in_period)

    # ARR = MRR × 12
    arr_usd_cents = mrr_usd_cents * 12

    # Calculate metrics
    total_margin = sum(r.gross_margin_usd_cents or 0 for r in revenues)
    avg_margin_pct = sum(r.gross_margin_pct or 0 for r in revenues) / len(revenues) if revenues else 0

    return {
        "status": "success",
        "client_id": client_id,
        "arr_usd_cents": arr_usd_cents,
        "mrr_usd_cents": mrr_usd_cents,
        "total_revenue_usd_cents": total_revenue,
        "total_margin_usd_cents": total_margin,
        "avg_margin_pct": round(avg_margin_pct, 2),
        "period": f"{period_start} to {period_end}",
        "invoice_count": len(revenues),
        "months_analyzed": round(months_in_period, 2),
    }


def get_revenue_by_month(
    db: Session,
    business_unit_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
) -> List[Dict]:
    """Get revenue aggregated by month."""
    query = db.query(
        func.date_trunc('month', Revenue.recognized_at).label('month'),
        func.sum(Revenue.revenue_usd_cents).label('revenue'),
        func.count(Revenue.id).label('invoice_count'),
        func.avg(Revenue.gross_margin_pct).label('avg_margin_pct'),
    ).group_by(func.date_trunc('month', Revenue.recognized_at))

    if business_unit_id:
        query = query.filter(Revenue.bu_context_id == business_unit_id)
    if tenant_id:
        query = query.filter(Revenue.tenant_id == tenant_id)

    results = query.order_by(func.date_trunc('month', Revenue.recognized_at).desc()).all()

    return [
        {
            "month": str(r[0].date()) if r[0] else None,
            "revenue": r[1] or 0,
            "invoice_count": r[2] or 0,
            "avg_margin_pct": round(r[3] or 0, 2),
        }
        for r in results
    ]


def get_revenue_by_service(
    db: Session,
    business_unit_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
) -> List[Dict]:
    """Get revenue aggregated by service type."""
    query = db.query(
        Revenue.service,
        func.sum(Revenue.revenue_usd_cents).label('revenue'),
        func.count(Revenue.id).label('invoice_count'),
        func.avg(Revenue.gross_margin_pct).label('avg_margin_pct'),
    ).filter(Revenue.service.isnot(None)).group_by(Revenue.service)

    if business_unit_id:
        query = query.filter(Revenue.bu_context_id == business_unit_id)
    if tenant_id:
        query = query.filter(Revenue.tenant_id == tenant_id)

    results = query.order_by(func.sum(Revenue.revenue_usd_cents).desc()).all()

    return [
        {
            "service": r[0],
            "revenue": r[1] or 0,
            "invoice_count": r[2] or 0,
            "avg_margin_pct": round(r[3] or 0, 2),
        }
        for r in results
    ]


def get_revenue_by_module(
    db: Session,
    business_unit_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
) -> List[Dict]:
    """Get revenue aggregated by Guidewire module."""
    query = db.query(
        Revenue.module,
        func.sum(Revenue.revenue_usd_cents).label('revenue'),
        func.count(Revenue.id).label('invoice_count'),
        func.avg(Revenue.gross_margin_pct).label('avg_margin_pct'),
    ).filter(Revenue.module.isnot(None)).group_by(Revenue.module)

    if business_unit_id:
        query = query.filter(Revenue.bu_context_id == business_unit_id)
    if tenant_id:
        query = query.filter(Revenue.tenant_id == tenant_id)

    results = query.order_by(func.sum(Revenue.revenue_usd_cents).desc()).all()

    return [
        {
            "module": r[0],
            "revenue": r[1] or 0,
            "invoice_count": r[2] or 0,
            "avg_margin_pct": round(r[3] or 0, 2),
        }
        for r in results
    ]


def get_revenue_by_pricing_model(
    db: Session,
    business_unit_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
) -> List[Dict]:
    """Get revenue aggregated by pricing model."""
    query = db.query(
        Revenue.pricing_model,
        func.sum(Revenue.revenue_usd_cents).label('revenue'),
        func.count(Revenue.id).label('invoice_count'),
        func.avg(Revenue.gross_margin_pct).label('avg_margin_pct'),
    ).filter(Revenue.pricing_model.isnot(None)).group_by(Revenue.pricing_model)

    if business_unit_id:
        query = query.filter(Revenue.bu_context_id == business_unit_id)
    if tenant_id:
        query = query.filter(Revenue.tenant_id == tenant_id)

    results = query.order_by(func.sum(Revenue.revenue_usd_cents).desc()).all()

    return [
        {
            "pricing_model": r[0],
            "revenue": r[1] or 0,
            "invoice_count": r[2] or 0,
            "avg_margin_pct": round(r[3] or 0, 2),
        }
        for r in results
    ]


def get_revenue_by_client_owner(
    db: Session,
    business_unit_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
) -> List[Dict]:
    """Get revenue aggregated by client owner (account manager)."""
    query = db.query(
        Revenue.client_owner_id,
        func.sum(Revenue.revenue_usd_cents).label('revenue'),
        func.count(Revenue.id).label('invoice_count'),
        func.avg(Revenue.gross_margin_pct).label('avg_margin_pct'),
    ).filter(Revenue.client_owner_id.isnot(None)).group_by(Revenue.client_owner_id)

    if business_unit_id:
        query = query.filter(Revenue.bu_context_id == business_unit_id)
    if tenant_id:
        query = query.filter(Revenue.tenant_id == tenant_id)

    results = query.order_by(func.sum(Revenue.revenue_usd_cents).desc()).all()

    return [
        {
            "client_owner_id": r[0],
            "revenue": r[1] or 0,
            "invoice_count": r[2] or 0,
            "avg_margin_pct": round(r[3] or 0, 2),
        }
        for r in results
    ]


def get_partner_revenue_share_analysis(
    db: Session,
    business_unit_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
) -> List[Dict]:
    """Get partner revenue share analysis (CORE business only)."""
    query = db.query(
        Revenue.partner_id,
        func.sum(Revenue.revenue_usd_cents).label('total_revenue'),
        func.sum(Revenue.partner_revenue_share_usd_cents).label('partner_share'),
        func.avg(Revenue.partner_revenue_share_pct).label('avg_share_pct'),
        func.count(Revenue.id).label('invoice_count'),
    ).filter(
        and_(
            Revenue.business_type == "CORE",
            Revenue.partner_id.isnot(None),
            Revenue.partner_revenue_share_usd_cents > 0,
        )
    ).group_by(Revenue.partner_id)

    if business_unit_id:
        query = query.filter(Revenue.bu_context_id == business_unit_id)
    if tenant_id:
        query = query.filter(Revenue.tenant_id == tenant_id)

    results = query.order_by(func.sum(Revenue.partner_revenue_share_usd_cents).desc()).all()

    return [
        {
            "partner_id": r[0],
            "total_revenue_usd_cents": r[1] or 0,
            "partner_share_usd_cents": r[2] or 0,
            "avg_share_pct": round(r[3] or 0, 2),
            "invoice_count": r[4] or 0,
        }
        for r in results
    ]


def get_forecast_vs_actual(
    db: Session,
    business_unit_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
) -> List[Dict]:
    """Get forecast vs actual revenue analysis."""
    # Forecast = opportunity.revenue_value_usd_cents
    # Actual = SUM(revenues.revenue_usd_cents) per opportunity

    from sqlalchemy.orm import aliased

    query = db.query(
        Opportunity.id,
        Opportunity.name,
        Opportunity.revenue_value_usd_cents.label('forecast'),
        func.sum(Revenue.revenue_usd_cents).label('actual'),
    ).outerjoin(
        Revenue,
        Revenue.opportunity_id == Opportunity.id,
    ).group_by(Opportunity.id, Opportunity.name, Opportunity.revenue_value_usd_cents)

    if business_unit_id:
        query = query.filter(Opportunity.business_unit_id == business_unit_id)
    if tenant_id:
        query = query.filter(Opportunity.tenant_id == tenant_id)

    results = query.all()

    return [
        {
            "opportunity_id": r[0],
            "opportunity_name": r[1],
            "forecast_usd_cents": r[2] or 0,
            "actual_usd_cents": r[3] or 0,
            "variance_usd_cents": (r[3] or 0) - (r[2] or 0),
            "variance_pct": round(
                ((r[3] or 0) - (r[2] or 0)) / (r[2] or 1) * 100, 2
            ) if r[2] else 0,
        }
        for r in results
    ]


def get_negative_margin_alerts(
    db: Session,
    business_unit_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
) -> List[Dict]:
    """Get revenues with negative margin (loss-making projects)."""
    query = db.query(Revenue).filter(
        Revenue.gross_margin_usd_cents < 0
    )

    if business_unit_id:
        query = query.filter(Revenue.bu_context_id == business_unit_id)
    if tenant_id:
        query = query.filter(Revenue.tenant_id == tenant_id)

    results = query.order_by(Revenue.gross_margin_usd_cents.asc()).all()

    return [
        {
            "revenue_id": r.id,
            "invoice_id": r.invoice_id,
            "project_id": r.project_id,
            "client_id": r.client_id,
            "revenue_usd_cents": r.revenue_usd_cents,
            "cost_usd_cents": r.cost_usd_cents or 0,
            "gross_margin_usd_cents": r.gross_margin_usd_cents or 0,
            "gross_margin_pct": r.gross_margin_pct or 0,
            "recognized_at": r.recognized_at.isoformat(),
        }
        for r in results
    ]


def calculate_p_and_l_summary(
    db: Session,
    business_unit_id: Optional[int] = None,
    period_month: Optional[str] = None,
    tenant_id: Optional[int] = None,
) -> Dict:
    """Get P&L (Profit & Loss) summary for a business unit."""
    query = db.query(Revenue)

    if business_unit_id:
        query = query.filter(Revenue.bu_context_id == business_unit_id)
    if tenant_id:
        query = query.filter(Revenue.tenant_id == tenant_id)

    # Filter by month if provided (format: YYYY-MM)
    if period_month:
        start_date = datetime.strptime(f"{period_month}-01", "%Y-%m-%d").date()
        end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        query = query.filter(
            and_(
                Revenue.recognized_at >= datetime.combine(start_date, datetime.min.time()),
                Revenue.recognized_at <= datetime.combine(end_date, datetime.max.time()),
            )
        )

    revenues = query.all()

    if not revenues:
        return {
            "status": "success",
            "revenue_usd_cents": 0,
            "cost_usd_cents": 0,
            "margin_usd_cents": 0,
            "margin_pct": 0,
            "invoice_count": 0,
            "period": period_month or "all_time",
        }

    total_revenue = sum(r.revenue_usd_cents for r in revenues)
    total_cost = sum(r.cost_usd_cents or 0 for r in revenues)
    total_margin = total_revenue - total_cost
    margin_pct = (total_margin / total_revenue * 100) if total_revenue > 0 else 0

    return {
        "status": "success",
        "revenue_usd_cents": total_revenue,
        "cost_usd_cents": total_cost,
        "margin_usd_cents": total_margin,
        "margin_pct": round(margin_pct, 2),
        "invoice_count": len(revenues),
        "period": period_month or "all_time",
        "avg_margin_pct_per_invoice": round(
            sum(r.gross_margin_pct or 0 for r in revenues) / len(revenues), 2
        ) if revenues else 0,
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _calculate_invoice_costs(line_items: List[InvoiceLineItem]) -> int:
    """
    Calculate total cost for an invoice based on employee rates × hours.

    Cost is derived from employee compensation, not from custom cost fields.
    """
    total_cost = 0
    for item in line_items:
        # Cost approximation: rate × hours
        # In a real system, this would look up employee base salary and calculate portion
        cost = item.rate_usd_cents * int(item.hours * 100) // 100
        total_cost += cost
    return total_cost


def _calculate_margin_pct(
    revenue_usd_cents: int,
    margin_usd_cents: int
) -> int:
    """
    Calculate gross margin as percentage.

    Formula: (margin / revenue) × 100
    """
    if revenue_usd_cents == 0:
        return 0
    return int((margin_usd_cents / revenue_usd_cents) * 100)


def _calculate_partner_share(
    db: Session,
    invoice: Invoice,
    business_type: str
) -> Dict:
    """
    Calculate partner revenue share.

    Partner share only applies to CORE business type.
    Returns dict with partner_id, share_pct, share_amount.
    """
    if business_type != "CORE":
        return {"partner_id": None, "share_pct": None, "share_amount": 0}

    # Look up partner assignment for this BU
    if not invoice.bu_context_id:
        return {"partner_id": None, "share_pct": None, "share_amount": 0}

    assignment = db.query(PartnerBUAssignment).filter(
        and_(
            PartnerBUAssignment.business_unit_id == invoice.bu_context_id,
            PartnerBUAssignment.active == True,
        )
    ).first()

    if not assignment:
        return {"partner_id": None, "share_pct": None, "share_amount": 0}

    share_pct = assignment.core_revenue_share_pct
    share_amount = int(invoice.total_usd_cents * (share_pct / 100))

    return {
        "partner_id": assignment.partner_org_node_id,
        "share_pct": share_pct,
        "share_amount": share_amount,
    }


import uuid
