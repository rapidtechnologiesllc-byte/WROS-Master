"""Async task for candidate creation from form submission.

Handles:
- Creating candidate record in database
- Extracting resume data if provided
- Thunder autonomous loop enrollment
- Email notifications
"""

import logging
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.db_utils import retry_on_db_lock

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.create_candidate_async")
@retry_on_db_lock(max_retries=3)
def create_candidate_async(
    self,
    email: str,
    first_name: str,
    last_name: str,
    mobile: str,
    gender: str,
    location: str,
    source: str = "form_submission",
    tenant_id: str = "1",
    user_id: str = None,
    resume_path: str = None,
    additional_data: dict = None,
):
    """
    Create candidate asynchronously via Celery task.

    Args:
        email: Candidate email address
        first_name: Candidate first name
        last_name: Candidate last name
        mobile: Candidate phone number
        gender: Candidate gender
        location: Candidate current location
        source: How candidate was acquired (default: form_submission)
        tenant_id: Organization tenant ID
        user_id: Creating user ID (if recruiter submitted)
        resume_path: Path to resume file (if uploaded)
        additional_data: Extra fields (education, experience, etc.)

    Returns:
        dict: {candidate_id, message, status}
    """
    from app.models import Candidate
    from sqlalchemy import func
    from sqlalchemy.exc import IntegrityError

    task_id = str(self.request.id)
    db = SessionLocal()

    try:
        logger.info(
            f"[TASK {task_id}] Starting candidate creation: {first_name} {last_name} ({email})"
        )

        # Validate: check for duplicate by email or phone before creating
        existing_candidate = db.query(Candidate).filter(
            (func.lower(Candidate.candidateEmail) == email.lower())
            | (Candidate.candidateMobile == mobile)
        ).first()

        if existing_candidate:
            logger.warning(
                f"[TASK {task_id}] Duplicate candidate: email={email}, phone={mobile}"
            )
            return {
                "candidate_id": existing_candidate.candidateID,
                "message": "Candidate already exists",
                "status": "duplicate",
                "is_new": False,
            }

        # After validation, create new candidate (existing_candidate is None)
        candidate = Candidate(
            candidateEmail=email,
            candidateFirstName=first_name,
            candidateLastName=last_name,
            candidateMobile=mobile,
            candidateGender=gender,
            candidate_current_location=location,
            candidate_source=source,
            tenant_id=tenant_id,
            created_by=user_id,
        )

        # Add and commit (now we know no duplicate exists)
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        candidate_id = candidate.candidateID
        logger.info(f"[TASK {task_id}] Candidate created: {candidate_id}")

        return {
            "candidate_id": candidate_id,
            "message": f"Candidate {first_name} {last_name} created successfully",
            "status": "completed",
            "is_new": True,
        }

    except IntegrityError as e:
        db.rollback()
        logger.error(f"[TASK {task_id}] Integrity error: {e}", exc_info=True)
        raise

    except Exception as e:
        db.rollback()
        logger.error(
            f"[TASK {task_id}] Failed to create candidate: {e}", exc_info=True
        )
        raise

    finally:
        db.close()
