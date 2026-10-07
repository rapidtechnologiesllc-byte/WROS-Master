"""
Flash Queue Metrics Reporter - 5-Minute Reporting for Orchestrator

Provides queue health metrics for Flash orchestration engine every 5 minutes.
Reports: queue depth, processing rate, stalled messages, health status.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role_template_permission
from app.core.permission_registry import Permissions
from app.models.queue_doctor import QueueDoctorState
from app.services.queue_doctor_service import QueueDoctorService
from app.utils.agent_logger import log_agent_execution as record_agent_run

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/flash", tags=["Flash Queue Metrics"])


@router.get(
    "/queue-health-pulse",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role_template_permission("message-queue", "can_view"))]
)
def get_queue_health_pulse(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    5-minute queue health pulse for Flash orchestrator.

    Reports:
    - Queue depth (pending messages)
    - Processing rate (messages/min last 5 min)
    - Error rate (failed / total)
    - Stalled messages
    - Success rate
    - Avg processing time
    """
    try:
        # Phase 4: Get queue health
        health = QueueDoctorService.get_queue_health(db)

        # Detect stalled messages
        stalled = QueueDoctorService.detect_stalled_messages(db, stalled_threshold_minutes=30)

        # Get last 5-minute processing rate
        five_min_ago = datetime.utcnow() - timedelta(minutes=5)
        recent_completed = db.query(QueueDoctorState).filter(
            QueueDoctorState.status == "COMPLETED",
            QueueDoctorState.completed_at >= five_min_ago
        ).count()

        recent_failed = db.query(QueueDoctorState).filter(
            QueueDoctorState.status == "FAILED",
            QueueDoctorState.completed_at >= five_min_ago
        ).count()

        processing_rate_per_min = (recent_completed + recent_failed) / 5.0

        # Current pending
        from app.models.channel_queue import ChannelQueueItem
        pending = db.query(ChannelQueueItem).filter(
            ChannelQueueItem.status == "PENDING"
        ).count()

        # Compile health report
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "queue_depth": pending,
            "total_messages_processed": health["total_messages"],
            "completed": health["completed"],
            "failed": health["failed"],
            "stalled_count": len(stalled),
            "success_rate": health["success_rate"],
            "error_rate": (health["failed"] / health["total_messages"] * 100) if health["total_messages"] > 0 else 0,
            "avg_processing_ms": health["avg_processing_ms"],
            "processing_rate_per_min": round(processing_rate_per_min, 2),
            "queue_paused": health["queue_paused"],
            "status": "healthy" if health["success_rate"] > 90 and len(stalled) == 0 else "degraded",
        }

        # Write to performance store for Flash tracking
        try:
            record_agent_run(
                db,
                agent_name="MessageQueueWorker",
                action_taken="health_pulse",
                tenant_id="system",
                action_data={
                    "queue_depth": pending,
                    "processing_rate": round(processing_rate_per_min, 2),
                    "stalled_count": len(stalled),
                    "success_rate": health["success_rate"],
                    "error_rate": report["error_rate"],
                }
            )
        except Exception as perf_err:
            logger.warning(f"[Flash] Failed to write performance event: {perf_err}")

        logger.info(f"[Flash] Queue health pulse: {report['status']} (depth={pending}, rate={round(processing_rate_per_min, 2)}/min)")
        return report

    except Exception as e:
        logger.error(f"[Flash] Failed to generate health pulse: {e}", exc_info=True)
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "error",
            "error": str(e),
        }


