"""Job Creation Flash Handler - Queue-driven job creation with atomic validation."""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError
from app.models.user import Jobs, Users
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger(__name__)


class JobCreationFlashHandler:
    """Handles job_created_flash queue messages with atomic validation."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
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

            # ARCHITECT FIX: Check for idempotency (duplicate job_id means retry)
            existing_job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
            if existing_job:
                logger.info(f"[JobCreationFlash] Job {job_id} already exists (idempotent retry), returning existing")
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

            business_unit_id = payload.get('business_unit')
            if business_unit_id:
                # Verify business unit exists (FK constraint)
                from app.models.user import BusinessUnit
                if not db.query(BusinessUnit).filter(BusinessUnit.id == business_unit_id).first():
                    raise ValueError(f"business_unit '{business_unit_id}' not found")

            salary_range = payload.get('salary_range')
            if salary_range is not None:
                try:
                    float(salary_range)
                except (ValueError, TypeError):
                    raise ValueError(f"salary_range must be numeric or null")

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
                    jobStatus=payload.get('job_status', 'pending_approval'),
                    noOfPositions=payload.get('no_of_positions', 1),
                    startDate=payload.get('start_date'),
                    endDate=payload.get('end_date'),
                    hiringManagerID=hiring_manager_id,
                    recuriterID=payload.get('recruiter_id'),
                    business_unit_id=business_unit_id,
                    department_id=payload.get('department_id'),
                    salaryRange=salary_range
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

                # QUEUE 2: Flash_Recruiter handler will find candidates & queue outreach
                from app.services.message_queue_service import MessageQueueService
                recruiter_msg_id = MessageQueueService.enqueue(
                    task_name='flash_recruiter',
                    task_id=job_id,
                    data={
                        'job_id': job_id,
                        'job_title': job_title,
                        'job_skills': message.payload.get('job_skills', ''),
                        'slm_analysis': message.payload.get('slm_analysis')
                    }
                )
                logger.info(f"[JobCreate] Queued flash_recruiter for job {job_id}: message_id={recruiter_msg_id}")

                return {
                    'status': 'success',
                    'job_id': job_id,
                    'created_at': datetime.utcnow().isoformat(),
                    'job_status': job.jobStatus,
                    'job_title': job_title,
                    'recruiter_queue_id': recruiter_msg_id
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
