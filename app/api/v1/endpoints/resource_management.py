"""
HRMS-1105 (canonical S-320) — Resource Management Agent — API Endpoints
=========================================================================
Prefix: /resource-management
Tag:    resource-management

Wires the service layer built earlier this program
(app.services.resource_management_agent_service) to real HTTP routes.
No REST layer previously existed for this story -- see the Definition of
Done correction in CLAUDE.md.

Auth: same posture as Thunder (get_current_hr_or_admin -- any internal
user, any role). No resource-management-specific RBAC permission exists
yet in this codebase's permission set (see app/core/dependencies.py's
require_permission() options); adding one is a separate, not-yet-scoped
RBAC story, not part of S-320.

Routes:
  POST   /resource-management/scan
      Trigger one bench-scan cycle (Core-Pull detection + LLM ranking of
      bench matches). No scheduler exists yet -- manually triggered,
      same "idempotent function exists, wiring is follow-up" posture as
      every other cron-shaped story in this codebase.

  GET    /resource-management/recommendations
      The RM's PENDING_RM_REVIEW review queue, confidence-sorted, with
      employee/demand/client names resolved for display.

  GET    /resource-management/recommendations/mine
      Recommendations the current user is actively pursuing (IN_PROGRESS)
      -- so the UI can show "why is this employee unavailable" context.

  POST   /resource-management/recommendations/{id}/pursue
      BR: the real "never pushed to 2 clients at once" enforcement point.
      Hard-blocks (409) if the employee is already IN_PROGRESS elsewhere.

  POST   /resource-management/recommendations/{id}/approve
      Creates the real employee_allocations row via the existing,
      already-gated allocate_employee_to_project().

  POST   /resource-management/recommendations/{id}/reject
      Releases the exclusivity hold.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin
from app.models.client import Client
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.resource_agent import BenchAllocationRecommendation
from app.models.user import Users
from app.services.employee_allocation_service import AllocationOverCapacity
from app.schemas.resource_management import (
    ApproveRecommendationResponse,
    RecommendationActionResponse,
    RecommendationItem,
    RecommendationQueueResponse,
    ScanTriggerResponse,
)
from app.services.resource_management_agent_service import (
    EmployeeAlreadyActivelyEngaged,
    RecommendationNotPending,
    approve_bench_recommendation,
    get_recommendation_queue,
    is_employee_actively_engaged,
    reject_bench_recommendation,
    run_bench_scan,
    start_pursuing_recommendation,
)

router = APIRouter(prefix="/resource-management", tags=["resource-management"])


def _to_item(db: Session, rec: BenchAllocationRecommendation) -> RecommendationItem:
    employee = db.query(Employee).filter(Employee.id == rec.employee_id).first()
    demand = db.query(Demand).filter(Demand.id == rec.demand_id).first()
    client = None
    if demand is not None and demand.client_id:
        client = db.query(Client).filter(Client.id == demand.client_id).first()

    employee_name = (
        f"{employee.first_name} {employee.last_name}".strip() if employee else "(unknown employee)"
    )

    return RecommendationItem(
        id=rec.id,
        status=rec.status,
        confidence_pct=float(rec.confidence_pct),
        rationale=rec.rationale,
        created_at=rec.created_at,
        pursued_by=rec.pursued_by,
        pursued_at=rec.pursued_at,
        reviewed_by=rec.reviewed_by,
        reviewed_at=rec.reviewed_at,
        employee_id=rec.employee_id,
        employee_name=employee_name,
        employee_current_title=employee.current_title if employee else None,
        employee_delivery_engine=employee.delivery_engine if employee else None,
        demand_id=rec.demand_id,
        demand_job_title=demand.job_title if demand else "(unknown demand)",
        client_name=client.company_name if client else None,
    )


def _get_recommendation_or_404(db: Session, recommendation_id: str) -> BenchAllocationRecommendation:
    rec = (
        db.query(BenchAllocationRecommendation)
        .filter(BenchAllocationRecommendation.id == recommendation_id)
        .first()
    )
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    return rec


@router.post(
    "/scan",
    response_model=ScanTriggerResponse,
    summary="Trigger one Resource Management Agent bench-scan cycle",
)
def trigger_scan(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    result = run_bench_scan(db, tenant_id=current_user.tenant_id, bu_head=current_user)
    db.commit()
    return ScanTriggerResponse(**result)


@router.get(
    "/recommendations",
    response_model=RecommendationQueueResponse,
    summary="Get the pending bench-allocation recommendation queue",
)
def get_queue(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    recs = get_recommendation_queue(db, tenant_id=current_user.tenant_id)
    return RecommendationQueueResponse(recommendations=[_to_item(db, r) for r in recs])


@router.post(
    "/recommendations/{recommendation_id}/pursue",
    response_model=RecommendationActionResponse,
    summary="Start actively pursuing a recommendation (interview stage)",
    description=(
        "Moves a recommendation from PENDING_RM_REVIEW to IN_PROGRESS. Hard-blocks with "
        "409 if this employee is already IN_PROGRESS on a different recommendation -- an "
        "employee already in play at one client can never be simultaneously pursued for a "
        "second (Avinash's explicit business rule)."
    ),
)
def pursue_recommendation(
    recommendation_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    rec = _get_recommendation_or_404(db, recommendation_id)
    try:
        rec = start_pursuing_recommendation(db, rec, actor_user_id=current_user.UserID)
    except EmployeeAlreadyActivelyEngaged as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except RecommendationNotPending as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(rec)
    return RecommendationActionResponse(
        message="Now pursuing this recommendation.", recommendation=_to_item(db, rec),
    )


@router.post(
    "/recommendations/{recommendation_id}/approve",
    response_model=ApproveRecommendationResponse,
    summary="Approve a recommendation and create the real allocation",
)
def approve_recommendation(
    recommendation_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    rec = _get_recommendation_or_404(db, recommendation_id)
    try:
        allocation = approve_bench_recommendation(db, rec, actor_user_id=current_user.UserID)
    except RecommendationNotPending as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except AllocationOverCapacity as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(rec)
    return ApproveRecommendationResponse(
        message="Recommendation approved and employee allocated.",
        recommendation=_to_item(db, rec),
        allocation_id=allocation.id,
    )


@router.post(
    "/recommendations/{recommendation_id}/reject",
    response_model=RecommendationActionResponse,
    summary="Reject a recommendation",
)
def reject_recommendation(
    recommendation_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    rec = _get_recommendation_or_404(db, recommendation_id)
    try:
        rec = reject_bench_recommendation(db, rec, actor_user_id=current_user.UserID)
    except RecommendationNotPending as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(rec)
    return RecommendationActionResponse(
        message="Recommendation rejected.", recommendation=_to_item(db, rec),
    )


@router.get(
    "/employees/{employee_id}/actively-engaged",
    summary="Check whether an employee is currently IN_PROGRESS on another recommendation",
)
def check_actively_engaged(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    return {"employee_id": employee_id, "actively_engaged": is_employee_actively_engaged(db, employee_id)}
