"""
Client timesheet approval -- the public page behind the emailed link (no login)
==================================================================================
Prefix: /public/client-timesheet-approval
Tag:    public-client-timesheet-approval

The client's timesheet approver has no account: the single-use, expiring token from the email
is the only credential (app.services.client_timesheet_approval_service). It is sent in the POST
body, never in a URL path or query, so it does not end up in access logs. Each call returns only
that one week (employee name, client, dates, hours): no rates, notes or other records. An
unknown, used, superseded or expired token is 410. Exempt from the login gate in
app.middleware.auth_middleware.PUBLIC_ROUTES; limited per client IP
(app.core.rate_limiter.public_rate_limit).

POST /public/client-timesheet-approval/view     {token}          the week to approve
POST /public/client-timesheet-approval/approve  {token}          approve it
POST /public/client-timesheet-approval/reject   {token, reason}  reject it (reason required)
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import logger
from app.core.rate_limiter import public_rate_limit
from app.services import client_timesheet_approval_service as client_approvals

router = APIRouter(prefix="/public/client-timesheet-approval", tags=["public-client-timesheet-approval"],
                   dependencies=[Depends(public_rate_limit("client-timesheet-approval"))])


class TokenRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)


class RejectRequest(TokenRequest):
    reason: str = Field(..., max_length=client_approvals.MAX_REASON_LENGTH)


def _ip(request: Request):
    return request.client.host if request.client else None


@router.post("/view", summary="The week behind an emailed client approval link (no login)")
def view(body: TokenRequest, db: Session = Depends(get_db)):
    try:
        return client_approvals.public_view(db, body.token)
    except client_approvals.ClientLinkInvalid as exc:
        raise HTTPException(status_code=410, detail=str(exc))


@router.post("/approve", summary="The client approves the week (no login; the link works once)")
def approve(body: TokenRequest, request: Request, db: Session = Depends(get_db)):
    try:
        client_approvals.approve_by_link(db, body.token, ip=_ip(request))
    except client_approvals.ClientLinkInvalid as exc:
        db.rollback()
        raise HTTPException(status_code=410, detail=str(exc))
    db.commit()
    return {"status": "APPROVED", "message": "Thank you. The timesheet is approved."}


@router.post("/reject", summary="The client rejects the week with a reason (no login; the link works once)")
def reject(body: RejectRequest, request: Request, db: Session = Depends(get_db)):
    from app.services.timesheet_approval_service import send_notices

    try:
        review = client_approvals.reject_by_link(db, body.token, body.reason, ip=_ip(request))
    except client_approvals.ClientLinkInvalid as exc:
        db.rollback()
        raise HTTPException(status_code=410, detail=str(exc))
    except client_approvals.ClientApprovalError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    try:
        send_notices(db, review)  # the employee's email; the resubmit task and Flash are already saved
    except RuntimeError as exc:
        logger.error(f"[ClientTimesheetApproval] rejection saved but the employee email could not be queued: {exc}",
                     exc_info=True)
    return {"status": "REJECTED", "message": "Thank you. The timesheet was sent back with your reason."}
