"""Message Handler: Unified Candidate Creation

Process queued candidate creation requests.
This is the ONLY place where create_candidate() actually runs.
"""

import logging
from typing import Dict, Any, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from app.core.logging import logger as base_logger
from app.models.channel_queue import ChannelQueueItem

logger = logging.getLogger(__name__)


def _parse_iso_date(value: Any) -> Optional[date]:
    """Optional fields must never fail a creation - an unparseable date becomes None."""
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        logger.warning(f"[CandidateCreationUnified] Ignoring unparseable date: {value!r}")
        return None


def _optional_candidate_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Map optional payload keys to Candidate columns.

    A fixed whitelist on purpose: other producers (progressive upload, bulk
    import) put keys like upload_status in the payload that must never reach
    the Candidate constructor. Salary rate types and assigned managers have
    no column yet and are intentionally not persisted.
    """
    skills = payload.get("candidate_skills")
    if isinstance(skills, list):
        skills = ", ".join(str(s).strip() for s in skills if str(s).strip())

    fields = {
        "candidateMiddleName": payload.get("candidate_middle_name"),
        "candidateJobTitle": payload.get("candidate_job_title"),
        "candidateGender": payload.get("candidate_gender"),
        "candidateCurrentLocation": payload.get("candidate_current_location"),
        "candidateDateOfBirth": _parse_iso_date(payload.get("candidate_date_of_birth")),
        "candidateJoiningDate": _parse_iso_date(payload.get("candidate_joining_date")),
        "candidateExperience": payload.get("candidate_experience"),
        "candidateSkills": skills,
        "candidateExpectedSalary": payload.get("candidate_expected_salary"),
        "candidateCurrentSalary": payload.get("candidate_current_salary"),
        "created_by_user_id": payload.get("created_by_user_id"),
    }
    return {k: v for k, v in fields.items() if v not in (None, "")}


def _add_education_and_experience(db: Session, candidate_id: str, payload: Dict[str, Any]) -> None:
    from app.models.candidate import CandidateEducationForm, CandidateExperienceForm

    education = payload.get("education_records")
    for edu in education if isinstance(education, list) else []:
        if not isinstance(edu, dict):
            continue
        db.add(CandidateEducationForm(
            candidateID=candidate_id,
            education_institute=edu.get("education_institute"),
            degree=edu.get("degree"),
            field_of_study=edu.get("field_of_study"),
            starting_year=edu.get("starting_year"),
            year_of_passing=edu.get("year_of_passing"),
            percentage=edu.get("percentage"),
            submittedAt=_parse_iso_date(edu.get("submitted_at")),
            document_is_submitted=edu.get("document_is_submitted"),
            document_id=edu.get("document_id"),
        ))

    experience = payload.get("experience_records")
    for exp in experience if isinstance(experience, list) else []:
        if not isinstance(exp, dict):
            continue
        db.add(CandidateExperienceForm(
            candidateID=candidate_id,
            company_name=exp.get("company_name"),
            job_title=exp.get("job_title"),
            start_date=_parse_iso_date(exp.get("start_date")),
            end_date=_parse_iso_date(exp.get("end_date")),
            year_of_experience=exp.get("year_of_experience"),
            submittedAt=_parse_iso_date(exp.get("submitted_at")),
            document_is_submitted=exp.get("document_is_submitted"),
            document_id=exp.get("document_id"),
        ))


class CandidateCreationUnifiedHandler:
    """Process candidate creation from queue - UNIFIED HANDLER for all sources."""

    HANDLER_NAME = "candidate_creation_unified"
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 30

    @staticmethod
    def _do_process(message: ChannelQueueItem, db: Session) -> Dict[str, Any]:
        """Internal: actual candidate creation logic (wrapped with timeout)."""
        if not message.payload:
            raise ValueError(f"Message {message.id} has no payload")

        payload = message.payload

        email = payload.get('candidate_email')
        first_name = payload.get('candidate_first_name')
        last_name = payload.get('candidate_last_name')
        mobile = payload.get('candidate_mobile')
        source = payload.get('candidate_source', 'unknown')
        tenant_id = payload.get('tenant_id', 1)

        if not all([email, first_name, last_name]):
            raise ValueError("Missing required fields: email, first_name, last_name")

        logger.info(
            f"[CandidateCreationUnified] Processing: {email} ({first_name} {last_name}), "
            f"source={source}"
        )

        # THE ONLY place create_candidate() is called
        from app.services.candidate_service import create_candidate

        candidate, is_new = create_candidate(
            db=db,
            email=email,
            mobile=mobile,
            linkedin_url=payload.get('linkedin_url'),
            candidate_id=None,
            tenant_id=tenant_id,
            candidateFirstName=first_name,
            candidateLastName=last_name,
            candidateSource=source,
            candidateRole="Candidate",
            **_optional_candidate_fields(payload),
        )

        db.flush()
        candidate_id = candidate.candidateID

        # A duplicate can match on phone alone (possibly a different person),
        # so records are only attached to a candidate created by this message.
        # No commit here: queue_processor_service commits candidate + records together.
        if is_new:
            _add_education_and_experience(db, candidate_id, payload)
            # First entry on the candidate's History tab (the replaced
            # per-source handlers logged this; the unified one did not)
            from app.services.candidate_activity_service import log_candidate_created
            log_candidate_created(
                db,
                candidate_id,
                created_by_user_id=payload.get('created_by_user_id'),
                created_by_name=payload.get('created_by_name'),
                recruitment_source=source,
            )
            # LinkedIn pipeline: recruiter is still doing manual outreach, so
            # Thunder stays off until the pipeline Import step
            if payload.get('thunder_enabled') is False:
                candidate.thunder_enabled = False
                db.add(candidate)

        # Queued from the LinkedIn pipeline: link the item and its open task
        if payload.get('linkedin_pipeline_id'):
            from app.services.linkedin_pipeline_task_service import link_candidate_to_pipeline
            link_candidate_to_pipeline(db, payload['linkedin_pipeline_id'], candidate_id)

        logger.info(
            f"[CandidateCreationUnified] ✅ Created: {candidate_id} "
            f"(new={is_new}, source={source})"
        )

        return {
            'status': 'success',
            'candidate_id': candidate_id,
            'email': candidate.candidateEmail,
            'is_new': is_new,
            'source': source,
        }

    @staticmethod
    def process(message: ChannelQueueItem, db: Session) -> Dict[str, Any]:
        """
        Process candidate creation message from queue with timeout protection.

        This is the ONLY place where candidates are actually created
        (all queue wrappers defer to here).

        Supports all creation sources:
        - bulk_csv_import, linkedin_fast, linkedin_slow, web_chat,
          thunder_test_demo, employee_referral, progressive_upload
        """
        try:
            # Enforce timeout to prevent stuck messages
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(
                CandidateCreationUnifiedHandler._do_process,
                message,
                db
            )
            try:
                return future.result(timeout=CandidateCreationUnifiedHandler.TIMEOUT_SECONDS)
            except FuturesTimeoutError:
                raise RuntimeError(
                    f"Candidate creation exceeded {CandidateCreationUnifiedHandler.TIMEOUT_SECONDS}s timeout"
                )
            finally:
                executor.shutdown(wait=False)

        except ValueError as e:
            logger.error(f"[CandidateCreationUnified] Validation error: {e}")
            raise
        except RuntimeError as e:
            logger.error(f"[CandidateCreationUnified] Runtime error: {e}")
            raise
        except Exception as e:
            logger.error(f"[CandidateCreationUnified] Processing error: {e}", exc_info=True)
            raise RuntimeError(f"Failed to create candidate: {str(e)}")

    @staticmethod
    def on_success(message: ChannelQueueItem, result: Dict[str, Any], db: Session) -> None:
        """Mark message as completed after successful handler execution."""
        try:
            # Verify candidate exists
            from app.models.candidate import Candidate
            candidate_id = result.get('candidate_id')

            if not candidate_id:
                raise ValueError("Result missing candidate_id")

            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found in database")

            # Mark queue item as completed
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result
            db.commit()

            logger.info(
                f"[CandidateCreationUnified] ✅ Message marked COMPLETED: "
                f"{message.message_id} → candidate {candidate_id}"
            )

        except Exception as e:
            db.rollback()
            logger.error(f"[CandidateCreationUnified] on_success error: {e}", exc_info=True)
            raise

    @staticmethod
    def on_retry(message: ChannelQueueItem, error: str, db: Session) -> None:
        """Schedule message for retry."""
        try:
            db.rollback()
            message.retry_count += 1
            message.error = error[:1000]

            if message.retry_count < CandidateCreationUnifiedHandler.MAX_RETRIES:
                from datetime import timedelta
                message.next_retry_at = datetime.utcnow() + timedelta(minutes=5)
                message.status = "PENDING"  # Retry
            else:
                message.status = "FAILED"  # Max retries exhausted
                message.completed_at = datetime.utcnow()

            db.commit()
            logger.info(
                f"[CandidateCreationUnified] Message retry scheduled: "
                f"{message.message_id} (attempt {message.retry_count})"
            )

        except Exception as e:
            db.rollback()
            logger.error(f"[CandidateCreationUnified] on_retry error: {e}", exc_info=True)

    @staticmethod
    def on_failed(message: ChannelQueueItem, final_error: str, db: Session) -> None:
        """Mark message as permanently failed."""
        try:
            db.rollback()
            message.status = "FAILED"
            message.error = final_error[:1000]
            message.completed_at = datetime.utcnow()
            db.commit()

            logger.error(
                f"[CandidateCreationUnified] ❌ Message marked FAILED: "
                f"{message.message_id} - {final_error[:200]}"
            )

        except Exception as e:
            logger.error(f"[CandidateCreationUnified] on_failed error: {e}", exc_info=True)
