"""
HRMS-0801 (Project Lifecycle) + HRMS-0804 (Milestones) + HRMS-0805
(Unfilled Roles) + HRMS-0806 (Revenue Estimate & Margin) + S-358/
HRMS-0519 (SI Partner Engagement Tagging) -- API Endpoints
=========================================================================
Prefix: /projects
Tag:    projects

Wires app.services.project_service (real, tested backend, pre-existing
this codebase -- HRMS-0801/0804/0805/0806) to real HTTP routes. No
REST layer previously existed at all for Project -- nothing in this
app could create one through the UI before this, which also blocked
S-358's SI Partner tagging (its own doc assumes a Project form exists
to attach the field to).

S-358/HRMS-0519 folded in here rather than a separate file, since it's
purely new columns + a validation rule on the same Project entity this
file already owns: si_partner is mandatory whenever delivery_engine=
SPECIALITY (SiPartnerRequired -> HTTP 400, per the doc's own AC-1).

HRMS-0807 (Project Risk Flagging) is deliberately not exposed here --
project_service.py's own docstring explains why (it's specified to
only ever display a Phase-3 agent's health score, which doesn't exist).

Auth: get_current_hr_or_admin, same posture as every endpoint this
program.

Routes:
  POST   /projects                              Create a project.
  GET    /projects                               List (optional client_id/status filter).
  GET    /projects/{id}                          Get one project.
  POST   /projects/{id}/status                   Transition status.
  POST   /projects/{id}/milestones               Create a milestone.
  GET    /projects/{id}/milestones               List milestones.
  POST   /projects/{id}/milestones/{mid}/complete  Complete a milestone.
  GET    /projects/{id}/unfilled-roles           Open headcount gaps.
  GET    /projects/{id}/expected-revenue         Rough revenue/margin estimate.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin
from app.models.client import Client
from app.models.project import (
    CORE_CURRENCIES,
    Project,
    ProjectMilestone,
    SPECIALITY_CURRENCIES,
)
from app.models.user import Users
from app.schemas.project import (
    CompleteMilestoneRequest,
    CreateMilestoneRequest,
    CreateProjectRequest,
    ExpectedRevenueResponse,
    MilestoneItem,
    MilestoneListResponse,
    ProjectItem,
    ProjectListResponse,
    TransitionProjectStatusRequest,
    UnfilledRoleItem,
    UnfilledRolesResponse,
)
from app.services.project_service import (
    InvalidProjectTransition,
    MilestoneValidationError,
    calculate_project_expected_revenue,
    complete_milestone,
    create_milestone,
    create_project,
    get_unfilled_project_roles,
    transition_project_status,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_item(project: Project) -> ProjectItem:
    return ProjectItem(
        id=project.id, client_id=project.client_id, opportunity_id=project.opportunity_id,
        name=project.name, status=project.status, billing_type=project.billing_type,
        currency=project.currency, continent=project.continent,
        delivery_engine=project.delivery_engine, si_partner=project.si_partner,
        end_client=project.end_client, client_partner=project.client_partner,
        business_type=project.business_type,
        allow_weekend_billing=project.allow_weekend_billing,
        start_date=project.start_date, end_date=project.end_date,
    )


def _milestone_to_item(m: ProjectMilestone) -> MilestoneItem:
    return MilestoneItem(
        id=m.id, project_id=m.project_id, title=m.title, description=m.description,
        due_date=m.due_date, owner_employee_id=m.owner_employee_id,
        is_complete=m.is_complete, completion_date=m.completion_date, delay_days=m.delay_days,
    )


def _get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@router.post("", response_model=ProjectItem, summary="Create a project")
def create_project_endpoint(
    body: CreateProjectRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    # 2026-08-06 redesign, confirmed directly with Avinash while testing
    # live: delivery_engine and si_partner are no longer caller-supplied
    # -- both are derived server-side from the selected client's own
    # line_type, the same single source of truth the real Client Master
    # workbook uses (SI Partners like PWC are just Client rows with
    # line_type=SPECIALITY, not a second disconnected concept). The
    # client is authoritative; body.delivery_engine/si_partner (still
    # accepted for backward-compat request shapes) are ignored.
    client = db.query(Client).filter(Client.id == body.client_id).first()
    if client is None:
        raise HTTPException(status_code=404, detail=f"Client {body.client_id!r} not found.")
    if not client.line_type:
        raise HTTPException(
            status_code=400,
            detail=f"Client {client.company_name!r} has no Line Type set -- cannot derive a delivery engine.",
        )
    delivery_engine = client.line_type
    si_partner = None  # client_id is the SI partner now -- no parallel field

    # Backlog item, 2026-08-05: business_type required for CORE (the
    # revenue-subtype breakdown Avinash asked for), meaningless for
    # Speciality -- same "enforced at the API boundary, not inside
    # create_project()" posture as si_partner above.
    if delivery_engine == "CORE" and not body.business_type:
        raise HTTPException(status_code=400, detail="Business Type is required for Core Engine projects.")

    # Currency-by-delivery_engine: Speciality allows INR or USD, Core is
    # USD-only at this point -- Avinash's own words.
    if delivery_engine == "SPECIALITY" and body.currency not in SPECIALITY_CURRENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Speciality Engine projects must be billed in {' or '.join(SPECIALITY_CURRENCIES)}.",
        )
    if delivery_engine == "CORE" and body.currency not in CORE_CURRENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Core Engine projects must be billed in {' or '.join(CORE_CURRENCIES)}.",
        )

    project = create_project(
        db, tenant_id=current_user.tenant_id, client_id=body.client_id, name=body.name,
        billing_type=body.billing_type, currency=body.currency, continent=body.continent,
        delivery_engine=delivery_engine, si_partner=si_partner,
        end_client=body.end_client, client_partner=body.client_partner,
        business_type=body.business_type,
        created_by=current_user.UserID,
    )
    project.allow_weekend_billing = body.allow_weekend_billing
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_item(project)


@router.get("", response_model=ProjectListResponse, summary="List projects")
def list_projects(
    client_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    query = db.query(Project).filter(Project.tenant_id == current_user.tenant_id)
    if client_id:
        query = query.filter(Project.client_id == client_id)
    if status:
        query = query.filter(Project.status == status)
    projects = query.order_by(Project.created_at.desc()).all()
    return ProjectListResponse(projects=[_to_item(p) for p in projects])


@router.get("/{project_id}", response_model=ProjectItem, summary="Get one project")
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    return _to_item(_get_project_or_404(db, project_id))


@router.post("/{project_id}/status", response_model=ProjectItem, summary="Transition project status")
def transition_status(
    project_id: str,
    body: TransitionProjectStatusRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    project = _get_project_or_404(db, project_id)
    try:
        project = transition_project_status(db, project, body.status)
    except InvalidProjectTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(project)
    return _to_item(project)


@router.post("/{project_id}/milestones", response_model=MilestoneItem, summary="Create a project milestone")
def create_milestone_endpoint(
    project_id: str,
    body: CreateMilestoneRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    project = _get_project_or_404(db, project_id)
    milestone = create_milestone(
        db, project, title=body.title, due_date=body.due_date,
        tenant_id=current_user.tenant_id, description=body.description,
        owner_employee_id=body.owner_employee_id,
    )
    db.commit()
    db.refresh(milestone)
    return _milestone_to_item(milestone)


@router.get("/{project_id}/milestones", response_model=MilestoneListResponse, summary="List project milestones")
def list_milestones(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    _get_project_or_404(db, project_id)
    milestones = (
        db.query(ProjectMilestone)
        .filter(ProjectMilestone.project_id == project_id)
        .order_by(ProjectMilestone.due_date.asc())
        .all()
    )
    return MilestoneListResponse(milestones=[_milestone_to_item(m) for m in milestones])


@router.post(
    "/{project_id}/milestones/{milestone_id}/complete", response_model=MilestoneItem,
    summary="Mark a milestone complete (delay_days always computed, never caller-supplied)",
)
def complete_milestone_endpoint(
    project_id: str,
    milestone_id: str,
    body: CompleteMilestoneRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    milestone = db.query(ProjectMilestone).filter(
        ProjectMilestone.id == milestone_id, ProjectMilestone.project_id == project_id,
    ).first()
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found.")
    try:
        milestone = complete_milestone(db, milestone, completion_date=body.completion_date)
    except MilestoneValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(milestone)
    return _milestone_to_item(milestone)


@router.get(
    "/{project_id}/unfilled-roles", response_model=UnfilledRolesResponse,
    summary="Open headcount gaps for this project's linked demands",
)
def unfilled_roles(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    project = _get_project_or_404(db, project_id)
    gaps = get_unfilled_project_roles(db, project)
    return UnfilledRolesResponse(roles=[UnfilledRoleItem(**g) for g in gaps])


@router.get(
    "/{project_id}/expected-revenue", response_model=ExpectedRevenueResponse,
    summary="Rough expected-revenue/margin estimate -- not a finance figure",
)
def expected_revenue(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    project = _get_project_or_404(db, project_id)
    result = calculate_project_expected_revenue(db, project)
    return ExpectedRevenueResponse(**result)
