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

Auth: the role template's projects permission decides the actions; the
business unit decides the records (CEO 2026-10-12, app.core.data_scope):
a project belongs to its client's BU. Every /projects/{id} route resolves
the project through _get_project_or_404 (tenant + scope).

Routes:
  POST   /projects                              Create a project.
  GET    /projects                               List (optional client_id/status filter).
  GET    /projects/options                       Billing types, statuses, currencies, managers.
  GET    /projects/{id}                          Get one project.
  PATCH  /projects/{id}                          Edit name, dates, billing type, project manager.
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

from app.core.data_scope import client_bu_id, client_filter, ensure_visible
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.logging import logger
from app.services.message_queue_service import MessageQueueService
from app.models.client import Client
from app.models.project import (
    BILLING_TYPES,
    CORE_CURRENCIES,
    PROJECT_BUSINESS_TYPES,
    PROJECT_STATUSES,
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
    ProjectManagerOption,
    ProjectOptionsResponse,
    TransitionProjectStatusRequest,
    UpdateProjectRequest,
    UnfilledRoleItem,
    UnfilledRolesResponse,
)
from app.services.project_service import (
    PROJECT_STATUS_TRANSITIONS,
    InvalidProjectTransition,
    MilestoneValidationError,
    ProjectValidationError,
    calculate_project_expected_revenue,
    complete_milestone,
    create_milestone,
    create_project,
    get_unfilled_project_roles,
    transition_project_status,
    update_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])

def _manager_names(db: Session, projects) -> dict:
    ids = {p.manager_user_id for p in projects if p.manager_user_id}
    if not ids:
        return {}
    return {uid: name or email for uid, name, email in
            db.query(Users.UserID, Users.UserName, Users.UserEmail).filter(Users.UserID.in_(ids)).all()}

def _to_item(project: Project, manager_names: Optional[dict] = None) -> ProjectItem:
    return ProjectItem(
        id=project.id, client_id=project.client_id, opportunity_id=project.opportunity_id,
        name=project.name, status=project.status, billing_type=project.billing_type,
        currency=project.currency, continent=project.continent,
        delivery_engine=project.delivery_engine, si_partner=project.si_partner,
        end_client=project.end_client, client_partner=project.client_partner,
        business_type=project.business_type,
        allow_weekend_billing=project.allow_weekend_billing, is_billable=project.is_billable,
        start_date=project.start_date, end_date=project.end_date,
        manager_user_id=project.manager_user_id,
        manager_name=(manager_names or {}).get(project.manager_user_id),
    )

def _one_item(db: Session, project: Project) -> ProjectItem:
    return _to_item(project, _manager_names(db, [project]))

def _milestone_to_item(m: ProjectMilestone) -> MilestoneItem:
    return MilestoneItem(
        id=m.id, project_id=m.project_id, title=m.title, description=m.description,
        due_date=m.due_date, owner_employee_id=m.owner_employee_id,
        is_complete=m.is_complete, completion_date=m.completion_date, delay_days=m.delay_days,
    )

def _get_project_or_404(db: Session, project_id: str, user: Users) -> Project:
    """One project of the caller's tenant whose client's business unit is in the caller's scope
    (app.core.data_scope); any other id is 404, the same answer as one that does not exist.
    Every /projects/{id} route goes through here."""
    project = db.query(Project).filter(
        Project.id == project_id, Project.tenant_id == user.tenant_id,
        client_filter(db, user, Project.client_id),
    ).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project

@router.post(
    "",
    response_model=ProjectItem,
    summary="Create a project",
    dependencies=[Depends(require_resource_permission("projects", "create"))]
)
def create_project_endpoint(
    body: CreateProjectRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    # 2026-08-06 redesign, confirmed directly with Avinash while testing
    # live: delivery_engine and si_partner are no longer caller-supplied
    # -- both are derived server-side from the selected client's own
    # line_type, the same single source of truth the real Client Master
    # workbook uses (SI Partners like PWC are just Client rows with
    # line_type=SPECIALITY, not a second disconnected concept). The
    # client is authoritative; body.delivery_engine/si_partner (still
    # accepted for backward-compat request shapes) are ignored.
    client = db.query(Client).filter(Client.id == body.client_id, Client.tenant_id == current_user.tenant_id).first()
    if client is None:
        raise HTTPException(status_code=404, detail=f"Client {body.client_id!r} not found.")
    ensure_visible(db, current_user, client_bu_id(db, client.id), f"Client {body.client_id!r}")
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

    try:
        project = create_project(
            db, tenant_id=current_user.tenant_id, client_id=body.client_id, name=body.name,
            billing_type=body.billing_type, currency=body.currency, continent=body.continent,
            delivery_engine=delivery_engine, si_partner=si_partner,
            end_client=body.end_client, client_partner=body.client_partner,
            business_type=body.business_type,
            created_by=current_user.UserID,
            start_date=body.start_date, end_date=body.end_date, manager_user_id=body.manager_user_id,
        )
    except ProjectValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    project.allow_weekend_billing = body.allow_weekend_billing
    project.is_billable = body.is_billable

    db.add(project)
    db.commit()  # PERSIST PROJECT TO DATABASE FIRST

    # Validation: Verify project actually saved
    persisted_project = db.query(Project).filter(Project.id == project.id).first()
    if not persisted_project:
        raise HTTPException(status_code=500, detail=f"Write validation failed: Project {project.id} not found in database after commit")
    from app.services.action_emails.projects import notify_project_created

    notify_project_created(db, project, actor=current_user)

    try:
        MessageQueueService.enqueue(
            task_name="project_created",
            tenant_id=project.tenant_id,
            data={
                "project_id": project.id,
                "project_name": project.name,
                "client_id": body.client_id,
                "delivery_engine": delivery_engine,
                "billing_type": body.billing_type,
                "currency": body.currency,
            }
        )
        db.refresh(project)
        return _one_item(db, project)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create project: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List projects",
    dependencies=[Depends(require_resource_permission("projects", "view"))]
)
def list_projects(
    client_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    query = db.query(Project).filter(
        Project.tenant_id == current_user.tenant_id, client_filter(db, current_user, Project.client_id),
    )
    if client_id:
        query = query.filter(Project.client_id == client_id)
    if status:
        query = query.filter(Project.status == status)
    projects = query.order_by(Project.created_at.desc()).all()
    names = _manager_names(db, projects)
    return ProjectListResponse(projects=[_to_item(p, names) for p in projects])


@router.get(
    "/options",
    response_model=ProjectOptionsResponse,
    summary="Choices for the project form: billing types, statuses, currencies, project managers",
    dependencies=[Depends(require_resource_permission("projects", "view"))]
)
def project_options(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """The backend's own lists (app.models.project), so the screen never hardcodes them; managers
    are the tenant's active internal users."""
    managers = (
        db.query(Users.UserID, Users.UserName, Users.UserEmail)
        .filter(Users.tenant_id == current_user.tenant_id, Users.terminated_at.is_(None))
        .order_by(Users.UserName, Users.UserEmail).all()
    )
    return ProjectOptionsResponse(
        billing_types=list(BILLING_TYPES),
        business_types=list(PROJECT_BUSINESS_TYPES),
        statuses=list(PROJECT_STATUSES),
        status_transitions={k: sorted(v) for k, v in PROJECT_STATUS_TRANSITIONS.items()},
        currencies_by_engine={"SPECIALITY": list(SPECIALITY_CURRENCIES), "CORE": list(CORE_CURRENCIES)},
        managers=[ProjectManagerOption(user_id=uid, name=name, email=email) for uid, name, email in managers],
    )


@router.get(
    "/{project_id}",
    response_model=ProjectItem,
    summary="Get one project",
    dependencies=[Depends(require_resource_permission("projects", "view"))]
)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    return _one_item(db, _get_project_or_404(db, project_id, current_user))


@router.patch(
    "/{project_id}",
    response_model=ProjectItem,
    summary="Edit a project's name, start/end dates, billing type and project manager",
    dependencies=[Depends(require_resource_permission("projects", "edit"))]
)
def update_project_endpoint(
    project_id: str,
    body: UpdateProjectRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    project = _get_project_or_404(db, project_id, current_user)
    previous_manager = project.manager_user_id
    try:
        update_project(db, project, body.model_dump(exclude_unset=True))
    except ProjectValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(project)
    from app.services.action_emails.projects import notify_project_manager_changed

    notify_project_manager_changed(db, project, actor=current_user, previous_manager=previous_manager)
    return _one_item(db, project)


@router.post(
    "/{project_id}/status",
    response_model=ProjectItem,
    summary="Transition project status",
    dependencies=[Depends(require_resource_permission("projects", "edit"))]
)
def transition_status(
    project_id: str,
    body: TransitionProjectStatusRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    project = _get_project_or_404(db, project_id, current_user)
    try:
        project = transition_project_status(db, project, body.status)
    except InvalidProjectTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()  # the transition is persisted before anyone is told about it
    from app.services.action_emails.projects import notify_project_status

    notify_project_status(db, project, actor=current_user)

    try:
        MessageQueueService.enqueue(
            task_name="project_status_changed",
            tenant_id=project.tenant_id,
            data={
                "project_id": project.id,
                "project_name": project.name,
                "new_status": body.status,
            }
        )
        db.refresh(project)
        return _one_item(db, project)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to transition project status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to transition project: {str(e)}")

@router.post(
    "/{project_id}/milestones",
    response_model=MilestoneItem,
    summary="Create a project milestone",
    dependencies=[Depends(require_resource_permission("projects", "create"))]
)
def create_milestone_endpoint(
    project_id: str,
    body: CreateMilestoneRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    project = _get_project_or_404(db, project_id, current_user)
    milestone = create_milestone(
        db, project, title=body.title, due_date=body.due_date,
        tenant_id=current_user.tenant_id, description=body.description,
        owner_employee_id=body.owner_employee_id,
    )
    db.commit()
    from app.services.action_emails.projects import notify_milestone_created

    notify_milestone_created(db, project, milestone, actor=current_user)

    try:
        MessageQueueService.enqueue(
            task_name="milestone_created",
            tenant_id=project.tenant_id,
            data={
                "milestone_id": milestone.id,
                "project_id": project.id,
                "milestone_title": body.title,
                "due_date": str(body.due_date) if body.due_date else None,
            }
        )
        db.refresh(milestone)
        return _milestone_to_item(milestone)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create milestone: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create milestone: {str(e)}")

@router.get(
    "/{project_id}/milestones",
    response_model=MilestoneListResponse,
    summary="List project milestones",
    dependencies=[Depends(require_resource_permission("projects", "view"))]
)
def list_milestones(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    _get_project_or_404(db, project_id, current_user)
    milestones = (
        db.query(ProjectMilestone)
        .filter(ProjectMilestone.project_id == project_id)
        .order_by(ProjectMilestone.due_date.asc())
        .all()
    )
    return MilestoneListResponse(milestones=[_milestone_to_item(m) for m in milestones])

@router.post(
    "/{project_id}/milestones/{milestone_id}/complete",
    response_model=MilestoneItem,
    summary="Mark a milestone complete (delay_days always computed, never caller-supplied)",
    dependencies=[Depends(require_resource_permission("projects", "edit"))]
)
def complete_milestone_endpoint(
    project_id: str,
    milestone_id: str,
    body: CompleteMilestoneRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    project = _get_project_or_404(db, project_id, current_user)
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
    from app.services.action_emails.projects import notify_milestone_completed

    notify_milestone_completed(db, project, milestone, actor=current_user)

    try:
        MessageQueueService.enqueue(
            task_name="milestone_completed",
            tenant_id=current_user.tenant_id,
            data={
                "milestone_id": milestone.id,
                "project_id": project_id,
                "milestone_title": milestone.title,
                "completion_date": str(body.completion_date) if body.completion_date else None,
                "delay_days": milestone.delay_days,
            }
        )
        db.refresh(milestone)
        return _milestone_to_item(milestone)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to complete milestone: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to complete milestone: {str(e)}")

@router.get(
    "/{project_id}/unfilled-roles",
    response_model=UnfilledRolesResponse,
    summary="Open headcount gaps for this project's linked demands",
    dependencies=[Depends(require_resource_permission("projects", "view"))]
)
def unfilled_roles(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    project = _get_project_or_404(db, project_id, current_user)
    gaps = get_unfilled_project_roles(db, project)
    return UnfilledRolesResponse(roles=[UnfilledRoleItem(**g) for g in gaps])

@router.get(
    "/{project_id}/expected-revenue",
    response_model=ExpectedRevenueResponse,
    summary="Rough expected-revenue/margin estimate -- not a finance figure",
    dependencies=[Depends(require_resource_permission("projects", "view"))]
)
def expected_revenue(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    project = _get_project_or_404(db, project_id, current_user)
    result = calculate_project_expected_revenue(db, project)
    return ExpectedRevenueResponse(**result)
