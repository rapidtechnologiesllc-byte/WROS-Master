"""
S-372 (HRMS-0528) Confirmed vs Potential Demand Workflow — API Endpoints
=========================================================================
Prefix: /demand-confirmation
import logging
Tag:    demand-confirmation

Wires app.services.demand_confirmation_service (built earlier this
program, no REST layer previously existed) to real HTTP routes. See the
Definition of Done correction in CLAUDE.md.

Auth: same posture as every other Phase 4 story this round
(get_current_internal_user -- any internal user). Scope note, flagged
rather than silently narrowed: this codebase has no employee self-
service login path at all (no get_current_employee dependency exists
anywhere), so BOTH the EMPLOYEE and BU_HEAD fit confirmations are
recorded here by an internal user selecting which participant they're
recording on behalf of via the request body -- confirm_fit()'s own
signature already takes `participant` as an explicit parameter, not an
inferred caller identity, so this doesn't change the service's
contract, just how the caller is authenticated. A genuine employee
self-service portal for this is a separate, unscoped story.

Routes:
  POST   /demand-confirmation/demands/{demand_id}/confirm-sow
      AC-6: records the SOW reference and flips confirmation_status to
      CONFIRMED.

  POST   /demand-confirmation/demands/{demand_id}/employees/{employee_id}/schedule-call
      Books (or returns the existing) 3-way alignment call.

  GET    /demand-confirmation/demands/{demand_id}/calls
      All alignment calls for a demand, enriched for display.

  POST   /demand-confirmation/calls/{call_id}/confirm-fit
      Records one participant's fit confirmation. Immutable once set.

  POST   /demand-confirmation/calls/{call_id}/trigger-release
      Hard gate: confirmation_status==CONFIRMED AND both fits True.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.demand import Demand
from app.models.demand_confirmation import DemandAlignmentCall
from app.models.employee import Employee
from app.models.user import Users
from app.schemas.demand_confirmation import (
    AlignmentCallItem,
    AlignmentCallListResponse,
    ConfirmFitRequest,
    ConfirmFitResponse,
    ConfirmSOWRequest,
    ConfirmSOWResponse,
    ScheduleCallRequest,
    TriggerReleaseResponse,
)
from app.services.demand_confirmation_service import (
    FitConfirmationAlreadyRecorded,
    InvalidParticipant,
    SOWReferenceRequired,
    SpecialtyClientReleaseNotAllowed,
    confirm_demand_with_sow,
    confirm_fit,
    schedule_alignment_call,
    trigger_specialty_client_release,
)

router = APIRouter(prefix="/demand-confirmation", tags=["demand-confirmation"])


def _to_item(db: Session, call: DemandAlignmentCall) -> AlignmentCallItem:
    demand = db.query(Demand).filter(Demand.id == call.demand_id).first()
    employee = db.query(Employee).filter(Employee.id == call.employee_id).first()
    employee_name = (
        f"{employee.first_name} {employee.last_name}".strip() if employee else "(unknown employee)"
    )
    return AlignmentCallItem(
        id=call.id,
        demand_id=call.demand_id,
        demand_job_title=demand.job_title if demand else "(unknown demand)",
        employee_id=call.employee_id,
        employee_name=employee_name,
        curtis_user_id=call.curtis_user_id,
        bu_head_user_id=call.bu_head_user_id,
        scheduled_at=call.scheduled_at,
        employee_fit_confirmed=call.employee_fit_confirmed,
        employee_fit_confirmed_at=call.employee_fit_confirmed_at,
        employee_fit_notes=call.employee_fit_notes,
        bu_head_fit_confirmed=call.bu_head_fit_confirmed,
        bu_head_fit_confirmed_at=call.bu_head_fit_confirmed_at,
        bu_head_fit_notes=call.bu_head_fit_notes,
        specialty_client_release_triggered_at=call.specialty_client_release_triggered_at,
    )


def _get_demand_or_404(db: Session, demand_id: str) -> Demand:
    demand = db.query(Demand).filter(Demand.id == demand_id).first()
    if demand is None:
        raise HTTPException(status_code=404, detail="Demand not found.")
    return demand


def _get_call_or_404(db: Session, call_id: str) -> DemandAlignmentCall:
    call = db.query(DemandAlignmentCall).filter(DemandAlignmentCall.id == call_id).first()
    if call is None:
        raise HTTPException(status_code=404, detail="Alignment call not found.")
    return call


@router.post(
    "/demands/{demand_id}/confirm-sow",
    dependencies=[Depends(get_current_internal_user)],
    response_model=ConfirmSOWResponse,
    summary="Record a SOW reference and confirm the demand",
)
def confirm_sow(
    demand_id: str,
    body: ConfirmSOWRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    demand = _get_demand_or_404(db, demand_id)
    try:
        demand = confirm_demand_with_sow(
            db, demand, sow_reference=body.sow_reference, sow_received_date=body.sow_received_date,
        )
    except SOWReferenceRequired as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    db.refresh(demand)
    return ConfirmSOWResponse(
        demand_id=demand.id,
        confirmation_status=demand.confirmation_status,
        sow_reference=demand.sow_reference,
        sow_received_date=demand.sow_received_date,
    )


@router.post(
    "/demands/{demand_id}/employees/{employee_id}/schedule-call",
    dependencies=[Depends(get_current_internal_user)],
    response_model=AlignmentCallItem,
    summary="Book (or return the existing) 3-way alignment call",
)
def schedule_call(
    demand_id: str,
    employee_id: str,
    body: ScheduleCallRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    demand = _get_demand_or_404(db, demand_id)
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")

    call = schedule_alignment_call(
        db, demand, employee,
        curtis_user_id=body.curtis_user_id, bu_head_user_id=body.bu_head_user_id,
    )
    db.commit()
    db.refresh(call)
    return _to_item(db, call)


@router.get(
    "/demands/{demand_id}/calls",
    dependencies=[Depends(get_current_internal_user)],
    response_model=AlignmentCallListResponse,
    summary="Get all alignment calls for a demand",
)
def get_calls_for_demand(
    demand_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    _get_demand_or_404(db, demand_id)
    calls = (
        db.query(DemandAlignmentCall)
        .filter(DemandAlignmentCall.demand_id == demand_id)
        .order_by(DemandAlignmentCall.created_at.desc())
        .all()
    )
    return AlignmentCallListResponse(calls=[_to_item(db, c) for c in calls])


@router.post(
    "/calls/{call_id}/confirm-fit",
    dependencies=[Depends(get_current_internal_user)],
    response_model=ConfirmFitResponse,
    summary="Record one participant's fit confirmation (immutable once set)",
)
def confirm_call_fit(
    call_id: str,
    body: ConfirmFitRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    call = _get_call_or_404(db, call_id)
    try:
        call = confirm_fit(
            db, call, participant=body.participant, confirmed=body.confirmed, notes=body.notes,
        )
    except InvalidParticipant as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except FitConfirmationAlreadyRecorded as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(call)
    return ConfirmFitResponse(message="Fit confirmation recorded.", call=_to_item(db, call))


@router.post(
    "/calls/{call_id}/trigger-release",
    dependencies=[Depends(get_current_internal_user)],
    response_model=TriggerReleaseResponse,
    summary="Trigger Specialty client release (hard gate: CONFIRMED + both fits True)",
)
def trigger_release(
    call_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    call = _get_call_or_404(db, call_id)
    demand = _get_demand_or_404(db, call.demand_id)
    try:
        call = trigger_specialty_client_release(
            db, call, demand, speciality_rm=current_user, tenant_id=current_user.tenant_id,
        )
    except SpecialtyClientReleaseNotAllowed as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(call)
    return TriggerReleaseResponse(message="Specialty client release triggered.", call=_to_item(db, call))
