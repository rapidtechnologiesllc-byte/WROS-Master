"""Message Queue Service - Production-grade task queueing with Celery fallback."""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger(__name__)


CELERY_TASK_PROCESS_CANDIDATE = 'process_candidate'
CELERY_TASK_ASSIGN_THUNDER = 'assign_thunder_agent'
CELERY_TASK_SEND_NOTIFICATION = 'send_notification'
CELERY_TASK_CREATE_CANDIDATE = 'create_candidate'

QUEUE_TYPE_CANDIDATE = 'CANDIDATE_QUEUE'
QUEUE_TYPE_THUNDER = 'THUNDER_QUEUE'
QUEUE_TYPE_EMAIL = 'EMAIL_QUEUE'

DEFAULT_DELAY_SECONDS = 0
QUEUE_ITEM_RETRY_COUNT_INITIAL = 0


class MessageQueueService:
    """Queue async tasks to Celery/Redis for background processing."""

    @staticmethod
    def enqueue(
        task_name: str,
        task_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        delay_seconds: int = DEFAULT_DELAY_SECONDS
    ) -> Dict[str, Any]:
        """Queue a task to Celery ONLY. Fails hard if Redis/Celery unavailable.

        NEVER fall back to database - that masks infrastructure failures.
        If Celery is down, we MUST FAIL and alert, not silently queue to database.
        """
        if not task_name:
            logger.error("Task name is required for enqueue")
            raise ValueError("Task name is required")

        data = data or {}

        try:
            return MessageQueueService._enqueue_celery(
                task_name, task_id, data, delay_seconds
            )
        except Exception as celery_error:
            # FAIL HARD - do not fall back to database
            error_msg = str(celery_error).lower()
            is_connection_error = any(
                key in error_msg
                for key in ["connection refused", "connect timeout", "unreachable", "redis"]
            )

            logger.error(
                f"CRITICAL: Celery queue failed for {task_name}: {celery_error}",
                exc_info=True
            )

            if is_connection_error:
                error_detail = (
                    "Redis broker is not running on localhost:6379. "
                    "Please start Redis: redis-server --port 6379"
                )
                logger.error(f"Redis/Celery infrastructure is DOWN: {error_detail}")
                raise RuntimeError(error_detail)
            else:
                logger.error("Redis/Celery infrastructure is DOWN - this is a critical system failure")
                raise RuntimeError(
                    f"Message queue unavailable (Celery/Redis down): {str(celery_error)}"
                )

    @staticmethod
    def _enqueue_celery(
        task_name: str,
        task_id: Optional[str],
        data: Dict[str, Any],
        delay_seconds: int
    ) -> Dict[str, Any]:
        """Enqueue task to Celery Redis backend AND log to database for dashboard visibility."""
        try:
            from app.celery_app import app
            from app.tasks.candidate_tasks import process_candidate, assign_thunder_agent
            from app.tasks.notification_tasks import send_notification
            from app.models.channel_queue import ChannelQueueItem
            from app.core.database import SessionLocal
        except ImportError as import_error:
            logger.error(f"Failed to import Celery or database models: {import_error}", exc_info=True)
            raise

        task = None
        db = None

        try:
            if task_name == CELERY_TASK_CREATE_CANDIDATE:
                candidate_email = data.get('candidate_email')
                tenant_id = data.get('tenant_id', 1)
                task = process_candidate.apply_async(
                    args=[data, tenant_id],
                    countdown=delay_seconds,
                    task_id=task_id
                )

            elif task_name == CELERY_TASK_PROCESS_CANDIDATE:
                candidate_id = data.get('candidate_id')
                tenant_id = data.get('tenant_id', 1)
                task = process_candidate.apply_async(
                    args=[candidate_id, tenant_id],
                    countdown=delay_seconds,
                    task_id=task_id
                )

            elif task_name == CELERY_TASK_ASSIGN_THUNDER:
                candidate_id = data.get('candidate_id')
                job_id = data.get('job_id')
                tenant_id = data.get('tenant_id', 1)
                task = assign_thunder_agent.apply_async(
                    args=[candidate_id, job_id, tenant_id],
                    countdown=delay_seconds,
                    task_id=task_id
                )

            elif task_name == CELERY_TASK_SEND_NOTIFICATION:
                notification_type = data.get('notification_type', 'email')
                recipient_id = data.get('recipient_id')
                notification_data = data.get('data', {})
                task = send_notification.apply_async(
                    args=[notification_type, recipient_id, notification_data],
                    countdown=delay_seconds,
                    task_id=task_id
                )

            else:
                from app.celery_app import app as celery_app
                celery_task = celery_app.tasks.get(task_name)
                if not celery_task:
                    logger.error(f"Unknown task: {task_name}")
                    raise ValueError(f"Unknown task: {task_name}")

                task = celery_task.apply_async(
                    kwargs=data,
                    countdown=delay_seconds,
                    task_id=task_id
                )

        except Exception as task_error:
            logger.error(
                f"Failed to create Celery task {task_name}: {task_error}",
                exc_info=True
            )
            raise

        if not task:
            logger.error(f"Task object is None after apply_async for {task_name}")
            raise RuntimeError(f"Failed to create Celery task {task_name}")

        logger.info(f"Task queued successfully: {task.id} ({task_name})")

        # Also log to database for dashboard visibility (non-blocking fallback)
        db = SessionLocal() if db is None else db
        try:
            # Determine channel type based on task name
            if task_name == CELERY_TASK_CREATE_CANDIDATE:
                channel_type = QUEUE_TYPE_CANDIDATE
                message_type = 'create_candidate'
            elif task_name == CELERY_TASK_PROCESS_CANDIDATE:
                channel_type = QUEUE_TYPE_THUNDER
                message_type = 'process_candidate'
            elif task_name == CELERY_TASK_ASSIGN_THUNDER:
                channel_type = QUEUE_TYPE_THUNDER
                message_type = 'assign_thunder'
            elif task_name == CELERY_TASK_SEND_NOTIFICATION:
                channel_type = QUEUE_TYPE_EMAIL
                message_type = 'send_notification'
            else:
                channel_type = task_name.upper() + "_QUEUE"
                message_type = task_name

            try:
                existing = db.query(ChannelQueueItem).filter(
                    ChannelQueueItem.message_id == task.id
                ).first()
            except Exception as query_err:
                logger.error(f"Query failed: {query_err}", exc_info=True)
                existing = None

            if not existing:
                try:
                    queue_item = ChannelQueueItem(
                        id=str(uuid4()),
                        message_id=task.id,
                        type=message_type,
                        channel_type=channel_type,
                        status="PENDING",
                        payload=data or {},
                        recipient=data.get('candidate_email') or data.get('recipient_id') if data else None,
                        retry_count=QUEUE_ITEM_RETRY_COUNT_INITIAL
                    )
                except Exception as create_err:
                    logger.error(f"Failed to create queue item: {create_err}", exc_info=True)
                    raise

                # Check if queue item already exists (avoid duplicate on retry)
                try:
                    existing = db.query(ChannelQueueItem).filter(
                        ChannelQueueItem.message_id == task.id
                    ).first()
                except Exception as query_err:
                    logger.error(f"Failed to query existing queue item: {query_err}", exc_info=True)
                    raise

                if not existing:
                    try:
                        db.add(queue_item)
                    except Exception as add_err:
                        logger.error(f"Failed to add queue item: {add_err}", exc_info=True)
                        raise

                try:
                    db.commit()
                except Exception as commit_err:
                    logger.error(f"Failed to commit: {commit_err}", exc_info=True)
                    db.rollback()
                    raise

                logger.info(f"Logged task {task.id} ({channel_type})")

        except Exception as db_error:
            # CRITICAL: Fail hard instead of swallowing error
            # Database logging is required for queue visibility
            # If it fails, the caller must know
            logger.error(f"CRITICAL: Failed to log task to database: {db_error}", exc_info=True)
            try:
                db.rollback()
            except Exception as rollback_err:
                # Intentional: rollback may fail if connection already closed
                # Task is already queued in Celery, so main flow succeeded
                logger.warning(f"Failed to rollback transaction: {rollback_err}")
            try:
                db.close()
            except Exception as close_err:
                # Intentional: close may fail if session already terminated
                # We've already logged the error above
                logger.warning(f"Failed to close database session: {close_err}")
            # Re-raise so caller knows logging failed
            raise RuntimeError(
                f"Queue task logging to database failed: {str(db_error)}. "
                f"Task may not be visible in dashboard. Check infrastructure."
            ) from db_error
        finally:
            try:
                if db and db.is_active:
                    db.close()
            except Exception as close_err:
                logger.warning(f"Failed to close database: {close_err}")

        return {
            "status": "queued",
            "message_id": task.id,
            "task_name": task_name,
            "polling_endpoint": f"/api/v1/tasks/{task.id}/status",
            "timestamp": datetime.now().isoformat()
        }

    @staticmethod
    def get_task_status(task_id: str) -> Dict[str, Any]:
        """Get the status of a queued task."""
        if not task_id:
            logger.error("Task ID is required for get_task_status")
            raise ValueError("Task ID is required")

        try:
            from app.celery_app import app
        except ImportError as import_error:
            logger.error(f"Failed to import Celery app: {import_error}", exc_info=True)
            raise

        try:
            task = app.AsyncResult(task_id)

            if not task:
                logger.warning(f"No task found for {task_id}")
                raise RuntimeError(f"Task not found: {task_id}")

            return {
                "task_id": task_id,
                "state": task.state,
                "result": task.result if task.successful() else None,
                "error": str(task.info) if task.failed() else None,
                "progress": getattr(task.info, 'current', None) if hasattr(task.info, 'current') else None,
                "is_ready": task.ready(),
                "is_successful": task.successful(),
                "is_failed": task.failed()
            }

        except Exception as status_error:
            logger.error(
                f"Failed to get task status for {task_id}: {status_error}",
                exc_info=True
            )
            raise
