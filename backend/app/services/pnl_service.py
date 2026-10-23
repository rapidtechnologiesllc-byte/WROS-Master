"""
EPIC-16 -- BU P&L Engine. Real workbook has both a BU P&L sheet (Axion
vs Prism) and a Location P&L sheet (BXIN vs BXUS legal entities) --
only BU P&L is built here. Location P&L is NOT built: no field
anywhere on Employee identified which legal entity (India vs US) an
employee sits in (since then: Employee.company_id / Client.contracting_company_id -- the
company P&L is revenue_chain_service._company_pnl) -- work_location (REMOTE/ONSITE/HYBRID) is a work-
arrangement concept, not a legal-entity one, and Employee.delivery_
engine (CORE/SPECIALITY) is a staffing-model split that correlates
with but isn't the same thing as legal entity. Building Location P&L
against either would be a guess dressed up as data. Flagged for
whoever adds a real entity/geography field to Employee next.

2026-10-08: both functions now read the revenue-chain P&L, so BU, partner
and org figures come from one calculation. Revenue is earned revenue by
timesheet week (was: invoice totals by creation month); cost is delivery
hours x hourly loaded cost plus bench (was: full salary of whoever is
currently allocated, regardless of the month).
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnit
from app.services.revenue_chain_service import month_bounds, pnl

logger = logging.getLogger(__name__)


def _legacy(section: dict) -> dict:
    """The revenue-chain P&L in the shape existing callers read: cost is None (not a
    fake figure) when any salary or cost-rate config is missing."""
    complete = section["cost_data_complete"]
    return {
        "revenue_usd_cents": section["revenue_usd_cents"],
        "cost_usd_cents": section["total_cost_usd_cents"] if complete else None,
        "gross_margin_usd_cents": section["margin_usd_cents"],
        "margin_pct": section["margin_pct"],
        "cost_data_complete": complete,
        "billed_usd_cents": section["billed_usd_cents"],
        "collected_usd_cents": section["collected_usd_cents"],
        "unbilled_usd_cents": section["unbilled_usd_cents"],
        "delivery_cost_usd_cents": section["delivery_cost_usd_cents"],
        "bench_cost_usd_cents": section["bench_cost_usd_cents"],
        "overhead_cost_usd_cents": section["overhead_cost_usd_cents"],
        "expense_cost_usd_cents": section["expense_cost_usd_cents"],
    }


def get_bu_pnl(db: Session, *, business_unit_id: int, year: int, month: int) -> dict:
    """One business unit's month from the revenue-chain P&L (app.services.revenue_chain_service):
    revenue earned on the BU's clients, their delivery cost, and the bench cost of the BU's own staff."""
    start, end = month_bounds(year, month)
    report = pnl(db, start=start, end=end)
    section = next((row for row in report["by_business_unit"] if row["key"] == business_unit_id), None)
    if section is None:
        return {"business_unit_id": business_unit_id, "year": year, "month": month,
                "revenue_usd_cents": 0, "cost_usd_cents": 0, "gross_margin_usd_cents": 0, "margin_pct": None,
                "cost_data_complete": True, "billed_usd_cents": 0, "collected_usd_cents": 0,
                "unbilled_usd_cents": 0, "delivery_cost_usd_cents": 0, "bench_cost_usd_cents": 0,
                "overhead_cost_usd_cents": 0,
                "expense_cost_usd_cents": 0}
    return {"business_unit_id": business_unit_id, "year": year, "month": month, **_legacy(section)}


def get_org_pnl_summary(db: Session, *, year: int, month: int, tenant_id: Optional[int] = None) -> dict:
    """Org month from the same calculation as every BU and partner, so they always add up."""
    start, end = month_bounds(year, month)
    report = pnl(db, start=start, end=end, tenant_id=tenant_id)
    names = {u.id: u.name for u in db.query(BusinessUnit).all()}
    org = _legacy(report)
    by_bu = [
        {"business_unit_id": row["key"], "business_unit_name": names.get(row["key"]),
         "year": year, "month": month, **_legacy(row)}
        for row in report["by_business_unit"] if row["key"] is not None
    ]
    return {
        "year": year, "month": month,
        "total_revenue_usd_cents": org["revenue_usd_cents"],
        "total_cost_usd_cents": org["cost_usd_cents"],
        "total_gross_margin_usd_cents": org["gross_margin_usd_cents"],
        "margin_pct": org["margin_pct"],
        "org_cost_data_complete": org["cost_data_complete"],
        "by_business_unit": by_bu,
        "by_partner": report["by_partner"],
        # each company's own P&L; the org totals above are the parent company's (tenant's)
        "by_company": report["by_company"],
    }
