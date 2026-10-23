"""
HRMS-0909 -- Client Revenue Realization Dashboard (S-228).

BR-0909-01 (the only numbered rule): internal-only, "distinct from
S-197's client-facing analytics" -- no client-facing exposure. That's
an API-layer scoping concern; nothing here changes for it since no
REST endpoints exist yet for this domain.

Pure aggregation, no new schema, per the doc's own Data Mapping table
("target table: N/A -- computed on view load"). Reuses HRMS-0906/0907
(Invoice, already built) as its own Depends On table specifies.

The source doc has real gaps this build had to fill with judgment,
each noted below:
  - Billable ratio's divide-by-zero (total_hours == 0) has no covering
    BR -- follows this session's established "insufficient data, not a
    misleading number" precedent (see HRMS-0806): returns None.
  - Earned is the revenue chain's earned revenue for the client to date
    (revenue_chain_service.earned_revenue: billed or approved work, by
    timesheet week), the same definition as the P&L.
  - Burn rate has no formula spec at all beyond "only meaningful for
    fixed-bid engagement types" -- implemented as earned
    revenue against the revenue a FIXED_BID project's elapsed timeline
    fraction alone would predict (100 = on pace, >100 = ahead of
    schedule spend, <100 = behind). Returns None whenever a project
    isn't FIXED_BID or lacks start/end dates, rather than guessing.
"""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.employee_allocation import EmployeeAllocation
from app.models.opportunity import Opportunity
from app.models.project import Project
from app.models.timesheet import Timesheet

REVENUE_DASHBOARD_NOTE = "Estimate only, not a finance figure."
# "to date" starts here: before any timesheet this system holds
EARLIEST_WORK = date(2000, 1, 1)

def _calculate_burn_rate_pct(projects, earned_usd_cents: int, planned_usd_cents: Optional[int],
                             today: Optional[date] = None) -> Optional[float]:
    if not planned_usd_cents or planned_usd_cents <= 0:
        return None

    fixed_bid = [p for p in projects if p.billing_type == "FIXED_BID" and p.start_date and p.end_date]
    if not fixed_bid:
        return None

    today = today or date.today()
    total_days = 0
    elapsed_days = 0
    for p in fixed_bid:
        span = (p.end_date - p.start_date).days
        if span <= 0:
            continue
        total_days += span
        elapsed_days += max(0, min(span, (today - p.start_date).days))

    if total_days <= 0:
        return None

    expected_spend = planned_usd_cents * (elapsed_days / total_days)
    if expected_spend <= 0:
        return None
    return round((earned_usd_cents / expected_spend) * 100, 2)

def get_client_revenue_dashboard(db: Session, client: Client, *, tenant_id: Optional[int] = None,
                                 today: Optional[date] = None) -> dict:
    from app.services.revenue_chain_service import earned_revenue

    today = today or date.today()
    projects = db.query(Project).filter(Project.client_id == client.id).all()
    if not projects:
        return {
            "earned_usd_cents": None, "planned_usd_cents": None,
            "billable_ratio_pct": None, "burn_rate_pct": None,
            "note": f"{REVENUE_DASHBOARD_NOTE} INSUFFICIENT_DATA -- no projects for this client.",
        }

    project_ids = [p.id for p in projects]

    earned_usd_cents = earned_revenue(db, start=EARLIEST_WORK, end=today, tenant_id=tenant_id,
                                      client_ids=[client.id])

    planned_usd_cents = None
    planned_total = 0
    for p in projects:
        if not p.opportunity_id:
            continue
        opp = db.query(Opportunity).filter(Opportunity.id == p.opportunity_id).first()
        if opp and opp.revenue_value_usd_cents:
            planned_total += opp.revenue_value_usd_cents
            planned_usd_cents = planned_total

    allocation_ids = [row[0] for row in db.query(EmployeeAllocation.id).filter(
        EmployeeAllocation.project_id.in_(project_ids)
    ).all()]
    billable_ratio_pct = None
    if allocation_ids:
        timesheets = db.query(Timesheet).filter(
            Timesheet.allocation_id.in_(allocation_ids), Timesheet.status == "APPROVED",
        ).all()
        total_hours = sum(float(t.total_hours) for t in timesheets)
        billable_hours = sum(float(t.billable_hours) for t in timesheets)
        if total_hours > 0:
            billable_ratio_pct = round((billable_hours / total_hours) * 100, 2)

    burn_rate_pct = _calculate_burn_rate_pct(projects, earned_usd_cents, planned_usd_cents, today)

    return {
        "earned_usd_cents": earned_usd_cents,
        "planned_usd_cents": planned_usd_cents,
        "billable_ratio_pct": billable_ratio_pct,
        "burn_rate_pct": burn_rate_pct,
        "note": REVENUE_DASHBOARD_NOTE,
    }
