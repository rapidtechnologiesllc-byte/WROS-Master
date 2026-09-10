"""Message Queue Service - Custom database-backed task queue."""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger(__name__)

QUEUE_TYPE_CANDIDATE = 'CANDIDATE_QUEUE'
QUEUE_TYPE_THUNDER = 'THUNDER_QUEUE'
QUEUE_TYPE_EMAIL = 'EMAIL_QUEUE'

DEFAULT_DELAY_SECONDS = 0
QUEUE_ITEM_RETRY_COUNT_INITIAL = 0


class MessageQueueService:
    """Queue async tasks to custom message queue system (database + Redis backend)."""

    @staticmethod
    def enqueue(
        task_name: str,
        task_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        delay_seconds: int = DEFAULT_DELAY_SECONDS
    ) -> Dict[str, Any]:
        """Queue a task to custom message queue. Uses database as primary store."""
        if not task_name:
            logger.error("Task name is required for enqueue")
            raise ValueError("Task name is required")

        data = data or {}
        task_id = task_id or str(uuid4())

        try:
            from app.models.channel_queue import ChannelQueueItem
            from app.core.database import SessionLocal

            db = SessionLocal()

            # ARCHITECT FIX: Support delayed message delivery
            from datetime import timedelta
            if delay_seconds > 0:
                status = 'SCHEDULED'
                scheduled_for = datetime.utcnow() + timedelta(seconds=delay_seconds)
            else:
                status = 'PENDING'
                scheduled_for = None

            # Create queue item in database
            queue_item = ChannelQueueItem(
                message_id=task_id,
                type=task_name,
                channel_type=QUEUE_TYPE_THUNDER if 'engage_candidate_with_thunder' in task_name.lower() or 'assign_thunder' in task_name.lower() else (QUEUE_TYPE_CANDIDATE if 'candidate' in task_name.lower() else QUEUE_TYPE_THUNDER),
                status=status,
                payload=data,
                retry_count=QUEUE_ITEM_RETRY_COUNT_INITIAL,
                created_at=datetime.utcnow(),
                scheduled_for=scheduled_for
            )

            db.add(queue_item)
            db.commit()

            logger.info(f"[QUEUE] Enqueued {task_name} (ID: {task_id})")

            return {
                "status": "queued",
                "message_id": task_id,
                "queue_item_id": queue_item.id if hasattr(queue_item, 'id') else task_id
            }

        except Exception as queue_error:
            logger.error(
                f"CRITICAL: Message queue failed for {task_name}: {queue_error}",
                exc_info=True
            )
            raise RuntimeError(f"Failed to queue task: {str(queue_error)}")
        finally:
            if 'db' in locals():
                db.close()
