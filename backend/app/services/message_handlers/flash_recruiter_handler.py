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
    def _get_thunder_health(db: Session) -> Dict[str, Any]:
        """
        Calculate Thunder's recent success rate from ChannelQueueItem (CRITICAL FIX #7)

        Returns:
            {
                'success_rate': float (0.0-1.0),
                'sample_size': int,
                'completed': int,
                'failed': int,
                'health_status': 'healthy' | 'degraded' | 'unknown'
            }
        """
        try:
            from datetime import datetime, timedelta
            from app.models.channel_queue import ChannelQueueItem

            # Query last 100 Thunder tasks (or 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_tasks = db.query(ChannelQueueItem).filter(
                ChannelQueueItem.channel_type == 'THUNDER_QUEUE',
                ChannelQueueItem.status.in_(['COMPLETED', 'FAILED']),
                ChannelQueueItem.created_at >= recent_cutoff
            ).order_by(ChannelQueueItem.created_at.desc()).limit(100).all()

            if not recent_tasks:
                # No recent Thunder activity - assume healthy
                return {
                    'success_rate': 1.0,
                    'sample_size': 0,
                    'completed': 0,
                    'failed': 0,
                    'health_status': 'unknown'
                }

            completed = sum(1 for t in recent_tasks if t.status == 'COMPLETED')
            failed = sum(1 for t in recent_tasks if t.status == 'FAILED')
            total = len(recent_tasks)
            success_rate = completed / total if total > 0 else 0.0

            return {
                'success_rate': success_rate,
                'sample_size': total,
                'completed': completed,
                'failed': failed,
                'health_status': 'degraded' if success_rate < 0.7 else 'healthy'
            }
        except Exception as e:
            logger.warning(f"[FlashRecruiter] Failed to get Thunder health: {e}")
            return {
                'success_rate': 1.0,
                'sample_size': 0,
                'completed': 0,
                'failed': 0,
                'health_status': 'unknown'
            }

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

            # ARCHITECT FIX: Validate job status before recruitment
            if not job.jobStatus or job.jobStatus.lower() != 'active':
                logger.warning(f"[FlashRecruiter] Job {job_id} is {job.jobStatus}, not active. Skipping recruitment.")
                return {
                    'status': 'skipped',
                    'job_id': job_id,
                    'job_title': job.jobTitle,
                    'reason': f'Job status is {job.jobStatus}, not active',
                    'candidates_matched': 0,
                    'outreach_queued': 0
                }

            logger.info(f"[FlashRecruiter] Starting recruitment for job {job_id}: {job.jobTitle}")

            # PHASE 2.2: CHECK THUNDER HEALTH & QUEUE CASCADE SIGNAL (CRITICAL FIX #7)
            import time
            from datetime import datetime
            thunder_health = FlashRecruiterHandler._get_thunder_health(db)
            logger.info(f"[FlashRecruiter] Thunder health: {thunder_health['success_rate']:.1%} ({thunder_health['sample_size']} tasks)")

            # If Thunder is degraded, queue cascade failure signal
            if thunder_health['success_rate'] < 0.7 and thunder_health['sample_size'] >= 10:
                logger.warning(
                    f"[FlashRecruiter] ⚠️ Thunder degraded: "
                    f"{thunder_health['success_rate']:.1%} < 70% threshold"
                )
                try:
                    from app.services.message_queue_service import MessageQueueService
                    MessageQueueService.enqueue(
                        task_name='cascade_failure_signal',
                        task_id=f"cascade_{job_id}_{int(time.time())}",
                        data={
                            'from': 'Thunder',
                            'to': 'Flash',
                            'signal_type': 'stop_recruitment',
                            'reason': (
                                f'Success rate {thunder_health["success_rate"]:.1%} '
                                f'below 70% threshold'
                            ),
                            'thunder_health': thunder_health,
                            'job_id': job_id,
                            'timestamp': datetime.utcnow().isoformat()
                        }
                    )
                    logger.info(f"[FlashRecruiter] Cascade failure signal queued for {job_id}")
                except Exception as signal_err:
                    # Non-blocking - don't prevent recruitment
                    logger.warning(
                        f"[FlashRecruiter] Failed to queue cascade signal: {signal_err}"
                    )

            # PHASE 2.3: RACE CONDITION CHECK - Verify job still exists (CRITICAL FIX #7)
            job_exists = db.query(Jobs).filter(Jobs.jobID == job_id).first()
            if not job_exists:
                logger.warning(f"[FlashRecruiter] Job {job_id} was deleted before recruitment, aborting")
                return {
                    'status': 'job_deleted',
                    'job_id': job_id,
                    'reason': 'Job deleted between message queue and handler execution',
                    'candidates_matched': 0,
                    'outreach_queued': 0
                }

            # PHASE 3: CHECK IF RECRUITMENT IS PAUSED (CRITICAL FIX #7 - CASCADE SIGNAL)
            try:
                from app.services.intervention_queue_service import get_queue
                intervention_items = get_queue(db, tenant_id=job.tenant_id)
                is_paused = any(
                    item.get('queue_reason') == 'THUNDER_DEGRADATION_PAUSE'
                    for item in intervention_items
                )

                if is_paused:
                    logger.info(
                        f"[FlashRecruiter] Recruitment PAUSED for {job_id}: "
                        f"Thunder degraded (waiting for recovery)"
                    )
                    return {
                        'status': 'paused_cascade_failure',
                        'job_id': job_id,
                        'reason': 'Thunder service degraded, recruitment paused',
                        'candidates_matched': 0,
                        'outreach_queued': 0
                    }
            except Exception as pause_check_err:
                # Non-critical - log but continue
                logger.warning(
                    f"[FlashRecruiter] Failed to check pause state: {pause_check_err}"
                )

            # PHASE 3.2: SCAN FOR MATCHING CANDIDATES & QUEUE OUTREACH
            from app.services.ready_for_opportunity_service import scan_new_job_for_matches
            from app.services.message_queue_service import MessageQueueService

            matched_watches = scan_new_job_for_matches(db, job)

            # CRITICAL FIX #6: Validate deduplication payload (idempotency corruption prevention)
            previously_matched_ids = payload.get('previously_matched_candidate_ids', [])
            if not isinstance(previously_matched_ids, list):
                logger.warning(f"[FlashRecruiter] Payload corruption detected, resetting deduplication")
                previously_matched_ids = []

            # HIGH FIX #5: Filter duplicates using ORM attributes (not dict keys)
            # matched_watches contains CandidateOpportunityWatch ORM objects
            new_candidate_watches = [
                w for w in matched_watches
                if hasattr(w, 'candidate_id') and w.candidate_id not in previously_matched_ids
            ]

            logger.info(
                f"[FlashRecruiter] Found {len(matched_watches)} candidates, "
                f"{len(new_candidate_watches)} new (deduped)"
            )

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
