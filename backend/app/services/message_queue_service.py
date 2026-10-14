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


# Queue items that have not finished yet (an idempotency key matches these, not finished ones)
IN_FLIGHT_STATUSES = ("PENDING", "SCHEDULED", "PROCESSING", "WAITING_FOR_SLM")


class MessageQueueService:
    """Queue async tasks to custom message queue system (database + Redis backend)."""

    MAX_PAYLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10MB max payload (HIGH FIX #13: Prevent OOM crashes)

    @staticmethod
    def enqueue(
        task_name: str,
        task_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        delay_seconds: int = DEFAULT_DELAY_SECONDS,
        trace_id: Optional[str] = None,  # HIGH FIX #4: Correlation ID for tracing
        idempotency_key: Optional[str] = None,
        status: Optional[str] = None,  # Allow overriding default status (e.g., 'WAITING_FOR_SLM')
        tenant_id: Optional[int] = None  # delivery routing: given, else data["tenant_id"], else the only tenant
    ) -> Dict[str, Any]:
        """Queue a task to custom message queue. Uses database as primary store."""
        if not task_name:
            logger.error("Task name is required for enqueue")
            raise ValueError("Task name is required")

        data = data or {}
        task_id = task_id or str(uuid4())
        if tenant_id is None:
            tenant_id = data.get("tenant_id")
        if tenant_id is None:
            from app.core.database import SessionLocal
            from app.core.tenant_context import sole_tenant_id
            lookup = SessionLocal()
            try:
                tenant_id = sole_tenant_id(lookup)
            finally:
                lookup.close()
        tenant_id = int(tenant_id)
        trace_id = trace_id or str(uuid4())  # Generate trace_id if not provided
        data['__trace_id'] = trace_id  # Embed trace_id in payload for propagation

        # HIGH FIX #13: Validate payload size to prevent OOM crashes
        import json as json_module
        payload_json = json_module.dumps(data)
        payload_size = len(payload_json.encode('utf-8'))
        if payload_size > MessageQueueService.MAX_PAYLOAD_SIZE_BYTES:
            logger.error(
                f"[QUEUE] Payload too large for {task_name}: "
                f"{payload_size / (1024*1024):.1f}MB > {MessageQueueService.MAX_PAYLOAD_SIZE_BYTES / (1024*1024):.1f}MB limit"
            )
            raise ValueError(
                f"Payload exceeds maximum size ({payload_size} > {MessageQueueService.MAX_PAYLOAD_SIZE_BYTES} bytes)"
            )

        try:
            from app.models.channel_queue import ChannelQueueItem
            from app.core.database import SessionLocal

            db = SessionLocal()

            # ARCHITECT FIX: Support delayed message delivery
            # Also support explicit status override (e.g., 'WAITING_FOR_SLM' for Thunder engagement)
            from datetime import timedelta
            if status:
                # Use provided status (e.g., 'WAITING_FOR_SLM')
                queue_status = status
                scheduled_for = None
            elif delay_seconds > 0:
                queue_status = 'SCHEDULED'  # uppercase for consistency with worker queries
                scheduled_for = datetime.utcnow() + timedelta(seconds=delay_seconds)
            else:
                queue_status = 'PENDING'  # uppercase for consistency with worker queries
                scheduled_for = None

            # ARCHITECT FIX: Populate idempotency key if provided (enables duplicate detection)
            # If not provided, generate one from task_id (ensures at least basic idempotency)
            if not idempotency_key:
                idempotency_key = f"{task_name}:{task_id}"

            # The same request while an earlier one is still in flight is the same message: return
            # it instead of queueing a duplicate (a double-clicked "Add candidate", a retried API
            # call). Once that message has finished, the same key queues again normally.
            existing = (db.query(ChannelQueueItem)
                        .filter(ChannelQueueItem.idempotency_key == idempotency_key,
                                ChannelQueueItem.status.in_(IN_FLIGHT_STATUSES))
                        .order_by(ChannelQueueItem.created_at.asc()).first())
            if existing is not None:
                logger.info(f"[QUEUE] {task_name}: duplicate of in-flight {existing.id} ({idempotency_key}) -- not queued again")
                return {"status": "queued", "task_id": existing.id, "message_id": existing.message_id or existing.id,
                        "queue_item_id": existing.id, "deduplicated": True}

            # Create queue item in database
            queue_item = ChannelQueueItem(
                id=task_id,  # Use task_id as primary key for tracking
                message_id=task_id,
                tenant_id=tenant_id,  # PHASE 2: Set tenant context for delivery_factory routing
                type=task_name,
                channel_type=QUEUE_TYPE_THUNDER if 'engage_candidate_with_thunder' in task_name.lower() or 'assign_thunder' in task_name.lower() else (QUEUE_TYPE_CANDIDATE if 'candidate' in task_name.lower() else QUEUE_TYPE_THUNDER),
                status=queue_status,
                payload=data,
                retry_count=QUEUE_ITEM_RETRY_COUNT_INITIAL,
                created_at=datetime.utcnow(),
                scheduled_for=scheduled_for,
                idempotency_key=idempotency_key
            )

            # HIGH FIX #4: Store trace_id for end-to-end tracing (if column exists)
            if hasattr(queue_item, 'trace_id'):
                queue_item.trace_id = trace_id

            db.add(queue_item)
            db.commit()

            logger.info(f"[QUEUE] Enqueued {task_name} (ID: {task_id})")

            return {
                "status": "queued",
                "task_id": task_id,
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
                try:
                    db.close()
                except Exception as close_err:
                    logger.error(f"[QUEUE] Failed to close DB connection for {task_name}: {close_err}", exc_info=True)
