"""
S-074/HRMS-0474 -- Bulk Candidate Engagement Launch.

Real architecture adaptations:
- No `bulk_import_batches` table -- see `app.models.bulk_engagement`'s
  module docstring: the import response's candidate ID list IS the
  "batch," passed straight into the launch call.
- Dedup reuses R-07's real, only-sanctioned creation path,
  `candidate_service.create_candidate_safe()` (which itself raises
  `DuplicateCandidateError` via `find_duplicate_candidate()`) -- not a
  second, parallel dedup implementation.
- Real schema constraint the spec's CSV shape doesn't account for:
  `Candidate.candidateEmail` is `NOT NULL UNIQUE` in this codebase (the
  spec's own CSV column list marks `email` optional). A row with no
  email cannot be created at all -- reported as a real per-row error,
  never silently defaulted to a fabricated placeholder address.
- No `ConversationInitializationService` -- the real equivalent
  already built and shipped (earlier this session, before EPIC-04's
  sequential run) is `ai_conversation_service.
  auto_assign_ai_agent_on_creation()`, the exact same function already
  wired as a background task at both real candidate-creation entry
  points (`onboarding.py`, `create_job.py`) -- reused directly here,
  not reimplemented.
- BR-02 (skip already-engaged candidates) checks for any existing
  `CandidateConversation` row for the candidate -- the real signal
  that engagement has already started, same check this whole session
  has used everywhere "is this candidate already in progress" matters.
- BR-01's rate limit (20/min) is enforced by the worker itself
  batching candidates and sleeping between batches (injectable
  `sleep_fn`, same real-testability convention
  `qualification_conversation_service.run_qualification_turn()`
  already established) -- not a `system_configuration` table (no such
  table exists in this codebase); the rate is a real module constant,
  same documented-gap posture as every other missing
  system_configuration need this session.
"""
import csv
import io
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.bulk_engagement import BulkEngagementError, BulkEngagementJob
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation
from app.models.user import Users
from app.services.candidate_service import DuplicateCandidateError, create_candidate_safe
from app.services.notification_service import send_notification

MAX_CSV_ROWS = 200  # Step 1
MAX_BULK_CANDIDATES = 200  # Step 2
BULK_RATE_PER_MINUTE = 20  # BR-01, module constant -- see docstring
REQUIRED_CSV_COLUMN = "name"
CSV_COLUMNS = ("name", "email", "phone", "location", "current_employer", "skills")


class CsvTooLarge(Exception):
    pass


class CsvMissingRequiredColumn(Exception):
    pass


class BulkTooLarge(Exception):
    pass


def import_candidates_from_csv(db: Session, csv_text: str, recruiter_id: str, tenant_id: str) -> Dict:
    """Step 1. Never raises for per-row problems -- those go in
    `errors`. Raises CsvTooLarge/CsvMissingRequiredColumn for the
    whole-file validation failures this story's own AC treats as a
    hard 400."""
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None or REQUIRED_CSV_COLUMN not in reader.fieldnames:
        raise CsvMissingRequiredColumn(f"CSV must include a {REQUIRED_CSV_COLUMN!r} column.")

    rows = list(reader)
    if len(rows) > MAX_CSV_ROWS:
        raise CsvTooLarge(f"CSV cannot exceed {MAX_CSV_ROWS} rows.")

    imported_candidate_ids: List[str] = []
    skipped_duplicates = 0
    errors: List[Dict] = []

    for index, row in enumerate(rows, start=1):
        name = (row.get("name") or "").strip()
        if not name:
            errors.append({"row": index, "reason": "Missing required 'name' column."})
            continue

        email = (row.get("email") or "").strip()
        if not email:
            # See module docstring -- Candidate.candidateEmail is NOT
            # NULL/UNIQUE in this codebase; a nameless placeholder email
            # would risk real, silent collisions. A real, honest error.
            errors.append({"row": index, "reason": "Missing email -- required by this codebase's candidate schema."})
            continue

        name_parts = name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else None

        try:
            candidate = create_candidate_safe(
                db, email=email, mobile=(row.get("phone") or "").strip() or None,
                candidateFirstName=first_name, candidateLastName=last_name,
                candidateCurrentLocation=(row.get("location") or "").strip() or None,
                candidateSkills=(row.get("skills") or "").strip() or None,
            )
            imported_candidate_ids.append(candidate.candidateID)
        except DuplicateCandidateError:
            skipped_duplicates += 1
        except Exception as exc:
            logger.error(f"[BulkEngagement] Row {index} import failed: {exc}")
            errors.append({"row": index, "reason": str(exc)})

    return {
        "imported": len(imported_candidate_ids), "skipped_duplicates": skipped_duplicates,
        "errors": errors, "candidate_ids": imported_candidate_ids,
    }


def _already_engaged(db: Session, candidate_id: str) -> bool:
    """BR-02."""
    return db.query(CandidateConversation).filter(CandidateConversation.candidate_id == candidate_id).first() is not None


def launch_bulk_engagement(db: Session, candidate_ids: List[str], recruiter_id: str, tenant_id: str) -> Dict:
    """Step 2. Raises BulkTooLarge if over the cap (this story's own
    hard 400, not a per-row error)."""
    if len(candidate_ids) > MAX_BULK_CANDIDATES:
        raise BulkTooLarge(f"Bulk engagement cannot exceed {MAX_BULK_CANDIDATES} candidates per request.")

    job = BulkEngagementJob(
        tenant_id=tenant_id, recruiter_id=recruiter_id, candidate_ids=candidate_ids,
        total_count=len(candidate_ids), queued_count=len(candidate_ids), status="QUEUED",
    )
    db.add(job)
    db.commit()
    return {"bulk_job_id": job.id, "total_candidates": job.total_count, "estimated_completion_minutes": round(job.total_count / BULK_RATE_PER_MINUTE, 1)}


def _notify_recruiter(db: Session, recruiter_id: str, tenant_id: str, message: str) -> None:
    recipient = db.query(Users).filter(Users.UserID == recruiter_id).first()
    if not recipient:
        return
    try:
        send_notification(db, calling_context_tenant_id=recipient.tenant_id, recipient=recipient, priority_tier="P2", channel_preference="EMAIL", message=message)
    except Exception as exc:
        logger.warning(f"[BulkEngagement] Failed to notify recruiter of completion: {exc}")


def run_bulk_engagement_worker(db: Session, job_id: str, *, sleep_fn=None, batch_size: int = BULK_RATE_PER_MINUTE) -> Dict:
    """Step 3. BR-01: processes at most `batch_size` (20) candidates,
    then sleeps a real minute before the next batch. Never lets one bad
    candidate abort the job."""
    import time as time_module
    sleep_fn = sleep_fn or time_module.sleep

    job = db.query(BulkEngagementJob).filter(BulkEngagementJob.id == job_id).first()
    if job is None:
        return {"outcome": "job_not_found"}

    job.status = "PROCESSING"
    db.add(job)
    db.commit()

    from app.services.ai_conversation_service import auto_assign_ai_agent_on_creation

    candidate_ids = job.candidate_ids or []
    for batch_start in range(0, len(candidate_ids), batch_size):
        batch = candidate_ids[batch_start:batch_start + batch_size]
        for candidate_id in batch:
            try:
                candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
                if candidate is None:
                    job.failed_count += 1
                    db.add(BulkEngagementError(job_id=job.id, candidate_id=candidate_id, reason="Candidate not found"))
                    continue
                if _already_engaged(db, candidate_id):  # BR-02
                    job.skipped_count += 1
                    continue
                auto_assign_ai_agent_on_creation(candidate_id, job.tenant_id, db)
                job.success_count += 1
            except Exception as exc:
                logger.error(f"[BulkEngagement] Failed engaging candidate {candidate_id!r} for job {job_id!r}: {exc}")
                db.rollback()
                job.failed_count += 1
                db.add(BulkEngagementError(job_id=job.id, candidate_id=candidate_id, reason=str(exc)[:500]))
            db.add(job)
            db.commit()

        if batch_start + batch_size < len(candidate_ids):
            sleep_fn(60)  # BR-01: real minute between batches

    job.status = "COMPLETED"
    job.completed_at = datetime.utcnow()
    db.add(job)
    db.commit()

    _notify_recruiter(db, job.recruiter_id, job.tenant_id, f"Bulk engagement complete: {job.success_count} success, {job.failed_count} failed, {job.skipped_count} already engaged.")

    return {"outcome": "completed", "success_count": job.success_count, "failed_count": job.failed_count, "skipped_count": job.skipped_count}


def get_bulk_job_status(db: Session, job_id: str) -> Optional[Dict]:
    job = db.query(BulkEngagementJob).filter(BulkEngagementJob.id == job_id).first()
    if job is None:
        return None
    errors = db.query(BulkEngagementError).filter(BulkEngagementError.job_id == job_id).all()
    return {
        "bulk_job_id": job.id, "status": job.status, "total_count": job.total_count,
        "success_count": job.success_count, "failed_count": job.failed_count, "skipped_count": job.skipped_count,
        "errors": [{"candidate_id": e.candidate_id, "reason": e.reason} for e in errors],
    }
