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
        """Queue a task to Celery with database fallback on connection failure."""
        if not task_name:
            logger.error("Task name is required for enqueue")
            raise ValueError("Task name is required")

        data = data or {}

        try:
            return MessageQueueService._enqueue_celery(
                task_name, task_id, data, delay_seconds
            )
        except Exception as celery_error:
            logger.error(
                f"Celery enqueue failed for {task_name}: {celery_error}",
                exc_info=True
            )
            return MessageQueueService._enqueue_database_fallback(
                task_name, data
            )

    @staticmethod
    def _enqueue_celery(
        task_name: str,
        task_id: Optional[str],
        data: Dict[str, Any],
        delay_seconds: int
    ) -> Dict[str, Any]:
        """Enqueue task to Celery Redis backend."""
        try:
            from app.celery_app import app
            from app.tasks.candidate_tasks import process_candidate, assign_thunder_agent
            from app.tasks.notification_tasks import send_notification
        except ImportError as import_error:
            logger.error(f"Failed to import Celery: {import_error}", exc_info=True)
            raise

        task = None

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

        return {
            "status": "queued",
            "message_id": task.id,
            "task_name": task_name,
            "polling_endpoint": f"/api/v1/tasks/{task.id}/status",
            "timestamp": datetime.now().isoformat()
        }

    @staticmethod
    def _enqueue_database_fallback(
        task_name: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fallback: store task in database queue when Celery unavailable."""
        try:
            from app.models.channel_queue import ChannelQueueItem
            from app.core.database import SessionLocal
        except ImportError as import_error:
            logger.error(f"Failed to import database models: {import_error}", exc_info=True)
            raise

        db = SessionLocal()

        try:
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

            queue_item_id = str(uuid4())
            message_id = str(uuid4())

            try:
                existing = db.query(ChannelQueueItem).filter(
                    ChannelQueueItem.id == queue_item_id
                ).first()
            except Exception as query_error:
                logger.error(
                    f"Failed to query existing item: {query_error}",
                    exc_info=True
                )
                existing = None

            if existing:
                logger.warning(f"UUID collision detected for {queue_item_id}, retrying")
                queue_item_id = str(uuid4())

            queue_item = None
            try:
                queue_item = ChannelQueueItem(
                    id=queue_item_id,
                    message_id=message_id,
                    type=message_type,
                    channel_type=channel_type,
                    status="PENDING",
                    payload=data or {},
                    recipient=data.get('candidate_email') or data.get('recipient_id') if data else None,
                    retry_count=QUEUE_ITEM_RETRY_COUNT_INITIAL
                )
            except Exception as creation_error:
                logger.error(
                    f"Failed to create ChannelQueueItem instance: {creation_error}",
                    exc_info=True
                )
                raise

            if not queue_item:
                logger.error("Queue item object is None after creation")
                raise RuntimeError("ChannelQueueItem creation returned None")

            try:
                db.add(queue_item)
            except Exception as add_error:
                logger.error(
                    f"Failed to add queue item to session: {add_error}",
                    exc_info=True
                )
                raise

            try:
                db.commit()
            except Exception as commit_error:
                logger.error(
                    f"Failed to commit queue item to database: {commit_error}",
                    exc_info=True
                )
                db.rollback()
                raise

            logger.info(
                f"Task stored in database queue: {message_id} ({channel_type})"
            )

            return {
                "status": "queued",
                "message_id": message_id,
                "task_name": task_name,
                "polling_endpoint": f"/api/v1/queues/{message_id}",
                "timestamp": datetime.now().isoformat(),
                "note": "Celery unavailable - database queue"
            }

        except Exception as db_error:
            logger.error(
                f"Database fallback failed: {db_error}",
                exc_info=True
            )
            raise

        finally:
            db.close()

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
