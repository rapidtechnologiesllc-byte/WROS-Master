"""
S-364 Buddy KPI Tracking + S-365 Graduation Gate.
==================================================================
Prefix: /buddy-program
import logging
Tag:    buddy-program

Weekly score submission is any internal staff member (HR/Buddy
engineer/RM each submit their own category -- no dedicated role exists
for any of the three in this codebase's RBAC yet, same gap already
flagged for Ask-Thunder). Graduation decisions (S-365) are gated to
HR/Admin -- a consequential, human-only call on a real person's job
track, never automatic.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, get_current_internal_user, require_resource_permission
from app.models.buddy_program import BuddyProgramRecord
from app.models.employee import Employee
from app.models.user import Users
from app.schemas.buddy_program import (
    BuddyProgramRecordCreateRequest, BuddyProgramRecordResponse, GraduationDecisionRequest,
    ScorecardResponse, WeeklyScoresSubmitRequest,
)
from app.services.buddy_program_service import (
    InvalidKPISubmission, SelfBuddyNotAllowed, compute_day30_scorecard, create_buddy_program_record,
    submit_weekly_scores,
)
from app.services.buddy_program_graduation_service import (
    ExtensionLimitReached, InvalidGraduationDecision, can_extend, record_graduation_decision,
)

router = APIRouter(prefix="/buddy-program", tags=["buddy-program"])


def _get_record_or_404(db: Session, record_id: str) -> BuddyProgramRecord:
    record = db.query(BuddyProgramRecord).filter(BuddyProgramRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"Buddy program record {record_id!r} not found.")
    return record


@router.get(
    "/records",
    response_model=list[BuddyProgramRecordResponse],
    dependencies=[Depends(require_resource_permission("record", "view"))]
)
def list_records(current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    return db.query(BuddyProgramRecord).filter(BuddyProgramRecord.status.in_(("IN_PROGRESS", "EXTENDED"))).all()


@router.post(
    "/records",
    response_model=BuddyProgramRecordResponse,
    dependencies=[Depends(require_resource_permission("record", "create"))]
)
def create_record(
    body: BuddyProgramRecordCreateRequest, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db),
):
    employee = db.query(Employee).filter(Employee.id == body.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee {body.employee_id!r} not found.")
    try:
        record = create_buddy_program_record(
            db, employee, buddy_engineer_user_id=body.buddy_engineer_user_id,
            program_start_date=body.program_start_date, expected_end_date=body.expected_end_date,
            tenant_id=employee.tenant_id,
        )
        db.commit()
        db.refresh(record)
        return record
    except SelfBuddyNotAllowed as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))


@router.get(
    "/records/{record_id}",
    response_model=BuddyProgramRecordResponse,
    dependencies=[Depends(require_resource_permission("record", "view"))]
)
def get_record(record_id: str, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    return _get_record_or_404(db, record_id)


@router.post(
    "/records/{record_id}/scores",
    dependencies=[Depends(require_resource_permission("record", "create"))]
)
def submit_scores(
    record_id: str, body: WeeklyScoresSubmitRequest,
    current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db),
):
    record = _get_record_or_404(db, record_id)
    try:
        rows = submit_weekly_scores(
            db, record, scores=body.scores, scored_by=current_user.UserID, week_number=body.week_number,
        )
        db.commit()
        return {"submitted": len(rows)}
    except InvalidKPISubmission as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))


@router.get(
    "/records/{record_id}/scorecard",
    response_model=ScorecardResponse,
    dependencies=[Depends(require_resource_permission("record", "view"))]
)
def get_scorecard(record_id: str, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    record = _get_record_or_404(db, record_id)
    return compute_day30_scorecard(db, record)


def _decide(db: Session, record_id: str, decision: str, notes: "str | None", changed_by: str) -> BuddyProgramRecord:
    record = _get_record_or_404(db, record_id)
    employee = db.query(Employee).filter(Employee.id == record.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail=f"No employee found for buddy program record {record_id!r}.")
    try:
        record_graduation_decision(db, record, employee, decision=decision, changed_by=changed_by, notes=notes)
        db.commit()
        db.refresh(record)
        return record
    except (InvalidGraduationDecision, ExtensionLimitReached) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))


@router.get(
    "/records/{record_id}/can-extend",
    dependencies=[Depends(require_resource_permission("record", "view"))]
)
def get_can_extend(record_id: str, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    """AC-5: whether the Extend option should even be shown -- hidden
    entirely on the third review, not just rejected after the fact."""
    record = _get_record_or_404(db, record_id)
    return {"can_extend": can_extend(record)}


@router.post(
    "/records/{record_id}/graduate",
    response_model=BuddyProgramRecordResponse,
    dependencies=[Depends(require_resource_permission("record", "create"))]
)
def graduate(record_id: str, body: GraduationDecisionRequest, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    return _decide(db, record_id, "GRADUATE", body.notes, current_user.UserID)


@router.post(
    "/records/{record_id}/extend",
    response_model=BuddyProgramRecordResponse,
    dependencies=[Depends(require_resource_permission("record", "create"))]
)
def extend(record_id: str, body: GraduationDecisionRequest, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    return _decide(db, record_id, "EXTEND", body.notes, current_user.UserID)


@router.post(
    "/records/{record_id}/exit",
    response_model=BuddyProgramRecordResponse,
    dependencies=[Depends(require_resource_permission("record", "create"))]
)
def exit_record(record_id: str, body: GraduationDecisionRequest, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    return _decide(db, record_id, "EXIT", body.notes, current_user.UserID)
