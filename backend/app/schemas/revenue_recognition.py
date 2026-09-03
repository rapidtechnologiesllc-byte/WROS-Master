"""
import logging
Pydantic schemas for Revenue Recognition (HRMS-0316)

Supports:
- Revenue recognition from paid invoices
- Revenue entry creation
- Annual subscription revenue (ASR/ARR) calculation
- Revenue reporting by various dimensions
- Margin analysis and P&L summaries
"""

import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.core.logging import logger


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================
logger = logging.getLogger(__name__)

class RecognizeRevenueRequest(BaseModel):
    """Request to recognize revenue from a paid invoice."""
    invoice_id: str = Field(..., description="ID of invoice to recognize")
    tenant_id: int = Field(..., description="Tenant ID")

    class Config:
        json_schema_extra = {
            "example": {
                "invoice_id": "inv_001",
                "tenant_id": 1,
            }
        }


class CreateRevenueEntriesRequest(BaseModel):
    """Request to create revenue entries for an invoice."""
    invoice_id: str = Field(..., description="ID of invoice")
    tenant_id: int = Field(..., description="Tenant ID")
    recognition_method: str = Field(
        default="MONTHLY",
        description="How to split revenue: MONTHLY, LINE_ITEM, QUARTERLY, ANNUAL"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "invoice_id": "inv_001",
                "tenant_id": 1,
                "recognition_method": "MONTHLY",
            }
        }


class CalculateASRRequest(BaseModel):
    """Request to calculate Annual Subscription Revenue (ASR/ARR)."""
    client_id: str = Field(..., description="Client ID")
    tenant_id: int = Field(..., description="Tenant ID")
    period_start: date = Field(..., description="Start date for analysis")
    period_end: date = Field(..., description="End date for analysis")

    class Config:
        json_schema_extra = {
            "example": {
                "client_id": "client_001",
                "tenant_id": 1,
                "period_start": "2024-01-01",
                "period_end": "2024-12-31",
            }
        }


class RevenueReportRequest(BaseModel):
    """Request for revenue reporting."""
    business_unit_id: Optional[int] = Field(None, description="Filter by business unit")
    tenant_id: Optional[int] = Field(None, description="Filter by tenant")
    period_start: Optional[date] = Field(None, description="Start of analysis period")
    period_end: Optional[date] = Field(None, description="End of analysis period")
    period_month: Optional[str] = Field(None, description="Specific month (YYYY-MM)")

    class Config:
        json_schema_extra = {
            "example": {
                "business_unit_id": 1,
                "tenant_id": 1,
                "period_start": "2024-01-01",
                "period_end": "2024-12-31",
            }
        }


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class RevenueRecognitionResponse(BaseModel):
    """Response after recognizing revenue from invoice."""
    status: str = Field(..., description="Status: success, error, already_recognized")
    invoice_id: str
    revenue_id: Optional[str] = None
    total_recognized_usd_cents: int
    gross_margin_usd_cents: int
    gross_margin_pct: int
    cost_usd_cents: int
    partner_share_usd_cents: Optional[int] = None
    entries_created: int
    recognized_at: str = Field(..., description="ISO 8601 timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "invoice_id": "inv_001",
                "revenue_id": "rev_001",
                "total_recognized_usd_cents": 400000,
                "gross_margin_usd_cents": 150000,
                "gross_margin_pct": 37,
                "cost_usd_cents": 250000,
                "partner_share_usd_cents": 80000,
                "entries_created": 1,
                "recognized_at": "2024-08-15T10:30:00Z",
            }
        }


class RevenueEntriesResponse(BaseModel):
    """Response after creating revenue entries."""
    status: str = Field(..., description="Status: success, already_recognized, error")
    invoice_id: str
    revenue_id: Optional[str] = None
    total_recognized_usd_cents: int
    entries_created: int
    recognition_method: str
    recognized_at: str = Field(..., description="ISO 8601 timestamp")
    gross_margin_usd_cents: int
    gross_margin_pct: int

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "invoice_id": "inv_001",
                "revenue_id": "rev_001",
                "total_recognized_usd_cents": 400000,
                "entries_created": 1,
                "recognition_method": "MONTHLY",
                "recognized_at": "2024-08-15T10:30:00Z",
                "gross_margin_usd_cents": 150000,
                "gross_margin_pct": 37,
            }
        }


class ASRResponse(BaseModel):
    """Response for Annual Subscription Revenue (ASR/ARR) calculation."""
    status: str = Field(..., description="Status: success, error")
    client_id: str
    arr_usd_cents: int = Field(..., description="Annual Recurring Revenue in USD cents")
    mrr_usd_cents: int = Field(..., description="Monthly Recurring Revenue in USD cents")
    total_revenue_usd_cents: int = Field(..., description="Total revenue in period")
    total_margin_usd_cents: int
    avg_margin_pct: float = Field(..., description="Average margin percentage")
    period: str
    invoice_count: int
    months_analyzed: float

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "client_id": "client_001",
                "arr_usd_cents": 14400000,
                "mrr_usd_cents": 1200000,
                "total_revenue_usd_cents": 4800000,
                "total_margin_usd_cents": 1800000,
                "avg_margin_pct": 37.5,
                "period": "2024-01-01 to 2024-12-31",
                "invoice_count": 12,
                "months_analyzed": 12.0,
            }
        }


class RevenueByMonthItem(BaseModel):
    """Single month's revenue data."""
    month: Optional[str]
    revenue: int = Field(..., description="USD cents")
    invoice_count: int
    avg_margin_pct: float


class RevenueByMonthResponse(BaseModel):
    """Revenue aggregated by month."""
    status: str = "success"
    data: List[RevenueByMonthItem]
    total_revenue: int = Field(default=0)
    total_invoices: int = Field(default=0)

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "data": [
                    {
                        "month": "2024-08",
                        "revenue": 400000,
                        "invoice_count": 2,
                        "avg_margin_pct": 35.5,
                    }
                ],
                "total_revenue": 4800000,
                "total_invoices": 12,
            }
        }


class RevenueByServiceItem(BaseModel):
    """Revenue data by service."""
    service: str
    revenue: int = Field(..., description="USD cents")
    invoice_count: int
    avg_margin_pct: float


class RevenueByServiceResponse(BaseModel):
    """Revenue aggregated by service type."""
    status: str = "success"
    data: List[RevenueByServiceItem]
    total_revenue: int = Field(default=0)

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "data": [
                    {
                        "service": "System Integration",
                        "revenue": 2000000,
                        "invoice_count": 5,
                        "avg_margin_pct": 38.0,
                    }
                ],
                "total_revenue": 4800000,
            }
        }


class RevenueByModuleItem(BaseModel):
    """Revenue data by Guidewire module."""
    module: str
    revenue: int = Field(..., description="USD cents")
    invoice_count: int
    avg_margin_pct: float


class RevenueByModuleResponse(BaseModel):
    """Revenue aggregated by Guidewire module."""
    status: str = "success"
    data: List[RevenueByModuleItem]
    total_revenue: int = Field(default=0)


class RevenueByPricingModelItem(BaseModel):
    """Revenue data by pricing model."""
    pricing_model: str
    revenue: int = Field(..., description="USD cents")
    invoice_count: int
    avg_margin_pct: float


class RevenueByPricingModelResponse(BaseModel):
    """Revenue aggregated by pricing model."""
    status: str = "success"
    data: List[RevenueByPricingModelItem]
    total_revenue: int = Field(default=0)


class RevenueByClientOwnerItem(BaseModel):
    """Revenue data by client owner."""
    client_owner_id: str
    revenue: int = Field(..., description="USD cents")
    invoice_count: int
    avg_margin_pct: float


class RevenueByClientOwnerResponse(BaseModel):
    """Revenue aggregated by client owner (account manager)."""
    status: str = "success"
    data: List[RevenueByClientOwnerItem]
    total_revenue: int = Field(default=0)


class PartnerRevenueShareItem(BaseModel):
    """Partner revenue share data."""
    partner_id: str
    total_revenue_usd_cents: int
    partner_share_usd_cents: int
    avg_share_pct: float
    invoice_count: int


class PartnerRevenueShareResponse(BaseModel):
    """Partner revenue share analysis."""
    status: str = "success"
    data: List[PartnerRevenueShareItem]
    total_partner_share: int = Field(default=0, description="Total USD cents paid to partners")


class ForecastVsActualItem(BaseModel):
    """Forecast vs actual data for an opportunity."""
    opportunity_id: str
    opportunity_name: str
    forecast_usd_cents: int = Field(..., description="Expected revenue from opportunity")
    actual_usd_cents: int = Field(..., description="Actual recognized revenue")
    variance_usd_cents: int = Field(..., description="Difference (actual - forecast)")
    variance_pct: float = Field(..., description="Variance percentage")


class ForecastVsActualResponse(BaseModel):
    """Forecast vs actual revenue analysis."""
    status: str = "success"
    data: List[ForecastVsActualItem]
    total_forecast: int = Field(default=0)
    total_actual: int = Field(default=0)
    total_variance: int = Field(default=0)


class NegativeMarginAlertItem(BaseModel):
    """Negative margin (loss-making) project alert."""
    revenue_id: str
    invoice_id: str
    project_id: str
    client_id: str
    revenue_usd_cents: int
    cost_usd_cents: int
    gross_margin_usd_cents: int
    gross_margin_pct: int
    recognized_at: str


class NegativeMarginAlertsResponse(BaseModel):
    """List of projects with negative margin."""
    status: str = "success"
    data: List[NegativeMarginAlertItem]
    alert_count: int = Field(default=0)
    total_loss_usd_cents: int = Field(default=0)


class PandLSummaryResponse(BaseModel):
    """Profit & Loss summary."""
    status: str = "success"
    revenue_usd_cents: int = Field(..., description="Total revenue")
    cost_usd_cents: int = Field(..., description="Total cost of delivery")
    margin_usd_cents: int = Field(..., description="Gross profit (revenue - cost)")
    margin_pct: float = Field(..., description="Gross margin percentage")
    invoice_count: int
    avg_margin_pct_per_invoice: float
    period: str = Field(..., description="all_time or YYYY-MM")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "revenue_usd_cents": 4800000,
                "cost_usd_cents": 3120000,
                "margin_usd_cents": 1680000,
                "margin_pct": 35.0,
                "invoice_count": 12,
                "avg_margin_pct_per_invoice": 35.2,
                "period": "2024-08",
            }
        }


class ErrorResponse(BaseModel):
    """Error response."""
    status: str = "error"
    message: str
    error_code: str = Field(None, description="Machine-readable error code")
    detail: Optional[Dict[str, Any]] = Field(None, description="Additional error details")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "error",
                "message": "Invoice inv_001 not found",
                "error_code": "INVOICE_NOT_FOUND",
                "detail": None,
            }
        }
