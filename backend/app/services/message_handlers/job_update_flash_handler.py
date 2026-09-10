"""Job Update Flash Handler - Queue-driven job updates with read-then-write pattern."""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError
from app.models.user import Jobs, Users
from datetime import datetime

logger = logging.getLogger(__name__)


class JobUpdateFlashHandler:
    """Handles job_updated_flash queue messages with read-then-write pattern."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process: Update existing job from queue payload

        Args:
            message: ChannelQueueItem with type='job_updated_flash'
            db: SQLAlchemy session

        Returns:
            {
                'status': 'success',
                'job_id': str,
                'updated_fields': ['jobTitle', 'jobSkills', ...],
                'previous_values': {...},
                'new_values': {...}
            }

        Raises:
            ValueError: Invalid payload or FK constraint (400, NOT retryable)
            RuntimeError: Job not found or DB write failure (500, retryable)

        Payload Schema:
        {
            'job_id': str (required, must exist),
            'job_title': str|null,
            'job_description': str|null,
            'job_skills': str|null,
            'job_location': str|null,
            'job_status': str|null,
            'hiring_manager_id': str|null (FK validation),
            'business_unit_id': str|null (FK validation),
            ... (other optional fields)
        }
        """
        try:
            payload = message.payload or {}

            # PHASE 1: VALIDATION
            job_id = payload.get('job_id')
            if not job_id:
                raise ValueError("Missing required field: job_id")

            # PHASE 2: READ (Query existing job)
            try:
                job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
                if not job:
                    raise ValueError(f"Job not found: {job_id}")

            except Exception as e:
                raise RuntimeError(f"Failed to query job {job_id}: {str(e)}") from e

            # PHASE 3: VALIDATION (FK constraints for provided updates)
            hiring_manager_id = payload.get('hiring_manager_id')
            if hiring_manager_id is not None:
                if not db.query(Users).filter(Users.UserID == hiring_manager_id).first():
                    raise ValueError(f"hiring_manager_id '{hiring_manager_id}' not found")

            business_unit_id = payload.get('business_unit_id')
            if business_unit_id is not None:
                from app.models.user import BusinessUnit
                if not db.query(BusinessUnit).filter(BusinessUnit.id == business_unit_id).first():
                    raise ValueError(f"business_unit_id '{business_unit_id}' not found")

            # PHASE 4: TRACK CHANGES (Build change map)
            change_map = {}
            previous_values = {}
            new_values = {}

            # Apply updates
            fields_to_update = {
                'job_title': 'jobTitle',
                'job_description': 'jobDescription',
                'job_skills': 'jobSkills',
                'job_experience': 'jobExperience',
                'job_location': 'jobLocation',
                'company_type': 'companyType',
                'company_name': 'companyName',
                'contact_person': 'contactPerson',
                'job_status': 'jobStatus',
                'no_of_positions': 'noOfPositions',
                'start_date': 'startDate',
                'end_date': 'endDate',
                'hiring_manager_id': 'hiringManagerID',
                'recruiter_id': 'recuriterID',
                'business_unit_id': 'business_unit_id',
                'department_id': 'department_id',
                'salary_range': 'salaryRange'
            }

            for payload_key, model_key in fields_to_update.items():
                if payload_key in payload and payload[payload_key] is not None:
                    old_value = getattr(job, model_key, None)
                    new_value = payload[payload_key]

                    if old_value != new_value:
                        change_map[model_key] = new_value
                        previous_values[model_key] = old_value
                        new_values[model_key] = new_value
                        setattr(job, model_key, new_value)

            if not change_map:
                logger.info(f"[JobUpdateFlash] No changes for job {job_id}")
                return {
                    'status': 'success',
                    'job_id': job_id,
                    'updated_fields': [],
                    'previous_values': {},
                    'new_values': {},
                    'message': 'No changes detected'
                }

            # PHASE 5: DB WRITE (Atomic commit)
            try:
                db.flush()

                # PHASE 6: NEIGHBOR MONITORING (Verify persistence)
                persisted_job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
                if not persisted_job:
                    raise RuntimeError(f"Write validation failed: job not found after update")

                # Verify all changes persisted
                for model_key, new_value in change_map.items():
                    persisted_value = getattr(persisted_job, model_key, None)
                    if persisted_value != new_value:
                        raise RuntimeError(
                            f"Write validation failed: {model_key} not persisted "
                            f"(expected={new_value}, got={persisted_value})"
                        )

                db.commit()
                logger.info(f"[JobUpdateFlash] ✅ Updated job {job_id}: {list(change_map.keys())}")

                return {
                    'status': 'success',
                    'job_id': job_id,
                    'updated_fields': list(change_map.keys()),
                    'previous_values': previous_values,
                    'new_values': new_values
                }

            except IntegrityError as e:
                db.rollback()
                logger.error(f"[JobUpdateFlash] FK constraint violation for {job_id}: {e}", exc_info=True)
                raise RuntimeError(f"FK constraint: {str(e)}") from e

            except OperationalError as e:
                db.rollback()
                logger.error(f"[JobUpdateFlash] DB operational error for {job_id}: {e}", exc_info=True)
                raise RuntimeError(f"DB unavailable: {str(e)}") from e

        except ValueError as ve:
            logger.error(f"[JobUpdateFlash] Validation error: {ve}")
            raise  # NOT RETRYABLE

        except RuntimeError as re:
            logger.error(f"[JobUpdateFlash] Runtime error (retryable): {re}")
            raise  # RETRYABLE

        except Exception as e:
            db.rollback()
            logger.error(f"[JobUpdateFlash] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e
