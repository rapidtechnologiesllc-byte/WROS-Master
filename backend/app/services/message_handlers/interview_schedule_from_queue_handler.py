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

logger = logging.getLogger(__name__)


class InterviewScheduleFromQueueHandler:
    """Handle interview scheduling from queue messages"""

    @staticmethod
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

            # PHASE 5: COMMIT TRANSACTION
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
