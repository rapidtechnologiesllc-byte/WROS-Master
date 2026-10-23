"""
Timesheet approvals -- the approver's side of the approval loop
(app.services.timesheet_approval_service).
==================================================================
Prefix: /timesheet-approvals
Tag:    timesheet-approvals

The routed approver is usually a reporting manager with no timesheet-administration rights, so
these routes need only the self-service my-tasks permission; the service decides who may act
(the routed approver, or timesheets edit on the timesheet's business unit). Anyone else gets 404
for a timesheet they cannot see.

GET  /timesheet-approvals                       my pending approvals
GET  /timesheet-approvals/{timesheet_id}        entries, revision, previous rejection, response, diff
POST /timesheet-approvals/{timesheet_id}/approve {comment, addressed}
POST /timesheet-approvals/{timesheet_id}/reject  {reason, flagged_dates}

Client approval (clients that approve their own timesheets, client_timesheet_approval_service):
POST /timesheet-approvals/{timesheet_id}/client-request    (re)send the client approver the link
POST /timesheet-approvals/{timesheet_id}/client-evidence   upload the client's approved timesheet
GET  /timesheet-approvals/{timesheet_id}/client-evidence   download it
"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.timesheet import Timesheet
from app.models.timesheet_review import TimesheetReview
from app.models.user import Users
from app.schemas.timesheet import ApproveTimesheetRequest, RejectTimesheetRequest
from app.services import timesheet_approval_service as approvals

router = APIRouter(prefix="/timesheet-approvals", tags=["timesheet-approvals"])


def _timesheet_for(db: Session, timesheet_id: str, user: Users) -> Timesheet:
    """A timesheet the caller reviews: routed to them in any revision, or visible to them with
    timesheet edit rights. Anything else is 404."""
    timesheet = db.query(Timesheet).filter(Timesheet.id == timesheet_id, Timesheet.tenant_id == user.tenant_id).first()
    if timesheet is None:
        raise HTTPException(status_code=404, detail="Timesheet not found.")
    routed = db.query(TimesheetReview.id).filter(TimesheetReview.timesheet_id == timesheet.id,
                                                 TimesheetReview.approver_user_id == user.UserID).first()
    review = approvals.latest_review(db, timesheet)
    if routed is None and (review is None or not approvals.may_decide(db, review, user)):
        raise HTTPException(status_code=404, detail="Timesheet not found.")
    return timesheet


@router.get("", dependencies=[Depends(require_resource_permission("my-tasks", "view"))],
            summary="Timesheets waiting for my approval")
def my_pending_approvals(current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    return {"approvals": [
        {"timesheet_id": t.id, "employee_id": e.id, "employee_name": f"{e.first_name} {e.last_name}".strip(),
         "week_starting_date": t.week_starting_date.isoformat(), "total_hours": float(t.total_hours or 0),
         "revision": r.revision, "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None}
        for r, t, e in approvals.pending_for(db, current_user)]}


@router.get("/{timesheet_id}", dependencies=[Depends(require_resource_permission("my-tasks", "view"))],
            summary="One timesheet as its approver sees it")
def approval_view(timesheet_id: str, current_user: Users = Depends(get_current_internal_user),
                  db: Session = Depends(get_db)):
    return approvals.review_view(db, _timesheet_for(db, timesheet_id, current_user), current_user)


@router.post("/{timesheet_id}/approve", dependencies=[Depends(require_resource_permission("my-tasks", "view"))],
             summary="Approve (with an optional comment; a resubmission needs addressed=true)")
def approve(timesheet_id: str, body: Optional[ApproveTimesheetRequest] = None,
            current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    from app.api.v1.endpoints.timesheets import run_approval_step

    timesheet = _timesheet_for(db, timesheet_id, current_user)
    body = body or ApproveTimesheetRequest()
    run_approval_step(db, lambda: approvals.approve(db, timesheet, current_user, comment=body.comment,
                                                    addressed=body.addressed))
    return approvals.review_view(db, timesheet, current_user)


@router.post("/{timesheet_id}/reject", dependencies=[Depends(require_resource_permission("my-tasks", "view"))],
             summary="Reject with a reason (required) and optionally the days at fault")
def reject(timesheet_id: str, body: RejectTimesheetRequest,
           current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    from app.api.v1.endpoints.timesheets import run_approval_step

    timesheet = _timesheet_for(db, timesheet_id, current_user)
    run_approval_step(db, lambda: approvals.reject(db, timesheet, current_user, reason=body.reason,
                                                   flagged_dates=body.flagged_dates))
    return approvals.review_view(db, timesheet, current_user)


def _client_step(db: Session, step):
    from app.services import client_timesheet_approval_service as client_approvals

    try:
        result = step()
    except client_approvals.NotAllowed as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc))
    except client_approvals.ClientApprovalError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    return result


@router.post("/{timesheet_id}/client-request", dependencies=[Depends(require_resource_permission("my-tasks", "view"))],
             summary="Send (or re-send) the client's approver the approve / reject link")
def request_client_approval(timesheet_id: str, current_user: Users = Depends(get_current_internal_user),
                            db: Session = Depends(get_db)):
    from app.services import client_timesheet_approval_service as client_approvals

    timesheet = _timesheet_for(db, timesheet_id, current_user)
    _client_step(db, lambda: client_approvals.request_again(db, timesheet, current_user))
    client_approvals.queue_email(db, timesheet)
    return approvals.review_view(db, timesheet, current_user)


@router.post("/{timesheet_id}/client-evidence", dependencies=[Depends(require_resource_permission("my-tasks", "view"))],
             summary="Upload the client's approved timesheet (e.g. the VMS export): the week becomes client-approved")
async def upload_client_evidence(timesheet_id: str, file: UploadFile = File(...), note: Optional[str] = Form(None),
                                 current_user: Users = Depends(get_current_internal_user),
                                 db: Session = Depends(get_db)):
    from app.core.config import settings
    from app.services import client_timesheet_approval_service as client_approvals

    timesheet = _timesheet_for(db, timesheet_id, current_user)
    data = await file.read(settings.CLIENT_TIMESHEET_EVIDENCE_MAX_BYTES + 1)
    _client_step(db, lambda: client_approvals.record_evidence(
        db, timesheet, current_user, filename=file.filename, content_type=file.content_type, data=data, note=note))
    return approvals.review_view(db, timesheet, current_user)


@router.get("/{timesheet_id}/client-evidence", dependencies=[Depends(require_resource_permission("my-tasks", "view"))],
            summary="The client's approved timesheet uploaded as evidence")
def download_client_evidence(timesheet_id: str, current_user: Users = Depends(get_current_internal_user),
                             db: Session = Depends(get_db)):
    from app.services import client_timesheet_approval_service as client_approvals

    timesheet = _timesheet_for(db, timesheet_id, current_user)
    evidence = client_approvals.evidence_for(db, timesheet)
    if evidence is None or not os.path.isfile(evidence.evidence_path):
        raise HTTPException(status_code=404, detail="No client approval evidence uploaded.")
    return FileResponse(evidence.evidence_path, media_type=evidence.evidence_content_type,
                        filename=evidence.evidence_filename)
