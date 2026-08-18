"""
S-074/HRMS-0474 -- Bulk Candidate Engagement Launch
==================================================================
Prefix: /candidates
Tag:    bulk-engagement

POST /candidates/bulk-import       -- CSV upload, creates candidates (Step 1)
POST /candidates/bulk-engage       -- queues + launches engagement (Step 2/3)
GET  /candidates/bulk-jobs/{id}/status -- progress polling (Step 4)

Auth: candidate.create for import (creates real candidate rows,
matches the existing single-candidate creation gate), candidate.edit
for launching engagement (matches S-062's mutating-action convention).
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.dependencies import get_current_hr_or_admin, require_resource_permission
from app.models.user import Users
from app.schemas.bulk_engagement import BulkEngageRequest, BulkEngageResponse, BulkImportResponse, BulkJobStatusResponse
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.bulk_engagement_service import (
    BulkTooLarge, CsvMissingRequiredColumn, CsvTooLarge, get_bulk_job_status,
    import_candidates_from_csv, launch_bulk_engagement, run_bulk_engagement_worker,
)

router = APIRouter(tags=["bulk-engagement"])


def _run_worker_in_background(job_id: str) -> None:
    """The background-task body opens its own session -- the request's
    `db` (from Depends(get_db)) is torn down once the HTTP response is
    sent, before a BackgroundTask necessarily gets its turn, same real
    `SessionLocal()` convention every scheduled job in this codebase
    already uses (see app/core/scheduler.py)."""
    db = SessionLocal()
    try:
        run_bulk_engagement_worker(db, job_id)
    finally:
        db.close()


@router.post("/candidates/bulk-import", response_model=BulkImportResponse, dependencies=[Depends(require_resource_permission("candidates", "create"))])
async def bulk_import(file: UploadFile, db: Session = Depends(get_db), current_user: Users = Depends(get_current_hr_or_admin)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv file.")
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    tenant_id = resolve_default_tenant_id(db)
    try:
        return import_candidates_from_csv(db, raw, current_user.UserID, tenant_id)
    except CsvMissingRequiredColumn as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except CsvTooLarge as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/candidates/bulk-engage", response_model=BulkEngageResponse, dependencies=[Depends(require_resource_permission("candidates", "edit"))])
def bulk_engage(payload: BulkEngageRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: Users = Depends(get_current_hr_or_admin)):
    tenant_id = resolve_default_tenant_id(db)
    try:
        result = launch_bulk_engagement(db, payload.candidate_ids, current_user.UserID, tenant_id)
    except BulkTooLarge as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    background_tasks.add_task(_run_worker_in_background, result["bulk_job_id"])
    return result


@router.get("/candidates/bulk-jobs/{job_id}/status", response_model=BulkJobStatusResponse, dependencies=[Depends(require_resource_permission("candidates", "view"))])
def bulk_job_status(job_id: str, db: Session = Depends(get_db)):
    status = get_bulk_job_status(db, job_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Bulk job {job_id!r} not found.")
    return status
