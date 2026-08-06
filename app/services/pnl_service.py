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
from typing import Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
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
