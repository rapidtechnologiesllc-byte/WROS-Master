"""
Task 6 (EPIC-03, "AI Revenue-to-Workforce Conversion"): converts a BU's
revenue forecast into a projected headcount need, so Demand planning
import logging
has a real number to plan against instead of guessing.

No new table, no invented rate card -- the conversion ratio (revenue
per head) is derived from the BU's own actual, already-computed data:
trailing-period Invoice revenue for the BU's clients divided by how
many employees are currently allocated to those clients. That ratio,
applied to the forward-looking weighted forecast
(forecast_variance_service.get_monthly_weighted_forecast, the same
shared calculation used everywhere else), gives projected headcount
need. Compared against currently-open Demand headcount for the same BU
to surface the real planning gap.
"""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.demand import Demand
from app.models.employee_allocation import EmployeeAllocation
from app.services.forecast_variance_service import (
    get_monthly_actual_revenue, get_monthly_weighted_forecast,
)


def _client_ids_for_bu(db: Session, business_unit_id: int) -> list:
    return [c.id for c in db.query(Client.id).filter(Client.business_unit_id == business_unit_id).all()]


def get_current_bu_headcount(db: Session, business_unit_id: int) -> int:
    """Distinct employees with an ACTIVE allocation against one of the
    BU's clients -- EmployeeAllocation.client_id is the real link (no
    business_unit_id exists directly on Employee/EmployeeAllocation,
    same gap this session already flagged for the Operating Model)."""
    client_ids = _client_ids_for_bu(db, business_unit_id)
    if not client_ids:
        return 0
    count = (
        db.query(EmployeeAllocation.employee_id)
        .filter(EmployeeAllocation.client_id.in_(client_ids), EmployeeAllocation.status == "ACTIVE")
        .distinct()
        .count()
    )
    return count


def get_open_demand_headcount(db: Session, business_unit_id: int) -> int:
    """Sum of open positions (headcount - positions_filled) on OPEN/
    IN_PROGRESS Demand rows already assigned to this BU -- what's
    already in the pipeline, separate from what revenue implies is
    needed."""
    demands = db.query(Demand).filter(
        Demand.assigned_bu_id == business_unit_id, Demand.status.in_(("OPEN", "IN_PROGRESS")),
    ).all()
    return sum(max(d.headcount - d.positions_filled, 0) for d in demands)


def get_revenue_to_demand_projection(
    db: Session, *, business_unit_id: int, year: int, month: int, trailing_months: int = 3,
) -> dict:
    """The real conversion: trailing revenue-per-head (actuals over the
    last trailing_months, divided by current headcount) applied to the
    forward weighted forecast for the target month. Returns None for
    projected_headcount_needed when there's no current headcount or no
    trailing revenue to derive a ratio from -- never a fabricated
    number from a zero-headcount or zero-revenue BU."""
    client_ids = _client_ids_for_bu(db, business_unit_id)
    current_headcount = get_current_bu_headcount(db, business_unit_id)

    trailing_revenue = 0
    m, y = month, year
    for _ in range(trailing_months):
        m -= 1
        if m == 0:
            m, y = 12, y - 1
        trailing_revenue += get_monthly_actual_revenue(db, client_ids=client_ids, year=y, month=m)

    revenue_per_head = (trailing_revenue / trailing_months / current_headcount) if current_headcount > 0 and trailing_revenue > 0 else None

    forecast_usd_cents = get_monthly_weighted_forecast(db, client_ids=client_ids, year=year, month=month)

    projected_headcount_needed = None
    if revenue_per_head:
        projected_headcount_needed = round(forecast_usd_cents / revenue_per_head, 1)

    open_demand_headcount = get_open_demand_headcount(db, business_unit_id)

    workforce_gap = None
    if projected_headcount_needed is not None:
        workforce_gap = round(projected_headcount_needed - current_headcount - open_demand_headcount, 1)

    return {
        "business_unit_id": business_unit_id, "year": year, "month": month,
        "current_headcount": current_headcount,
        "trailing_avg_monthly_revenue_usd_cents": round(trailing_revenue / trailing_months) if trailing_revenue else 0,
        "revenue_per_head_usd_cents": round(revenue_per_head) if revenue_per_head else None,
        "forecast_usd_cents": forecast_usd_cents,
        "projected_headcount_needed": projected_headcount_needed,
        "open_demand_headcount": open_demand_headcount,
        "workforce_gap": workforce_gap,
    }
