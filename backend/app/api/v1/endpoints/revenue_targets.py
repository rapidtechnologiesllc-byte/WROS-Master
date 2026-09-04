"""
S-267/HRMS-0301 (BU Revenue Target) + PartnerGoal + S-241/HRMS-0212
import logging
(Executive Revenue Dashboard) + S-244/HRMS-0215 (Pipeline Coverage).

Gated behind revenue.view_pnl throughout -- these are target-setting
and P&L-adjacent figures, the same permission tier this codebase
already uses for markup/margin-sensitive actions. No bespoke
"revenue.set_target" permission exists yet; PartnerGoal additionally
enforces CEO-only in the service layer (an RBAC-role question, not
a permission-tier one -- see revenue_target_service.set_partner_goal()).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.core.revenue_visibility_scope import get_revenue_scoped_client_ids
from app.models.user import Users
from app.schemas.revenue_target import (
    BUTargetCreateRequest, BUTargetVsActualResponse, ExecutiveRevenueDashboardResponse,
    PartnerGoalCreateRequest, PartnerGoalItem, PartnerMultiYearPositionResponse,
    PipelineCoverageResponse,
)
from app.services.revenue_target_service import (
    RevenueTargetValidationError, get_bu_target_vs_actual, get_executive_revenue_dashboard,
    get_partner_multi_year_position, get_pipeline_coverage, set_bu_revenue_target, set_partner_goal,
)

router = APIRouter(tags=["revenue-targets"])

@router.post(
    "/revenue-targets/bu",
    response_model=BUTargetVsActualResponse,
    status_code=201,
    dependencies=[Depends(require_resource_permission("revenue-target", "create"))]
)
def create_bu_target(
    body: BUTargetCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    try:
        set_bu_revenue_target(
            db, business_unit_id=body.business_unit_id, target_period=body.target_period,
            fiscal_year=body.fiscal_year, target_amount_usd_cents=body.target_amount_usd_cents,
            created_by=current_user.UserID, tenant_id=current_user.tenant_id, notes=body.notes,
        )
    except RevenueTargetValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return get_bu_target_vs_actual(db, body.business_unit_id, body.target_period, body.fiscal_year)

@router.get(
    "/revenue-targets/bu/{business_unit_id}",
    response_model=BUTargetVsActualResponse,
    dependencies=[Depends(require_resource_permission("revenue-target", "view"))]
)
def get_bu_target(
    business_unit_id: int,
    target_period: str,
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    return get_bu_target_vs_actual(db, business_unit_id, target_period, fiscal_year)

@router.post(
    "/revenue-targets/partner-goals",
    response_model=PartnerGoalItem,
    status_code=201,
    dependencies=[Depends(require_resource_permission("revenue-target", "create"))]
)
def create_partner_goal(
    body: PartnerGoalCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    try:
        return set_partner_goal(
            db, partner_user_id=body.partner_user_id, target_period=body.target_period,
            fiscal_year=body.fiscal_year, target_amount_usd_cents=body.target_amount_usd_cents,
            created_by_user=current_user, tenant_id=current_user.tenant_id, notes=body.notes,
        )
    except RevenueTargetValidationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

@router.get(
    "/revenue-targets/partners/{partner_user_id}/position",
    response_model=PartnerMultiYearPositionResponse,
    dependencies=[Depends(require_resource_permission("revenue-target", "view"))]
)
def get_partner_position(
    partner_user_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    return get_partner_multi_year_position(db, partner_user_id)

@router.get(
    "/revenue-targets/dashboard",
    response_model=ExecutiveRevenueDashboardResponse,
    dependencies=[Depends(require_resource_permission("revenue-target", "view"))]
)
def executive_dashboard(
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    client_ids = get_revenue_scoped_client_ids(db, current_user)
    return get_executive_revenue_dashboard(db, client_ids=list(client_ids) if client_ids is not None else None)

@router.get(
    "/revenue-targets/pipeline-coverage",
    response_model=PipelineCoverageResponse,
    dependencies=[Depends(require_resource_permission("revenue-target", "view"))]
)
def pipeline_coverage(
    revenue_target_usd_cents: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    client_ids = get_revenue_scoped_client_ids(db, current_user)
    ratio = get_pipeline_coverage(
        db, client_ids=list(client_ids) if client_ids is not None else None,
        revenue_target_usd_cents=revenue_target_usd_cents,
    )
    return PipelineCoverageResponse(revenue_target_usd_cents=revenue_target_usd_cents, coverage_ratio=ratio)
