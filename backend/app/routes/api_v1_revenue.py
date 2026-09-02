"""
import logging
COMPLETE REVENUE API ENDPOINTS - Production Grade

All revenue recognition and reporting endpoints wired to business logic.
"""
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.revenue_recognition_service import (
    recognize_revenue_from_paid_invoice,
    get_revenue_by_month,
    get_revenue_by_service,
    get_revenue_by_module,
    get_revenue_by_pricing_model,
    get_revenue_by_client_owner,
    get_partner_revenue_share_analysis,
    get_forecast_vs_actual,
    get_negative_margin_alerts,
    calculate_p_and_l_summary,
)

router = APIRouter(prefix="/api/v1/revenue", tags=["revenue"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================
logger = logging.getLogger(__name__)

class RevenueBreakdownResponse(BaseModel):
    dimension: str
    value: str
    revenue_usd_cents: int
    cost_usd_cents: int
    margin_usd_cents: int
    margin_pct: float
    deal_count: int

    class Config:
        from_attributes = True


class MonthlyRevenueResponse(BaseModel):
    month: str
    revenue_usd_cents: int
    cost_usd_cents: int
    margin_usd_cents: int
    margin_pct: float
    deal_count: int

    class Config:
        from_attributes = True


class ForecastVsActualResponse(BaseModel):
    period: str
    forecast_usd_cents: int
    actual_usd_cents: int
    variance_usd_cents: int
    variance_pct: float
    status: str  # "ON_TRACK", "AT_RISK", "EXCEEDING"

    class Config:
        from_attributes = True


class NegativeMarginAlertResponse(BaseModel):
    invoice_id: str
    opportunity_id: Optional[str]
    client_owner_id: Optional[str]
    revenue_usd_cents: int
    cost_usd_cents: int
    margin_usd_cents: int
    billing_period_end: date
    severity: str  # "HIGH" or "MEDIUM"

    class Config:
        from_attributes = True


class PandLSummaryResponse(BaseModel):
    month: str
    business_unit_id: int
    total_revenue_usd_cents: int
    total_cost_usd_cents: int
    total_margin_usd_cents: int
    margin_pct: float
    deal_count: int
    forecast_usd_cents: int
    forecast_variance_pct: float

    class Config:
        from_attributes = True


class PartnerRevenueShareResponse(BaseModel):
    business_unit_id: int
    period: str
    core_revenue_usd_cents: int
    partner_share_pct: float
    partner_share_usd_cents: int
    company_retains_usd_cents: int

    class Config:
        from_attributes = True


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get(
    "/dashboard/{business_unit_id}",
    response_model=PandLSummaryResponse,
    summary="Revenue Dashboard",
    description="Get complete P&L summary for a business unit"
)
def get_revenue_dashboard(
    business_unit_id: int,
    month: Optional[str] = Query(None, description="YYYY-MM format, defaults to current month"),
    db: Session = Depends(get_db),
):
    """
    Get complete revenue dashboard for P&L summary.

    Returns:
    - Total revenue (from paid invoices)
    - Total cost (from timesheets)
    - Total margin and margin %
    - Deal count
    - Forecast vs actual comparison
    """
    try:
        if not month:
            month = datetime.now().strftime("%Y-%m")

        result = calculate_p_and_l_summary(db, business_unit_id, month)

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No revenue data found for BU {business_unit_id} in {month}"
            )

        return result

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/by-opportunity/{opportunity_id}",
    response_model=List[PandLSummaryResponse],
    summary="Revenue by Opportunity",
    description="Get all revenue records for an opportunity"
)
def get_revenue_by_opportunity(
    opportunity_id: str,
    db: Session = Depends(get_db),
):
    """
    Get all recognized revenue for a single opportunity.

    An opportunity can have multiple invoices recognized over time.
    Returns all revenue records linked to this opportunity.
    """
    try:
        from app.models.invoice import Invoice

        invoices = db.query(Invoice).filter(
            Invoice.opportunity_id == opportunity_id
        ).all()

        if not invoices:
            raise HTTPException(
                status_code=404,
                detail=f"No invoices found for opportunity {opportunity_id}"
            )

        # Return aggregated revenue by month
        result = []
        for invoice in invoices:
            if invoice.status == "PAID":
                summary = calculate_p_and_l_summary(
                    db,
                    invoice.business_unit_id,
                    invoice.billing_period_end.strftime("%Y-%m")
                )
                if summary:
                    result.append(summary)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/by-client-owner/{client_owner_id}",
    response_model=List[PandLSummaryResponse],
    summary="Revenue by Account Manager",
    description="Get P&L attribution for a specific account manager"
)
def get_revenue_by_account_manager(
    client_owner_id: str,
    month_from: Optional[str] = Query(None, description="YYYY-MM"),
    month_to: Optional[str] = Query(None, description="YYYY-MM"),
    db: Session = Depends(get_db),
):
    """
    Get revenue attributed to a specific account manager.

    P&L is attributed to the client_owner field on opportunities.
    Supports date range filtering.
    """
    try:
        result = get_revenue_by_client_owner(
            db,
            client_owner_id,
            month_from,
            month_to
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No revenue found for client owner {client_owner_id}"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/breakdowns/{business_unit_id}",
    response_model=List[RevenueBreakdownResponse],
    summary="Revenue Breakdowns",
    description="Get revenue breakdown by dimension"
)
def get_revenue_breakdowns(
    business_unit_id: int,
    breakdown_type: str = Query(
        "service",
        description="Breakdown type: service, module, pricing, or client"
    ),
    month: Optional[str] = Query(None, description="YYYY-MM format"),
    db: Session = Depends(get_db),
):
    """
    Get revenue breakdown by specified dimension.

    Supported breakdowns:
    - service: by service type (System Integration, Development, etc.)
    - module: by Guidewire module (PolicyCenter, ClaimsCenter, etc.)
    - pricing: by pricing model (FTE-based, Fixed Bid, T&M, etc.)
    - client: by client type (Commercial, Speciality, etc.)
    """
    if not month:
        month = datetime.now().strftime("%Y-%m")

    try:
        if breakdown_type == "service":
            result = get_revenue_by_service(db, business_unit_id, month)
        elif breakdown_type == "module":
            result = get_revenue_by_module(db, business_unit_id, month)
        elif breakdown_type == "pricing":
            result = get_revenue_by_pricing_model(db, business_unit_id, month)
        elif breakdown_type == "client":
            # TODO: Implement get_revenue_by_client_type
            raise HTTPException(
                status_code=400,
                detail="Client breakdown not yet implemented"
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown breakdown type: {breakdown_type}"
            )

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No revenue data for {breakdown_type} breakdown"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/forecast-vs-actual/{business_unit_id}",
    response_model=List[ForecastVsActualResponse],
    summary="Forecast vs Actual",
    description="Compare weighted opportunity forecast to recognized revenue"
)
def get_revenue_forecast_vs_actual(
    business_unit_id: int,
    month_from: Optional[str] = Query(None, description="YYYY-MM"),
    month_to: Optional[str] = Query(None, description="YYYY-MM"),
    db: Session = Depends(get_db),
):
    """
    Compare weighted opportunity forecasts to actual recognized revenue.

    Useful for:
    - Tracking forecast accuracy
    - Pipeline health assessment
    - Variance analysis
    """
    try:
        result = get_forecast_vs_actual(db, business_unit_id, month_from, month_to)

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No forecast data for BU {business_unit_id}"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/margin-analysis/{business_unit_id}",
    response_model=List[RevenueBreakdownResponse],
    summary="Margin Analysis",
    description="Get margin analysis by service"
)
def get_revenue_margin_analysis(
    business_unit_id: int,
    service: Optional[str] = Query(None, description="Filter by service type"),
    month: Optional[str] = Query(None, description="YYYY-MM format"),
    db: Session = Depends(get_db),
):
    """
    Get margin trend analysis by service over time.

    Useful for:
    - Service profitability tracking
    - Pricing model effectiveness
    - Margin trend analysis
    """
    try:
        if not month:
            month = datetime.now().strftime("%Y-%m")

        result = get_revenue_by_service(db, business_unit_id, month)

        if service:
            result = [r for r in result if r.get("service") == service]

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No margin data found"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/partner-share/{business_unit_id}",
    response_model=List[PartnerRevenueShareResponse],
    summary="Partner Revenue Share",
    description="Get partner revenue share analysis (Core business only)"
)
def get_revenue_partner_share(
    business_unit_id: int,
    month: Optional[str] = Query(None, description="YYYY-MM format"),
    db: Session = Depends(get_db),
):
    """
    Get partner revenue share analysis.

    Partner share applies ONLY to Core business at configured percentage.
    Speciality business generates 0% partner share.

    Returns:
    - Total Core revenue
    - Partner share % and amount
    - Company retains
    """
    try:
        if not month:
            month = datetime.now().strftime("%Y-%m")

        result = get_partner_revenue_share_analysis(db, business_unit_id, month)

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No Core business revenue found for BU {business_unit_id}"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/alerts",
    response_model=List[NegativeMarginAlertResponse],
    summary="Revenue Alerts",
    description="Get negative margin alerts and monitoring"
)
def get_revenue_alerts(
    business_unit_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None, description="HIGH or MEDIUM"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    Get negative margin alerts for immediate action.

    Alerts include:
    - Negative margin: cost > revenue
    - Low margin: <15% margin %
    - Flagged for review and investigation
    """
    try:
        result = get_negative_margin_alerts(db, business_unit_id)

        if severity:
            result = [a for a in result if a.get("severity") == severity]

        return result[:limit]

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
