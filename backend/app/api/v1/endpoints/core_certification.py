"""
Direct Certification -- API
=========================================================================
Prefix: /core-certification
Tag:    core-certification

Approval of Direct certification by the employee's BU Head (CEO 2026-10-14). Requests are raised
by the daily core_certification_sweep job (app.services.core_certification_service). Deciding in
Flash: the approval task opens the bubble on the request (flash workflow core_cert); a rejection
is a short Flash discussion there that becomes follow-up tasks.

Auth: the workforce-overview permission to see requests (scoped to the caller's business
units); deciding is for the request's BU Head or another leader of that business unit.

Routes:
  GET  /core-certification/requests?status=
  GET  /core-certification/eligibility/{employee_id}
  POST /core-certification/requests/{id}/approve
  POST /core-certification/requests/{id}/close          (no longer eligible)
  PUT  /core-certification/employees/{id}              (a leader sets Core eligibility)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.data_scope import bu_filter
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.core_certification import REQUEST_STATUSES, CoreCertificationRequest
from app.models.employee import Employee
from app.models.user import Users
from app.schemas.core_certification import (
    CoreCertificationListResponse,
    CoreCertificationRequestItem,
    EligibilityResponse,
)
from app.services import core_certification_service as service

router = APIRouter(prefix="/core-certification", tags=["core-certification"])

VIEW = [Depends(require_resource_permission("workforce-overview", "view")), Depends(get_current_internal_user)]


def _item(db: Session, request: CoreCertificationRequest, employee: Employee, user: Users) -> CoreCertificationRequestItem:
    item = CoreCertificationRequestItem(
        id=request.id, employee_id=employee.id, candidate_id=employee.candidate_id,
        employee_name=f"{employee.first_name} {employee.last_name}".strip(), status=request.status,
        billable_days=request.billable_days, counted_from=request.counted_from,
        bu_head_user_id=request.bu_head_user_id, created_at=request.created_at,
        decided_by_user_id=request.decided_by_user_id, decided_at=request.decided_at,
        rejection_reason=request.rejection_reason, follow_up_plan=request.follow_up_plan,
    )
    if request.status == "PENDING":
        check = service.eligibility(db, employee)
        item.still_eligible, item.eligibility_reasons = check["eligible"], check["reasons"]
        item.can_decide = service.may_decide(db, request, user)
        item.chat_in_progress = bool(request.chat_state)
    return item


def _request_or_404(db: Session, request_id: str, user: Users):
    row = service.visible_request(db, user, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found.")
    return row


def _decide(fn, *args):
    try:
        return fn(*args)
    except service.CertificationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/requests", dependencies=VIEW, response_model=CoreCertificationListResponse,
            summary="Direct certification requests in the caller's business units")
def list_requests(status: Optional[str] = None, db: Session = Depends(get_db),
                  current_user: Users = Depends(get_current_internal_user)):
    if status and status not in REQUEST_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {REQUEST_STATUSES}")
    query = service.visible_requests(db, current_user)
    if status:
        query = query.filter(CoreCertificationRequest.status == status)
    rows = query.order_by(CoreCertificationRequest.created_at.desc()).all()
    return CoreCertificationListResponse(requests=[_item(db, r, e, current_user) for r, e in rows])


@router.get("/eligibility/{employee_id}", dependencies=VIEW, response_model=EligibilityResponse,
            summary="Where an employee stands against the Direct certification rules")
def get_eligibility(employee_id: str, db: Session = Depends(get_db),
                    current_user: Users = Depends(get_current_internal_user)):
    employee = (db.query(Employee).filter(Employee.id == employee_id, Employee.tenant_id == current_user.tenant_id,
                                          bu_filter(db, current_user, Employee.bu_id)).first())
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    check = service.eligibility(db, employee)
    return EligibilityResponse(employee_id=employee.id, **check)


@router.post("/requests/{request_id}/approve", dependencies=VIEW, response_model=CoreCertificationRequestItem,
             summary="Approve: the employee becomes Direct-certified")
def approve_request(request_id: str, db: Session = Depends(get_db),
                    current_user: Users = Depends(get_current_internal_user)):
    request, employee = _request_or_404(db, request_id, current_user)
    _decide(service.approve, db, request, current_user)
    return _item(db, request, employee, current_user)


@router.post("/requests/{request_id}/close", dependencies=VIEW, response_model=CoreCertificationRequestItem,
             summary="Close a request whose employee is no longer eligible")
def close_request(request_id: str, db: Session = Depends(get_db),
                  current_user: Users = Depends(get_current_internal_user)):
    request, employee = _request_or_404(db, request_id, current_user)
    _decide(service.close, db, request, current_user)
    return _item(db, request, employee, current_user)


class CoreEligibleRequest(BaseModel):
    eligible: bool
    reason: Optional[str] = None


@router.put("/employees/{employee_id}",
            dependencies=[Depends(require_resource_permission("employees", "view")), Depends(get_current_internal_user)],
            summary="Set Core eligibility on the employee page (a leader of the employee's business unit)")
def set_core_eligible(employee_id: str, body: CoreEligibleRequest, db: Session = Depends(get_db),
                      current_user: Users = Depends(get_current_internal_user)):
    employee = (db.query(Employee).filter(Employee.id == employee_id, Employee.tenant_id == current_user.tenant_id,
                                          bu_filter(db, current_user, Employee.bu_id)).first())
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    try:
        return service.set_core_eligible(db, employee, body.eligible, current_user, body.reason)
    except service.CertificationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
