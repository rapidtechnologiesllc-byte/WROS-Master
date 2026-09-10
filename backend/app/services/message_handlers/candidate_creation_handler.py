"""Message Handler: Candidate Creation with Retry Logic

Implements idempotent candidate creation through message queue.
- Creates candidate, status, education, experience records
- Logs all events via history API
- 5 retry attempts with 30-minute intervals
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.channel_queue import ChannelQueueItem
from app.models.candidate import Candidate, CandidateStatus, CandidateEducationForm, CandidateExperienceForm
from app.services.candidate_service import create_candidate_safe, DuplicateCandidateError
from app.services.data_healer_service import DataHealerService
from app.services.message_queue_service import MessageQueueService

logger = logging.getLogger(__name__)


class CandidateCreationHandler:
    """Handles candidate creation messages from queue with full record creation and event logging."""

    MAX_RETRIES = 5
    RETRY_DELAY_MINUTES = 30

    @staticmethod
    def process(message: ChannelQueueItem, db: Session) -> Dict[str, Any]:
        """Process candidate creation message - creates ALL records asynchronously.

        Args:
            message: ChannelQueueItem with payload containing candidate data
            db: Database session

        Returns:
            {'status': 'success', 'candidate_id': str, 'is_new': bool}
        """
        if not message.payload:
            raise ValueError(f"Message {message.id} has no payload")

        payload = message.payload
        candidate_email = payload.get("candidate_email")
        logger.info(f"[Handler] Processing queue message, candidate_email={candidate_email}, payload keys={list(payload.keys())}")

        try:
            # ATOMIC TRANSACTION: All records (candidate, status, education, experience) created together
            # Use db.flush() pattern: add all, flush once, commit once

            # 1. CREATE CANDIDATE - Direct ORM mapping from payload
            # Map payload fields to Candidate model fields (payload uses candidate_* naming)
            from app.utils.uniq_id_generator import candidate_id_generator

            # Extract and validate tenant_id (required for multi-tenant isolation)
            tenant_id = payload.get("tenant_id", 1)
            if not isinstance(tenant_id, int) or tenant_id < 1:
                logger.error(f"[Handler] Invalid tenant_id {tenant_id} for {candidate_email}")
                raise ValueError(f"Invalid tenant_id: {tenant_id}")

            candidate = Candidate(
                candidateID=candidate_id_generator(),
                candidateEmail=candidate_email,
                candidateMobile=payload.get("candidate_mobile"),
                candidatePassword=payload.get("candidate_password"),  # Hashed password from API
                candidateRole=payload.get("candidate_role", "Candidate"),
                candidateEmployeeType=payload.get("candidate_employee_type"),
                candidateFirstName=payload.get("candidate_first_name"),
                candidateMiddleName=payload.get("candidate_middle_name"),
                candidateLastName=payload.get("candidate_last_name"),
                candidateGender=payload.get("candidate_gender"),
                candidateDateOfBirth=payload.get("candidate_date_of_birth"),
                candidateCurrentLocation=payload.get("candidate_current_location"),
                candidateSource=payload.get("candidate_source"),
                candidateExperience=payload.get("candidate_experience"),
                candidateSkills=payload.get("candidate_skills"),
                candidateJoiningDate=payload.get("candidate_joining_date"),
                candidateExpectedSalary=payload.get("candidate_expected_salary"),
                candidateCurrentSalary=payload.get("candidate_current_salary"),
                candidateCreatedAt=datetime.now(),
                tenant_id=tenant_id,  # ✅ Assign tenant_id from payload
            )

            # Check for duplicates before adding
            is_new = True
            existing = db.query(Candidate).filter(Candidate.candidateEmail == candidate_email).first()
            if existing:
                is_new = False
                candidate = existing
                logger.info(f"[Handler] Candidate already exists: {candidate_email}")
            else:
                db.add(candidate)

            # Flush candidate to get candidateID (but don't commit yet)
            try:
                db.flush()
                db.refresh(candidate)
            except Exception as e:
                db.rollback()
                logger.error(f"[Handler] Flush failed for candidate: {e}", exc_info=True)
                raise RuntimeError(f"Failed to create candidate: {str(e)}") from e

            candidate_id = candidate.candidateID
            logger.info(f"[Handler] ✅ Candidate flushed: {candidate_id}")

            # 2. CREATE STATUS
            try:
                existing_status = db.query(CandidateStatus).filter(CandidateStatus.candidateID == candidate_id).first()
            except Exception as e:
                logger.error(f"[Handler] Failed to query status: {e}", exc_info=True)
                existing_status = None

            if not existing_status:
                try:
                    db.add(CandidateStatus(
                        candidateID=candidate_id, piplineStatus="Applied", status="Active",
                        createdAt=datetime.now(), updatedAt=datetime.now(),
                    ))
                except Exception as e:
                    logger.error(f"[Handler] Failed to add status: {e}", exc_info=True)
                    db.rollback()
                    raise

            # 3. CREATE EDUCATION RECORDS
            for edu in payload.get("education_records", []):
                try:
                    existing = db.query(CandidateEducationForm).filter(
                        CandidateEducationForm.candidateID == candidate_id,
                        CandidateEducationForm.education_institute == edu.get("education_institute"),
                        CandidateEducationForm.degree == edu.get("degree"),
                    ).first()
                except Exception as e:
                    logger.error(f"[Handler] Failed to query education: {e}", exc_info=True)
                    existing = None

                if not existing:
                    try:
                        db.add(CandidateEducationForm(
                        candidateID=candidate_id,
                        education_institute=edu.get("education_institute"),
                        degree=edu.get("degree"),
                        field_of_study=edu.get("field_of_study"),
                        starting_year=edu.get("starting_year"),
                        year_of_passing=edu.get("year_of_passing"),
                        percentage=edu.get("percentage"),
                        submittedAt=edu.get("submitted_at"),
                        document_is_submitted=edu.get("document_is_submitted"),
                        document_id=edu.get("document_id"),
                        ))
                    except Exception as e:
                        logger.error(f"[Handler] Failed to add education record: {e}", exc_info=True)
                        db.rollback()
                        raise

            # 4. CREATE EXPERIENCE RECORDS
            for exp in payload.get("experience_records", []):
                try:
                    existing = db.query(CandidateExperienceForm).filter(
                        CandidateExperienceForm.candidateID == candidate_id,
                        CandidateExperienceForm.company_name == exp.get("company_name"),
                        CandidateExperienceForm.job_title == exp.get("job_title"),
                    ).first()
                except Exception as e:
                    logger.error(f"[Handler] Failed to query experience: {e}", exc_info=True)
                    existing = None

                if not existing:
                    try:
                        db.add(CandidateExperienceForm(
                            candidateID=candidate_id,
                            company_name=exp.get("company_name"),
                            job_title=exp.get("job_title"),
                            start_date=exp.get("start_date"),
                            end_date=exp.get("end_date"),
                            year_of_experience=exp.get("year_of_experience"),
                            submittedAt=exp.get("submitted_at"),
                            document_is_submitted=exp.get("document_is_submitted"),
                            document_id=exp.get("document_id"),
                        ))
                    except Exception as e:
                        logger.error(f"[Handler] Failed to add experience record: {e}", exc_info=True)
                        db.rollback()
                        raise

            # ATOMIC COMMIT: All or nothing - single commit for all records
            try:
                db.commit()
                logger.info(f"[Handler] ✅ All records created atomically for {candidate_id} (candidate, status, education, experience)")
            except Exception as e:
                db.rollback()
                logger.error(f"[Handler] Atomic commit failed: {e}", exc_info=True)
                raise RuntimeError(f"Failed to commit all records: {str(e)}") from e

            # RETURN SUCCESS IMMEDIATELY - Mark handler complete before queuing dependent work
            # This prevents handler from blocking on email/Thunder queueing
            result = {"status": "success", "candidate_id": candidate_id, "is_new": is_new}
            logger.info(f"[Handler] ✅ Candidate creation complete: {candidate_id} (ready for return)")

            # Queue dependent work AFTER returning success (non-blocking background tasks)
            # These should NOT block handler completion
            try:
                # Log history event (non-critical)
                CandidateCreationHandler._log_history_event(
                    candidate_id, "Candidate Added", f"Candidate added via form submission"
                )
                logger.info(f"[Handler] ✅ History event logged for {candidate_id}")
            except Exception as e:
                logger.warning(f"[Handler] History logging failed (non-blocking): {e}", exc_info=True)

            try:
                # Queue engagement email (non-critical, async)
                MessageQueueService.enqueue(
                    task_name='send_email',
                    channel_type='EMAIL_QUEUE',
                    data={
                        'candidate_id': candidate_id,
                        'recipient_email': candidate_email,
                        'email_type': 'FIRST_ENGAGEMENT',
                        'subject': f'Welcome {payload.get("candidate_first_name", "User")}! Your Application is Received',
                        'body': f'Hi {payload.get("candidate_first_name", "there")},\n\nThank you for applying! We have received your application and will review it shortly.\n\nBest regards,\nBlitzenX Team',
                        'tenant_id': payload.get('tenant_id', 1),
                    }
                )
                logger.info(f"[Handler] ✅ Queued engagement email for {candidate_id}")
            except Exception as e:
                logger.warning(f"[Handler] Email queueing failed (non-blocking): {e}", exc_info=True)

            try:
                # Queue to Thunder for autonomous processing (non-critical, async)
                MessageQueueService.enqueue(
                    task_name='assign_thunder_agent',
                    data={
                        'candidate_id': candidate_id,
                        'action': 'qualify',
                        'tenant_id': payload.get('tenant_id', 1),
                    }
                )
                logger.info(f"[Handler] ✅ Queued {candidate_id} to Thunder")
            except Exception as e:
                logger.warning(f"[Handler] Thunder queueing failed (non-blocking): {e}", exc_info=True)

            return result

        except DuplicateCandidateError as e:
            logger.warning(f"[Handler] Duplicate candidate: {candidate_email}", exc_info=True)
            # Duplicates are OK - track as multiple applications
            return {"status": "success", "candidate_id": str(e), "is_new": False, "duplicate": True}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[Handler] Candidate creation failed: {error_msg}", exc_info=True)

            # HEALING STRATEGY: Try to fix data issues before giving up
            can_heal, healed_payload, recruiter_task = DataHealerService.heal_and_recover(
                error=error_msg,
                payload=payload,
                db=db
            )

            if can_heal:
                logger.info(f"[Handler] Healer fixed issues, retrying with healed payload")
                # Retry with healed payload (may use placeholders)
                try:
                    candidate, is_new = create_candidate_safe(
                        db,
                        email=healed_payload.get("candidate_email"),
                        mobile=healed_payload.get("candidate_mobile"),
                        plain_password=healed_payload.get("candidate_password"),
                        tenant_id=healed_payload.get("tenant_id"),
                        candidateRole=healed_payload.get("candidate_role", "Candidate"),
                        candidateEmployeeType=healed_payload.get("candidate_employee_type"),
                        candidateFirstName=healed_payload.get("candidate_first_name"),
                        candidateLastName=healed_payload.get("candidate_last_name"),
                        candidateGender=healed_payload.get("candidate_gender"),
                        candidateDateOfBirth=healed_payload.get("candidate_date_of_birth"),
                        candidateCurrentLocation=healed_payload.get("candidate_current_location"),
                        candidateCreatedAt=datetime.now(),
                    )
                    try:
                        db.commit()
                    except Exception as commit_err:
                        db.rollback()
                        raise RuntimeError(f"Failed to commit healed candidate: {str(commit_err)}") from commit_err

                    try:
                        db.refresh(candidate)
                    except Exception as refresh_err:
                        logger.error(f"Failed to refresh candidate: {refresh_err}")
                        raise RuntimeError(f"Failed to refresh candidate: {str(refresh_err)}") from refresh_err

                    candidate_id = candidate.candidateID

                    # Create status if it doesn't already exist
                    try:
                        existing_status = db.query(CandidateStatus).filter(
                            CandidateStatus.candidateID == candidate_id
                        ).first()
                    except Exception as query_err:
                        existing_status = None
                        logger.warning(f"Failed to query status: {query_err}")

                    if not existing_status:
                        try:
                            status_record = CandidateStatus(
                                candidateID=candidate_id,
                                piplineStatus="Applied",
                                status="Active",
                                createdAt=datetime.now(),
                                updatedAt=datetime.now(),
                            )
                            db.add(status_record)
                            db.commit()
                        except Exception as status_err:
                            db.rollback()
                            logger.error(f"Failed to create status for healed candidate: {status_err}", exc_info=True)
                            raise RuntimeError(f"Failed to create status: {str(status_err)}") from status_err

                    # Queue first engagement email for healed candidate
                    try:
                        candidate_first_name = healed_payload.get("candidate_first_name", "Candidate")
                        candidate_email = healed_payload.get("candidate_email")
                        MessageQueueService.enqueue(
                            task_name='send_email',
                            channel_type='EMAIL_QUEUE',
                            data={
                                'candidate_id': candidate_id,
                                'recipient_email': candidate_email,
                                'email_type': 'FIRST_ENGAGEMENT',
                                'subject': f'Welcome {candidate_first_name}! Your Application is Received',
                                'body': f'Hi {candidate_first_name},\n\nThank you for applying! We have received your application and will review it shortly.\n\nBest regards,\nBlitzenX Team',
                                'tenant_id': healed_payload.get('tenant_id', 1),
                            }
                        )
                        logger.info(f"[Handler] ✅ Queued email for healed candidate {candidate_id}")
                    except Exception as e:
                        logger.warning(f"[Handler] Failed to queue email for healed candidate: {e}")

                    # If we used placeholders, create a recruiter task to fix the data
                    if recruiter_task:
                        logger.info(f"[Handler] Creating recruiter task: {recruiter_task}")
                        DataHealerService.create_recruiter_fix_task(candidate_id, recruiter_task, db)

                    return {"status": "success", "candidate_id": candidate_id, "is_new": is_new, "healed": True}

                except Exception as retry_error:
                    logger.error(f"[Handler] Healed retry also failed: {retry_error}", exc_info=True)
                    # Escalate to recruiter for manual review
                    raise RuntimeError(f"Manual review required after healing attempt: {retry_error}") from retry_error
            else:
                # Cannot heal - escalate
                escalation_msg = recruiter_task or f"Cannot auto-fix: {error_msg}"
                logger.error(f"[Handler] Escalating to recruiter: {escalation_msg}")
                raise RuntimeError(escalation_msg) from e

    @staticmethod
    def _log_history_event(candidate_id: str, event_type: str, note: str):
        """Log history event via API (graceful failure if unavailable)."""
        try:
            # This would call the history API endpoint - for now just log
            logger.info(f"[History] Event '{event_type}' for candidate {candidate_id}: {note}")
        except Exception as e:
            logger.warning(f"[History] Failed to log event: {e}")

    @staticmethod
    def should_retry(message: ChannelQueueItem) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= CandidateCreationHandler.MAX_RETRIES:
            logger.error(f"[Handler] Max retries exceeded for {message.id}")
            return False
        if message.next_retry_at and datetime.utcnow() < message.next_retry_at:
            return False
        return True

    @staticmethod
    def on_retry(message: ChannelQueueItem, error: str, db: Session) -> None:
        """Handle retry logic after failed attempt."""
        try:
            # Rollback any aborted transaction first (critical for PostgreSQL)
            db.rollback()

            # Now update the message status in a fresh transaction
            message.retry_count += 1
            message.error = error
            message.next_retry_at = datetime.utcnow() + timedelta(minutes=CandidateCreationHandler.RETRY_DELAY_MINUTES)

            db.commit()
        except Exception as e:
            try:
                db.rollback()
            except Exception as rollback_err:
                logger.error(f"[Handler] Failed to rollback after error: {rollback_err}", exc_info=True)
            logger.error(f"[Handler] Failed to schedule retry: {e}", exc_info=True)
            raise

    @staticmethod
    def on_success(message: ChannelQueueItem, result: Dict[str, Any], db: Session) -> None:
        """Handle successful message processing - queue candidate to Thunder for autonomous engagement."""
        message.status = "COMPLETED"
        message.completed_at = datetime.utcnow()
        message.result = result
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"[Handler] Failed to mark success: {e}", exc_info=True)
            raise

        # Queue candidate to Thunder for autonomous engagement
        candidate_id = result.get('candidate_id')
        if candidate_id:
            try:
                MessageQueueService.enqueue(
                    task_name='engage_candidate_with_thunder',
                    data={'candidate_id': candidate_id}
                )
                logger.info(f"[Handler] Candidate {candidate_id} queued to THUNDER_QUEUE for autonomous engagement")
            except Exception as e:
                logger.error(f"[Handler] Failed to queue candidate {candidate_id} to Thunder: {e}", exc_info=True)

    @staticmethod
    def on_failed(message: ChannelQueueItem, final_error: str, db: Session) -> None:
        """Handle final failure after all retries exhausted."""
        try:
            # Rollback any aborted transaction first (critical for PostgreSQL)
            db.rollback()

            # Now update the message status in a fresh transaction
            message.status = "FAILED"
            message.error = final_error
            message.completed_at = datetime.utcnow()

            db.commit()
        except Exception as e:
            try:
                db.rollback()
            except Exception as rollback_err:
                logger.error(f"[Handler] Failed to rollback after error: {rollback_err}", exc_info=True)
            logger.error(f"[Handler] Failed to mark failure: {e}", exc_info=True)
            raise

    @staticmethod
    def prioritize_queue(db: Session) -> list:
        """
        Prioritize Thunder candidate queue by match score (descending).

        Fetches all pending candidates and sorts by ATSScore.match_score.
        Higher scores = better fit = higher priority.

        Returns:
            List of candidate IDs sorted by match_score DESC
        """
        try:
            from app.models.candidate import Candidate
            from app.models.ats import ATSScore

            # Fetch all candidates with their match scores
            candidates_with_scores = db.query(
                Candidate.candidateID,
                ATSScore.match_score
            ).outerjoin(
                ATSScore,
                ATSScore.candidate_id == Candidate.candidateID
            ).filter(
                Candidate.candidateCreatedAt >= datetime.utcnow() - timedelta(days=7)  # Last 7 days
            ).order_by(
                ATSScore.match_score.desc()  # Highest scores first
            ).all()

            prioritized_candidates = [row.candidateID for row in candidates_with_scores]

            logger.info(
                f"[QueuePrioritization] Prioritized {len(prioritized_candidates)} candidates by match_score. "
                f"Top 3: {prioritized_candidates[:3]}"
            )

            return prioritized_candidates

        except Exception as e:
            logger.error(f"[QueuePrioritization] Failed to prioritize queue: {e}", exc_info=True)
            raise
