"""Job Creation Flash Handler - Queue-driven job creation with atomic validation."""
from app.core.tenant_context import sole_tenant_id
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError
from app.models.user import JOB_WORK_LOCATIONS, Jobs, Users
from datetime import datetime, timedelta
from uuid import uuid4
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class JobCreationFlashHandler:
    """Handles job_created_flash queue messages with atomic validation."""

    # Job creation SLA (gate rule: every queue handler declares its timeout)
    TIMEOUT_SECONDS = 45

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process: Create job from queue payload

        Args:
            message: ChannelQueueItem with type='job_created_flash'
            db: SQLAlchemy session

        Returns:
            {
                'status': 'success',
                'job_id': str,
                'created_at': ISO timestamp,
                'job_status': 'active'|'pending_approval'
            }

        Raises:
            ValueError: Invalid payload (400 client error)
            RuntimeError: DB write failures (500 internal, retry eligible)
        """
        try:
            payload = message.payload or {}

            # PHASE 1: VALIDATION (BEFORE any DB writes)
            required_fields = ['job_id', 'job_title', 'job_location']
            for field in required_fields:
                if not payload.get(field):
                    raise ValueError(f"Missing required field: {field}")

            job_id = payload.get('job_id')

            # ARCHITECT FIX #5: Check for idempotency using both job_id AND idempotency_key
            # (Deduplication prevents duplicate jobs if message is retried after handler crashes)
            idempotency_key = message.idempotency_key or f"job_created_flash:{job_id}"

            # Query: Is there already a job with this ID (deduplication by job_id)
            existing_job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
            if existing_job:
                logger.info(
                    f"[JobCreationFlash] Job {job_id} already exists (idempotent retry via "
                    f"idempotency_key={idempotency_key}), returning existing"
                )
                return {
                    'status': 'success',
                    'job_id': job_id,
                    'created_at': existing_job.jobCreatedAt.isoformat(),
                    'job_status': existing_job.jobStatus,
                    'job_title': existing_job.jobTitle,
                    'idempotent': True
                }
            job_title = payload.get('job_title')
            job_location = payload.get('job_location')

            # Validate field types and lengths
            if not isinstance(job_title, str) or len(job_title) > 200:
                raise ValueError(f"job_title must be string < 200 chars")
            if not isinstance(job_location, str):
                raise ValueError(f"job_location must be string")

            # Validate FK constraints (if provided)
            hiring_manager_id = payload.get('hiring_manager_id')
            if hiring_manager_id:
                if not db.query(Users).filter(Users.UserID == hiring_manager_id).first():
                    raise ValueError(f"hiring_manager_id '{hiring_manager_id}' not found in Users")

            # create_job enqueues "business_unit_id"; older messages used "business_unit"
            business_unit_id = payload.get('business_unit_id') or payload.get('business_unit')
            if business_unit_id:
                # Verify business unit exists (FK constraint)
                from app.models.business_unit import BusinessUnit
                if not db.query(BusinessUnit).filter(BusinessUnit.id == business_unit_id).first():
                    raise ValueError(f"business_unit '{business_unit_id}' not found")

            # Jobs.salaryRange is free text ("140000 $/Year"), parsed back by the job edit form
            salary_range = payload.get('salary_range')
            if salary_range is not None:
                salary_range = str(salary_range).strip() or None
                if salary_range and len(salary_range) > 512:
                    raise ValueError("salary_range must be at most 512 characters")

            # Structured skills (SkillRequirement shape) drive candidate matching
            structured_skills = payload.get('structured_skills') or []
            if not isinstance(structured_skills, list):
                raise ValueError("structured_skills must be a list")
            for skill in structured_skills:
                if not isinstance(skill, dict) or not isinstance(skill.get('name'), str) or not skill['name'].strip():
                    raise ValueError(f"Each structured skill needs a name: {skill!r}")
            boolean_mode = (payload.get('job_skills_boolean_mode') or 'AND').upper()
            if boolean_mode not in ('AND', 'OR'):
                raise ValueError(f"job_skills_boolean_mode must be AND or OR, got {boolean_mode!r}")
            work_location = (payload.get('work_location') or 'REMOTE').upper()
            if work_location not in JOB_WORK_LOCATIONS:
                raise ValueError(f"work_location must be one of {JOB_WORK_LOCATIONS}, got {work_location!r}")
            min_experience_years = payload.get('min_experience_years')
            if min_experience_years is not None:
                try:
                    min_experience_years = float(min_experience_years)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"min_experience_years must be a number, got {min_experience_years!r}") from exc
                if min_experience_years < 0:
                    raise ValueError("min_experience_years cannot be negative")

            # PHASE 2: DB WRITE (After validation)
            try:
                # Build job object
                job = Jobs(
                    jobID=job_id,
                    jobTitle=job_title,
                    jobDescription=payload.get('job_description'),
                    jobSkills=payload.get('job_skills', ''),
                    jobExperience=payload.get('job_experience'),
                    jobLocation=job_location,
                    jobCreatedAt=datetime.utcnow(),
                    companyType=payload.get('company_type'),
                    companyName=payload.get('company_name'),
                    contactPerson=payload.get('contact_person'),
                    # Approval flow is disabled: a missing status means active
                    jobStatus=payload.get('job_status') or 'active',
                    # The key is present with None when the form leaves it empty: one position
                    noOfPositions=payload.get('no_of_positions') or 1,
                    startDate=payload.get('start_date'),
                    endDate=payload.get('end_date'),
                    hiringManagerID=hiring_manager_id,
                    recuriterID=payload.get('recuriter_id') or payload.get('recruiter_id'),
                    business_unit_id=business_unit_id,
                    tenant_id=payload.get('tenant_id') or message.tenant_id or sole_tenant_id(db),
                    department_id=payload.get('department_id'),
                    salaryRange=salary_range,
                    client_id=payload.get('client_id'),
                    project_id=payload.get('project_id'),
                    billing_rate_usd_cents=payload.get('billing_rate_usd_cents'),
                    required_skills_canonical=structured_skills,
                    job_skills_boolean_mode=boolean_mode,
                    min_experience_years=min_experience_years,
                    work_location=work_location,
                )

                db.add(job)
                db.flush()  # Force to DB but don't commit yet

                # PHASE 3: NEIGHBOR MONITORING (Verify write succeeded)
                db.flush()
                persisted_job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
                if not persisted_job:
                    raise RuntimeError(f"Write validation failed: job not found after flush")

                db.commit()
                logger.info(f"[JobCreate] ✅ Created job {job_id}: {job_title}")

                from app.services.action_emails.jobs import notify_job_created

                notify_job_created(db, job, actor_id=payload.get('created_by_user_id'))

                # HANDLER LOGIC: Handle job-specific workflows (after persisted to DB)
                # These were moved from endpoint to handler to follow queue-driven architecture

                job_status = job.jobStatus

                if job_status == "active":
                    # Scan for ready candidates matching this job
                    try:
                        from app.services.ready_for_opportunity_service import scan_new_job_for_matches
                        scan_new_job_for_matches(db, job)
                        logger.info(f"[JobCreate] Scanned ready-for-opportunity candidates for {job_id}")
                    except Exception as scan_err:
                        logger.warning(f"[JobCreate] Ready-for-opportunity scan failed (non-blocking): {scan_err}")

                elif job_status == "pending_approval":
                    # Send approval notification
                    try:
                        from app.services.job_approval_workflow_service import handle_job_creation_approval_flow
                        created_by = payload.get('created_by_user_id')
                        approval_info = handle_job_creation_approval_flow(db, job, None, send_emails=True)
                        logger.info(f"[JobCreate] Job {job_id} pending approval. {approval_info.get('routing_reason', 'Routing to approver')}")
                    except Exception as approval_err:
                        logger.warning(f"[JobCreate] Approval flow failed (non-blocking): {approval_err}")

                # NOTE: flash_recruiter queue is handled by QueueProcessorService after SLM analysis
                # (Don't queue it here - that's orchestration, not handler's job)

                return {
                    'status': 'success',
                    'job_id': job_id,
                    'created_at': datetime.utcnow().isoformat(),
                    'job_status': job.jobStatus,
                    'job_title': job_title
                }

            except IntegrityError as e:
                db.rollback()
                logger.error(f"[JobCreationFlash] FK constraint violation for {job_id}: {e}", exc_info=True)
                raise RuntimeError(f"FK constraint: {str(e)}") from e

            except OperationalError as e:
                db.rollback()
                logger.error(f"[JobCreationFlash] DB operational error for {job_id}: {e}", exc_info=True)
                raise RuntimeError(f"DB unavailable: {str(e)}") from e

        except ValueError as ve:
            logger.error(f"[JobCreationFlash] Validation error: {ve}")
            raise  # NOT RETRYABLE - client error

        except RuntimeError as re:
            logger.error(f"[JobCreationFlash] Runtime error (retryable): {re}")
            raise  # RETRYABLE - infrastructure error

        except Exception as e:
            db.rollback()
            logger.error(f"[JobCreationFlash] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= JobCreationFlashHandler.MAX_RETRIES:
            logger.error(f"[JobCreationFlash] Max retries exceeded for {message.id}")
            return False

        if hasattr(message, 'next_retry_at') and message.next_retry_at:
            if datetime.utcnow() < message.next_retry_at:
                return False

        return True

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """
        Validate that job creation actually completed successfully.

        Runs BEFORE marking message as COMPLETED. Verifies:
        1. Job record exists in database
        2. Job title matches payload
        3. Job status is correct
        4. Record was created recently (not old duplicate)

        Args:
            message: Queue message with payload
            result: Result dict from process()
            db: Database session

        Raises:
            ValueError: Job not found (non-retryable)
            RuntimeError: Database validation error (retryable)
        """
        if not result or "job_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        job_id = result.get("job_id")
        payload = message.payload or {}

        try:
            # 1. VERIFY JOB EXISTS
            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found in database after creation")

            # 2. VERIFY JOB TITLE MATCHES
            expected_title = payload.get("job_title")
            if expected_title and job.jobTitle != expected_title:
                raise ValueError(
                    f"Title mismatch for {job_id}: expected '{expected_title}', got '{job.jobTitle}'"
                )

            # 3. VERIFY JOB STATUS
            # Same default as process(): a missing status means active
            expected_status = payload.get("job_status") or "active"
            if job.jobStatus != expected_status:
                raise ValueError(
                    f"Status mismatch for {job_id}: expected '{expected_status}', got '{job.jobStatus}'"
                )

            # 4. VERIFY FK CONSTRAINTS (NEW)
            if job.hiringManagerID:
                hiring_mgr = db.query(Users).filter(Users.UserID == job.hiringManagerID).first()
                if not hiring_mgr:
                    raise ValueError(
                        f"Hiring manager {job.hiringManagerID} not found (FK validation failed)"
                    )

            if job.business_unit_id:
                from app.models.business_unit import BusinessUnit
                bu = db.query(BusinessUnit).filter(BusinessUnit.id == job.business_unit_id).first()
                if not bu:
                    raise ValueError(
                        f"Business unit {job.business_unit_id} not found (FK validation failed)"
                    )

            # 5. VERIFY CREATION TIMESTAMP
            if not job.jobCreatedAt:
                raise ValueError(f"Job {job_id} has no createdAt timestamp")

            age_seconds = (datetime.utcnow() - job.jobCreatedAt).total_seconds()
            if age_seconds > 300:  # Created more than 5 minutes ago = likely not this operation
                logger.warning(f"Job {job_id} was created {age_seconds}s ago, not recent")

            logger.info(f"✅ Job creation validated: {job_id}, Title={job.jobTitle}, Status={job.jobStatus}")

        except (ValueError, AttributeError) as e:
            logger.error(f"[JobCreationFlash] NON-RETRYABLE validation error: {e}")
            raise ValueError(str(e)) from e

        except Exception as e:
            logger.error(f"[JobCreationFlash] RETRYABLE validation error: {e}", exc_info=True)
            raise RuntimeError(f"Database validation error: {str(e)}") from e

    @staticmethod
    def on_retry(message: Any, error: str, db: Session) -> None:
        """Schedule message for retry after failed attempt."""
        try:
            db.rollback()

            message.retry_count += 1
            message.error = error[:1000] if error else "Unknown error"
            message.next_retry_at = datetime.utcnow() + timedelta(
                minutes=JobCreationFlashHandler.RETRY_DELAY_MINUTES
            )

            db.commit()
            logger.info(
                f"[JobCreationFlash] Scheduled retry for {message.id}: "
                f"retry_count={message.retry_count}/{JobCreationFlashHandler.MAX_RETRIES}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[JobCreationFlash] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """
        Mark message as COMPLETED after validation passes.

        Calls validate() which verifies job was created successfully.
        Only marks COMPLETED if validation passes.
        """
        try:
            # Call validate() which follows base handler pattern
            JobCreationFlashHandler.validate(message, result, db)

            # ✅ VALIDATION PASSED - Mark as COMPLETED
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit COMPLETED status: {str(commit_err)}") from commit_err

            job_id = result.get("job_id", "unknown")
            logger.info(f"[JobCreationFlash] ✅ Message {message.id} marked COMPLETED (job {job_id})")

            return {
                'is_valid': True,
                'job_id': job_id,
                'message': 'Validation passed and message marked COMPLETED'
            }

        except ValueError as e:
            db.rollback()
            logger.error(f"[JobCreationFlash] ❌ NON-RETRYABLE validation failure: {e}")
            raise

        except RuntimeError as e:
            db.rollback()
            logger.error(f"[JobCreationFlash] ❌ RETRYABLE validation failure: {e}")
            raise

        except Exception as e:
            db.rollback()
            logger.error(f"[JobCreationFlash] ❌ Unexpected error during on_success: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error during on_success: {str(e)}") from e

    @staticmethod
    def on_failed(message: Any, final_error: str, db: Session) -> None:
        """Mark message as FAILED after all retries exhausted."""
        try:
            db.rollback()

            message.status = "FAILED"
            message.error = final_error[:1000] if final_error else "Unknown error"
            message.completed_at = datetime.utcnow()

            db.commit()
            logger.error(
                f"[JobCreationFlash] Message {message.id} FAILED after "
                f"{message.retry_count} retries: {final_error}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[JobCreationFlash] Failed to mark as FAILED: {e}", exc_info=True)
            raise
