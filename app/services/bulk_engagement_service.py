"""
S-074/HRMS-0474 -- Bulk Candidate Engagement Launch.

Real architecture adaptations:
- No `bulk_import_batches` table -- see `app.models.bulk_engagement`'s
  module docstring: the import response's candidate ID list IS the
  "batch," passed straight into the launch call.
- Dedup (merge) strategy: email OR phone identifies duplicates. Both are
  equal primary identifiers. If either email OR phone matches existing
  candidate, merge into that record (consolidate). Reuses R-07's real,
  only-sanctioned creation path, `candidate_service.create_candidate_safe()`
  (which itself raises `DuplicateCandidateError` via `find_duplicate_candidate()`).
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
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.bulk_engagement import BulkEngagementError, BulkEngagementJob
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation
from app.models.user import Users
from app.services.candidate_service import DuplicateCandidateError, create_candidate_safe
from app.services.ai_conversation_service import auto_assign_ai_agent_on_creation
from app.services.notification_service import send_notification

MAX_CSV_ROWS = 100000  # Step 1 - allow bulk imports of up to 100K candidates per file
MAX_BULK_CANDIDATES = 100000  # Step 2
BULK_RATE_PER_MINUTE = 20  # BR-01, module constant -- see docstring
REQUIRED_CSV_COLUMN = "name"
CSV_COLUMNS = ("name", "email", "phone", "location", "current_employer", "skills")

# Column name variations to support different CSV formats
NAME_COLUMN_ALIASES = ("name", "full_name", "candidate_name", "candidate", "applicant_name", "applicant")
EMAIL_COLUMN_ALIASES = ("email", "email_address", "candidate_email", "applicant_email", "e_mail")
PHONE_COLUMN_ALIASES = ("phone", "phone_number", "mobile", "mobile_number", "candidate_phone", "contact_number")
LOCATION_COLUMN_ALIASES = ("location", "city", "current_location", "candidate_location", "based_in", "preferred_location")
EMPLOYER_COLUMN_ALIASES = ("current_employer", "employer", "company", "current_company", "organization", "previous_company", "previous company")
SKILLS_COLUMN_ALIASES = ("skills", "skill", "candidate_skills", "technical_skills", "competencies")
JOB_TITLE_ALIASES = ("job_title", "job title", "position", "desired_role", "desired role", "applied_for", "applied for")
EXPERIENCE_ALIASES = ("experience", "years_of_experience", "years of experience", "yoe", "exp")
CURRENT_LOCATION_ALIASES = ("current_location", "current location", "location", "based_in", "based in", "city")
GENDER_ALIASES = ("gender", "sex")
DOB_ALIASES = ("date_of_birth", "date of birth", "dob", "birth_date", "birth date")
NATIONALITY_ALIASES = ("nationality", "country", "national_origin")
SOURCE_ALIASES = ("source", "referral_source", "sourcing_channel", "applied_via")
CURRENT_SALARY_ALIASES = ("current_salary", "current salary", "current_ctc", "current pay", "current compensation")
EXPECTED_SALARY_ALIASES = ("expected_salary", "expected salary", "expected_ctc", "salary_expectation", "salary expectation")


class CsvTooLarge(Exception):
    pass


class CsvMissingRequiredColumn(Exception):
    pass


class BulkTooLarge(Exception):
    pass


def _normalize_column_name(header: str) -> str:
    """Convert header to lowercase, remove spaces and underscores for matching."""
    return header.lower().strip().replace(" ", "").replace("_", "")


def _find_matching_column(headers: List[str], aliases: tuple) -> Optional[str]:
    """Find the first column that matches any of the given aliases."""
    normalized_headers = {_normalize_column_name(h): h for h in headers}
    normalized_aliases = {_normalize_column_name(alias) for alias in aliases}

    for header, original in normalized_headers.items():
        if header in normalized_aliases:
            return original
    return None


def _extract_value(row: Dict, column_aliases: tuple) -> Optional[str]:
    """Extract value from row using column aliases, returns None if not found."""
    for key in row.keys():
        if _normalize_column_name(key) in {_normalize_column_name(alias) for alias in column_aliases}:
            value = (row.get(key) or "").strip()
            return value if value else None
    return None


def _parse_experience(experience_str: Optional[str]) -> Optional[str]:
    """Parse experience in various formats: '6y6m', '6 years 6 months', '72', etc.
    Returns normalized format: '6 years 6 months' or the original string if unparseable."""
    if not experience_str:
        return None

    import re

    # Normalize the string
    exp = experience_str.strip().lower()
    if not exp:
        return None

    # Try to parse formats like "6y6m", "6y", "6 years 6 months", etc.
    # Pattern: optional number + 'y' or 'year(s)', optional number + 'm' or 'month(s)'
    years = 0
    months = 0

    # Match patterns like "6y", "6 years", "6years"
    year_match = re.search(r'(\d+)\s*(?:year|y)s?', exp)
    if year_match:
        years = int(year_match.group(1))

    # Match patterns like "6m", "6 months", "6months"
    month_match = re.search(r'(\d+)\s*(?:month|m)s?', exp)
    if month_match:
        months = int(month_match.group(1))

    # If we parsed years or months, return formatted string
    if years > 0 or months > 0:
        parts = []
        if years > 0:
            parts.append(f"{years} year{'s' if years != 1 else ''}")
        if months > 0:
            parts.append(f"{months} month{'s' if months != 1 else ''}")
        return " ".join(parts)

    # If no parse match, return original (might be "5", "10", etc.)
    return experience_str


def _parse_date(date_str: Optional[str]) -> Optional:
    """Parse date strings in various formats: YYYY-MM-DD, DD/MM/YYYY, MM-DD-YYYY, etc.
    Returns Python date object or None if unparseable."""
    if not date_str:
        return None

    from datetime import datetime
    import re

    date_str = date_str.strip()
    if not date_str:
        return None

    # Try common date formats
    formats = [
        "%Y-%m-%d",      # 2000-01-15
        "%d-%m-%Y",      # 15-01-2000
        "%m-%d-%Y",      # 01-15-2000
        "%Y/%m/%d",      # 2000/01/15
        "%d/%m/%Y",      # 15/01/2000
        "%m/%d/%Y",      # 01/15/2000
        "%Y.%m.%d",      # 2000.01.15
        "%d.%m.%Y",      # 15.01.2000
        "%m.%d.%Y",      # 01.15.2000
        "%d %b %Y",      # 15 Jan 2000
        "%d %B %Y",      # 15 January 2000
        "%b %d %Y",      # Jan 15 2000
        "%B %d %Y",      # January 15 2000
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except (ValueError, TypeError):
            continue

    # If nothing matched, return None (will be skipped in database)
    logger.warning(f"[BulkEngagement] Could not parse date: {date_str}")
    return None


def _commit_with_retry(db: Session, max_retries: int = 3) -> None:
    """Commit database changes with automatic retry on lock."""
    import time
    wait_time = 0.05

    for attempt in range(max_retries):
        try:
            db.commit()
            return
        except Exception as e:
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                time.sleep(wait_time)
                wait_time *= 2
                logger.warning(f"[BulkImport] DB locked on commit (attempt {attempt + 1}/{max_retries}), retrying...")
                continue
            raise


def _update_duplicate_candidate(existing_candidate: Candidate, row: Dict) -> None:
    """Update an existing duplicate candidate with new data from CSV row.
    Overwrites phone and job_title (primary identifiers for dedup).
    Updates location and skills only if not already set."""
    updated_fields = []

    # ALWAYS update phone (primary dedup identifier) - overwrite existing
    phone = _extract_value(row, PHONE_COLUMN_ALIASES)
    if phone:
        existing_candidate.candidateMobile = phone
        updated_fields.append("phone")

    # ALWAYS update job_title (primary requirement field) - overwrite existing
    job_title = _extract_value(row, JOB_TITLE_ALIASES)
    if job_title:
        existing_candidate.candidateJobTitle = job_title
        updated_fields.append("job_title")

    # Update location if provided and candidate doesn't have one
    location = _extract_value(row, LOCATION_COLUMN_ALIASES)
    if location and not existing_candidate.candidateCurrentLocation:
        existing_candidate.candidateCurrentLocation = location
        updated_fields.append("location")

    # Update skills if provided and candidate doesn't have them
    skills = _extract_value(row, SKILLS_COLUMN_ALIASES)
    if skills and not existing_candidate.candidateSkills:
        existing_candidate.candidateSkills = skills
        updated_fields.append("skills")

    if updated_fields:
        logger.info(f"[BulkImport] Updated duplicate candidate {existing_candidate.candidateID}: {', '.join(updated_fields)}")


def import_candidates_from_csv(db: Session, csv_text: str, recruiter_id: str, tenant_id: str, job_id: str = None) -> Dict:
    """Step 1. Never raises for per-row problems -- those go in
    `errors`. Raises CsvTooLarge/CsvMissingRequiredColumn for the
    whole-file validation failures this story's own AC treats as a
    hard 400."""

    # Auto-detect delimiter (comma, tab, semicolon, pipe)
    sample = csv_text[:1024]  # First 1KB for sniffing
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',\t;|')
    except csv.Error:
        dialect = csv.excel  # Fallback to comma-separated

    reader = csv.DictReader(io.StringIO(csv_text), dialect=dialect)
    if reader.fieldnames is None:
        raise CsvMissingRequiredColumn("CSV is empty or has no headers.")

    # Check if CSV has a name column (using aliases)
    name_column = _find_matching_column(reader.fieldnames, NAME_COLUMN_ALIASES)
    if not name_column:
        raise CsvMissingRequiredColumn(
            f"CSV must include a name column (e.g., 'name', 'full_name', 'candidate_name', etc.)"
        )

    rows = list(reader)
    if len(rows) > MAX_CSV_ROWS:
        raise CsvTooLarge(f"CSV cannot exceed {MAX_CSV_ROWS} rows.")

    imported_candidate_ids: List[str] = []  # Only candidates that have been COMMITTED to database
    pending_candidate_ids: List[str] = []   # Candidates in current batch waiting to commit
    skipped_duplicates = 0
    errors: List[Dict] = []

    # Adaptive batching: start with 100, fall back to 50 if database gets overwhelmed
    batch_size = 100
    failed_commits = 0

    for index, row in enumerate(rows, start=1):
        email = _extract_value(row, EMAIL_COLUMN_ALIASES)
        if not email:
            # See module docstring -- Candidate.candidateEmail is NOT
            # NULL/UNIQUE in this codebase; a nameless placeholder email
            # would risk real, silent collisions. A real, honest error.
            errors.append({"row": index, "reason": "Missing email -- required by this codebase's candidate schema."})
            continue

        phone = _extract_value(row, PHONE_COLUMN_ALIASES)
        if not phone:
            errors.append({"row": index, "reason": "Missing required phone number (phone, phone_number, mobile, contact_number, etc.)."})
            continue

        job_title = _extract_value(row, JOB_TITLE_ALIASES)
        if not job_title:
            errors.append({"row": index, "reason": "Missing required job title (job_title, position, desired_role, applied_for, etc.)."})
            continue

        location = _extract_value(row, LOCATION_COLUMN_ALIASES)
        if not location:
            errors.append({"row": index, "reason": "Missing required location (location, city, current_location, based_in, etc.)."})
            continue

        # Support both "Full Name" column and separate "First Name"/"Last Name" columns
        first_name = _extract_value(row, ("first_name", "firstname", "first name", "given_name", "given name"))
        last_name = _extract_value(row, ("last_name", "lastname", "last name", "family_name", "family name", "surname"))

        if first_name and last_name:
            # Both first and last names provided separately
            pass
        else:
            # Try to extract from combined "name" column
            name = _extract_value(row, NAME_COLUMN_ALIASES)
            if not name:
                errors.append({"row": index, "reason": "Missing required name field (either 'Name' or separate 'First Name'/'Last Name' columns)."})
                continue
            name_parts = name.split(" ", 1)
            first_name = first_name or name_parts[0]
            last_name = last_name or (name_parts[1] if len(name_parts) > 1 else None)

        try:
            # Extract all optional fields (map to actual Candidate model field names)
            experience_raw = _extract_value(row, EXPERIENCE_ALIASES)
            dob_raw = _extract_value(row, DOB_ALIASES)
            candidate_data = {
                "email": email,
                "mobile": phone,
                "candidateFirstName": first_name,
                "candidateLastName": last_name,
                "candidateCurrentLocation": location,
                "candidateJobTitle": job_title,
                "candidateSkills": _extract_value(row, SKILLS_COLUMN_ALIASES),
                "candidateExperience": _parse_experience(experience_raw),
                "candidateGender": _extract_value(row, GENDER_ALIASES),
                "candidateDateOfBirth": _parse_date(dob_raw),
                "candidateSource": _extract_value(row, SOURCE_ALIASES),
                "candidateCurrentSalary": _extract_value(row, CURRENT_SALARY_ALIASES),
                "candidateExpectedSalary": _extract_value(row, EXPECTED_SALARY_ALIASES),
            }
            # Remove None values to avoid overwriting existing defaults
            candidate_data = {k: v for k, v in candidate_data.items() if v is not None}

            candidate = create_candidate_safe(db, **candidate_data)
            db.flush()  # Flush to get the candidateID before full commit
            pending_candidate_ids.append(candidate.candidateID)  # Add to PENDING batch

            # Auto-assign to Thunder (AI recruiter) immediately after creation
            # This ensures candidates are picked up for autonomous processing
            try:
                auto_assign_ai_agent_on_creation(candidate.candidateID, tenant_id, db)
            except Exception as e:
                logger.warning(f"[BulkImport] Failed to assign Thunder to candidate {candidate.candidateID}: {e}")

            # Adaptive batching: commit every N candidates (start with 100, fallback to 50 if overwhelmed)
            if len(pending_candidate_ids) >= batch_size:
                retry_count = 0
                max_retries = 3

                while retry_count < max_retries:
                    try:
                        db.commit()
                        failed_commits = 0  # Reset counter on success
                        # Move all pending candidates to committed list AFTER successful commit
                        imported_candidate_ids.extend(pending_candidate_ids)
                        pending_candidate_ids.clear()
                        logger.info(f"[BulkEngagement] Batch commit successful: {len(imported_candidate_ids)}/{len(rows)} candidates")

                        # Update job progress if job_id provided
                        if job_id:
                            try:
                                job_record = db.query(BulkEngagementJob).filter(BulkEngagementJob.id == job_id).first()
                                if job_record:
                                    job_record.success_count = len(imported_candidate_ids)
                                    job_record.skipped_count = skipped_duplicates
                                    job_record.failed_count = len(errors)
                                    db.commit()
                                    # Check if job has been cancelled - stop importing if so
                                    if job_record.status == "CANCELLED":
                                        logger.info(f"[BulkImport] Job {job_id} was cancelled - stopping import")
                                        return {"imported": len(imported_candidate_ids), "skipped_duplicates": skipped_duplicates, "errors": errors, "candidate_ids": imported_candidate_ids}
                            except Exception as e:
                                logger.warning(f"[BulkEngagement] Failed to update job progress: {e}")
                        break
                    except Exception as e:
                        retry_count += 1
                        failed_commits += 1
                        error_msg = str(e).lower()

                        # If database is locked, try with smaller batch size
                        if "database is locked" in error_msg and batch_size > 50:
                            batch_size = 50  # Fall back to smaller batch size
                            logger.warning(f"[BulkEngagement] Database overwhelmed, reducing batch size to 50")
                            db.rollback()
                            pending_candidate_ids.clear()  # Clear pending on rollback
                        elif retry_count < max_retries:
                            db.rollback()
                            import time
                            wait_time = 0.5 * retry_count  # Linear backoff: 0.5s, 1s, 1.5s
                            time.sleep(wait_time)
                            logger.warning(f"[BulkEngagement] Batch commit retry {retry_count}/{max_retries} after {wait_time}s")
                        else:
                            db.rollback()
                            logger.error(f"[BulkEngagement] Batch commit FAILED after {max_retries} retries: {e}")
                            # Clear pending on final failure
                            pending_candidate_ids.clear()
                            break

        except DuplicateCandidateError as dup_err:
            # Update existing duplicate candidate with new data from CSV
            try:
                _update_duplicate_candidate(dup_err.existing, row)
                db.commit()
                logger.info(f"[BulkImport] Merged duplicate candidate (matched on {dup_err.matched_on}): {dup_err.existing.candidateID}")
            except Exception as e:
                logger.warning(f"[BulkImport] Failed to update duplicate candidate: {e}")
                db.rollback()
            skipped_duplicates += 1
        except Exception as exc:
            logger.error(f"[BulkEngagement] Row {index} import failed: {exc}", exc_info=True)
            errors.append({"row": index, "reason": str(exc)})

    # Final commit for any remaining candidates
    if pending_candidate_ids or imported_candidate_ids:
        retry_count = 0
        max_retries = 3
        while retry_count < max_retries:
            try:
                db.commit()
                # Move pending to committed after successful final commit
                imported_candidate_ids.extend(pending_candidate_ids)
                pending_candidate_ids.clear()
                logger.info(f"[BulkEngagement] Import completed: {len(imported_candidate_ids)} candidates imported, {skipped_duplicates} duplicates skipped, {len(errors)} errors")
                # Update job progress for final batch
                if job_id:
                    try:
                        job_record = db.query(BulkEngagementJob).filter(BulkEngagementJob.id == job_id).first()
                        if job_record:
                            job_record.success_count = len(imported_candidate_ids)
                            job_record.skipped_count = skipped_duplicates
                            job_record.failed_count = len(errors)
                            # Only mark as COMPLETED if not already cancelled
                            if job_record.status != "CANCELLED":
                                job_record.status = "COMPLETED"
                            db.commit()
                    except Exception as e:
                        logger.warning(f"[BulkEngagement] Failed to update job progress (final): {e}")
                break
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    db.rollback()
                    import time
                    time.sleep(0.5)
                    logger.warning(f"[BulkEngagement] Final commit retry {retry_count}/{max_retries}")
                else:
                    db.rollback()
                    logger.error(f"[BulkEngagement] Final commit failed after {max_retries} retries: {e}")
                    # Clear pending on final failure
                    pending_candidate_ids.clear()

    return {
        "imported": len(imported_candidate_ids), "skipped_duplicates": skipped_duplicates,
        "errors": errors, "candidate_ids": imported_candidate_ids,
    }


def update_candidates_from_csv(db: Session, csv_text: str, tenant_id: str) -> Dict:
    """Bulk update existing candidates with job_title and location from CSV.
    Matches by email. Only updates if email found.

    Required columns: email, job_title, location
    Returns: {updated: count, not_found: count, errors: []}
    """
    # Auto-detect delimiter
    sample = csv_text[:1024]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',\t;|')
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(csv_text), dialect=dialect)
    if reader.fieldnames is None:
        raise CsvMissingRequiredColumn("CSV is empty or has no headers.")

    # Find email column
    email_column = _find_matching_column(reader.fieldnames, EMAIL_COLUMN_ALIASES)
    if not email_column:
        raise CsvMissingRequiredColumn("CSV must include an email column (e.g., 'email', 'email_address', etc.)")

    rows = list(reader)
    if len(rows) > MAX_CSV_ROWS:
        raise CsvTooLarge(f"CSV cannot exceed {MAX_CSV_ROWS} rows.")

    updated_count = 0
    not_found_count = 0
    errors: List[Dict] = []

    for index, row in enumerate(rows, start=1):
        email = _extract_value(row, EMAIL_COLUMN_ALIASES)
        if not email:
            errors.append({"row": index, "reason": "Missing email."})
            not_found_count += 1
            continue

        job_title = _extract_value(row, JOB_TITLE_ALIASES)
        location = _extract_value(row, LOCATION_COLUMN_ALIASES)

        if not job_title and not location:
            errors.append({"row": index, "reason": "Must provide either job_title or location to update."})
            not_found_count += 1
            continue

        # Find candidate by email
        candidate = db.query(Candidate).filter(Candidate.candidateEmail == email).first()
        if not candidate:
            errors.append({"row": index, "reason": f"Candidate with email '{email}' not found."})
            not_found_count += 1
            continue

        # Update fields
        if job_title:
            candidate.candidateJobTitle = job_title
        if location:
            candidate.candidateCurrentLocation = location

        try:
            db.flush()
            updated_count += 1
        except Exception as e:
            db.rollback()
            errors.append({"row": index, "reason": f"Failed to update: {str(e)}"})
            not_found_count += 1

    # Final commit
    if updated_count > 0:
        try:
            db.commit()
            logger.info(f"[BulkUpdate] Completed: {updated_count} updated, {not_found_count} not found, {len(errors)} errors")
        except Exception as e:
            db.rollback()
            logger.error(f"[BulkUpdate] Final commit failed: {e}")
            errors.append({"row": 0, "reason": f"Final commit failed: {str(e)}"})

    return {
        "updated": updated_count,
        "not_found": not_found_count,
        "errors": errors,
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
