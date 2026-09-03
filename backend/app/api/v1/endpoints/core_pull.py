"""
S-353 (HRMS-0514) Core-Pull Engine + S-373 (HRMS-0529) Specialty Pool
Minimum 40 Guard — API Endpoints
=========================================================================
Prefix: /core-pull
import logging
Tag:    core-pull

Wires app.services.core_pull_service (built earlier this program, no
REST layer previously existed) to real HTTP routes. See the Definition
of Done correction in CLAUDE.md.

Auth: same posture as Thunder/Resource Management (get_current_internal_user
-- any internal user). override is additionally gated on the acting
user's UserRole == "BU Head" inside override_core_pull() itself (403 if
not); no separate RBAC permission exists for this area yet.

Routes:
  GET    /core-pull/specialty-pool-status
      Current Specialty Core-Certified pool size vs the 40-minimum floor.

  GET    /core-pull/events
      Pending Core-Pull events (detected conflicts awaiting execute or
      override), enriched with employee/demand names for display.

  POST   /core-pull/events/{event_id}/execute
      Same-day forced transfer. 409 if it would breach the Specialty
      pool minimum and no replacement plan has been logged since
      detection.

  POST   /core-pull/events/{event_id}/override
      BU Head only, 100+ char justification required.

  POST   /core-pull/replacement-plans
      Logs a replacement plan to unblock a guard-blocked execute.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.core_pull import CorePullEvent
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.user import Users
from app.schemas.core_pull import (
    CorePullEventItem,
    CorePullEventQueueResponse,
    ExecuteCorePullResponse,
    OverrideCorePullRequest,
    OverrideCorePullResponse,
    ReplacementPlanRequest,
    ReplacementPlanResponse,
    SpecialtyPoolStatusResponse,
)
from app.services.core_pull_service import (
    CorePullOverrideForbidden,
    InvalidOverrideJustification,
    InvalidReplacementPlan,
    SpecialtyPoolBelowMinimum,
    check_specialty_pool_guard,
    execute_core_pull,
    get_specialty_pool_status,
    log_replacement_plan,
    override_core_pull,
)
from app.services.orchestration_router_service import ActionBlocked, ActionDelayed

router = APIRouter(prefix="/core-pull", tags=["core-pull"])


def _to_item(db: Session, event: CorePullEvent) -> CorePullEventItem:
    employee = db.query(Employee).filter(Employee.id == event.employee_id).first()
    demand = db.query(Demand).filter(Demand.id == event.core_demand_id).first()
    employee_name = (
        f"{employee.first_name} {employee.last_name}".strip() if employee else "(unknown employee)"
    )
    return CorePullEventItem(
        id=event.id,
        status=event.status,
        detected_at=event.detected_at,
        executed_at=event.executed_at,
        override_justification=event.override_justification,
        overridden_by=event.overridden_by,
        overridden_at=event.overridden_at,
        employee_id=event.employee_id,
        employee_name=employee_name,
        core_demand_id=event.core_demand_id,
        core_demand_job_title=demand.job_title if demand else "(unknown demand)",
    )


def _get_event_or_404(db: Session, event_id: str) -> CorePullEvent:
    event = db.query(CorePullEvent).filter(CorePullEvent.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Core-Pull event not found.")
    return event


@router.get(
    "/specialty-pool-status",
    dependencies=[Depends(get_current_internal_user)],
    response_model=SpecialtyPoolStatusResponse,
    summary="Get the current Specialty Core-Certified pool size vs the 40-minimum floor",
)
def get_pool_status(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    status = get_specialty_pool_status(db, tenant_id=current_user.tenant_id)
    return SpecialtyPoolStatusResponse(**status)


@router.get(
    "/events",
    dependencies=[Depends(get_current_internal_user)],
    response_model=CorePullEventQueueResponse,
    summary="Get pending Core-Pull events",
)
def get_pending_events(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    events = (
        db.query(CorePullEvent)
        .filter(
            CorePullEvent.tenant_id == current_user.tenant_id,
            CorePullEvent.status == "PENDING",
        )
        .order_by(CorePullEvent.detected_at.asc())
        .all()
    )
    return CorePullEventQueueResponse(events=[_to_item(db, e) for e in events])


@router.post(
    "/events/{event_id}/execute",
    dependencies=[Depends(get_current_internal_user)],
    response_model=ExecuteCorePullResponse,
    summary="Execute a pending Core-Pull event (same-day forced transfer)",
)
def execute_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    event = _get_event_or_404(db, event_id)
    employee = db.query(Employee).filter(Employee.id == event.employee_id).first()
    try:
        event = execute_core_pull(
            db, event, tenant_id=current_user.tenant_id, bu_head=current_user,
        )
    except SpecialtyPoolBelowMinimum as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (ActionBlocked, ActionDelayed) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(event)

    guard = check_specialty_pool_guard(db, employee) if employee else {"pool_size_after_move": None}
    return ExecuteCorePullResponse(
        message="Core-Pull executed.",
        event=_to_item(db, event),
        specialty_pool_size_after=guard["pool_size_after_move"],
    )


@router.post(
    "/events/{event_id}/override",
    dependencies=[Depends(get_current_internal_user)],
    response_model=OverrideCorePullResponse,
    summary="Override a pending Core-Pull event (BU Head only)",
)
def override_event(
    event_id: str,
    body: OverrideCorePullRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    event = _get_event_or_404(db, event_id)
    try:
        event = override_core_pull(
            db, event,
            actor_role=current_user.UserRole,
            actor_user_id=current_user.UserID,
            justification=body.justification,
            tenant_id=current_user.tenant_id,
            director=None,
        )
    except CorePullOverrideForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except InvalidOverrideJustification as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(event)
    return OverrideCorePullResponse(message="Core-Pull event overridden.", event=_to_item(db, event))


@router.post(
    "/replacement-plans",
    dependencies=[Depends(get_current_internal_user)],
    response_model=ReplacementPlanResponse,
    summary="Log a Specialty Pool replacement plan to unblock a guard-blocked execute",
)
def submit_replacement_plan(
    body: ReplacementPlanRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    employee = db.query(Employee).filter(Employee.id == body.employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    try:
        plan = log_replacement_plan(
            db,
            employee_being_moved=employee,
            replacement_strategy=body.replacement_strategy,
            expected_replacement_date=body.expected_replacement_date,
            logged_by=current_user.UserID,
        )
    except InvalidReplacementPlan as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    db.refresh(plan)
    return ReplacementPlanResponse(
        id=plan.id,
        employee_id_moving=plan.employee_id_moving,
        replacement_strategy=plan.replacement_strategy,
        expected_replacement_date=plan.expected_replacement_date,
        logged_by=plan.logged_by,
        logged_at=plan.logged_at,
    )
