"""
Executive Signal & Culture Agent.
==================================================================
Prefix: /executive-signal
Tag:    executive-signal

Advisory-only surface -- watches, drafts, surfaces; never autonomously
acts on a real person's job, comp, or standing (see culture_agent_service
module docstring). Org-health + admin actions gated to HR/Admin;
employee-facing feedback/concern submission open to any internal user
acting on their own linked Employee record.

GET  /executive-signal/org-health
POST /executive-signal/feedback-cycles
POST /executive-signal/feedback-cycles/{id}/close
POST /executive-signal/feedback-cycles/{id}/responses   -- employee submits their own
POST /executive-signal/recognition/birthday-drafts       -- generate today's drafts
POST /executive-signal/recognition/{id}/approve
POST /executive-signal/recognition/{id}/reject
POST /executive-signal/concerns                          -- employee submits their own
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin, get_current_internal_user
from app.models.employee import Employee
from app.models.executive_signal import EmployeeFeedbackCycle, RecognitionMessageDraft
from app.models.user import Users
from app.schemas.executive_signal import (
    ConcernResponse, ConcernSubmitRequest, FeedbackCycleCreateRequest, FeedbackCycleResponse,
    FeedbackSubmitRequest, RecognitionDraftResponse,
)
from app.services.culture_agent_service import (
    approve_and_send_recognition, close_cycle_and_summarize, generate_birthday_drafts, reject_recognition,
    start_quarterly_cycle, submit_concern, submit_feedback,
)
from app.services.org_health_service import get_org_health_snapshot

router = APIRouter(prefix="/executive-signal", tags=["executive-signal"])


def _current_employee(db: Session, current_user: Users) -> Employee:
    employee = db.query(Employee).filter(Employee.wros_user_id == current_user.UserID).first()
    if not employee:
        raise HTTPException(status_code=404, detail="No employee record linked to your account.")
    return employee


@router.get("/org-health", dependencies=[Depends(get_current_hr_or_admin)])
def org_health(db: Session = Depends(get_db)):
    return get_org_health_snapshot(db)


@router.post("/feedback-cycles", response_model=FeedbackCycleResponse, dependencies=[Depends(get_current_hr_or_admin)])
def create_cycle(body: FeedbackCycleCreateRequest, db: Session = Depends(get_db)):
    return start_quarterly_cycle(db, body.quarter_label)


@router.post("/feedback-cycles/{cycle_id}/close", dependencies=[Depends(get_current_hr_or_admin)])
def close_cycle(cycle_id: str, current_user: Users = Depends(get_current_hr_or_admin), db: Session = Depends(get_db)):
    cycle = db.query(EmployeeFeedbackCycle).filter(EmployeeFeedbackCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail=f"Feedback cycle {cycle_id!r} not found.")
    return close_cycle_and_summarize(db, cycle, closed_by=current_user.UserID)


@router.post("/feedback-cycles/{cycle_id}/responses")
def submit_response(
    cycle_id: str, body: FeedbackSubmitRequest,
    current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db),
):
    cycle = db.query(EmployeeFeedbackCycle).filter(EmployeeFeedbackCycle.id == cycle_id, EmployeeFeedbackCycle.status == "OPEN").first()
    if not cycle:
        raise HTTPException(status_code=404, detail=f"Open feedback cycle {cycle_id!r} not found.")
    employee = _current_employee(db, current_user)
    submit_feedback(db, cycle, employee, body.response_text)
    return {"submitted": True}


@router.post("/recognition/birthday-drafts", response_model=list[RecognitionDraftResponse], dependencies=[Depends(get_current_hr_or_admin)])
def birthday_drafts(db: Session = Depends(get_db)):
    return generate_birthday_drafts(db)


@router.post("/recognition/{draft_id}/approve", response_model=RecognitionDraftResponse)
def approve_recognition(draft_id: str, current_user: Users = Depends(get_current_hr_or_admin), db: Session = Depends(get_db)):
    draft = db.query(RecognitionMessageDraft).filter(RecognitionMessageDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail=f"Recognition draft {draft_id!r} not found.")
    try:
        return approve_and_send_recognition(db, draft, approved_by=current_user.UserID)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/recognition/{draft_id}/reject", response_model=RecognitionDraftResponse, dependencies=[Depends(get_current_hr_or_admin)])
def reject_recognition_endpoint(draft_id: str, db: Session = Depends(get_db)):
    draft = db.query(RecognitionMessageDraft).filter(RecognitionMessageDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail=f"Recognition draft {draft_id!r} not found.")
    return reject_recognition(db, draft)


@router.post("/concerns", response_model=ConcernResponse)
def raise_concern(body: ConcernSubmitRequest, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    employee = _current_employee(db, current_user)
    return submit_concern(db, employee, body.message_text)
