"""
S-242 (EPIC-02 Forecast vs Actual).

Actual revenue for a month is EARNED revenue from the revenue chain
(revenue_chain_service.earned_revenue): work billed or approved, by
timesheet week -- the same income line as the P&L (CEO 2026-10-23: one
definition of monthly revenue). It used to be invoices by created_at,
which put a month's work into whatever month the invoice was raised.
Partner revenue share and the blended delivery rate read the same
get_monthly_actual_revenue().

Forecast is opportunity_service.calculate_weighted_forecast(), the one
shared calculation per HRMS-0209 BR-0209-01 -- no local recalculation.
"""
import calendar
from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.opportunity import WON_STAGES, Opportunity
from app.services.opportunity_service import calculate_weighted_forecast
from app.services.revenue_target_service import status_band

def _month_bounds(year: int, month: int):
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end

def get_monthly_actual_revenue(db: Session, *, client_ids: Optional[List[str]], year: int, month: int) -> int:
    """Earned revenue (USD cents) of the month for these clients (None = every client)."""
    from app.services.revenue_chain_service import earned_revenue

    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    return earned_revenue(db, start=start, end=end, client_ids=client_ids)

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
        o.revenue_value_usd_cents if o.stage in WON_STAGES else calculate_weighted_forecast(o)
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
    client_ids = [c.id for c in db.query(Client.id).filter(Client.business_unit_id == business_unit_id).all()]
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
