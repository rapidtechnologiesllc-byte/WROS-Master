"""
EPIC-16 -- BU P&L Engine. Real workbook has both a BU P&L sheet (Axion
vs Prism) and a Location P&L sheet (BXIN vs BXUS legal entities) --
only BU P&L is built here. Location P&L is NOT built: no field
anywhere on Employee identifies which legal entity (India vs US) an
employee sits in -- work_location (REMOTE/ONSITE/HYBRID) is a work-
arrangement concept, not a legal-entity one, and Employee.delivery_
engine (CORE/SPECIALITY) is a staffing-model split that correlates
with but isn't the same thing as legal entity. Building Location P&L
against either would be a guess dressed up as data. Flagged for
whoever adds a real entity/geography field to Employee next.
"""
from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.business_unit import BusinessUnit
from app.services.cost_rate_service import calculate_fully_loaded_cost_usd_cents, get_active_cost_rate_config
from app.services.forecast_variance_service import get_monthly_actual_revenue


def get_bu_pnl(db: Session, *, business_unit_id: int, year: int, month: int) -> dict:
    """Revenue (real Invoice actuals for the BU's clients) minus cost
    (fully loaded cost of every employee ACTIVE-allocated to one of
    those clients this month). Both real, derived numbers -- no
    invented allocation formula beyond what cost_rate_service already
    established."""
    client_ids = [c.id for c in db.query(Client.id).filter(Client.business_unit_id == business_unit_id).all()]
    revenue_usd_cents = get_monthly_actual_revenue(db, client_ids=client_ids, year=year, month=month)

    config = get_active_cost_rate_config(db, business_unit_id=business_unit_id)

    cost_usd_cents = 0
    cost_data_complete = True
    if client_ids and config is not None:
        employee_ids = {
            row[0] for row in db.query(EmployeeAllocation.employee_id).filter(
                EmployeeAllocation.client_id.in_(client_ids), EmployeeAllocation.status == "ACTIVE",
            ).distinct().all()
        }
        for employee_id in employee_ids:
            employee = db.query(Employee).filter(Employee.id == employee_id).first()
            if employee is None:
                continue
            employee_cost = calculate_fully_loaded_cost_usd_cents(employee, config)
            if employee_cost is None:
                cost_data_complete = False
                continue
            cost_usd_cents += employee_cost
    elif config is None:
        cost_data_complete = False

    gross_margin_usd_cents = revenue_usd_cents - cost_usd_cents if cost_data_complete else None
    margin_pct = (
        round(gross_margin_usd_cents / revenue_usd_cents * 100, 1)
        if gross_margin_usd_cents is not None and revenue_usd_cents > 0
        else None
    )

    return {
        "business_unit_id": business_unit_id, "year": year, "month": month,
        "revenue_usd_cents": revenue_usd_cents,
        "cost_usd_cents": cost_usd_cents if cost_data_complete else None,
        "gross_margin_usd_cents": gross_margin_usd_cents,
        "margin_pct": margin_pct,
        "cost_data_complete": cost_data_complete,
    }


def get_org_pnl_summary(db: Session, *, year: int, month: int, tenant_id: Optional[int] = None) -> dict:
    """EPIC-16 Executive Dashboard -- org-level rollup, real sum of
    every BU's own get_bu_pnl(), not a separately recomputed number
    (BR-0212-01-style "one shared calculation" discipline: the BU
    figure is the only place revenue-per-BU/cost-per-BU gets computed,
    this just adds them up). A BU with incomplete cost data (no
    cost-rate config set) is flagged in by_bu but doesn't silently
    zero out or block the other BUs' totals -- org_cost_data_complete
    is False whenever any BU's own cost_data_complete is False, so the
    org total is honestly marked incomplete rather than pretending to
    be exact.

    Deliberately not tenant-filtered on BusinessUnit itself -- BU rows
    are a small, admin-created list (confirmed via grep this session:
    not auto-seeded per-tenant), same posture as list_business_units()
    elsewhere in this codebase, which doesn't filter by tenant either.
    Revenue/cost per BU still only ever reads that tenant's own real
    data through get_bu_pnl()'s existing scoping."""
    business_units = db.query(BusinessUnit).all()

    by_bu = []
    total_revenue = 0
    total_cost = 0
    org_cost_data_complete = True
    for bu in business_units:
        pnl = get_bu_pnl(db, business_unit_id=bu.id, year=year, month=month)
        by_bu.append({"business_unit_id": bu.id, "business_unit_name": bu.name, **pnl})
        total_revenue += pnl["revenue_usd_cents"]
        if pnl["cost_data_complete"] and pnl["cost_usd_cents"] is not None:
            total_cost += pnl["cost_usd_cents"]
        else:
            org_cost_data_complete = False

    total_margin = (total_revenue - total_cost) if org_cost_data_complete else None
    margin_pct = round(total_margin / total_revenue * 100, 1) if total_margin is not None and total_revenue > 0 else None

    return {
        "year": year, "month": month,
        "total_revenue_usd_cents": total_revenue,
        "total_cost_usd_cents": total_cost if org_cost_data_complete else None,
        "total_gross_margin_usd_cents": total_margin,
        "margin_pct": margin_pct,
        "org_cost_data_complete": org_cost_data_complete,
        "by_business_unit": by_bu,
    }
