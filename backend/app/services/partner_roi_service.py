"""Partner performance (the Partner Home): KPIs, trend and prioritised actions for the business
units a partner leads, per BU and in total.

Scope is always an explicit set of business unit ids, chosen by the caller from the partner's own
BUs (app.services.bu_leadership.partnered_business_units) -- a partner with several BUs sees every
one of them, never only the BU on their user record.

KPIs per BlitzenX Operating Model: invoiced revenue, gross margin (revenue-chain P&L), net new
logos, practice utilization (billable hours / available hours of allocated staff) and YoY growth.
"""
import logging
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.employee_allocation import EmployeeAllocation
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.user import Users
from app.services.revenue_chain_service import month_bounds, pnl
from app.services.scope_helpers import allocation_in_bu, invoice_in_bu
from app.utils.agent_logger import log_agent_execution

logger = logging.getLogger(__name__)

# Available hours per allocated person per month: 40 h/week x ~4.33 weeks
AVAILABLE_HOURS_PER_MONTH = 173
INVOICED_STATUSES = ("APPROVED", "SENT", "PAID")
UTILIZATION_TARGET_PCT = 70
MARGIN_FLOOR_PCT = 15
NEW_LOGOS_FLOOR = 2


def _period(year_month: Optional[str]) -> tuple:
    if not year_month:
        return datetime.utcnow().year, datetime.utcnow().month
    try:
        year, month = (int(part) for part in year_month.split("-"))
    except ValueError as exc:
        raise ValueError(f"year_month must be YYYY-MM, got {year_month!r}") from exc
    if not 1 <= month <= 12:
        raise ValueError(f"year_month must be YYYY-MM, got {year_month!r}")
    return year, month


def _bounds(year: int, month: int) -> tuple:
    """[first of the month, first of the next month) as datetimes."""
    ny, nm = _shift(year, month, -1)
    return datetime(year, month, 1), datetime(ny, nm, 1)


def _shift(year: int, month: int, back: int) -> tuple:
    index = year * 12 + (month - 1) - back
    return index // 12, index % 12 + 1


def _invoiced_cents(db: Session, bu_id: int, start, end) -> int:
    return db.query(func.sum(Invoice.total_usd_cents)).filter(
        invoice_in_bu(bu_id), Invoice.created_at >= start, Invoice.created_at < end,
        Invoice.status.in_(INVOICED_STATUSES)).scalar() or 0


def _bu_month(db: Session, bu_id: int, year: int, month: int, pnl_rows: Dict[int, dict]) -> dict:
    """Raw monthly figures for one BU (summable across BUs)."""
    start, end = _bounds(year, month)
    prev_start, prev_end = _bounds(year - 1, month)
    allocated = db.query(func.count(func.distinct(EmployeeAllocation.employee_id))).filter(
        allocation_in_bu(bu_id), EmployeeAllocation.start_date < end,
        or_(EmployeeAllocation.end_date.is_(None), EmployeeAllocation.end_date >= start)).scalar() or 0
    billable_hours = float(db.query(func.sum(InvoiceLineItem.hours)).join(
        Invoice, Invoice.id == InvoiceLineItem.invoice_id).filter(
        invoice_in_bu(bu_id), Invoice.created_at >= start, Invoice.created_at < end).scalar() or 0)
    row = pnl_rows.get(bu_id) or {}
    margin_known = row.get("margin_usd_cents") is not None  # None: a salary/cost rate is missing
    return {
        "revenue_usd_cents": _invoiced_cents(db, bu_id, start, end),
        "prior_year_revenue_usd_cents": _invoiced_cents(db, bu_id, prev_start, prev_end),
        "net_new_logos": db.query(func.count(Client.id)).filter(
            Client.business_unit_id == bu_id, Client.status == "ACTIVE",
            Client.created_at >= start, Client.created_at < end).scalar() or 0,
        "allocated_headcount": allocated,
        "billable_hours": billable_hours,
        "pnl_revenue_usd_cents": (row.get("revenue_usd_cents") or 0) if margin_known else 0,
        "pnl_usd_cents": row["margin_usd_cents"] if margin_known else 0,
    }


def _kpis(raw: List[dict]) -> dict:
    """KPIs from the summed raw figures of one or more BUs."""
    total = {key: sum(r[key] for r in raw) for key in (
        "revenue_usd_cents", "prior_year_revenue_usd_cents", "net_new_logos", "allocated_headcount",
        "billable_hours", "pnl_revenue_usd_cents", "pnl_usd_cents")}
    available = total["allocated_headcount"] * AVAILABLE_HOURS_PER_MONTH
    prior = total["prior_year_revenue_usd_cents"]
    margin = (total["pnl_usd_cents"] / total["pnl_revenue_usd_cents"] * 100) if total["pnl_revenue_usd_cents"] else 0
    return {
        "revenue_usd": total["revenue_usd_cents"] / 100,
        "revenue_usd_cents": total["revenue_usd_cents"],
        "gross_margin_pct": round(margin, 1),
        "pnl_usd": total["pnl_usd_cents"] / 100,
        "pnl_usd_cents": total["pnl_usd_cents"],
        "pnl_margin_pct": round(margin, 1),
        "net_new_logos": total["net_new_logos"],
        "practice_utilization_pct": round(total["billable_hours"] / available * 100, 1) if available else 0,
        # No prior-year revenue -> growth is undefined, reported as 0 (never +infinity)
        "practice_growth_yoy_pct": round((total["revenue_usd_cents"] - prior) / prior * 100, 1) if prior else 0,
        "billable_hours": total["billable_hours"],
        "allocated_headcount": total["allocated_headcount"],
    }


def _month_pnl(db: Session, year: int, month: int, bu_ids: Iterable[int]) -> Dict[int, dict]:
    start, end = month_bounds(year, month)
    wanted = set(bu_ids)
    return {row["key"]: row for row in pnl(db, start=start, end=end)["by_business_unit"] if row["key"] in wanted}


def _partner(db: Session, partner_id: str) -> Users:
    partner = db.query(Users).filter(Users.UserID == partner_id).first()
    if partner is None:
        raise ValueError(f"Partner {partner_id} not found")
    return partner


def get_partner_kpis(db: Session, partner_id: str, business_unit_ids: Iterable[int],
                     year_month: Optional[str] = None) -> dict:
    """One month's KPIs over the given BUs in total, plus each BU's own."""
    bu_ids = sorted(set(business_unit_ids))
    partner = _partner(db, partner_id)
    year, month = _period(year_month)
    pnl_rows = _month_pnl(db, year, month, bu_ids)
    raw = {bu_id: _bu_month(db, bu_id, year, month, pnl_rows) for bu_id in bu_ids}
    result = {
        "partner_id": partner_id,
        "partner_name": partner.UserName,
        "business_unit_ids": bu_ids,
        "period": f"{year:04d}-{month:02d}",
        **_kpis(list(raw.values())),
        "by_business_unit": [{"business_unit_id": bu_id, **_kpis([raw[bu_id]])} for bu_id in bu_ids],
    }
    log_agent_execution(db=db, agent_name="Partner ROI Agent", action_taken="get_partner_kpis",
                        tenant_id=str(partner.tenant_id),
                        action_data={"business_unit_ids": bu_ids, "period": result["period"],
                                     "revenue_usd_cents": result["revenue_usd_cents"]}, success=True)
    return result


def get_partner_trend(db: Session, partner_id: str, business_unit_ids: Iterable[int], months_back: int = 6,
                      year_month: Optional[str] = None) -> List[dict]:
    """Total KPIs over the given BUs for each of the months_back months ending with year_month
    (default: the current month), oldest first."""
    if not 1 <= months_back <= 24:
        raise ValueError("months_back must be between 1 and 24")
    bu_ids = sorted(set(business_unit_ids))
    _partner(db, partner_id)
    year, month = _period(year_month)
    trend = []
    for back in range(months_back - 1, -1, -1):
        y, m = _shift(year, month, back)
        pnl_rows = _month_pnl(db, y, m, bu_ids)
        trend.append({"period": f"{y:04d}-{m:02d}",
                      **_kpis([_bu_month(db, bu_id, y, m, pnl_rows) for bu_id in bu_ids])})
    return trend


def get_partner_actions(kpis: dict) -> List[dict]:
    """Prioritised action items from a KPI set (get_partner_kpis)."""
    actions = []
    if kpis["practice_utilization_pct"] < UTILIZATION_TARGET_PCT:
        actions.append({"priority": "HIGH", "category": "UTILIZATION", "metric": "practice_utilization_pct",
                        "message": f"Practice utilization at {kpis['practice_utilization_pct']}% -- below "
                                   f"{UTILIZATION_TARGET_PCT}% target. Review open demands and bench allocation."})
    if kpis["pnl_margin_pct"] < MARGIN_FLOOR_PCT:
        actions.append({"priority": "HIGH", "category": "MARGIN", "metric": "pnl_margin_pct",
                        "message": f"Gross margin at {kpis['pnl_margin_pct']}% -- below {MARGIN_FLOOR_PCT}%. "
                                   "Review pricing and delivery costs."})
    if kpis["practice_growth_yoy_pct"] < 0:
        actions.append({"priority": "MEDIUM", "category": "GROWTH", "metric": "practice_growth_yoy_pct",
                        "message": f"Year-over-year revenue declined {abs(kpis['practice_growth_yoy_pct'])}% -- "
                                   "accelerate new customer acquisition."})
    if kpis["net_new_logos"] < NEW_LOGOS_FLOOR:
        actions.append({"priority": "MEDIUM", "category": "LOGOS", "metric": "net_new_logos",
                        "message": f"Only {kpis['net_new_logos']} new logos this month -- increase pipeline activity."})
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    return sorted(actions, key=lambda a: (order[a["priority"]], a["category"]))
