"""Cascade Failure Signal Handler - Handles inter-component health signals (CRITICAL FIX #7)

When Thunder's success rate drops below 70%, Flash should pause new recruitment.
When Thunder recovers (> 80%), Flash can resume.
"""
import logging
from typing import Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class CascadeFailureSignalHandler:
    """Handle cascade failure signals between Thunder and Flash"""

    # Configuration
    DEGRADATION_THRESHOLD = 0.70  # 70% success rate = degraded
    RECOVERY_THRESHOLD = 0.80     # 80% success rate = recovered

    @staticmethod
    @time_bound(timeout_seconds=10)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process cascade failure signal from Thunder

        Args:
            message: ChannelQueueItem with type='cascade_failure_signal'
            db: SQLAlchemy session

        Returns:
            {
                'status': 'success',
                'action_taken': 'pause_recruitment' | 'resume_recruitment' | 'continue_normal',
                'thunder_success_rate': float,
                'recruitment_state': 'paused' | 'resumed' | 'unchanged'
            }

        Actions:
        - If success_rate < 70%: Pause Flash recruitment
        - If success_rate > 80%: Resume Flash recruitment
        - Alert ops if success_rate < 50% (critical degradation)
        """
        try:
            payload = message.payload or {}

            # Parse signal
            signal_type = payload.get('signal_type')
            thunder_health = payload.get('thunder_health', {})
            success_rate = thunder_health.get('success_rate', 0.0)
            job_id = payload.get('job_id')
            tenant_id = payload.get('tenant_id', 'system')

            logger.info(
                f"[CascadeSignal] Received: {signal_type}, "
                f"Thunder health: {success_rate:.1%}, job: {job_id}"
            )

            # PHASE 1: DETERMINE ACTION
            if success_rate < 0.5:
                # CRITICAL: Thunder is severely broken
                action = 'alert_ops_and_pause'
                priority = 'CRITICAL'
                reason = f'Thunder severely degraded ({success_rate:.1%})'
            elif success_rate < 0.7:
                # WARNING: Thunder is degraded, pause but don't alert yet
                action = 'pause_recruitment'
                priority = 'HIGH'
                reason = f'Thunder degraded ({success_rate:.1%})'
            elif success_rate >= 0.8:
                # RECOVERY: Thunder recovered, resume recruitment
                action = 'resume_recruitment'
                priority = 'MEDIUM'
                reason = f'Thunder recovered ({success_rate:.1%})'
            else:
                # NORMAL: No action needed
                action = 'continue_normal'
                priority = 'LOW'
                reason = 'Thunder health normal'

            logger.info(
                f"[CascadeSignal] Determined action: {action} "
                f"(priority: {priority})"
            )

            # PHASE 2: UPDATE FLASH STATE VIA INTERVENTION QUEUE
            if action in ['pause_recruitment', 'alert_ops_and_pause']:
                try:
                    from app.services.intervention_queue_service import add_to_queue
                    from app.models.recruiter_intervention_queue import (
                        PRIORITY_CRITICAL, PRIORITY_HIGH
                    )

                    add_to_queue(
                        db=db,
                        candidate_id='SYSTEM',  # Affects all, not candidate-specific
                        tenant_id=tenant_id,
                        queue_reason='THUNDER_DEGRADATION_PAUSE',
                        reason_detail=reason,
                        priority=PRIORITY_CRITICAL if action == 'alert_ops_and_pause' else PRIORITY_HIGH,
                        commit=True
                    )
                    logger.warning(
                        f"[CascadeSignal] Flash recruitment paused: {reason}"
                    )
                except Exception as queue_err:
                    logger.error(
                        f"[CascadeSignal] Failed to add pause to intervention queue: {queue_err}",
                        exc_info=True
                    )
                    raise RuntimeError(f"Failed to pause recruitment: {str(queue_err)}")

            elif action == 'resume_recruitment':
                try:
                    from app.services.intervention_queue_service import resolve_queue_items

                    resolve_queue_items(
                        db=db,
                        candidate_id='SYSTEM',
                        tenant_id=tenant_id,
                        reasons=['THUNDER_DEGRADATION_PAUSE'],
                        note=f'Thunder recovered: {success_rate:.1%}',
                        commit=True
                    )
                    logger.info(
                        f"[CascadeSignal] Flash recruitment resumed: "
                        f"Thunder recovered to {success_rate:.1%}"
                    )
                except Exception as resolve_err:
                    logger.warning(
                        f"[CascadeSignal] Failed to resolve pause items: {resolve_err}"
                    )
                    # Non-fatal - continue

            # PHASE 3: ALERT OPS IF CRITICAL
            if action == 'alert_ops_and_pause':
                try:
                    from app.services.message_queue_service import MessageQueueService

                    MessageQueueService.enqueue(
                        task_name='ops_alert_thunder_critical',
                        data={
                            'alert_type': 'THUNDER_CRITICAL_DEGRADATION',
                            'success_rate': success_rate,
                            'sample_size': thunder_health.get('sample_size'),
                            'failed_count': thunder_health.get('failed'),
                            'recommendation': (
                                'Check Thunder service health, database connection, '
                                'and error logs. Recruitment paused until recovery.'
                            ),
                            'timestamp': datetime.utcnow().isoformat()
                        }
                    )
                    logger.info("[CascadeSignal] Ops alert queued")
                except Exception as alert_err:
                    logger.warning(f"[CascadeSignal] Failed to queue ops alert: {alert_err}")

            return {
                'status': 'success',
                'action_taken': action,
                'thunder_success_rate': success_rate,
                'recruitment_state': (
                    'paused'
                    if action in ['pause_recruitment', 'alert_ops_and_pause']
                    else 'resumed'
                    if action == 'resume_recruitment'
                    else 'unchanged'
                )
            }

        except Exception as e:
            logger.error(f"[CascadeSignal] Handler failed: {e}", exc_info=True)
            raise RuntimeError(f"Cascade signal processing failed: {str(e)}")

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate cascade signal and pause/resume action was recorded."""
        if not result or result.get('status') != 'success':
            raise ValueError(f"Invalid cascade signal result: {result}")

        if result.get('action_taken') not in ['pause_recruitment', 'resume_recruitment', 'continue_normal', 'alert_ops_and_pause']:
            raise ValueError(f"Invalid cascade action: {result.get('action_taken')}")

        # Verify pause was recorded if action is pause
        if result.get('action_taken') == 'pause_recruitment':
            try:
                from app.services.intervention_queue_service import get_queue_items
                queue_items = get_queue_items(db, reason='THUNDER_DEGRADATION_PAUSE')
                if not queue_items:
                    logger.warning(f"[CascadeFailure] Pause action taken but not recorded in intervention queue")
            except Exception as check_err:
                logger.warning(f"[CascadeFailure] Could not verify pause recording: {check_err}")

        logger.info(f"[CascadeFailure] ✅ Validated: action={result.get('action_taken')}, recruitment_state={result.get('recruitment_state')}")

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
            logger.info(f"[CascadeFailure] Scheduled retry: retry_count={message.retry_count}")
        except Exception as e:
            db.rollback()
            logger.error(f"[CascadeFailure] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation passes."""
        from datetime import datetime
        try:
            CascadeFailureSignalHandler.validate(message, result, db)
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result
            db.commit()
            logger.info(f"[CascadeFailure] ✅ Message marked COMPLETED: action={result.get('action_taken')}")
        except ValueError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"[CascadeFailure] Failed to mark success: {e}", exc_info=True)
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
            logger.error(f"[CascadeFailure] Message FAILED: {final_error}")
        except Exception as e:
            db.rollback()
            logger.error(f"[CascadeFailure] Failed to mark as FAILED: {e}", exc_info=True)
            raise
