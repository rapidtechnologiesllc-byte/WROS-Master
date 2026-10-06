"""
Interview Scheduling Handler - Queue-Driven (PHASE A FIX #2)

Purpose: Queue-based interview scheduling (not direct DB)
- Receives interview_scheduled message from queue
- Creates Interview record in database
- Notifies Thunder to pause outreach for this candidate
- Stores interview details for candidate portal

Pattern: Same as other queue handlers (job_created_flash, offer_approved)
"""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from datetime import datetime
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class InterviewScheduleFromQueueHandler:
    """Handle interview scheduling from queue messages"""
    # Enforced by queue_processor_service (its default for this task type)
    TIMEOUT_SECONDS = 30


    @staticmethod
    @time_bound(timeout_seconds=12)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process: Schedule interview for candidate

        Args:
            message: ChannelQueueItem with type='interview_scheduled'
            db: SQLAlchemy session

        Returns:
            {
                'status': 'success',
                'interview_id': str,
                'candidate_id': str,
                'job_id': str,
                'scheduled_date': str
            }

        Raises:
            ValueError: Invalid payload (400 client error)
            RuntimeError: DB operation failures (500 internal, retry eligible)
        """
        try:
            payload = message.payload or {}

            # PHASE 1: VALIDATION
            candidate_id = payload.get('candidate_id')
            job_id = payload.get('job_id')
            interview_date = payload.get('interview_date')
            interview_time = payload.get('interview_time')
            interviewer_id = payload.get('interviewer_id')

            if not all([candidate_id, job_id, interview_date, interview_time]):
                raise ValueError(
                    "Missing required fields: candidate_id, job_id, interview_date, interview_time"
                )

            logger.info(
                f"[InterviewScheduler] Processing interview for "
                f"candidate={candidate_id}, job={job_id}, date={interview_date}"
            )

            # PHASE 2: VERIFY CANDIDATE & JOB EXIST
            from app.models.user import Candidate, Jobs

            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()

            if not job:
                raise ValueError(f"Job {job_id} not found")

            logger.info(
                f"[InterviewScheduler] Verified: candidate={candidate.candidateEmail}, "
                f"job={job.jobTitle}"
            )

            # PHASE 3: CREATE INTERVIEW RECORD
            from app.models.interview import Interview

            interview = Interview(
                candidate_id=candidate_id,
                job_id=job_id,
                interview_date=interview_date,
                interview_time=interview_time,
                interviewer_id=interviewer_id,
                status="SCHEDULED",
                created_at=datetime.utcnow(),
                interview_notes=payload.get('notes', ''),
            )

            db.add(interview)
            db.flush()  # Get interview_id before commit
            interview_id = interview.id

            logger.info(f"[InterviewScheduler] Interview record created: {interview_id}")

            # PHASE 3B: SLM PRE-FLIGHT CHECK
            slm_analysis = None
            try:
                from app.services.slm_service import SLMService

                slm_analysis = SLMService.analyze_before_handler(
                    message_id=str(message.id),
                    message_type='interview_scheduled',
                    payload=payload,
                    context={
                        'business_goal': 'Schedule interview for candidate',
                        'risk_level': 'HIGH',
                        'candidate_id': candidate_id,
                        'interview_id': interview_id,
                        'job_id': job_id,
                    },
                    db=db
                )
                if not slm_analysis.get('should_proceed'):
                    logger.error(f"[InterviewScheduler] SLM escalation required: {slm_analysis.get('reasoning')}")
                    raise ValueError(f"SLM escalation: {slm_analysis.get('reasoning')}")
            except ImportError:
                logger.debug("[InterviewScheduler] SLMService not available, continuing")
            except ValueError:
                raise
            except Exception as slm_err:
                logger.warning(f"[InterviewScheduler] SLM pre-flight failed: {slm_err}")

            # PHASE 4: NOTIFY THUNDER (Queue pause signal)
            # Thunder should pause outreach for this candidate (in interview)
            try:
                from app.services.message_queue_service import MessageQueueService

                MessageQueueService.enqueue(
                    task_name='interview_scheduled_pause_thunder',
                    task_id=f"interview_{interview_id}",
                    data={
                        'candidate_id': candidate_id,
                        'interview_id': interview_id,
                        'reason': f'Interview scheduled for {interview_date}',
                        'pause_until': interview_date,  # Resume after interview
                    }
                )
                logger.info(f"[InterviewScheduler] Thunder pause signal queued for {candidate_id}")

            except Exception as thunder_err:
                logger.warning(
                    f"[InterviewScheduler] Failed to queue Thunder pause: {thunder_err} "
                    f"(non-blocking, interview already created)"
                )

            # PHASE 5: SEND INTERVIEW INVITE EMAIL
            delivery_id = None
            try:
                from app.services.email_service import EmailService

                candidate_name = getattr(candidate, 'candidateFirstName', 'Candidate')
                candidate_email = candidate.candidateEmail
                job_title = job.jobTitle if hasattr(job, 'jobTitle') else 'Position'

                email_subject = f"Interview Scheduled - {job_title}"
                email_body = f"""
Dear {candidate_name},

Congratulations! We're pleased to invite you to interview for the {job_title} position.

**INTERVIEW DETAILS**
Date: {interview_date}
Time: {interview_time}
Position: {job_title}

Please confirm your availability by clicking the link below or replying to this email.
Our team will send you additional details and meeting link soon.

We look forward to speaking with you!

Best regards,
Recruiting Team
"""

                result = EmailService.send_email(
                    to_email=candidate_email,
                    subject=email_subject,
                    body_content=email_body,
                    is_html=True
                )

                if result.get('status') == 'skipped':
                    logger.warning(f"[InterviewScheduler] Email skipped to {candidate_email}: {result.get('reason')}")
                elif result.get('status') != 'success':
                    logger.warning(f"[InterviewScheduler] Email delivery failed: {result}")
                else:
                    delivery_id = "msgraph_" + str(hash(candidate_email))
                    logger.info(f"[InterviewScheduler] Interview invite sent to {candidate_email}, delivery_id={delivery_id}")

            except Exception as delivery_err:
                logger.warning(f"[InterviewScheduler] Email delivery error (non-blocking): {delivery_err}")

            # PHASE 6: SLM POST-FLIGHT OUTCOME RECORDING
            if slm_analysis:
                try:
                    from app.services.slm_service import SLMService

                    SLMService.record_outcome(
                        slm_analysis=slm_analysis,
                        message_id=str(message.id),
                        handler_name='interview_schedule_from_queue_handler',
                        handler_result={
                            'status': 'success',
                            'interview_id': interview_id,
                            'email_sent': delivery_id is not None,
                            'candidate_notified': delivery_id is not None,
                        },
                        business_impact={
                            'candidate_affected': True,
                            'interview_scheduled': True,
                            'candidate_notified': delivery_id is not None,
                            'expected_outcome': 'interview_confirmed',
                            'can_be_reversed': False,
                            'accountability_required': True,
                        },
                        db=db
                    )
                except ImportError:
                    pass  # SLMService not available
                except Exception as slm_record_err:
                    logger.warning(f"[InterviewScheduler] SLM outcome recording failed: {slm_record_err}")

            # PHASE 7: COMMIT TRANSACTION
            db.commit()

            logger.info(
                f"[InterviewScheduler] ✅ Interview scheduled successfully for {candidate_id}"
            )

            return {
                'status': 'success',
                'interview_id': interview_id,
                'candidate_id': candidate_id,
                'job_id': job_id,
                'scheduled_date': interview_date,
                'scheduled_time': interview_time,
                'delivery_id': delivery_id,
            }

        except ValueError as ve:
            logger.error(f"[InterviewScheduler] Validation error: {ve}")
            raise  # NOT RETRYABLE - client error

        except RuntimeError as re:
            logger.error(f"[InterviewScheduler] Runtime error (retryable): {re}")
            raise  # RETRYABLE - infrastructure error

        except OperationalError as oe:
            logger.error(f"[InterviewScheduler] DB operational error: {oe}", exc_info=True)
            raise RuntimeError(f"DB unavailable: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[InterviewScheduler] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that interview scheduling completed successfully."""
        from app.models.user import Interview
        from sqlalchemy.orm import Session as DbSession

        if not result or "interview_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        interview_id = result.get("interview_id")

        try:
            interview = db.query(Interview).filter(Interview.id == interview_id).first()
            if not interview:
                raise ValueError(f"Interview {interview_id} not found after scheduling")

            logger.info(f"✅ Interview scheduled validated: {interview_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[InterviewScheduler] RETRYABLE validation error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        from datetime import datetime
        MAX_RETRIES = 3
        RETRY_DELAY_MINUTES = 15

        if message.retry_count >= MAX_RETRIES:
            return False
        if hasattr(message, 'next_retry_at') and message.next_retry_at:
            if datetime.utcnow() < message.next_retry_at:
                return False
        return True

    @staticmethod
    def on_retry(message: Any, error: str, db: Session) -> None:
        """Schedule message for retry."""
        from datetime import datetime, timedelta

        try:
            db.rollback()
            message.retry_count += 1
            message.error = error[:1000]
            message.next_retry_at = datetime.utcnow() + timedelta(minutes=15)
            db.commit()
        except Exception as e:
            db.rollback()
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Mark message as COMPLETED after validation."""
        from datetime import datetime

        try:
            InterviewScheduleFromQueueHandler.validate(message, result, db)

            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit COMPLETED status: {str(commit_err)}") from commit_err

            return {'is_valid': True, 'interview_id': result.get("interview_id")}

        except ValueError:
            db.rollback()
            raise

        except RuntimeError:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def on_failed(message: Any, final_error: str, db: Session) -> None:
        """Mark message as FAILED after all retries."""
        from datetime import datetime

        try:
            db.rollback()
            message.status = "FAILED"
            message.error = final_error[:1000]
            message.completed_at = datetime.utcnow()
            db.commit()
        except Exception as e:
            db.rollback()
            raise
