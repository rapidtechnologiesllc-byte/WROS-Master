"""
HRMS-0801 (Project Lifecycle) + HRMS-0804 (Milestones) + HRMS-0805
(Unfilled Roles) + HRMS-0806 (Revenue Estimate & Margin).

HRMS-0807 (Project Risk Flagging) is NOT built -- it's specified to
only ever display HRMS-1107's health score (Phase 3 EPIC-11 agent,
doesn't exist), never recompute one; there's nothing to display yet,
and building a second scoring formula would contradict that story's
own BR-0807-01.
"""
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.demand import Demand
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.opportunity import Opportunity
from app.models.project import Project, ProjectMilestone

PROJECT_STATUS_TRANSITIONS = {
    "PLANNING": {"ACTIVE", "CLOSED"},
    "ACTIVE": {"ON_HOLD", "COMPLETED", "CLOSED"},
    "ON_HOLD": {"ACTIVE", "CLOSED"},
    "COMPLETED": {"CLOSED"},
    "CLOSED": set(),
}


class InvalidProjectTransition(Exception):
    pass


class MilestoneValidationError(Exception):
    pass


def create_project_from_won_opportunity(
    db: Session, opportunity: Opportunity, *, name: str, tenant_id: Optional[int] = None,
    billing_type: str = "TIME_AND_MATERIALS", continent: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Project:
    """HRMS-0801 BR-0801-01: inherits client_id/currency directly from
    the won opportunity, no manual re-selection."""
    if opportunity.stage != "WON":
        raise ValueError(f"Cannot create a project from opportunity {opportunity.id} -- stage is '{opportunity.stage}', not WON.")

    project = Project(
        tenant_id=tenant_id or opportunity.tenant_id, client_id=opportunity.client_id,
        opportunity_id=opportunity.id, name=name, status="ACTIVE",
        billing_type=billing_type, currency=opportunity.currency, continent=continent,
        created_by=created_by,
    )
    db.add(project)
    return project


def create_project(
    db: Session, *, tenant_id: Optional[int], client_id: str, name: str,
    billing_type: str = "TIME_AND_MATERIALS", currency: str = "USD",
    continent: Optional[str] = None, created_by: Optional[str] = None,
) -> Project:
    """Manual creation path for non-opportunity-originated work (e.g. an
    existing client's direct follow-on request)."""
    project = Project(
        tenant_id=tenant_id, client_id=client_id, name=name, status="ACTIVE",
        billing_type=billing_type, currency=currency, continent=continent, created_by=created_by,
    )
    db.add(project)
    return project


def transition_project_status(db: Session, project: Project, new_status: str) -> Project:
    allowed = PROJECT_STATUS_TRANSITIONS.get(project.status, set())
    if new_status not in allowed:
        raise InvalidProjectTransition(
            f"Cannot transition project from '{project.status}' to '{new_status}'. "
            f"Allowed: {sorted(allowed) or 'none (terminal state)'}"
        )
    project.status = new_status
    project.updated_at = datetime.utcnow()
    db.add(project)
    return project


def create_milestone(
    db: Session, project: Project, *, title: str, due_date: date,
    tenant_id: Optional[int] = None, description: Optional[str] = None, owner_employee_id: Optional[str] = None,
) -> ProjectMilestone:
    milestone = ProjectMilestone(
        tenant_id=tenant_id or project.tenant_id, project_id=project.id,
        title=title, due_date=due_date, description=description, owner_employee_id=owner_employee_id,
    )
    db.add(milestone)
    return milestone


def complete_milestone(db: Session, milestone: ProjectMilestone, *, completion_date: Optional[date] = None) -> ProjectMilestone:
    """HRMS-0804 BR-0804-01: delay_days is always computed here, never
    accepted as a caller-supplied value -- there is no parameter for it."""
    if milestone.is_complete == "COMPLETE":
        raise MilestoneValidationError(f"Milestone {milestone.id} is already complete.")

    completion_date = completion_date or date.today()
    milestone.is_complete = "COMPLETE"
    milestone.completion_date = completion_date
    milestone.delay_days = max(0, (completion_date - milestone.due_date).days)
    db.add(milestone)
    return milestone


def get_unfilled_project_roles(db: Session, project: Project, *, now: Optional[date] = None) -> List[dict]:
    """
    HRMS-0805: cross-references each role demand linked to this project
    (Demand.project_id) against actual active allocations for that
    demand+project. A demand is a gap whenever its headcount exceeds
    the number of currently-ACTIVE allocations against it. gap_status
    is always derived fresh, never stored (per the doc's own note).
    """
    now = now or date.today()
    demands = db.query(Demand).filter(Demand.project_id == project.id).all()

    gaps = []
    for demand in demands:
        active_count = db.query(EmployeeAllocation).filter(
            EmployeeAllocation.demand_id == demand.id,
            EmployeeAllocation.project_id == project.id,
            EmployeeAllocation.status == "ACTIVE",
        ).count()
        open_positions = demand.headcount - active_count
        if open_positions <= 0:
            continue

        days_until_start = None
        gap_status = "OPEN"
        if demand.required_start_date:
            days_until_start = (demand.required_start_date - now).days
            if days_until_start < 0:
                gap_status = "OVERDUE"
            elif days_until_start <= 7:
                gap_status = "URGENT"

        gaps.append({
            "demand_id": demand.id, "job_title": demand.job_title,
            "open_positions": open_positions, "days_until_start": days_until_start,
            "gap_status": gap_status,
        })
    return gaps


def calculate_project_expected_revenue(db: Session, project: Project, *, now: Optional[date] = None) -> dict:
    """
    HRMS-0806 BR-0806-01: explicitly a rough estimate, never a finance-
    grade figure -- every result carries an "Estimate only -- not a
    finance figure" label, and missing cost data returns an explicit
    "insufficient data" state rather than a misleadingly confident
    number. Expected revenue = sum(billing_rate_usd_cents * 8h *
    business_days_remaining * utilization_pct) per active allocation;
    resource cost prorates Employee.base_salary_usd_cents (monthly)
    over the same remaining span.
    """
    now = now or date.today()
    allocations = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.project_id == project.id,
        EmployeeAllocation.status == "ACTIVE",
    ).all()

    if not allocations:
        return {
            "expected_revenue_usd_cents": None, "margin_indicator": "INSUFFICIENT_DATA",
            "note": "Estimate only -- not a finance figure. No active allocations to estimate from.",
        }

    total_revenue = 0
    total_cost = 0
    missing_cost_data = False

    for allocation in allocations:
        if not allocation.end_date or not allocation.billing_rate_usd_cents:
            missing_cost_data = True
            continue

        remaining_days = max(0, (allocation.end_date - now).days)
        business_days = remaining_days * 5 / 7  # rough weekday approximation
        utilization = float(allocation.utilization_pct or 100) / 100
        total_revenue += allocation.billing_rate_usd_cents * 8 * business_days * utilization

        employee = db.query(Employee).filter(Employee.id == allocation.employee_id).first()
        if employee and employee.base_salary_usd_cents:
            remaining_months = remaining_days / 30
            total_cost += employee.base_salary_usd_cents * remaining_months
        else:
            missing_cost_data = True

    if missing_cost_data and total_revenue == 0:
        return {
            "expected_revenue_usd_cents": None, "margin_indicator": "INSUFFICIENT_DATA",
            "note": "Estimate only -- not a finance figure. Missing billing rate, end date, or cost data.",
        }

    expected_revenue = round(total_revenue)
    margin = round(total_revenue - total_cost) if not missing_cost_data else None

    if margin is None:
        margin_indicator = "INSUFFICIENT_DATA"
    elif margin < 0:
        margin_indicator = "AT_RISK"
    elif total_revenue and margin / total_revenue < 0.2:
        margin_indicator = "TIGHT"
    else:
        margin_indicator = "HEALTHY"

    return {
        "expected_revenue_usd_cents": expected_revenue,
        "margin_usd_cents": margin,
        "margin_indicator": margin_indicator,
        "note": "Estimate only -- not a finance figure.",
    }
