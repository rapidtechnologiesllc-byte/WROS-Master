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
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)

# ARCHITECT FIX: Spartan Phalanx Formation Definition
# Formation Position: Flash = Position 1 (Alpha Wolf, Orchestrator)
# Neighbor: Thunder (Position 2, Candidate Outreach)
# Dependency: Flash queues recruitment work for Thunder to execute

NEIGHBOR_DEFINITION = {
    'position': 'Alpha Wolf (Orchestrator)',
    'position_number': 1,
    'name': 'Flash_Recruiter',
    'role': 'Autonomous recruitment orchestration (job → candidate matching → queue Thunder outreach)',
    'neighbor': {
        'position': 2,
        'name': 'Thunder',
        'role': 'Autonomous candidate outreach (SMS, Email, WhatsApp)',
        'success_metric': 'Message delivery + response rate',
        'failure_signal': 'Delivery failure, no responses, timeout'
    },
    'formation_threshold': 0.70,  # This position + neighbor combined must be > 70% healthy
    'escalation_contact': 'Platform On-Call',
    'escalation_action': 'Pause recruitment, debug Thunder, resume manually'
}

# ARCHITECT FIX: Spartan Phalanx Formation Thresholds
THUNDER_HEALTH_THRESHOLD = 0.70  # 70% success rate required (neighbor health)
FORMATION_INTEGRITY_THRESHOLD = 0.70  # Overall formation must be >70% healthy


class FlashRecruiterHandler:
    """Flash Recruiter - autonomous candidate matching and outreach orchestration."""

    @staticmethod
    def _check_thunder_health(db: Session) -> Dict[str, Any]:
        """
        ARCHITECT FIX: Neighbor health monitoring - Check if Thunder outreach is healthy.

        Returns: {
            'healthy': bool,
            'success_rate': float (0-1),
            'recent_messages': int,
            'completed': int,
            'failed': int
        }

        Checks: Thunder messages from last 4 hours
        Threshold: Success rate >= 70%
        """
        try:
            from datetime import datetime, timedelta
            from sqlalchemy import and_

            # Get Thunder messages from last 4 hours
            four_hours_ago = datetime.utcnow() - timedelta(hours=4)

            thunder_stats = db.query(
                __import__('sqlalchemy').func.count(__import__('app.models.channel_queue', fromlist=['ChannelQueueItem']).ChannelQueueItem.id).label('total'),
                __import__('sqlalchemy').func.count(
                    __import__('sqlalchemy').case(
                        (__import__('app.models.channel_queue', fromlist=['ChannelQueueItem']).ChannelQueueItem.status == 'COMPLETED', 1),
                    )
                ).label('completed')
            ).filter(
                and_(
                    __import__('app.models.channel_queue', fromlist=['ChannelQueueItem']).ChannelQueueItem.type.like('%thunder%'),
                    __import__('app.models.channel_queue', fromlist=['ChannelQueueItem']).ChannelQueueItem.updated_at >= four_hours_ago
                )
            ).first()

            total_messages = thunder_stats.total or 0
            completed_messages = thunder_stats.completed or 0

            # If no recent Thunder messages, assume healthy (nothing to measure)
            if total_messages == 0:
                return {
                    'healthy': True,
                    'success_rate': 1.0,
                    'recent_messages': 0,
                    'completed': 0,
                    'failed': 0,
                    'reason': 'No recent Thunder activity'
                }

            # Calculate success rate
            success_rate = completed_messages / total_messages
            failed_messages = total_messages - completed_messages

            is_healthy = success_rate >= THUNDER_HEALTH_THRESHOLD

            return {
                'healthy': is_healthy,
                'success_rate': success_rate,
                'recent_messages': total_messages,
                'completed': completed_messages,
                'failed': failed_messages,
                'reason': f'Thunder success rate {success_rate*100:.1f}%'
            }

        except Exception as e:
            logger.error(f"[FlashRecruiter] Failed to check Thunder health: {e}")
            # Fail safe: if we can't measure health, assume unhealthy (pause recruitment)
            return {
                'healthy': False,
                'success_rate': 0,
                'recent_messages': 0,
                'completed': 0,
                'failed': 0,
                'reason': f'Health check error: {str(e)}'
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

            # PHASE 2.5: CHECK NEIGHBOR (THUNDER) HEALTH - Spartan Phalanx Formation Check
            thunder_health = FlashRecruiterHandler._check_thunder_health(db)
            if not thunder_health['healthy']:
                logger.critical(
                    f"[FlashRecruiter] ⚠️ FORMATION INTEGRITY BROKEN - Thunder health {thunder_health['success_rate']*100:.1f}% "
                    f"(threshold: {THUNDER_HEALTH_THRESHOLD*100:.1f}%). Pausing recruitment for {job_id}"
                )

                # Queue escalation alert to ops
                try:
                    from app.services.message_queue_service import MessageQueueService
                    MQS = MessageQueueService
                    MQS.enqueue(
                        task_name='formation_integrity_escalation',
                        task_id=f"escalation_flash_{job_id}",
                        data={
                            'formation_component': 'Flash (Recruitment)',
                            'broken_neighbor': 'Thunder (Outreach)',
                            'job_id': job_id,
                            'job_title': job.jobTitle,
                            'thunder_success_rate': thunder_health['success_rate'],
                            'threshold': THUNDER_HEALTH_THRESHOLD,
                            'recent_messages': thunder_health['recent_messages'],
                            'completed': thunder_health['completed'],
                            'failed': thunder_health['failed'],
                            'action_required': 'Debug Thunder handler and resume recruitment manually',
                            'timestamp': __import__('datetime').datetime.utcnow().isoformat()
                        }
                    )
                    logger.info(f"[FlashRecruiter] Escalation queued for {job_id}")
                except Exception as esc_err:
                    logger.error(f"[FlashRecruiter] Failed to queue escalation: {esc_err}")

                # Return PAUSED status - don't continue with recruitment
                return {
                    'status': 'paused',
                    'job_id': job_id,
                    'job_title': job.jobTitle,
                    'reason': f'Formation integrity broken: Thunder health {thunder_health["success_rate"]*100:.1f}% < {THUNDER_HEALTH_THRESHOLD*100:.1f}%',
                    'candidates_matched': 0,
                    'outreach_queued': 0,
                    'formation_integrity': thunder_health
                }

            logger.info(f"[FlashRecruiter] ✅ Thunder health OK ({thunder_health['success_rate']*100:.1f}%), proceeding with recruitment")

            # PHASE 3: SCAN FOR MATCHING CANDIDATES & QUEUE OUTREACH
            from app.services.ready_for_opportunity_service import scan_new_job_for_matches
            from app.services.message_queue_service import MessageQueueService

            matched_watches = scan_new_job_for_matches(db, job)

            # ARCHITECT FIX: Deduplication - filter out candidates already matched in previous runs
            previously_matched_ids = payload.get('previously_matched_candidate_ids', [])
            new_candidate_watches = [w for w in matched_watches if w.get('candidate_id') not in previously_matched_ids]

            logger.info(
                f"[FlashRecruiter] Found {len(matched_watches)} matching candidates for {job_id}, "
                f"deduped to {len(new_candidate_watches)} new candidates"
            )

            # Track newly matched candidates for next run
            new_candidate_ids = [w.get('candidate_id') for w in new_candidate_watches if w.get('candidate_id')]
            updated_previously_matched = previously_matched_ids + new_candidate_ids

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
                        'candidates_matched': len(new_candidate_watches),
                        'candidates_deduped': len(matched_watches) - len(new_candidate_watches),
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

                    # Prepare next run payload with updated deduplication list
                    next_payload = payload.copy()
                    next_payload['previously_matched_candidate_ids'] = updated_previously_matched

                    # Schedule next recruitment run in 4 hours (14400 seconds)
                    next_recruiter_msg_id = MessageQueueService.enqueue(
                        task_name='flash_recruiter',
                        task_id=f"{job_id}_next",
                        data=next_payload,
                        delay_seconds=14400  # 4 hours
                    )
                    logger.info(
                        f"[FlashRecruiter] Scheduled next run for {job_id} in 4 hours: "
                        f"message_id={next_recruiter_msg_id}, "
                        f"tracking {len(updated_previously_matched)} previously matched"
                    )
                except Exception as schedule_err:
                    logger.warning(f"[FlashRecruiter] Failed to schedule next run: {schedule_err}")

            logger.info(
                f"[FlashRecruiter] ✅ Completed recruitment for {job_id}: "
                f"{len(new_candidate_watches)} new candidates matched, "
                f"{len(matched_watches) - len(new_candidate_watches)} deduped"
            )

            return {
                'status': 'success',
                'job_id': job_id,
                'job_title': job.jobTitle,
                'candidates_matched': len(matched_watches),
                'candidates_new': len(new_candidate_watches),
                'candidates_deduped': len(matched_watches) - len(new_candidate_watches),
                'outreach_queued': len(new_candidate_watches),
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

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate recruitment results and candidates were matched."""
        if not result:
            raise ValueError(f"Invalid recruitment result: {result}")

        status = result.get('status')
        if status not in ['success', 'skipped', 'paused_cascade_failure', 'job_deleted']:
            raise ValueError(f"Invalid recruitment status: {status}")

        job_id = result.get('job_id')
        if not job_id:
            raise ValueError(f"Result missing job_id")

        try:
            # VERIFY 1: Job still exists (race condition check)
            from app.models.user import Jobs
            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
            if not job:
                # This is expected if job was deleted, but validate it's in result
                if status == 'job_deleted':
                    logger.info(f"Job {job_id} deleted (expected for job_deleted status)")
                else:
                    raise ValueError(f"Job {job_id} not found but status is {status}")

            # VERIFY 2: Match counts are valid (no negative numbers)
            candidates_matched = result.get('candidates_matched', 0)
            outreach_queued = result.get('outreach_queued', 0)

            if candidates_matched < 0 or outreach_queued < 0:
                raise ValueError(
                    f"Invalid match counts: matched={candidates_matched}, queued={outreach_queued}"
                )

            # VERIFY 3: For success status, verify at least some candidates were considered
            if status == 'success' and candidates_matched == 0:
                logger.warning(f"Job {job_id}: no candidates matched (may be normal for niche role)")

            logger.info(f"[FlashRecruiter] ✅ Validated: job={job_id}, status={status}, matched={candidates_matched}")

        except ValueError:
            raise  # Non-retryable

        except Exception as e:
            logger.error(f"[FlashRecruiter] RETRYABLE validation error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        MAX_RETRIES = 3
        return message.retry_count < MAX_RETRIES

    @staticmethod
    def on_retry(message: Any, error: str, db: Session) -> None:
        """Schedule message for retry."""
        from datetime import datetime, timedelta
        try:
            db.rollback()
            message.retry_count += 1
            message.error = error[:1000] if error else "Unknown error"
            message.next_retry_at = datetime.utcnow() + timedelta(minutes=15)
            db.commit()
            logger.info(f"[FlashRecruiter] Scheduled retry: retry_count={message.retry_count}")
        except Exception as e:
            db.rollback()
            logger.error(f"[FlashRecruiter] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation passes."""
        from datetime import datetime
        try:
            FlashRecruiterHandler.validate(message, result, db)
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result
            db.commit()
            logger.info(f"[FlashRecruiter] ✅ Message marked COMPLETED: job={result.get('job_id')}")
        except ValueError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"[FlashRecruiter] Failed to mark success: {e}", exc_info=True)
            raise RuntimeError(f"Failed to mark success: {str(e)}") from e

    @staticmethod
    def on_failed(message: Any, final_error: str, db: Session) -> None:
        """Mark message as FAILED after all retries exhausted."""
        from datetime import datetime
        try:
            db.rollback()
            message.status = "FAILED"
            message.error = final_error[:1000] if final_error else "Unknown error"
            message.completed_at = datetime.utcnow()
            db.commit()
            logger.error(f"[FlashRecruiter] Message FAILED: {final_error}")
        except Exception as e:
            db.rollback()
            logger.error(f"[FlashRecruiter] Failed to mark as FAILED: {e}", exc_info=True)
            raise
