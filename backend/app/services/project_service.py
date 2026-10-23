"""
HRMS-0801 (Project Lifecycle) + HRMS-0804 (Milestones) + HRMS-0805
(Unfilled Roles) + HRMS-0806 (Revenue Estimate & Margin).

HRMS-0807 (Project Risk Flagging) is NOT built -- it's specified to
only ever display HRMS-1107's health score (Phase 3 EPIC-11 agent,
doesn't exist), never recompute one; there's nothing to display yet,
and building a second scoring formula would contradict that story's
own BR-0807-01.
"""
import logging
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.demand import Demand
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.opportunity import Opportunity
from app.models.project import BILLING_TYPES, Project, ProjectMilestone
from app.models.user import Users

PROJECT_STATUS_TRANSITIONS = {
    "PLANNING": {"ACTIVE", "CLOSED"},
    "ACTIVE": {"ON_HOLD", "COMPLETED", "CLOSED"},
    "ON_HOLD": {"ACTIVE", "CLOSED"},
    "COMPLETED": {"CLOSED"},
    "CLOSED": set(),
}

logger = logging.getLogger(__name__)

class InvalidProjectTransition(Exception):
    pass

class MilestoneValidationError(Exception):
    pass

class ProjectValidationError(ValueError):
    """A project field the caller sent is not valid (unknown billing type, end before start,
    unknown manager). The REST layer answers 400."""

def _validate_billing_type(billing_type: str) -> None:
    if billing_type not in BILLING_TYPES:
        raise ProjectValidationError(f"billing_type must be one of {list(BILLING_TYPES)}, not {billing_type!r}.")

def _validate_dates(start_date: Optional[date], end_date: Optional[date]) -> None:
    if start_date and end_date and end_date < start_date:
        raise ProjectValidationError(f"end_date {end_date} is before start_date {start_date}.")

def _validate_manager(db: Session, manager_user_id: Optional[str], tenant_id: Optional[int]) -> None:
    """The manager must be an active internal user of the project's tenant."""
    if manager_user_id is None:
        return
    query = db.query(Users.UserID).filter(Users.UserID == manager_user_id, Users.terminated_at.is_(None))
    if tenant_id is not None:
        query = query.filter(Users.tenant_id == tenant_id)
    if query.first() is None:
        raise ProjectValidationError(f"Project manager {manager_user_id!r} is not an active user of this tenant.")

class SiPartnerRequired(Exception):
    """S-358/HRMS-0519 BR: SI Partner Mandatory for SPECIALITY Projects.
    Raised by the REST layer (app.api.v1.endpoints.projects), not here --
    create_project()/create_project_from_won_opportunity() are reused as
    plain fixture helpers by many other stories' tests (invoices,
    milestones, anomaly detection) that have nothing to do with SI
    partner tagging and never supply one; forcing this BR into the
    shared service function would break every one of those callers for
    a rule the doc's own AC-1 phrases as an API-call behavior
    ("API call with delivery_engine=CORE... returns HTTP 400"), not a
    service-layer invariant every caller must satisfy.

    2026-08-06: no longer raised at all. si_partner is retired from the
    create-project flow entirely -- Avinash's direct instruction: SI
    Partners (PWC, EY, etc.) ARE clients (line_type=SPECIALITY, real
    rows in the same Client Master), client_id already identifies the
    SI partner, a parallel si_partner field is redundant. The DB column
    is left in place (untouched schema) but every new project leaves it
    null; nothing reads it as authoritative anymore."""

def create_project_from_won_opportunity(
    db: Session, opportunity: Opportunity, *, name: str, tenant_id: Optional[int] = None,
    billing_type: str = "TIME_AND_MATERIALS", continent: Optional[str] = None,
    delivery_engine: str = "SPECIALITY", si_partner: Optional[str] = None,
    end_client: Optional[str] = None, client_partner: Optional[str] = None,
    business_type: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Project:
    """HRMS-0801 BR-0801-01: inherits client_id/currency directly from
    the won opportunity, no manual re-selection."""
    _validate_billing_type(billing_type)
    if opportunity.stage != "CONTRACT":
        raise ValueError(f"Cannot create a project from opportunity {opportunity.id} -- stage is "
                         f"'{opportunity.stage}', not CONTRACT (the signed contract is the win).")
    if db.query(Project.id).filter(Project.opportunity_id == opportunity.id).first():
        raise ValueError(f"Opportunity {opportunity.id} already has a project.")

    project = Project(
        tenant_id=tenant_id or opportunity.tenant_id, client_id=opportunity.client_id,
        opportunity_id=opportunity.id, name=name, status="ACTIVE",
        billing_type=billing_type, currency=opportunity.currency, continent=continent,
        delivery_engine=delivery_engine, si_partner=si_partner,
        end_client=end_client, client_partner=client_partner, business_type=business_type,
        created_by=created_by,
    )
    db.add(project)
    return project

def create_project(
    db: Session, *, tenant_id: Optional[int], client_id: str, name: str,
    billing_type: str = "TIME_AND_MATERIALS", currency: str = "USD",
    continent: Optional[str] = None, delivery_engine: str = "SPECIALITY",
    si_partner: Optional[str] = None,
    end_client: Optional[str] = None, client_partner: Optional[str] = None,
    business_type: Optional[str] = None,
    created_by: Optional[str] = None,
    start_date: Optional[date] = None, end_date: Optional[date] = None,
    manager_user_id: Optional[str] = None,
) -> Project:
    """Manual creation path for non-opportunity-originated work (e.g. an
    existing client's direct follow-on request)."""
    _validate_billing_type(billing_type)
    _validate_dates(start_date, end_date)
    _validate_manager(db, manager_user_id, tenant_id)
    project = Project(
        tenant_id=tenant_id, client_id=client_id, name=name, status="ACTIVE",
        billing_type=billing_type, currency=currency, continent=continent,
        delivery_engine=delivery_engine, si_partner=si_partner,
        end_client=end_client, client_partner=client_partner, business_type=business_type,
        created_by=created_by, start_date=start_date, end_date=end_date, manager_user_id=manager_user_id,
    )
    db.add(project)
    return project

EDITABLE_PROJECT_FIELDS = ("name", "start_date", "end_date", "billing_type", "manager_user_id")

def update_project(db: Session, project: Project, changes: dict) -> Project:
    """Edit a project's name, dates, billing type and project manager. `changes` holds only the
    fields the caller sent; start_date, end_date and manager_user_id may be None to clear them.
    Dates make the fixed-bid burn rate (client_revenue_dashboard_service) computable."""
    unknown = set(changes) - set(EDITABLE_PROJECT_FIELDS)
    if unknown:
        raise ProjectValidationError(f"Cannot edit {sorted(unknown)}; editable: {list(EDITABLE_PROJECT_FIELDS)}.")
    if "name" in changes:
        name = (changes["name"] or "").strip()
        if not name:
            raise ProjectValidationError("Project name cannot be empty.")
        changes = {**changes, "name": name}
    if "billing_type" in changes:
        if changes["billing_type"] is None:
            raise ProjectValidationError("billing_type cannot be cleared.")
        _validate_billing_type(changes["billing_type"])
    _validate_dates(changes.get("start_date", project.start_date), changes.get("end_date", project.end_date))
    if "manager_user_id" in changes:
        _validate_manager(db, changes["manager_user_id"], project.tenant_id)
    for field, value in changes.items():
        setattr(project, field, value)
    project.updated_at = datetime.utcnow()
    db.add(project)
    logger.info(f"[Project] {project.id} updated: {sorted(changes)}")
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
    number.

    For each active allocation, over its remaining span (from today or its start, whichever is
    later, to its end date): hours = standard daily hours x business days x utilization;
    revenue = hours x bill rate; cost = hours x the employee's hourly LOADED cost (salary +
    statutory + overhead, revenue_chain_service.CostBook) -- the same cost the P&L charges for
    delivered hours, so this estimate and the P&L margin can never disagree on cost.
    """
    from app.core.config import settings
    from app.services.revenue_chain_service import CostBook

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

    costs = CostBook(db)
    daily_hours = settings.STANDARD_DAILY_HOURS
    total_revenue = 0.0
    total_cost = 0.0
    missing_cost_data = False

    for allocation in allocations:
        if not allocation.end_date or not allocation.billing_rate_usd_cents:
            missing_cost_data = True
            continue

        span_start = max(now, allocation.start_date) if allocation.start_date else now
        remaining_days = max(0, (allocation.end_date - span_start).days)
        business_days = remaining_days * 5 / 7  # rough weekday approximation
        utilization = float(allocation.utilization_pct or 100) / 100
        hours = daily_hours * business_days * utilization
        total_revenue += allocation.billing_rate_usd_cents * hours

        employee = db.query(Employee).filter(Employee.id == allocation.employee_id).first()
        hourly = costs.hourly(employee, span_start) if employee is not None else None
        if hourly is None:
            missing_cost_data = True
        else:
            total_cost += hourly * hours

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
    elif total_revenue and margin / total_revenue * 100 < settings.PROJECT_MARGIN_TIGHT_PCT:
        margin_indicator = "TIGHT"
    else:
        margin_indicator = "HEALTHY"

    return {
        "expected_revenue_usd_cents": expected_revenue,
        "margin_usd_cents": margin,
        "margin_indicator": margin_indicator,
        "note": "Estimate only -- not a finance figure. Cost is loaded cost (salary + statutory + overhead), "
                "as in the P&L.",
    }
