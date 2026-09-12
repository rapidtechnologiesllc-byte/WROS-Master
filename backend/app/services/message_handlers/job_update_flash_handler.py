"""Job Update Flash Handler - Queue-driven job updates with read-then-write pattern."""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError
from app.models.user import Jobs, Users
from datetime import datetime, timedelta
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class JobUpdateFlashHandler:
    """Handles job_updated_flash queue messages with read-then-write pattern."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=15)
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

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= JobUpdateFlashHandler.MAX_RETRIES:
            logger.error(f"[JobUpdateFlash] Max retries exceeded for {message.id}")
            return False

        if hasattr(message, 'next_retry_at') and message.next_retry_at:
            if datetime.utcnow() < message.next_retry_at:
                return False

        return True

    @staticmethod
    def on_retry(message: Any, error: str, db: Session) -> None:
        """Schedule message for retry after failed attempt."""
        try:
            db.rollback()

            message.retry_count += 1
            message.error = error[:1000] if error else "Unknown error"
            message.next_retry_at = datetime.utcnow() + timedelta(
                minutes=JobUpdateFlashHandler.RETRY_DELAY_MINUTES
            )

            db.commit()
            logger.info(
                f"[JobUpdateFlash] Scheduled retry for {message.id}: "
                f"retry_count={message.retry_count}/{JobUpdateFlashHandler.MAX_RETRIES}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[JobUpdateFlash] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Handle successful message processing with validation before marking COMPLETED."""
        try:
            # ===== VALIDATION STEP 1: Check result structure =====
            if not isinstance(result, dict):
                raise ValueError(f"Handler returned invalid type: {type(result)}")

            required_fields = ['job_id', 'status']
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Handler result missing required field: {field}")
                if not result[field]:
                    raise ValueError(f"Handler result has empty field: {field}")

            job_id = result['job_id']
            logger.info(f"[Handler] ✅ Step 1: Result structure valid (job_id={job_id})")

            # ===== VALIDATION STEP 2: Database verification =====
            # Query to verify job actually exists in database
            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()

            if not job:
                raise RuntimeError(
                    f"Record {job_id} not found in database after handler completed. "
                    f"Handler returned ID but record was not persisted."
                )

            logger.info(f"[Handler] ✅ Step 2: Database verification passed, job exists")

            # ===== VALIDATION STEP 3: Related records consistency =====
            # Verify updates persisted (spot-check first updated field)
            updated_fields = result.get('updated_fields', [])
            if updated_fields:
                new_values = result.get('new_values', {})
                first_field = updated_fields[0]
                if first_field in new_values:
                    expected_value = new_values[first_field]
                    persisted_value = getattr(job, first_field, None)
                    if persisted_value != expected_value:
                        raise RuntimeError(
                            f"Update validation failed: {first_field} not persisted correctly "
                            f"(expected={expected_value}, got={persisted_value})"
                        )

            logger.info(f"[Handler] ✅ Step 3: Related records valid, updates persisted")

            # ===== FINAL: Mark COMPLETED after all validations pass =====
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit success status: {str(commit_err)}") from commit_err

            logger.info(f"[Handler] ✅✅✅ ALL VALIDATIONS PASSED - Message marked COMPLETED")

        except ValueError as e:
            # Non-retryable error
            db.rollback()
            logger.error(f"[Handler] ❌ NON-RETRYABLE validation failure: {e}")
            raise

        except RuntimeError as e:
            # Retryable error
            db.rollback()
            logger.error(f"[Handler] ❌ RETRYABLE validation failure: {e}")
            raise

        except Exception as e:
            # Unexpected error
            db.rollback()
            logger.error(f"[Handler] ❌ Unexpected validation error: {e}", exc_info=True)
            raise RuntimeError(f"Validation error: {str(e)}") from e

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
                f"[JobUpdateFlash] Message {message.id} FAILED after "
                f"{message.retry_count} retries: {final_error}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[JobUpdateFlash] Failed to mark as FAILED: {e}", exc_info=True)
            raise
