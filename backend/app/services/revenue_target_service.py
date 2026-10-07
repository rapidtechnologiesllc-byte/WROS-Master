"""
S-267/HRMS-0301 (Set BU Revenue Target) + PartnerGoal + S-241/HRMS-0212
(Executive Revenue Dashboard) + S-244/HRMS-0215 (Pipeline Coverage,
exposed via calculate_pipeline_coverage_ratio() -- already built,
reused here not reimplemented).

Actuals come from Invoice (client_id, total_usd_cents), never the
nonexistent analytics_fact_revenue S-267/S-242's own docs cite --
confirmed absent from this codebase, same call already made for the
Forecast vs Actual story.
"""
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.invoice import Invoice
from app.models.opportunity import Opportunity
from app.models.revenue_target import BURevenueTarget, PartnerGoal
from app.models.user import Users
from app.core.logging import logger
from app.services.opportunity_service import (
    aggregate_weighted_forecast, calculate_pipeline_coverage_ratio, calculate_weighted_forecast,
)
from app.services.permission_helper import PermissionHelper

# S-267's own bands.
ON_TRACK_THRESHOLD = 0.95
AT_RISK_THRESHOLD = 0.80

logger = logging.getLogger(__name__)

class RevenueTargetValidationError(Exception):
    pass

def status_band(actual_usd_cents: int, target_usd_cents: int) -> str:
    if target_usd_cents <= 0:
        return "NO_TARGET"
    pct = actual_usd_cents / target_usd_cents
    if pct >= ON_TRACK_THRESHOLD:
        return "ON_TRACK"
    if pct >= AT_RISK_THRESHOLD:
        return "AT_RISK"
    return "BEHIND"

def _fy_invoice_total_for_clients(db: Session, client_ids: List[str], fiscal_year: int) -> int:
    if not client_ids:
        return 0
    start = datetime(fiscal_year, 1, 1)
    end = datetime(fiscal_year + 1, 1, 1)
    total = (
        db.query(func.sum(Invoice.total_usd_cents))
        .filter(
            Invoice.client_id.in_(client_ids),
            Invoice.status.in_(("APPROVED", "SENT", "PAID")),
            Invoice.created_at >= start, Invoice.created_at < end,
        )
        .scalar()
    )
    return total or 0

# ---------------------------------------------------------------------------
# S-267: BU Revenue Target (BU Head/Director/Admin-set, per the doc's own BR)
# ---------------------------------------------------------------------------

def set_bu_revenue_target(
    db: Session, *, business_unit_id: int, target_period: str, fiscal_year: int,
    target_amount_usd_cents: int, created_by: str, tenant_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> BURevenueTarget:
    if target_amount_usd_cents <= 0:
        raise RevenueTargetValidationError("target_amount_usd_cents must be positive.")
    target = BURevenueTarget(
        tenant_id=tenant_id, business_unit_id=business_unit_id, target_period=target_period,
        fiscal_year=fiscal_year, target_amount_usd_cents=target_amount_usd_cents,
        created_by=created_by, notes=notes,
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    return target

def get_active_bu_target(db: Session, business_unit_id: int, target_period: str, fiscal_year: int) -> Optional[BURevenueTarget]:
    """Most recent row for the period wins -- append-only history, per
    S-267's own "cannot be deleted, only superseded" rule. Ordered by
    the autoincrement primary key (real, DB-guaranteed insertion order),
    not created_at -- see app.models.revenue_target's module docstring
    for why a wall-clock tiebreak is not safe here."""
    return (
        db.query(BURevenueTarget)
        .filter(
            BURevenueTarget.business_unit_id == business_unit_id,
            BURevenueTarget.target_period == target_period,
            BURevenueTarget.fiscal_year == fiscal_year,
        )
        .order_by(BURevenueTarget.id.desc())
        .first()
    )

def get_bu_target_vs_actual(db: Session, business_unit_id: int, target_period: str, fiscal_year: int) -> dict:
    target = get_active_bu_target(db, business_unit_id, target_period, fiscal_year)
    client_ids = [c.id for c in db.query(Client.id).filter(Client.business_unit_id == business_unit_id).all()]
    actual = _fy_invoice_total_for_clients(db, client_ids, fiscal_year)
    target_amount = target.target_amount_usd_cents if target else 0
    return {
        "business_unit_id": business_unit_id, "target_period": target_period, "fiscal_year": fiscal_year,
        "target_amount_usd_cents": target_amount, "actual_usd_cents": actual,
        "variance_usd_cents": actual - target_amount,
        "status": status_band(actual, target_amount) if target else "NO_TARGET",
    }

# ---------------------------------------------------------------------------
# PartnerGoal -- CEO-set only, per Avinash's explicit 2026-08-05 override
# of S-267's BR for the Partner level specifically.
# ---------------------------------------------------------------------------

def set_partner_goal(
    db: Session, *, partner_user_id: str, target_period: str, fiscal_year: int,
    target_amount_usd_cents: int, created_by_user: Users, tenant_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> PartnerGoal:
    """CEO-only, enforced via RBAC permission system.
    Users must have admin.manage or revenue.manage permission to set partner goals."""

    tenant_id = getattr(created_by_user, 'TenantID', 1) if created_by_user else 1
    has_permission = (
        PermissionHelper.has_permission(created_by_user.UserID, "admin-settings.edit", db, tenant_id) or
        PermissionHelper.has_permission(created_by_user.UserID, "revenue.edit", db, tenant_id)
    )
    if not has_permission:
        raise RevenueTargetValidationError(
            "Permission denied: only users with admin or revenue management access can set partner goals."
        )
    if target_amount_usd_cents <= 0:
        raise RevenueTargetValidationError("target_amount_usd_cents must be positive.")

    goal = PartnerGoal(
        tenant_id=tenant_id, partner_user_id=partner_user_id, target_period=target_period,
        fiscal_year=fiscal_year, target_amount_usd_cents=target_amount_usd_cents,
        created_by=created_by_user.UserID, notes=notes, created_at=datetime.utcnow(),
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal

def _partner_actual_revenue_for_fy(db: Session, partner_user_id: str, fiscal_year: int) -> int:
    partner = db.query(Users).filter(Users.UserID == partner_user_id).first()
    if partner is None or partner.business_unit_id is None:
        return 0
    client_ids = [c.id for c in db.query(Client.id).filter(Client.business_unit_id == partner.business_unit_id).all()]
    return _fy_invoice_total_for_clients(db, client_ids, fiscal_year)

def get_partner_multi_year_position(db: Session, partner_user_id: str) -> dict:
    """The FY carry-forward design from earlier this session: a
    negative year's shortfall accumulates into a running deficit that
    persists until a later positive year pays it down; a positive year
    with no outstanding deficit is shown as that year's own surplus,
    never banked forward as credit against a future target."""
    goals: List[PartnerGoal] = (
        db.query(PartnerGoal)
        .filter(PartnerGoal.partner_user_id == partner_user_id, PartnerGoal.target_period == "ANNUAL")
        .order_by(PartnerGoal.fiscal_year.asc())
        .all()
    )

    cumulative_deficit = 0
    years = []
    for goal in goals:
        actual = _partner_actual_revenue_for_fy(db, partner_user_id, goal.fiscal_year)
        variance = actual - goal.target_amount_usd_cents
        surplus_this_year = 0
        if variance >= 0:
            paydown = min(cumulative_deficit, variance)
            cumulative_deficit -= paydown
            surplus_this_year = variance - paydown
        else:
            cumulative_deficit += -variance
        years.append({
            "fiscal_year": goal.fiscal_year, "target_amount_usd_cents": goal.target_amount_usd_cents,
            "actual_usd_cents": actual, "variance_usd_cents": variance,
            "cumulative_deficit_usd_cents": cumulative_deficit, "current_fy_surplus_usd_cents": surplus_this_year,
        })

    return {
        "partner_user_id": partner_user_id,
        "years": years,
        "cumulative_deficit_usd_cents": cumulative_deficit,
        "current_fy_surplus_usd_cents": years[-1]["current_fy_surplus_usd_cents"] if years else 0,
    }

# ---------------------------------------------------------------------------
# S-241: Executive Revenue Dashboard -- pure aggregation, BR-0212-01:
# every figure calls S-238's shared calculate_weighted_forecast(), no
# local recalculation.
# ---------------------------------------------------------------------------

def get_executive_revenue_dashboard(db: Session, *, client_ids: Optional[List[str]] = None) -> dict:
    """Single JOIN, not a per-opportunity query -- an earlier version of
    this function issued one `SELECT clients WHERE id=...` per
    opportunity to resolve its BU, which is an N+1 query pattern that
    falls over at real data volume (hundreds/thousands of opportunities
    means hundreds/thousands of round trips for one dashboard load).
    Client.business_unit_id is joined in directly instead, one query
    total for the BU breakdown."""
    query = (
        db.query(Opportunity, Client.business_unit_id)
        .outerjoin(Client, Client.id == Opportunity.client_id)
    )
    if client_ids is not None:
        query = query.filter(Opportunity.client_id.in_(client_ids))
    rows = query.all()

    opportunities = [o for o, _bu_id in rows]
    # Won = contract signed / active engagement (there is no "WON" stage)
    won = [o for o in opportunities if o.stage in WON_STAGES]
    lost = [o for o in opportunities if o.stage == "LOST"]
    open_opps = [o for o in opportunities if o.stage not in WON_STAGES + ("LOST",)]

    total_pipeline_usd_cents = sum(o.revenue_value_usd_cents for o in open_opps)
    won_usd_cents = sum(o.revenue_value_usd_cents for o in won)
    lost_usd_cents = sum(o.revenue_value_usd_cents for o in lost)
    weighted_forecast_usd_cents = aggregate_weighted_forecast(open_opps)

    by_bu = {}
    for o, bu_id in rows:
        bucket = by_bu.setdefault(bu_id, {"business_unit_id": bu_id, "pipeline_usd_cents": 0, "won_usd_cents": 0, "weighted_forecast_usd_cents": 0})
        if o.stage in WON_STAGES:
            bucket["won_usd_cents"] += o.revenue_value_usd_cents
        elif o.stage != "LOST":
            bucket["pipeline_usd_cents"] += o.revenue_value_usd_cents
            bucket["weighted_forecast_usd_cents"] += calculate_weighted_forecast(o)

    return {
        "total_pipeline_usd_cents": total_pipeline_usd_cents,
        "won_usd_cents": won_usd_cents,
        "lost_usd_cents": lost_usd_cents,
        "weighted_forecast_usd_cents": weighted_forecast_usd_cents,
        "by_business_unit": list(by_bu.values()),
        **_executive_extras(db, client_ids=client_ids, pipeline_by_bu=by_bu,
                            total_pipeline_usd_cents=total_pipeline_usd_cents),
    }


WON_STAGES = ("CONTRACT", "ACTIVE")
BENCH_AGING_DAYS = 60


def _executive_extras(db: Session, *, client_ids, pipeline_by_bu: dict, total_pipeline_usd_cents: int) -> dict:
    """CEO Executive Metrics: YTD revenue, revenue per BU (every active BU
    from Business Units admin, with its FY revenue target from the goal
    tree), pipeline coverage of the org FY revenue target, capacity
    utilization and risk counts -- all from real records."""
    from datetime import date as date_type, timedelta as td

    from app.models.business_unit import BusinessUnit
    from app.models.employee import Employee
    from app.models.employee_allocation import EmployeeAllocation
    from app.models.revenue_leakage import RevenueLeakageFlag
    from app.models.strategic_goal import GoalTarget
    from app.services.ar_followup_service import scan_overdue_invoices

    now = datetime.utcnow()
    year = now.year
    start, end = datetime(year, 1, 1), datetime(year + 1, 1, 1)

    revenue_query = (
        db.query(Client.business_unit_id, func.sum(Invoice.total_usd_cents))
        .join(Client, Client.id == Invoice.client_id)
        .filter(Invoice.status.in_(("APPROVED", "SENT", "PAID")), Invoice.created_at >= start, Invoice.created_at < end)
    )
    if client_ids is not None:
        revenue_query = revenue_query.filter(Invoice.client_id.in_(client_ids))
    revenue_by_bu = {bu_id: int(total or 0) for bu_id, total in revenue_query.group_by(Client.business_unit_id).all()}

    bu_targets = {
        row.entity_id: row.target
        for row in db.query(GoalTarget).filter(GoalTarget.year == year, GoalTarget.level == "BU",
                                               GoalTarget.metric == "revenue").all()
    }
    visible_bus = None if client_ids is None else {bu for bu in revenue_by_bu} | {bu for bu in pipeline_by_bu}
    bu_metrics = []
    for bu in db.query(BusinessUnit).filter(BusinessUnit.active.is_(True)).order_by(BusinessUnit.name).all():
        if visible_bus is not None and bu.id not in visible_bus:
            continue
        target = bu_targets.get(str(bu.id))
        pipeline = pipeline_by_bu.get(bu.id, {})
        bu_metrics.append({
            "business_unit_id": bu.id,
            "name": bu.display_name or bu.name,
            "revenue_usd_cents": revenue_by_bu.get(bu.id, 0),
            "target_usd_cents": int(round(target * 100)) if target else None,
            "pipeline_usd_cents": pipeline.get("pipeline_usd_cents", 0),
            "won_usd_cents": pipeline.get("won_usd_cents", 0),
        })
    bu_metrics.sort(key=lambda b: b["revenue_usd_cents"], reverse=True)
    unassigned_revenue = revenue_by_bu.get(None, 0)

    org_target = db.query(GoalTarget).filter(GoalTarget.year == year, GoalTarget.level == "ORG",
                                             GoalTarget.metric == "revenue").first()
    pipeline_coverage = (
        round(total_pipeline_usd_cents / (org_target.target * 100), 2) if org_target and org_target.target else None
    )

    working = db.query(Employee).filter(Employee.status.notin_(("PRE_JOINING", "EXITED"))).all()
    allocated_ids = {
        row[0] for row in db.query(EmployeeAllocation.employee_id).filter(EmployeeAllocation.status == "ACTIVE").all()
    }
    allocated = sum(1 for e in working if e.id in allocated_ids)
    utilization = round(allocated / len(working) * 100, 1) if working else None
    unallocated = [e for e in working if e.id not in allocated_ids]
    aging_cutoff = date_type.today() - td(days=BENCH_AGING_DAYS)
    bench_aging = sum(1 for e in unallocated if e.joining_date and e.joining_date <= aging_cutoff)

    leakage_flags = db.query(func.count(RevenueLeakageFlag.id)).filter(
        RevenueLeakageFlag.partial_billing_reason.is_(None)
    ).scalar() or 0
    overdue = scan_overdue_invoices(db)

    return {
        "total_revenue_usd_cents": sum(revenue_by_bu.values()),
        "unassigned_bu_revenue_usd_cents": unassigned_revenue,
        "bu_metrics": bu_metrics,
        "pipeline_coverage": pipeline_coverage,
        "team_capacity_utilization_pct": utilization,
        "risks": [
            {"key": "revenue_leakage", "label": "Revenue Leakage", "severity": "high", "value": leakage_flags,
             "detail": "Approved hours not invoiced (unexplained)"},
            {"key": "overdue_invoices", "label": "Overdue Invoices", "severity": "medium", "value": len(overdue),
             "detail": "Sent and unpaid past the grace period"},
            {"key": "bench_aging", "label": f"Bench Aging > {BENCH_AGING_DAYS}d", "severity": "medium", "value": bench_aging,
             "detail": f"Unallocated, joined more than {BENCH_AGING_DAYS} days ago"},
            {"key": "unallocated", "label": "Unallocated Employees", "severity": "low", "value": len(unallocated),
             "detail": "Working employees without an active allocation"},
        ],
    }

def get_pipeline_coverage(db: Session, *, client_ids: Optional[List[str]], revenue_target_usd_cents: int) -> Optional[float]:
    """S-244 -- reuses opportunity_service.calculate_pipeline_coverage_ratio(),
    never a second implementation."""
    query = db.query(Opportunity).filter(Opportunity.stage.notin_(("WON", "LOST")))
    if client_ids is not None:
        query = query.filter(Opportunity.client_id.in_(client_ids))
    total_pipeline = sum(o.revenue_value_usd_cents for o in query.all())
    return calculate_pipeline_coverage_ratio(total_pipeline, revenue_target_usd_cents)
