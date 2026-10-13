"""Background verification (BGV).

GET  /bgv                        open and recent BGVs (filter by status)
GET  /bgv/candidate/{id}         a candidate's BGV records
POST /bgv/{id}/start             record the vendor and reference (needs the candidate's consent)
POST /bgv/{id}/verdict           PASSED or FAILED
POST /bgv/{id}/waive             skip BGV for this hire, with a reason
POST /bgv/webhook/{vendor}       vendor callback {vendor_reference, status, report_url}; X-Webhook-Secret
Every change re-evaluates the candidate's hiring pipeline (PASSED/WAIVED leads to the bench,
FAILED closes it).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.webhook_auth import require_webhook_secret
from app.models.background_verification import BackgroundVerification
from app.services import bgv_service
from app.services.hiring_pipeline_service import notify

router = APIRouter(prefix="/bgv", tags=["bgv"])


class StartRequest(BaseModel):
    vendor_name: str
    vendor_reference: Optional[str] = None


class VerdictRequest(BaseModel):
    verdict: str
    report_url: Optional[str] = None
    notes: Optional[str] = None


class WaiveRequest(BaseModel):
    reason: str


class VendorCallback(BaseModel):
    vendor_reference: str
    status: str
    report_url: Optional[str] = None
    notes: Optional[str] = None


def _out(row: BackgroundVerification) -> dict:
    return {"id": row.id, "candidate_id": row.candidate_id, "offer_letter_id": row.offer_letter_id,
            "status": row.status, "vendor_name": row.vendor_name, "vendor_reference": row.vendor_reference,
            "initiated_at": row.initiated_at, "verdict_at": row.verdict_at, "verdict_by": row.verdict_by,
            "report_url": row.report_url, "waiver_reason": row.waiver_reason, "notes": row.notes}


def _get(db: Session, bgv_id: int, user) -> BackgroundVerification:
    row = db.query(BackgroundVerification).filter(BackgroundVerification.id == bgv_id).with_for_update().first()
    if row is None or (user.tenant_id is not None and row.tenant_id not in (None, user.tenant_id)):
        raise HTTPException(status_code=404, detail=f"BGV {bgv_id} not found")
    return row


def _commit_and_notify(db: Session, row: BackgroundVerification, trigger: str) -> dict:
    db.commit()
    notify(row.candidate_id, trigger, f"{row.id}:{row.status}")
    return _out(row)


@router.get("", dependencies=[Depends(require_resource_permission("candidates", "view"))])
def list_bgv(status: Optional[str] = None, db: Session = Depends(get_db), user=Depends(get_current_internal_user)):
    query = db.query(BackgroundVerification)
    if user.tenant_id is not None:
        query = query.filter(BackgroundVerification.tenant_id.in_([user.tenant_id]) | BackgroundVerification.tenant_id.is_(None))
    if status:
        query = query.filter(BackgroundVerification.status == status.upper())
    return [_out(r) for r in query.order_by(BackgroundVerification.id.desc()).limit(500).all()]


@router.get("/candidate/{candidate_id}", dependencies=[Depends(require_resource_permission("candidates", "view"))])
def candidate_bgv(candidate_id: str, db: Session = Depends(get_db)):
    rows = db.query(BackgroundVerification).filter(BackgroundVerification.candidate_id == candidate_id) \
        .order_by(BackgroundVerification.id.desc()).all()
    return [_out(r) for r in rows]


@router.post("/{bgv_id}/start", dependencies=[Depends(require_resource_permission("candidates", "edit"))])
def start_bgv(bgv_id: int, request: StartRequest, db: Session = Depends(get_db), user=Depends(get_current_internal_user)):
    row = _get(db, bgv_id, user)
    if row.status == "IN_PROGRESS":
        row.vendor_name, row.vendor_reference = request.vendor_name, request.vendor_reference or row.vendor_reference
    elif not bgv_service.start_if_consented(db, row, request.vendor_name, request.vendor_reference):
        db.rollback()
        detail = (f"BGV is already {row.status}." if row.status != "NOT_STARTED"
                  else "The candidate's background check consent has not been received.")
        raise HTTPException(status_code=409, detail=detail)
    return _commit_and_notify(db, row, "bgv_started")


@router.post("/{bgv_id}/verdict", dependencies=[Depends(require_resource_permission("candidates", "edit"))])
def bgv_verdict(bgv_id: int, request: VerdictRequest, db: Session = Depends(get_db), user=Depends(get_current_internal_user)):
    row = _get(db, bgv_id, user)
    try:
        bgv_service.record_verdict(db, row, request.verdict.upper(), user.UserID, request.report_url, request.notes)
    except bgv_service.BGVError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    return _commit_and_notify(db, row, "bgv_verdict")


@router.post("/{bgv_id}/waive", dependencies=[Depends(require_resource_permission("candidates", "edit"))])
def waive_bgv(bgv_id: int, request: WaiveRequest, db: Session = Depends(get_db), user=Depends(get_current_internal_user)):
    row = _get(db, bgv_id, user)
    try:
        bgv_service.waive(db, row, request.reason, user.UserID)
    except bgv_service.BGVError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    return _commit_and_notify(db, row, "bgv_waived")


@router.post("/webhook/{vendor}", dependencies=[Depends(require_webhook_secret)])
def vendor_callback(vendor: str, body: VendorCallback, db: Session = Depends(get_db)):
    row = db.query(BackgroundVerification).filter(BackgroundVerification.vendor_reference == body.vendor_reference) \
        .with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown vendor reference")
    status = body.status.strip().upper()
    if status not in ("PASSED", "FAILED"):
        return {"status": "ignored", "bgv_status": row.status}  # interim vendor statuses
    if row.status == status:
        return {"status": "duplicate", "bgv_status": row.status}
    try:
        bgv_service.record_verdict(db, row, status, f"vendor:{vendor}", body.report_url, body.notes)
    except bgv_service.BGVError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    return _commit_and_notify(db, row, "bgv_verdict")
