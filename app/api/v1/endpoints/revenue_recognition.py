"""
REST API Endpoints for Revenue Recognition (HRMS-0316)

Implements complete revenue recognition workflow:
- POST /revenue/recognize - Recognize revenue from paid invoice
- POST /revenue/entries - Create revenue entries
- POST /revenue/asr - Calculate annual recurring revenue
- GET /revenue/by-month - Revenue by month
- GET /revenue/by-service - Revenue by service
- GET /revenue/by-module - Revenue by Guidewire module
- GET /revenue/by-pricing-model - Revenue by pricing model
- GET /revenue/by-client-owner - Revenue by client owner
- GET /revenue/partner-shares - Partner revenue share analysis
- GET /revenue/forecast-vs-actual - Forecast vs actual analysis
- GET /revenue/negative-margins - Loss-making projects
- GET /revenue/pnl-summary - Profit & loss summary
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.revenue_recognition import (
    RecognizeRevenueRequest,
    CreateRevenueEntriesRequest,
    CalculateASRRequest,
    RevenueReportRequest,
    RevenueRecognitionResponse,
    RevenueEntriesResponse,
    ASRResponse,
    RevenueByMonthResponse,
    RevenueByMonthItem,
    RevenueByServiceResponse,
    RevenueByServiceItem,
    RevenueByModuleResponse,
    RevenueByModuleItem,
    RevenueByPricingModelResponse,
    RevenueByPricingModelItem,
    RevenueByClientOwnerResponse,
    RevenueByClientOwnerItem,
    PartnerRevenueShareResponse,
    PartnerRevenueShareItem,
    ForecastVsActualResponse,
    ForecastVsActualItem,
    NegativeMarginAlertsResponse,
    NegativeMarginAlertItem,
    PandLSummaryResponse,
    ErrorResponse,
)
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
    InvalidInvoiceError,
    ValidationError,
)
from app.models.invoice import Invoice

router = APIRouter(prefix="/revenue", tags=["revenue-recognition"])


# ============================================================================
# REVENUE RECOGNITION ENDPOINTS
# ============================================================================

@router.post(
    "/recognize",
    response_model=RevenueRecognitionResponse,
    summary="Recognize revenue from paid invoice",
    description="Create revenue recognition entry for a PAID invoice per ASC 606"
)
def recognize_revenue(
    request: RecognizeRevenueRequest,
    db: Session = Depends(get_db)
) -> RevenueRecognitionResponse:
    """
    Recognize revenue from a paid invoice.

    Only invoices with status=PAID can be recognized.
    Revenue is calculated as invoice total minus costs.
    Gross margin is tracked and P&L is updated.

    Args:
        request: RecognizeRevenueRequest with invoice_id and tenant_id
        db: Database session

    Returns:
        RevenueRecognitionResponse with details of recognized revenue

    Raises:
        HTTPException: If invoice not found, not PAID, or validation fails
    """
    try:
        # Fetch invoice
        invoice = db.query(Invoice).filter(
            Invoice.id == request.invoice_id,
            Invoice.tenant_id == request.tenant_id
        ).first()

        if not invoice:
            raise HTTPException(
                status_code=404,
                detail=f"Invoice {request.invoice_id} not found"
            )

        # Recognize revenue
        revenue = recognize_revenue_from_paid_invoice(db, invoice)

        return RevenueRecognitionResponse(
            status="success",
            invoice_id=invoice.id,
            revenue_id=revenue.id,
            total_recognized_usd_cents=revenue.revenue_usd_cents,
            gross_margin_usd_cents=revenue.gross_margin_usd_cents,
            gross_margin_pct=revenue.gross_margin_pct,
            cost_usd_cents=revenue.cost_usd_cents or 0,
            partner_share_usd_cents=revenue.partner_revenue_share_usd_cents,
            entries_created=1,
            recognized_at=revenue.recognized_at.isoformat(),
        )

    except InvalidInvoiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/entries",
    response_model=RevenueEntriesResponse,
    summary="Create revenue entries for invoice",
    description="Creates individual or aggregated revenue entries based on recognition method"
)
def create_entries(
    request: CreateRevenueEntriesRequest,
    db: Session = Depends(get_db)
) -> RevenueEntriesResponse:
    """
    Create revenue entries for an invoice.

    Creates revenue entries based on the specified recognition method.
    Supports MONTHLY (default), LINE_ITEM, QUARTERLY, ANNUAL.

    Args:
        request: CreateRevenueEntriesRequest
        db: Database session

    Returns:
        RevenueEntriesResponse with count of entries created

    Raises:
        HTTPException: If invoice not found or invalid state
    """
    try:
        result = create_revenue_entries(
            db,
            request.invoice_id,
            request.tenant_id,
            request.recognition_method
        )

        return RevenueEntriesResponse(
            status=result["status"],
            invoice_id=result["invoice_id"],
            revenue_id=result.get("revenue_id"),
            total_recognized_usd_cents=result.get("total_recognized_usd_cents", 0),
            entries_created=result.get("entries_created", 0),
            recognition_method=request.recognition_method,
            recognized_at=result.get("recognized_at", datetime.utcnow().isoformat()),
            gross_margin_usd_cents=result.get("gross_margin_usd_cents", 0),
            gross_margin_pct=result.get("gross_margin_pct", 0),
        )

    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except InvalidInvoiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/asr",
    response_model=ASRResponse,
    summary="Calculate Annual Recurring Revenue (ASR/ARR)",
    description="Calculates ARR and MRR for a client over a period"
)
def calculate_annual_recurring_revenue(
    request: CalculateASRRequest,
    db: Session = Depends(get_db)
) -> ASRResponse:
    """
    Calculate Annual Recurring Revenue (ASR/ARR) for a client.

    ARR = (Total Revenue in Period / Months in Period) × 12

    Args:
        request: CalculateASRRequest with client_id, period dates
        db: Database session

    Returns:
        ASRResponse with ARR, MRR, and supporting metrics

    Raises:
        HTTPException: If data validation fails
    """
    try:
        result = calculate_asr(
            db,
            request.client_id,
            request.tenant_id,
            request.period_start,
            request.period_end
        )

        return ASRResponse(
            status=result["status"],
            client_id=result["client_id"],
            arr_usd_cents=result.get("arr_usd_cents", 0),
            mrr_usd_cents=result.get("mrr_usd_cents", 0),
            total_revenue_usd_cents=result.get("total_revenue_usd_cents", 0),
            total_margin_usd_cents=result.get("total_margin_usd_cents", 0),
            avg_margin_pct=result.get("avg_margin_pct", 0),
            period=result.get("period", ""),
            invoice_count=result.get("invoice_count", 0),
            months_analyzed=result.get("months_analyzed", 0),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# REVENUE REPORTING ENDPOINTS
# ============================================================================

@router.get(
    "/by-month",
    response_model=RevenueByMonthResponse,
    summary="Get revenue by month",
    description="Aggregates recognized revenue by month with margin analysis"
)
def get_revenue_monthly(
    business_unit_id: Optional[int] = Query(None, description="Filter by BU"),
    tenant_id: Optional[int] = Query(None, description="Filter by tenant"),
    db: Session = Depends(get_db)
) -> RevenueByMonthResponse:
    """Get revenue aggregated by month."""
    try:
        data = get_revenue_by_month(db, business_unit_id, tenant_id)
        items = [RevenueByMonthItem(**item) for item in data]
        total_revenue = sum(item.revenue for item in items)
        total_invoices = sum(item.invoice_count for item in items)

        return RevenueByMonthResponse(
            status="success",
            data=items,
            total_revenue=total_revenue,
            total_invoices=total_invoices,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/by-service",
    response_model=RevenueByServiceResponse,
    summary="Get revenue by service",
    description="Aggregates revenue by service type"
)
def get_revenue_service(
    business_unit_id: Optional[int] = Query(None, description="Filter by BU"),
    tenant_id: Optional[int] = Query(None, description="Filter by tenant"),
    db: Session = Depends(get_db)
) -> RevenueByServiceResponse:
    """Get revenue aggregated by service type."""
    try:
        data = get_revenue_by_service(db, business_unit_id, tenant_id)
        items = [RevenueByServiceItem(**item) for item in data]
        total_revenue = sum(item.revenue for item in items)

        return RevenueByServiceResponse(
            status="success",
            data=items,
            total_revenue=total_revenue,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/by-module",
    response_model=RevenueByModuleResponse,
    summary="Get revenue by Guidewire module",
    description="Aggregates revenue by Guidewire product module"
)
def get_revenue_module(
    business_unit_id: Optional[int] = Query(None, description="Filter by BU"),
    tenant_id: Optional[int] = Query(None, description="Filter by tenant"),
    db: Session = Depends(get_db)
) -> RevenueByModuleResponse:
    """Get revenue aggregated by module."""
    try:
        data = get_revenue_by_module(db, business_unit_id, tenant_id)
        items = [RevenueByModuleItem(**item) for item in data]
        total_revenue = sum(item.revenue for item in items)

        return RevenueByModuleResponse(
            status="success",
            data=items,
            total_revenue=total_revenue,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/by-pricing-model",
    response_model=RevenueByPricingModelResponse,
    summary="Get revenue by pricing model",
    description="Aggregates revenue by pricing model (FTE, T&M, etc.)"
)
def get_revenue_pricing_model(
    business_unit_id: Optional[int] = Query(None, description="Filter by BU"),
    tenant_id: Optional[int] = Query(None, description="Filter by tenant"),
    db: Session = Depends(get_db)
) -> RevenueByPricingModelResponse:
    """Get revenue aggregated by pricing model."""
    try:
        data = get_revenue_by_pricing_model(db, business_unit_id, tenant_id)
        items = [RevenueByPricingModelItem(**item) for item in data]
        total_revenue = sum(item.revenue for item in items)

        return RevenueByPricingModelResponse(
            status="success",
            data=items,
            total_revenue=total_revenue,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/by-client-owner",
    response_model=RevenueByClientOwnerResponse,
    summary="Get revenue by client owner",
    description="Aggregates revenue by client owner (account manager) for P&L attribution"
)
def get_revenue_client_owner(
    business_unit_id: Optional[int] = Query(None, description="Filter by BU"),
    tenant_id: Optional[int] = Query(None, description="Filter by tenant"),
    db: Session = Depends(get_db)
) -> RevenueByClientOwnerResponse:
    """Get revenue aggregated by client owner."""
    try:
        data = get_revenue_by_client_owner(db, business_unit_id, tenant_id)
        items = [RevenueByClientOwnerItem(**item) for item in data]
        total_revenue = sum(item.revenue for item in items)

        return RevenueByClientOwnerResponse(
            status="success",
            data=items,
            total_revenue=total_revenue,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/partner-shares",
    response_model=PartnerRevenueShareResponse,
    summary="Get partner revenue share analysis",
    description="Aggregates partner revenue shares (CORE business only)"
)
def get_partner_shares(
    business_unit_id: Optional[int] = Query(None, description="Filter by BU"),
    tenant_id: Optional[int] = Query(None, description="Filter by tenant"),
    db: Session = Depends(get_db)
) -> PartnerRevenueShareResponse:
    """Get partner revenue share analysis."""
    try:
        data = get_partner_revenue_share_analysis(db, business_unit_id, tenant_id)
        items = [PartnerRevenueShareItem(**item) for item in data]
        total_partner_share = sum(item.partner_share_usd_cents for item in items)

        return PartnerRevenueShareResponse(
            status="success",
            data=items,
            total_partner_share=total_partner_share,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/forecast-vs-actual",
    response_model=ForecastVsActualResponse,
    summary="Get forecast vs actual revenue",
    description="Compares forecasted revenue (opportunities) vs actual recognized revenue"
)
def get_forecast_actual(
    business_unit_id: Optional[int] = Query(None, description="Filter by BU"),
    tenant_id: Optional[int] = Query(None, description="Filter by tenant"),
    db: Session = Depends(get_db)
) -> ForecastVsActualResponse:
    """Get forecast vs actual revenue analysis."""
    try:
        data = get_forecast_vs_actual(db, business_unit_id, tenant_id)
        items = [ForecastVsActualItem(**item) for item in data]
        total_forecast = sum(item.forecast_usd_cents for item in items)
        total_actual = sum(item.actual_usd_cents for item in items)
        total_variance = total_actual - total_forecast

        return ForecastVsActualResponse(
            status="success",
            data=items,
            total_forecast=total_forecast,
            total_actual=total_actual,
            total_variance=total_variance,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/negative-margins",
    response_model=NegativeMarginAlertsResponse,
    summary="Get loss-making projects",
    description="Identifies projects/invoices with negative gross margin (losses)"
)
def get_negative_margins(
    business_unit_id: Optional[int] = Query(None, description="Filter by BU"),
    tenant_id: Optional[int] = Query(None, description="Filter by tenant"),
    db: Session = Depends(get_db)
) -> NegativeMarginAlertsResponse:
    """Get negative margin alerts."""
    try:
        data = get_negative_margin_alerts(db, business_unit_id, tenant_id)
        items = [NegativeMarginAlertItem(**item) for item in data]
        total_loss = sum(item.gross_margin_usd_cents for item in items)

        return NegativeMarginAlertsResponse(
            status="success",
            data=items,
            alert_count=len(items),
            total_loss_usd_cents=total_loss,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/pnl-summary",
    response_model=PandLSummaryResponse,
    summary="Get P&L summary",
    description="Provides complete Profit & Loss summary for a period"
)
def get_pnl_summary(
    business_unit_id: Optional[int] = Query(None, description="Filter by BU"),
    tenant_id: Optional[int] = Query(None, description="Filter by tenant"),
    period_month: Optional[str] = Query(None, description="Specific month (YYYY-MM)"),
    db: Session = Depends(get_db)
) -> PandLSummaryResponse:
    """Get P&L summary."""
    try:
        result = calculate_p_and_l_summary(
            db,
            business_unit_id,
            period_month,
            tenant_id
        )

        return PandLSummaryResponse(
            status=result["status"],
            revenue_usd_cents=result["revenue_usd_cents"],
            cost_usd_cents=result["cost_usd_cents"],
            margin_usd_cents=result["margin_usd_cents"],
            margin_pct=result["margin_pct"],
            invoice_count=result["invoice_count"],
            avg_margin_pct_per_invoice=result["avg_margin_pct_per_invoice"],
            period=result["period"],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
