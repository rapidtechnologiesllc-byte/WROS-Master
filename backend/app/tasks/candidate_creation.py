"""Async task for candidate creation from form submission.

Handles:
- Creating candidate record in database
- Creating related records (CandidateStatus, CandidateInfoForm)
- Processing education/experience records
- Thunder autonomous loop enrollment
- Email notifications
"""

import logging
import re
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
    Create candidate asynchronously via Celery task (shared with sync path).

    CRITICAL: This must create same related records as create_candidate_safe()
    to maintain parity between async and sync paths.

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
        dict: {candidate_id, message, status, is_new}
    """
    from app.models.candidate import Candidate, CandidateStatus, CandidateInfoForm
    from sqlalchemy import func
    from sqlalchemy.exc import IntegrityError

    task_id = str(self.request.id)
    db = SessionLocal()

    try:
        logger.info(
            f"[TASK {task_id}] Starting candidate creation: {first_name} {last_name} ({email})"
        )

        # ISSUE #7: Validate email format before database insert
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            logger.error(f"[TASK {task_id}] Invalid email format: {email}")
            raise ValueError(f"Invalid email format: {email}")

        # ISSUE #5: Check for duplicate by email or phone before creating
        existing_candidate = db.query(Candidate).filter(
            (func.lower(Candidate.candidateEmail) == email.lower())
            | (Candidate.candidateMobile == mobile)
        ).first()

        if existing_candidate:
            logger.warning(
                f"[TASK {task_id}] Duplicate candidate: email={email}, phone={mobile}"
            )
            # ISSUE #5 FIX: Raise error instead of returning silently
            raise ValueError(f"Candidate with email {email} or phone {mobile} already exists")

        # ISSUE #6 FIX: Use correct field names from model (camelCase, not snake_case)
        candidate = Candidate(
            candidateEmail=email,
            candidateFirstName=first_name,
            candidateLastName=last_name,
            candidateMobile=mobile,
            candidateGender=gender,
            candidateCurrentLocation=location,  # FIXED: was candidate_current_location
            candidateSource=source,              # FIXED: was candidate_source
            tenant_id=tenant_id,
            created_by=user_id,
        )

        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        candidate_id = candidate.candidateID
        logger.info(f"[TASK {task_id}] Candidate created: {candidate_id}")

        # ISSUE #9 FIX: Create related CandidateStatus record (parity with sync path)
        try:
            candidate_status = CandidateStatus(
                candidateID=candidate_id,
                piplineStatus="Applied",
                status="Active",
            )
            try:
                db.add(candidate_status)
                db.commit()
            except Exception as db_error:
                logger.error(f"[TASK {task_id}] Failed to commit CandidateStatus: {db_error}")
                db.rollback()
                raise
            logger.info(f"[TASK {task_id}] CandidateStatus created for {candidate_id}")
        except Exception as e:
            logger.error(f"[TASK {task_id}] Failed to create CandidateStatus: {e}", exc_info=True)
            raise

        # ISSUE #9 FIX: Create CandidateInfoForm record (parity with sync path)
        try:
            candidate_info = CandidateInfoForm(
                candidateID=candidate_id,
                name=f"{first_name} {last_name}",
                email=email,
                phone=mobile,
                gender=gender,
                location=location,
            )
            try:
                db.add(candidate_info)
                db.commit()
            except Exception as db_error:
                logger.error(f"[TASK {task_id}] Failed to commit CandidateInfoForm: {db_error}")
                db.rollback()
                raise
            logger.info(f"[TASK {task_id}] CandidateInfoForm created for {candidate_id}")
        except Exception as e:
            logger.error(f"[TASK {task_id}] Failed to create CandidateInfoForm: {e}", exc_info=True)
            raise

        # ISSUE #13 FIX: Process additional_data if provided (education, experience, etc.)
        if additional_data:
            try:
                from app.models.candidate import CandidateEducationForm, CandidateExperienceForm

                # Process education records
                if additional_data.get("education"):
                    try:
                        for edu in additional_data["education"]:
                            edu_record = CandidateEducationForm(
                                candidateID=candidate_id,
                                education_level=edu.get("level"),
                                university=edu.get("university"),
                                course=edu.get("course"),
                                start_date=edu.get("start_date"),
                                end_date=edu.get("end_date"),
                            )
                            db.add(edu_record)
                        db.commit()
                        logger.info(f"[TASK {task_id}] {len(additional_data['education'])} education records created")
                    except Exception as edu_error:
                        logger.error(f"[TASK {task_id}] Failed to create education records: {edu_error}")
                        db.rollback()
                        raise

                # Process experience records
                if additional_data.get("experience"):
                    try:
                        for exp in additional_data["experience"]:
                            exp_record = CandidateExperienceForm(
                                candidateID=candidate_id,
                                company=exp.get("company"),
                                job_title=exp.get("job_title"),
                                start_date=exp.get("start_date"),
                                end_date=exp.get("end_date"),
                                description=exp.get("description"),
                            )
                            db.add(exp_record)
                        db.commit()
                        logger.info(f"[TASK {task_id}] {len(additional_data['experience'])} experience records created")
                    except Exception as exp_error:
                        logger.error(f"[TASK {task_id}] Failed to create experience records: {exp_error}")
                        db.rollback()
                        raise
            except Exception as e:
                logger.error(f"[TASK {task_id}] Failed to process additional_data: {e}", exc_info=True)
                # Don't fail the whole task for additional data

        # ISSUE #10 FIX: Trigger Thunder auto-assignment (parity with sync path)
        try:
            from app.services.ai_conversation_service import run_auto_assign_ai_agent_in_background
            run_auto_assign_ai_agent_in_background(candidate_id)
            logger.info(f"[TASK {task_id}] Thunder auto-assignment triggered for {candidate_id}")
        except Exception as e:
            logger.error(f"[TASK {task_id}] Failed to trigger Thunder auto-assignment: {e}")
            # Don't fail the task for Thunder failure

        return {
            "candidate_id": candidate_id,
            "message": f"Candidate {first_name} {last_name} created successfully",
            "status": "completed",
            "is_new": True,
        }

    except ValueError as e:
        logger.error(f"[TASK {task_id}] Validation error: {e}")
        raise

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
