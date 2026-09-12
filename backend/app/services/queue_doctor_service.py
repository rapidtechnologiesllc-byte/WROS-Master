"""
Queue Doctor Service - Queue Health & Diagnostics

Tracks message processing lifecycle, detects stalled messages,
measures performance, and integrates with pause/resume controls.
"""
import logging
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from app.models.queue_doctor import QueueDoctorState
from app.models.channel_queue import ChannelQueueItem
from app.services.thunder_pause_service import is_thunder_paused

logger = logging.getLogger(__name__)


class QueueDoctorService:
    """Diagnostics and health tracking for queue processing."""

    @staticmethod
    def start_tracking(message: ChannelQueueItem, db: Session) -> QueueDoctorState:
        """Create tracking record when message processing starts."""
        doctor_state = QueueDoctorState(
            id=f"qds-{uuid.uuid4().hex[:12]}",
            message_id=message.id,
            message_type=message.type,
            queued_at=message.created_at,
            candidate_id=message.payload.get('candidate_id') if message.payload else None,
            status="PROCESSING",
        )
        db.add(doctor_state)
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"[QueueDoctor] Failed to create tracking: {e}")
        return doctor_state

    @staticmethod
    def complete_tracking(doctor_state: QueueDoctorState, message: ChannelQueueItem, db: Session):
        """Mark message processing complete."""
        now = datetime.utcnow()
        doctor_state.completed_at = now
        doctor_state.status = message.status
        doctor_state.error_message = message.error

        if doctor_state.started_at:
            doctor_state.processing_time_ms = int((now - doctor_state.started_at).total_seconds() * 1000)

        db.add(doctor_state)
        try:
            db.commit()
            logger.info(f"[QueueDoctor] Completed tracking for {message.id}: {message.status} ({doctor_state.processing_time_ms}ms)")
        except Exception as e:
            db.rollback()
            logger.error(f"[QueueDoctor] Failed to update tracking: {e}")

    @staticmethod
    def detect_stalled_messages(db: Session, stalled_threshold_minutes: int = 30) -> list:
        """Find messages queued but not processed for too long."""
        stalled_time = datetime.utcnow() - timedelta(minutes=stalled_threshold_minutes)

        stalled = db.query(QueueDoctorState).filter(
            QueueDoctorState.queued_at < stalled_time,
            QueueDoctorState.completed_at.is_(None),
            QueueDoctorState.is_stalled == False
        ).all()

        for doc_state in stalled:
            doc_state.is_stalled = True
            doc_state.status = "STALLED"

        if stalled:
            db.commit()
            logger.warning(f"[QueueDoctor] Found {len(stalled)} stalled messages")

        return stalled

    @staticmethod
    def get_queue_health(db: Session) -> Dict[str, Any]:
        """Get overall queue health metrics."""
        total = db.query(QueueDoctorState).count()
        completed = db.query(QueueDoctorState).filter(QueueDoctorState.status == "COMPLETED").count()
        failed = db.query(QueueDoctorState).filter(QueueDoctorState.status == "FAILED").count()
        stalled = db.query(QueueDoctorState).filter(QueueDoctorState.is_stalled == True).count()

        # Avg processing time (completed messages only)
        completed_records = db.query(QueueDoctorState).filter(
            QueueDoctorState.status == "COMPLETED",
            QueueDoctorState.processing_time_ms.isnot(None)
        ).all()

        avg_processing_ms = 0
        if completed_records:
            avg_processing_ms = sum(r.processing_time_ms for r in completed_records) / len(completed_records)

        return {
            "total_messages": total,
            "completed": completed,
            "failed": failed,
            "stalled": stalled,
            "success_rate": (completed / total * 100) if total > 0 else 0,
            "avg_processing_ms": int(avg_processing_ms),
            "queue_paused": is_thunder_paused(db),
        }

    @staticmethod
    def record_healing(doctor_state: QueueDoctorState, strategy: str, succeeded: bool, db: Session):
        """Record data healing attempt."""
        doctor_state.healing_attempted = True
        doctor_state.healing_succeeded = succeeded
        doctor_state.healing_strategy = strategy
        db.add(doctor_state)
        db.commit()

    @staticmethod
    def record_retry(message: ChannelQueueItem, db: Session):
        """Record that a message is being retried."""
        doctor_state = db.query(QueueDoctorState).filter(
            QueueDoctorState.message_id == message.id
        ).first()

        if doctor_state:
            doctor_state.attempt_count = (message.retry_count or 0) + 1
            doctor_state.status = "PENDING"  # Reset to pending for retry
            db.add(doctor_state)
            db.commit()
            logger.info(f"[QueueDoctor] Retry {message.id}: attempt {doctor_state.attempt_count}/{doctor_state.max_attempts}")

    @staticmethod
    def diagnose_stuck_message(
        message: ChannelQueueItem,
        doctor_state: QueueDoctorState,
        db: Session
    ) -> Dict[str, Any]:
        """
        Phase 3: Analyze why a message is stuck and calculate recovery safety score.

        Returns comprehensive diagnosis:
        {
            'error_classification': ErrorClassification,
            'safety_score': 0-100,
            'root_cause': str,
            'recommended_action': str,
            'diagnostic_summary': str
        }
        """
        from app.services.stale_message_detector import StaleMessageDetector

        try:
            # Calculate message age
            now = datetime.utcnow()
            message_age_seconds = int((now - message.created_at).total_seconds()) if message.created_at else 0

            # Get diagnosis
            diagnosis = StaleMessageDetector.diagnose_message(
                message_id=str(message.id),
                error_message=message.error or "",
                handler_duration_ms=message.handler_duration_ms or 0,
                retry_count=message.retry_count or 0,
                message_age_seconds=message_age_seconds,
            )

            # Record diagnosis in doctor state
            doctor_state.diagnosed_at = now
            doctor_state.diagnosis_classification = diagnosis['error_classification']
            doctor_state.safety_score = diagnosis['safety_score']
            doctor_state.root_cause = diagnosis['root_cause']
            doctor_state.recommended_action = diagnosis['recommended_action']

            db.add(doctor_state)
            db.commit()

            logger.warning(
                f"[QueueDoctor] DIAGNOSIS {message.id}: {diagnosis['error_classification']} "
                f"(safety_score={diagnosis['safety_score']}) - {diagnosis['root_cause']}"
            )

            return diagnosis

        except Exception as e:
            logger.error(f"[QueueDoctor] Diagnosis failed for {message.id}: {e}", exc_info=True)
            db.rollback()
            return {
                'error_classification': 'UNKNOWN',
                'safety_score': 0,
                'root_cause': f'Diagnosis failed: {str(e)}',
                'recommended_action': 'Escalate to ops',
                'diagnostic_summary': f'Failed to diagnose message {message.id}'
            }

    @staticmethod
    def attempt_safe_recovery(
        diagnosis: Dict[str, Any],
        message: ChannelQueueItem,
        doctor_state: QueueDoctorState,
        db: Session
    ) -> Dict[str, Any]:
        """
        Phase 3: Attempt safe recovery if diagnosis indicates it's safe (safety_score >= 80).

        Returns recovery result:
        {
            'action_taken': RecoveryAction or None,
            'success': bool,
            'reason': str
        }
        """
        from app.services.recovery_engine import RecoveryEngine

        try:
            # Check if safe to recover
            safety_score = diagnosis.get('safety_score', 0)
            if safety_score < 80:
                logger.info(f"[QueueDoctor] Recovery skipped for {message.id}: safety_score {safety_score} < 80")
                return {
                    'action_taken': None,
                    'success': False,
                    'reason': f'Safety score {safety_score}/100 below minimum 80 for auto-recovery'
                }

            # Attempt recovery
            recovery_result = RecoveryEngine.attempt_recovery(
                error_classification=diagnosis.get('error_classification'),
                safety_score=safety_score,
                message=message,
                doctor_state=doctor_state,
                db=db
            )

            logger.info(f"[QueueDoctor] Recovery {recovery_result['action_taken']}: {recovery_result['reason']}")

            return recovery_result

        except Exception as e:
            logger.error(f"[QueueDoctor] Recovery execution failed for {message.id}: {e}", exc_info=True)
            db.rollback()
            return {
                'action_taken': None,
                'success': False,
                'reason': f'Recovery execution failed: {str(e)}'
            }

    @staticmethod
    def escalate_to_ops(
        diagnosis: Dict[str, Any],
        message: ChannelQueueItem,
        recovery_result: Dict[str, Any],
        doctor_state: QueueDoctorState,
        db: Session
    ) -> str:
        """
        Phase 3: Create ops alert task so ops team sees the issue on UI dashboard.

        Returns: ops_alert_task_id
        """
        try:
            from app.services.message_queue_service import MessageQueueService

            # Build alert payload with full diagnosis
            now = datetime.utcnow()
            message_age_seconds = int((now - message.created_at).total_seconds()) if message.created_at else 0

            ops_alert_data = {
                'alert_type': 'stuck_message_diagnosis',
                'message_id': str(message.id),
                'message_type': message.type,
                'error_classification': diagnosis.get('error_classification', 'UNKNOWN'),
                'safety_score': diagnosis.get('safety_score', 0),
                'root_cause': diagnosis.get('root_cause', ''),
                'recommended_action': diagnosis.get('recommended_action', ''),
                'recovery_attempted': recovery_result.get('action_taken') is not None,
                'recovery_success': recovery_result.get('success', False),
                'recovery_reason': recovery_result.get('reason', ''),
                'time_in_processing_seconds': message_age_seconds,
                'retry_count': message.retry_count or 0,
                'handler_duration_ms': message.handler_duration_ms or 0,
                'error_message': (message.error or '')[:500],  # Truncate for safety
                'diagnostic_summary': diagnosis.get('diagnostic_summary', ''),
                'timestamp': now.isoformat()
            }

            # Determine next action based on diagnosis
            if recovery_result.get('success'):
                next_action = 'auto_recovery_executed'
            elif diagnosis.get('safety_score', 0) >= 60:
                next_action = 'manual_intervention_recommended'
            else:
                next_action = 'manual_intervention_required'

            ops_alert_data['next_action'] = next_action

            # Queue as ops_alert task (shows on dashboard)
            ops_alert_task_id = f"ops_alert_{uuid.uuid4().hex[:12]}"
            MessageQueueService.enqueue(
                task_name='ops_alert',
                task_id=ops_alert_task_id,
                data=ops_alert_data
            )

            # Record escalation in doctor state
            doctor_state.escalated_at = now
            doctor_state.escalation_reason = f"Stuck message diagnosis: {diagnosis.get('error_classification')}"
            doctor_state.ops_alert_task_id = ops_alert_task_id

            db.add(doctor_state)
            db.commit()

            logger.critical(
                f"[QueueDoctor] ESCALATED {message.id} to ops: {next_action} "
                f"(alert task: {ops_alert_task_id})"
            )

            return ops_alert_task_id

        except Exception as e:
            logger.error(f"[QueueDoctor] Escalation failed for {message.id}: {e}", exc_info=True)
            db.rollback()
            raise
