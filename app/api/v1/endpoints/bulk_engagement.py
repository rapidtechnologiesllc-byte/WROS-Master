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
from app.core.logging import logger
from app.core.dependencies import get_current_hr_or_admin, require_permission
from app.models.user import Users
from app.schemas.bulk_engagement import BulkEngageRequest, BulkEngageResponse, BulkImportResponse, BulkJobStatusResponse
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.bulk_engagement_service import (
    BulkTooLarge, CsvMissingRequiredColumn, CsvTooLarge, get_bulk_job_status,
    import_candidates_from_csv, launch_bulk_engagement, run_bulk_engagement_worker,
    update_candidates_from_csv,
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


def _run_import_in_background(job_id: str, csv_text: str, recruiter_id: str, tenant_id: str) -> None:
    """Process CSV import in background without blocking HTTP response."""
    from app.models.bulk_engagement import BulkEngagementJob
    from app.core.database import SessionLocal
    import csv as csv_module
    import io as io_module

    db = SessionLocal()
    try:
        # Count total rows FIRST (before creating job)
        sample = csv_text[:1024]
        try:
            dialect = csv_module.Sniffer().sniff(sample, delimiters=',\t;|')
        except csv_module.Error:
            dialect = csv_module.excel

        reader = csv_module.DictReader(io_module.StringIO(csv_text), dialect=dialect)
        total_rows = len(list(reader)) if reader.fieldnames else 0

        # Create job record with CORRECT total_count
        job = BulkEngagementJob(
            id=job_id,
            recruiter_id=recruiter_id,
            tenant_id=tenant_id,
            candidate_ids=[],  # Empty for import jobs
            total_count=total_rows,  # NOW SET TO ACTUAL TOTAL
            status="PROCESSING",
            success_count=0,
            failed_count=0,
            skipped_count=0
        )
        db.add(job)
        db.commit()
        logger.info(f"[BulkImport] Job {job_id} STARTED: total_rows={total_rows}")

        # Run import with job tracking
        logger.info(f"[BulkImport] Job {job_id} calling import_candidates_from_csv...")
        result = import_candidates_from_csv(db, csv_text, recruiter_id, tenant_id, job_id=job_id)
        logger.info(f"[BulkImport] Job {job_id} import_candidates_from_csv completed: {result}")

        # Update job record with final results
        job = db.query(BulkEngagementJob).filter(BulkEngagementJob.id == job_id).first()
        if job:
            job.status = "COMPLETED"
            job.success_count = result.get('imported', 0)
            job.skipped_count = result.get('skipped_duplicates', 0)
            job.failed_count = len(result.get('errors', []))
            db.commit()

        logger.info(f"[BulkImport] Job {job_id} COMPLETED: {result.get('imported', 0)} imported, {result.get('skipped_duplicates', 0)} skipped, {len(result.get('errors', []))} errors")
    except Exception as exc:
        logger.error(f"[BulkImport] Background job {job_id} EXCEPTION: {exc}", exc_info=True)
        try:
            job = db.query(BulkEngagementJob).filter(BulkEngagementJob.id == job_id).first()
            if job:
                job.status = "FAILED"
                db.commit()
                logger.info(f"[BulkImport] Marked job {job_id} as FAILED")
        except Exception as e:
            logger.error(f"[BulkImport] Failed to mark job {job_id} as FAILED: {e}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/candidates/bulk-import", response_model=BulkImportResponse, dependencies=[Depends(require_permission("candidate.create"))])
async def bulk_import(file: UploadFile, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: Users = Depends(get_current_hr_or_admin)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv file.")
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    tenant_id = resolve_default_tenant_id(db)

    # Quick validation: check headers only (fail fast if format is wrong)
    import csv as csv_module
    import io as io_module

    # Auto-detect delimiter (comma, tab, semicolon, pipe)
    sample = raw[:1024]  # First 1KB for sniffing
    try:
        dialect = csv_module.Sniffer().sniff(sample, delimiters=',\t;|')
    except csv_module.Error:
        dialect = csv_module.excel  # Fallback to comma-separated

    reader = csv_module.DictReader(io_module.StringIO(raw), dialect=dialect)
    if reader.fieldnames is None:
        raise HTTPException(status_code=400, detail="CSV is empty or has no headers.")

    from app.services.bulk_engagement_service import _find_matching_column, NAME_COLUMN_ALIASES
    name_column = _find_matching_column(reader.fieldnames, NAME_COLUMN_ALIASES)
    if not name_column:
        raise HTTPException(status_code=400, detail="CSV must include a name column (e.g., 'name', 'full_name', 'candidate_name', etc.)")

    # Queue import as background task - return success immediately (don't count rows - too slow for 100K+ CSVs)
    import uuid
    job_id = str(uuid.uuid4())
    background_tasks.add_task(_run_import_in_background, job_id, raw, current_user.UserID, tenant_id)
    logger.info(f"[BulkImport] Job {job_id} queued for processing")

    return {
        "imported": 0,
        "skipped_duplicates": 0,
        "errors": [],
        "candidate_ids": [],
        "message": f"✅ CSV upload accepted! Processing in background (job_id: {job_id}). Check Bulk Launch > Step 2 for progress."
    }


@router.post("/candidates/bulk-engage", response_model=BulkEngageResponse, dependencies=[Depends(require_permission("candidate.edit"))])
def bulk_engage(payload: BulkEngageRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: Users = Depends(get_current_hr_or_admin)):
    tenant_id = resolve_default_tenant_id(db)
    try:
        result = launch_bulk_engagement(db, payload.candidate_ids, current_user.UserID, tenant_id)
    except BulkTooLarge as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    background_tasks.add_task(_run_worker_in_background, result["bulk_job_id"])
    return result


@router.get("/candidates/bulk-jobs/{job_id}/status", response_model=BulkJobStatusResponse, dependencies=[Depends(require_permission("candidate.view"))])
def bulk_job_status(job_id: str, db: Session = Depends(get_db)):
    status = get_bulk_job_status(db, job_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Bulk job {job_id!r} not found.")
    return status


@router.get("/candidates/bulk-import/list")
def list_import_jobs(db: Session = Depends(get_db)):
    """Get list of all import jobs with their status. Mark stuck jobs as FAILED."""
    from app.models.bulk_engagement import BulkEngagementJob, BulkEngagementError
    from datetime import datetime, timedelta

    jobs = db.query(BulkEngagementJob).order_by(BulkEngagementJob.created_at.desc()).limit(50).all()

    # Mark jobs as FAILED if stuck in PROCESSING for 3+ minutes with no progress
    now = datetime.utcnow()
    for job in jobs:
        if job.status == "PROCESSING":
            # Check if job has been processing for 3+ minutes with zero progress
            if job.created_at and (now - job.created_at) > timedelta(minutes=3):
                # If no progress made, mark as FAILED
                if job.success_count == 0 and job.failed_count == 0 and job.skipped_count == 0:
                    job.status = "FAILED"
                    logger.warning(f"[BulkImport] Marked stuck job {job.id} as FAILED (no progress in 3 min)")
                    try:
                        db.commit()
                    except Exception as e:
                        logger.error(f"[BulkImport] Failed to mark job {job.id} as FAILED: {e}")
                        db.rollback()

    # Refresh jobs after potential status updates
    jobs = db.query(BulkEngagementJob).order_by(BulkEngagementJob.created_at.desc()).limit(50).all()

    result = []
    for job in jobs:
        total = job.total_count or 1
        processed = job.success_count + job.failed_count + job.skipped_count
        percent = int((processed / total) * 100) if total > 0 else 0

        # Get error reasons for FAILED jobs
        error_reasons = []
        if job.status == "FAILED":
            errors = db.query(BulkEngagementError).filter(BulkEngagementError.job_id == job.id).limit(5).all()
            error_reasons = [{"row": e.candidate_id, "reason": e.reason} for e in errors]

        result.append({
            "id": job.id,
            "status": job.status,
            "total_rows": total,
            "imported": job.success_count,
            "skipped": job.skipped_count,
            "errors": job.failed_count,
            "percent_complete": percent,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_reasons": error_reasons
        })

    return result


@router.get("/candidates/bulk-import/{job_id}/progress")
def bulk_import_progress(job_id: str, db: Session = Depends(get_db)):
    """Get real-time progress of bulk import job.
    Returns: {job_id, status, total_rows, imported, skipped, errors, percent_complete}"""
    from app.models.bulk_engagement import BulkEngagementJob

    job = db.query(BulkEngagementJob).filter(BulkEngagementJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")

    total = job.total_count or 1
    processed = job.success_count + job.failed_count + job.skipped_count
    percent = int((processed / total) * 100) if total > 0 else 0

    return {
        "job_id": job.id,
        "status": job.status,
        "total_rows": total,
        "imported": job.success_count,
        "skipped": job.skipped_count,
        "errors": job.failed_count,
        "processed": processed,
        "percent_complete": percent
    }


@router.post("/candidates/bulk-update", dependencies=[Depends(require_permission("candidate.edit"))])
async def bulk_update(file: UploadFile, db: Session = Depends(get_db), current_user: Users = Depends(get_current_hr_or_admin)):
    """Bulk update existing candidates with job_title and/or location.

    Matches by email. Only updates if email is found.

    Required columns: email, (job_title OR location - at least one)

    CSV columns (use any matching alias):
    - email: email, email_address, candidate_email, applicant_email
    - job_title: job_title, job title, position, desired_role, applied_for
    - location: location, city, current_location, based_in

    Returns: {updated: count, not_found: count, errors: []}
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv file.")

    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    tenant_id = resolve_default_tenant_id(db)

    try:
        result = update_candidates_from_csv(db, raw, tenant_id)
        return {
            "updated": result.get("updated", 0),
            "not_found": result.get("not_found", 0),
            "errors": result.get("errors", []),
            "message": f"Updated {result.get('updated', 0)} candidates"
        }
    except CsvMissingRequiredColumn as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CsvTooLarge as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[BulkUpdate] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
