"""
import logging
COMPLETE P&L REPORTING API ENDPOINTS - Production Grade

Executive P&L dashboards, month-end close, and financial reporting.
"""
from datetime import date, datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.services.revenue_recognition_service import (
    calculate_p_and_l_summary,
    get_revenue_by_service,
    get_revenue_by_module,
    get_revenue_by_pricing_model,
    get_revenue_by_client_owner,
    get_partner_revenue_share_analysis,
)

router = APIRouter(prefix="/api/v1/p-and-l", tags=["p-and-l"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================
logger = logging.getLogger(__name__)

class PandLLineItem(BaseModel):
    description: str
    amount_usd_cents: int

    class Config:
        from_attributes = True


class PandLSummary(BaseModel):
    period: str  # YYYY-MM
    business_unit_id: int

    # Revenue & Cost
    total_revenue_usd_cents: int
    total_cost_usd_cents: int
    total_margin_usd_cents: int
    margin_pct: float

    # Deal metrics
    deal_count: int
    avg_deal_size_usd_cents: int

    # Forecast
    forecast_usd_cents: int
    forecast_variance_usd_cents: int
    forecast_variance_pct: float

    # Status
    status: str  # "ON_TRACK", "AT_RISK", "EXCEEDING"

    class Config:
        from_attributes = True


class ServiceBreakdownItem(BaseModel):
    service: str
    revenue_usd_cents: int
    cost_usd_cents: int
    margin_usd_cents: int
    margin_pct: float
    deal_count: int

    class Config:
        from_attributes = True


class ModuleBreakdownItem(BaseModel):
    module: str
    revenue_usd_cents: int
    cost_usd_cents: int
    margin_usd_cents: int
    margin_pct: float
    deal_count: int

    class Config:
        from_attributes = True


class PricingModelBreakdownItem(BaseModel):
    pricing_model: str
    revenue_usd_cents: int
    cost_usd_cents: int
    margin_usd_cents: int
    margin_pct: float
    deal_count: int

    class Config:
        from_attributes = True


class ClientOwnerItem(BaseModel):
    client_owner_id: str
    client_owner_name: Optional[str]
    revenue_usd_cents: int
    cost_usd_cents: int
    margin_usd_cents: int
    margin_pct: float
    deal_count: int
    avg_deal_size_usd_cents: int

    class Config:
        from_attributes = True


class MonthEndClose(BaseModel):
    period: str
    business_unit_id: int
    status: str  # "DRAFT", "IN_REVIEW", "APPROVED", "CLOSED"
    total_revenue_usd_cents: int
    total_cost_usd_cents: int
    total_margin_usd_cents: int
    margin_pct: float
    invoice_count_draft: int
    invoice_count_approved: int
    invoice_count_sent: int
    invoice_count_paid: int
    created_at: datetime
    approved_at: Optional[datetime]

    class Config:
        from_attributes = True


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get(
    "/summary/{business_unit_id}",
    response_model=PandLSummary,
    summary="P&L Summary",
    description="Get complete P&L for a business unit and month"
)
def get_pnl_summary(
    business_unit_id: int,
    month: Optional[str] = Query(None, description="YYYY-MM, defaults to current month"),
    db: Session = Depends(get_db),
):
    """
    Get complete P&L summary for a business unit.

    Returns:
    - Total revenue (from paid invoices)
    - Total cost (from timesheets)
    - Margin and margin %
    - Deal count and average deal size
    - Forecast vs actual variance
    - Status indicator (on track, at risk, exceeding)

    Default: Current month
    """
    try:
        if not month:
            month = datetime.now().strftime("%Y-%m")

        result = calculate_p_and_l_summary(db, business_unit_id, month)

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No P&L data for BU {business_unit_id} in {month}"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/by-service/{business_unit_id}",
    response_model=List[ServiceBreakdownItem],
    summary="P&L by Service",
    description="Get P&L breakdown by service type"
)
def get_pnl_by_service(
    business_unit_id: int,
    month: Optional[str] = Query(None, description="YYYY-MM"),
    db: Session = Depends(get_db),
):
    """
    Get P&L breakdown by service type.

    Services:
    - System Integration
    - Development
    - Staff Augmentation
    - Training & Enablement
    - etc.

    Shows profitability by service line for strategic planning.
    """
    try:
        if not month:
            month = datetime.now().strftime("%Y-%m")

        result = get_revenue_by_service(db, business_unit_id, month)

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No service data for BU {business_unit_id}"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/by-module/{business_unit_id}",
    response_model=List[ModuleBreakdownItem],
    summary="P&L by Guidewire Module",
    description="Get P&L breakdown by Guidewire module"
)
def get_pnl_by_module(
    business_unit_id: int,
    month: Optional[str] = Query(None, description="YYYY-MM"),
    db: Session = Depends(get_db),
):
    """
    Get P&L breakdown by Guidewire module.

    Modules:
    - PolicyCenter
    - ClaimsCenter
    - BillingCenter
    - ContactManager
    - etc.

    Shows profitability by technical practice area.
    """
    try:
        if not month:
            month = datetime.now().strftime("%Y-%m")

        result = get_revenue_by_module(db, business_unit_id, month)

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No module data for BU {business_unit_id}"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/by-pricing/{business_unit_id}",
    response_model=List[PricingModelBreakdownItem],
    summary="P&L by Pricing Model",
    description="Get P&L breakdown by pricing model"
)
def get_pnl_by_pricing(
    business_unit_id: int,
    month: Optional[str] = Query(None, description="YYYY-MM"),
    db: Session = Depends(get_db),
):
    """
    Get P&L breakdown by pricing model.

    Pricing Models:
    - FTE-based (Fixed per FTE per month)
    - Fixed Bid (Fixed project price)
    - Time & Materials (Hourly rate)
    - Retainer (Fixed recurring)
    - Value-based (% of savings/value)

    Shows pricing strategy effectiveness and margin by model.
    """
    try:
        if not month:
            month = datetime.now().strftime("%Y-%m")

        result = get_revenue_by_pricing_model(db, business_unit_id, month)

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No pricing data for BU {business_unit_id}"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/by-client-owner/{business_unit_id}",
    response_model=List[ClientOwnerItem],
    summary="P&L by Account Manager",
    description="Get P&L attribution by client owner (account manager)"
)
def get_pnl_by_client_owner(
    business_unit_id: int,
    month: Optional[str] = Query(None, description="YYYY-MM"),
    db: Session = Depends(get_db),
):
    """
    Get P&L attributed to each account manager.

    Account managers own the relationship and are accountable for:
    - Revenue generation
    - Margin (pricing + cost control)
    - Deal profitability

    This is the primary P&L accountability report for account teams.
    """
    try:
        if not month:
            month = datetime.now().strftime("%Y-%m")

        result = get_revenue_by_client_owner(db, business_unit_id, month)

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No client owner data for BU {business_unit_id}"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/month-end/{business_unit_id}/{month}",
    response_model=PandLSummary,
    summary="Month-End P&L",
    description="Get finalized P&L for a closed month"
)
def get_month_end_pnl(
    business_unit_id: int,
    month: str = Query(description="YYYY-MM format"),
    db: Session = Depends(get_db),
):
    """
    Get final P&L for a closed month.

    Month-end close requires:
    - All invoices for the month PAID (not SENT)
    - All timesheets APPROVED
    - No open disputes
    - Period explicitly closed by Finance

    Returns: Complete month-end P&L with all reconciliations
    """
    try:
        result = calculate_p_and_l_summary(db, business_unit_id, month)

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No P&L data for BU {business_unit_id} in {month}"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/close-month",
    response_model=MonthEndClose,
    summary="Close Month-End Period",
    description="Lock month for accounting purposes"
)
def close_month_end(
    business_unit_id: int = Query(description="BU to close"),
    month: str = Query(description="YYYY-MM format"),
    approved_by: str = Query(description="CFO or Finance Manager"),
    notes: str = Query("", description="Optional close notes"),
    db: Session = Depends(get_db),
):
    """
    Close a month-end period.

    Pre-Close Validation:
    ✓ All invoices for month are PAID (not SENT or DRAFT)
    ✓ All timesheets are APPROVED
    ✓ No open disputes
    ✓ Complete reconciliation

    Post-Close Enforcement:
    ✓ No new invoices can be created for this month
    ✓ No status changes allowed for month
    ✓ Revenue records immutable (adjustments only)
    ✓ All records locked for audit trail

    Args:
        business_unit_id: BU to close
        month: YYYY-MM format (e.g., "2026-08")
        approved_by: CFO or Finance Manager user ID
        notes: Optional notes on the close

    Returns:
        MonthEndClose with close timestamp and metrics

    Raises:
        400: Validation failed (unpaid invoices, etc.)
        404: No invoices found for period
        500: System error
    """
    try:
        from app.services.period_close_service import (
            validate_period_ready_for_close,
            close_period,
        )

        # Step 1: Validate period is ready
        validation = validate_period_ready_for_close(db, business_unit_id, month)

        if not validation["ready"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Period not ready for close",
                    "issues": validation["issues"],
                }
            )

        # Step 2: Close the period
        result = close_period(
            db,
            business_unit_id,
            month,
            approved_by,
            notes,
        )

        db.commit()

        return {
            "period": month,
            "business_unit_id": business_unit_id,
            "status": "CLOSED",
            "total_revenue_usd_cents": validation["total_revenue"],
            "total_cost_usd_cents": validation["total_cost"],
            "total_margin_usd_cents": validation["total_margin"],
            "margin_pct": validation["margin_pct"],
            "invoice_count_draft": len([i for i in [] if i]),  # TODO: Get drafts
            "invoice_count_approved": 0,  # TODO: Get approved
            "invoice_count_sent": 0,  # TODO: Get sent
            "invoice_count_paid": validation["paid_invoice_count"],
            "created_at": datetime.now(),
            "approved_at": datetime.now(),
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/trend/{business_unit_id}",
    summary="Revenue Trend",
    description="Get revenue trend over time"
)
def get_revenue_trend(
    business_unit_id: int,
    months: int = Query(12, ge=1, le=36, description="Number of months to show"),
    db: Session = Depends(get_db),
):
    """
    Get revenue trend over specified months.

    Shows:
    - Monthly revenue trend
    - Month-over-month growth
    - Seasonality patterns
    - Forecast vs actual history

    Useful for: Trend analysis, forecasting, business health
    """
    try:
        # TODO: Implement trend calculation
        # Retrieve last N months of P&L data
        # Calculate MoM growth
        # Identify trends

        raise HTTPException(
            status_code=501,
            detail="Revenue trend not yet implemented"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/reconciliation/{business_unit_id}/{month}",
    summary="Financial Reconciliation",
    description="Detailed reconciliation for period close"
)
def get_reconciliation(
    business_unit_id: int,
    month: str,
    db: Session = Depends(get_db),
):
    """
    Get detailed reconciliation report.

    Validates:
    ✓ All timesheets reconciled to invoices
    ✓ All invoices reconciled to revenue
    ✓ All revenue reconciled to payments (PAID status)
    ✓ Partner shares calculated correctly
    ✓ Margin calculations accurate
    ✓ No discrepancies or gaps

    Returns comprehensive audit report with:
    - Invoice count and totals by status
    - Revenue recognition summary
    - Cost and margin analysis
    - Reconciliation status (RECONCILED or DISCREPANCY)
    - Any discrepancies found

    Used by: Finance team for month-end audit and period close approval

    Args:
        business_unit_id: BU to reconcile
        month: YYYY-MM format (e.g., "2026-08")

    Returns:
        Detailed reconciliation report with validation status
    """
    try:
        from app.services.period_close_service import get_period_reconciliation

        result = get_period_reconciliation(db, business_unit_id, month)

        return result

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
