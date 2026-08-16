"""
S-242 (EPIC-02 Forecast vs Actual). Actuals come from Invoice, the same
computation revenue_target_service._fy_invoice_total_for_clients()
already established for the fiscal-year granularity (no
analytics_fact_revenue ETL table exists anywhere in this codebase).
Forecast is opportunity_service.calculate_weighted_forecast(), the one
shared calculation per HRMS-0209 BR-0209-01 -- no local recalculation.

Does NOT depend on S-279/HRMS-0313 (Plan vs Execution Variance) despite
S-242's own doc citing it as its actuals source -- that story is
unrelated hiring-headcount variance (planned heads vs actual hires),
confirmed by reading it directly. Revenue actuals come from Invoice
either way; this module doesn't wait on S-279.
"""
from datetime import date
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.invoice import Invoice
from app.models.opportunity import Opportunity
from app.services.opportunity_service import calculate_weighted_forecast
from app.services.revenue_target_service import status_band


def _month_bounds(year: int, month: int):
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


def get_monthly_actual_revenue(db: Session, *, client_ids: Optional[List[str]], year: int, month: int) -> int:
    start, end = _month_bounds(year, month)
    query = db.query(func.sum(Invoice.total_usd_cents)).filter(
        Invoice.status.in_(("APPROVED", "SENT", "PAID")),
        Invoice.created_at >= start, Invoice.created_at < end,
    )
    if client_ids is not None:
        if not client_ids:
            return 0
        query = query.filter(Invoice.client_id.in_(client_ids))
    return query.scalar() or 0


def get_monthly_weighted_forecast(db: Session, *, client_ids: Optional[List[str]], year: int, month: int) -> int:
    """WON opportunities count at their full realized value (not
    probability-weighted -- they already closed); everything else
    still open uses calculate_weighted_forecast(). LOST is excluded --
    dead pipeline isn't forecast."""
    start, end = _month_bounds(year, month)
    query = db.query(Opportunity).filter(
        Opportunity.stage != "LOST",
        Opportunity.expected_close_date.isnot(None),
        Opportunity.expected_close_date >= start, Opportunity.expected_close_date < end,
    )
    if client_ids is not None:
        if not client_ids:
            return 0
        query = query.filter(Opportunity.client_id.in_(client_ids))
    opportunities = query.all()
    return sum(
        o.revenue_value_usd_cents if o.stage == "WON" else calculate_weighted_forecast(o)
        for o in opportunities
    )


def get_forecast_vs_actual(
    db: Session, *, client_ids: Optional[List[str]], year: int, month: int, business_unit_id: Optional[int] = None,
) -> dict:
    actual = get_monthly_actual_revenue(db, client_ids=client_ids, year=year, month=month)
    forecast = get_monthly_weighted_forecast(db, client_ids=client_ids, year=year, month=month)
    variance = actual - forecast
    return {
        "business_unit_id": business_unit_id, "year": year, "month": month,
        "actual_usd_cents": actual, "forecast_usd_cents": forecast,
        "variance_usd_cents": variance,
        "status": status_band(actual, forecast) if forecast > 0 else "NO_FORECAST",
    }


def get_forecast_vs_actual_by_bu(db: Session, *, business_unit_id: int, year: int, month: int) -> dict:
    client_ids = [c.id for c in db.query(Client.id).filter(Client.bu_context_id == business_unit_id).all()]
    return get_forecast_vs_actual(db, client_ids=client_ids, year=year, month=month, business_unit_id=business_unit_id)


def get_forecast_vs_actual_trend(
    db: Session, *, client_ids: Optional[List[str]], year: int, business_unit_id: Optional[int] = None,
) -> List[dict]:
    """12-month trend for the fiscal year, one row per month -- the
    shape a chart on the CEO FY Progress dashboard and Executive
    Revenue Dashboard both need."""
    return [
        get_forecast_vs_actual(db, client_ids=client_ids, year=year, month=m, business_unit_id=business_unit_id)
        for m in range(1, 13)
    ]

