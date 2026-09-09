"""
Queue Doctor Service - Queue Health & Diagnostics

Tracks message processing lifecycle, detects stalled messages,
measures performance, and integrates with pause/resume controls.
"""
import logging
import uuid
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
