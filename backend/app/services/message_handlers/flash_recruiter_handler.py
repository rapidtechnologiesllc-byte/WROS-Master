"""Flash Recruiter Handler - Queue-driven candidate matching and autonomous outreach

CYCLE 19: Flash AI Recruiter Handler
Finds matching candidates for newly created jobs and queues Thunder autonomous outreach.

Responsibilities:
1. Retrieve job from database
2. Find matching candidates (active watches)
3. Queue Thunder messages for autonomous outreach
4. Train SLM with recruitment results
"""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)


class FlashRecruiterHandler:
    """Flash Recruiter - autonomous candidate matching and outreach orchestration."""

    @staticmethod
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process: Find matching candidates and queue Thunder outreach

        Args:
            message: ChannelQueueItem with type='flash_recruiter'
            db: SQLAlchemy session

        Returns:
            {
                'status': 'success',
                'job_id': str,
                'candidates_matched': int,
                'outreach_queued': int
            }

        Raises:
            ValueError: Invalid payload (400 client error)
            RuntimeError: DB operation failures (500 internal, retry eligible)
        """
        try:
            payload = message.payload or {}

            # PHASE 1: VALIDATION
            job_id = payload.get('job_id')
            if not job_id:
                raise ValueError("Missing required field: job_id")

            # PHASE 2: RETRIEVE JOB FROM DATABASE
            from app.models.user import Jobs
            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
            if not job:
                raise RuntimeError(f"Job {job_id} not found in database")

            logger.info(f"[FlashRecruiter] Starting recruitment for job {job_id}: {job.jobTitle}")

            # PHASE 3: SCAN FOR MATCHING CANDIDATES & QUEUE OUTREACH
            from app.services.ready_for_opportunity_service import scan_new_job_for_matches
            from app.services.message_queue_service import MessageQueueService

            matched_watches = scan_new_job_for_matches(db, job)
            logger.info(f"[FlashRecruiter] Found {len(matched_watches)} matching candidates for {job_id}")

            # PHASE 4: TRAIN SLM WITH RESULTS
            try:
                slm_analysis = payload.get('slm_analysis', {})
                from app.services.slm_service import SLMService
                from app.services.architect_codebase_learning import ArchitectKnowledgeTeacher

                slm_decision = SLMService.analyze_message_result(
                    message_id=message.id,
                    message_type='flash_recruitment',
                    result={
                        'success': True,
                        'job_id': job_id,
                        'job_title': job.jobTitle,
                        'candidates_matched': len(matched_watches),
                        'recruitment_urgency': slm_analysis.get('urgency', 'MEDIUM')
                    },
                    db=db
                )

                # Record learning pattern
                teacher = ArchitectKnowledgeTeacher()
                teacher.teach_pattern(
                    pattern_type='flash_recruitment',
                    pattern_data={
                        'job_id': job_id,
                        'urgency': slm_analysis.get('urgency'),
                        'candidates_matched': len(matched_watches),
                        'slm_decision': slm_decision.get('decision'),
                        'timestamp': __import__('datetime').datetime.utcnow().isoformat()
                    }
                )
                logger.info(f"[FlashRecruiter] SLM trained: {len(matched_watches)} candidates for {job_id}")

            except Exception as slm_err:
                logger.warning(f"[FlashRecruiter] SLM training failed (non-blocking): {slm_err}")

            # PHASE 5: SCHEDULE NEXT RUN (if job still active)
            # Flash_Recruiter continues every 4 hours until job closes (1-N months)
            if job.jobStatus and job.jobStatus.lower() == 'active':
                try:
                    from app.services.message_queue_service import MessageQueueService

                    # Schedule next recruitment run in 4 hours (14400 seconds)
                    next_recruiter_msg_id = MessageQueueService.enqueue(
                        task_name='flash_recruiter',
                        task_id=f"{job_id}_next",
                        data=payload,
                        delay_seconds=14400  # 4 hours
                    )
                    logger.info(
                        f"[FlashRecruiter] Scheduled next run for {job_id} in 4 hours: "
                        f"message_id={next_recruiter_msg_id}"
                    )
                except Exception as schedule_err:
                    logger.warning(f"[FlashRecruiter] Failed to schedule next run: {schedule_err}")

            logger.info(
                f"[FlashRecruiter] ✅ Completed recruitment for {job_id}: "
                f"{len(matched_watches)} candidates matched and outreach queued"
            )

            return {
                'status': 'success',
                'job_id': job_id,
                'job_title': job.jobTitle,
                'candidates_matched': len(matched_watches),
                'outreach_queued': len(matched_watches),
                'job_status': job.jobStatus,
                'next_run_in_hours': 4 if (job.jobStatus and job.jobStatus.lower() == 'active') else 0
            }

        except ValueError as ve:
            logger.error(f"[FlashRecruiter] Validation error: {ve}")
            raise  # NOT RETRYABLE - client error

        except RuntimeError as re:
            logger.error(f"[FlashRecruiter] Runtime error (retryable): {re}")
            raise  # RETRYABLE - infrastructure error

        except OperationalError as oe:
            logger.error(f"[FlashRecruiter] DB operational error: {oe}", exc_info=True)
            raise RuntimeError(f"DB unavailable: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[FlashRecruiter] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e
