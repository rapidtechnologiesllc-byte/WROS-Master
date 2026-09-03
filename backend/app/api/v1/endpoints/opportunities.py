"""
S-236/HRMS-0207 (Create Opportunity), S-237/HRMS-0208 (Pipeline Kanban),
S-239/HRMS-0210 (Role Demand from Opportunity), S-240/HRMS-0211
import logging
(Revenue Potential rollup).

Backend (app.services.opportunity_service) was already real and tested
-- this is the first API surface for any of it. Gated behind
revenue.view (Avinash's 2026-08-05 EPIC-02/03 access spec: CEO/Finance/
HR Manager org-wide, Partner/BU Head scoped to their own BU) via
app.core.revenue_visibility_scope, reusing the exact same BU-scoping
mechanism the other machine's session already built rather than a
second, divergent one.

Stage list stays the hardcoded OPPORTUNITY_STAGES default (per
app.models.opportunity's own docstring: HRMS-0115 config-driven stages
don't exist in this codebase yet) -- not built here either, flagged,
not silently invented.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.core.revenue_visibility_scope import get_revenue_scoped_client_ids
from app.models.client import Client
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.opportunity import OPPORTUNITY_STAGES, Opportunity
from app.models.user import Users
from app.schemas.opportunity import (
    OpportunityCreateRequest, OpportunityItem, OpportunityListResponse,
    OpportunityStageTransitionRequest, OpportunityStageTransitionResponse,
    PipelineColumn, PipelineResponse, RoleDemandFromOpportunityRequest,
    RoleDemandFromOpportunityResponse,
)
from app.services.opportunity_service import (
    InvalidStageTransition, OpportunityValidationError, calculate_weighted_forecast,
    create_opportunity, create_role_demand_from_opportunity, get_opportunity_revenue_rollup,
    transition_stage,
)

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


def _to_item(db: Session, opportunity: Opportunity) -> OpportunityItem:
    client = db.query(Client).filter(Client.id == opportunity.client_id).first()
    owner = (
        db.query(Employee).filter(Employee.id == opportunity.owner_employee_id).first()
        if opportunity.owner_employee_id else None
    )
    client_owner = (
        db.query(Users).filter(Users.UserID == opportunity.client_owner_id).first()
        if opportunity.client_owner_id else None
    )
    return OpportunityItem(
        id=opportunity.id, client_id=opportunity.client_id,
        client_name=client.company_name if client else None,
        owner_employee_id=opportunity.owner_employee_id,
        owner_name=(f"{owner.first_name} {owner.last_name}".strip() if owner else None),
        client_owner_id=opportunity.client_owner_id,
        client_owner_name=(f"{client_owner.first_name} {client_owner.last_name}".strip() if client_owner else None),
        stage=opportunity.stage, revenue_value_usd_cents=opportunity.revenue_value_usd_cents,
        revenue_value_native=opportunity.revenue_value_native, currency=opportunity.currency,
        probability_pct=opportunity.probability_pct,
        weighted_forecast_usd_cents=calculate_weighted_forecast(opportunity),
        expected_close_date=opportunity.expected_close_date,
        created_at=opportunity.created_at, updated_at=opportunity.updated_at,
    )


def _scoped_query(db: Session, current_user: Users):
    query = db.query(Opportunity)
    client_ids = get_revenue_scoped_client_ids(db, current_user)
    if client_ids is not None:
        query = query.filter(Opportunity.client_id.in_(client_ids))
    return query


@router.post(
    "",
    response_model=OpportunityItem,
    status_code=201,
    dependencies=[Depends(require_resource_permission("unknown", "create"))]
)
def create_opportunity_endpoint(
    body: OpportunityCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    try:
        opportunity = create_opportunity(
            db, tenant_id=current_user.tenant_id, client_id=body.client_id,
            revenue_value_usd_cents=body.revenue_value_usd_cents,
            currency=body.currency,
            revenue_value_native=body.revenue_value_native,
            owner_employee_id=body.owner_employee_id,
            expected_close_date=body.expected_close_date, stage=body.stage,
        )
        db.commit()
        db.refresh(opportunity)
    except OpportunityValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_item(db, opportunity)


@router.get(
    "",
    response_model=OpportunityListResponse,
    dependencies=[Depends(require_resource_permission("unknown", "view"))]
)
def list_opportunities(
    stage: Optional[str] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    query = _scoped_query(db, current_user)
    if stage:
        query = query.filter(Opportunity.stage == stage)
    if client_id:
        query = query.filter(Opportunity.client_id == client_id)
    opportunities = query.order_by(Opportunity.created_at.desc()).all()
    return OpportunityListResponse(opportunities=[_to_item(db, o) for o in opportunities])


@router.get(
    "/eligible-owners",
    dependencies=[Depends(require_resource_permission("eligible-owner", "view"))]
)
def list_eligible_owners(
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    """Opportunity Owner options -- 2026-08-12, Avinash: "anyone with
    access to opportunity should be in the dropdown," not the full
    employee roster. Scoped to employees with a linked WROS user
    account whose role actually carries revenue.view -- the exact
    permission gating this whole Opportunity Pipeline screen."""
    rows = (
        db.query(Employee)
        .join(Users, Users.UserID == Employee.wros_user_id)
        .join(Role, Role.id == Users.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .filter(Permission.name == "revenue.view")
        .distinct()
        .all()
    )
    return {"employees": [{"id": e.id, "first_name": e.first_name, "last_name": e.last_name} for e in rows]}


@router.get(
    "/pipeline",
    response_model=PipelineResponse,
    dependencies=[Depends(require_resource_permission("pipeline", "view"))]
)
def get_pipeline(
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    """S-237 Kanban -- columns per configured stage, revenue + weighted
    forecast totals per column, respecting the same BU scope as the
    list endpoint."""
    opportunities = _scoped_query(db, current_user).all()
    columns = []
    for stage in OPPORTUNITY_STAGES:
        stage_opps = [o for o in opportunities if o.stage == stage]
        columns.append(PipelineColumn(
            stage=stage,
            total_revenue_usd_cents=sum(o.revenue_value_usd_cents for o in stage_opps),
            total_weighted_forecast_usd_cents=sum(calculate_weighted_forecast(o) for o in stage_opps),
            opportunities=[_to_item(db, o) for o in stage_opps],
        ))
    return PipelineResponse(columns=columns)


@router.get(
    "/{opportunity_id}",
    response_model=OpportunityItem,
    dependencies=[Depends(require_resource_permission("opportunities", "view"))]
)
def get_opportunity(
    opportunity_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail=f"Opportunity {opportunity_id!r} not found.")
    return _to_item(db, opportunity)


@router.post(
    "/{opportunity_id}/transition",
    response_model=OpportunityStageTransitionResponse,
    dependencies=[Depends(require_resource_permission("opportunities", "create"))]
)
def transition_opportunity_stage(
    opportunity_id: str,
    body: OpportunityStageTransitionRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail=f"Opportunity {opportunity_id!r} not found.")
    try:
        result = transition_stage(
            db, opportunity, body.new_stage,
            project_name=body.project_name, billing_type=body.billing_type,
            continent=body.continent, changed_by=current_user.UserID,
        )
        db.commit()
    except InvalidStageTransition as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    project_id = None
    if isinstance(result, tuple):
        opportunity, project = result
        project_id = project.id
    db.refresh(opportunity)
    return OpportunityStageTransitionResponse(opportunity=_to_item(db, opportunity), project_id=project_id)


@router.get(
    "/{opportunity_id}/revenue-rollup",
    dependencies=[Depends(require_resource_permission("opportunities", "view"))]
)
def get_revenue_rollup(
    opportunity_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail=f"Opportunity {opportunity_id!r} not found.")
    return {"opportunity_id": opportunity_id, "role_demand_revenue_usd_cents": get_opportunity_revenue_rollup(db, opportunity)}


@router.post(
    "/{opportunity_id}/role-demand",
    response_model=RoleDemandFromOpportunityResponse,
    status_code=201,
    dependencies=[Depends(require_resource_permission("opportunities", "create"))]
)
def create_role_demand(
    opportunity_id: str,
    body: RoleDemandFromOpportunityRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail=f"Opportunity {opportunity_id!r} not found.")
    try:
        demand = create_role_demand_from_opportunity(
            db, opportunity, tenant_id=current_user.tenant_id,
            job_title=body.job_title, required_skills=body.required_skills,
            min_experience_years=body.min_experience_years, work_location=body.work_location,
            quantity=body.quantity, duration_hours=body.duration_hours,
            billing_rate_usd_cents=body.billing_rate_usd_cents, changed_by=current_user.UserID,
        )
        db.commit()
        db.refresh(demand)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return demand
