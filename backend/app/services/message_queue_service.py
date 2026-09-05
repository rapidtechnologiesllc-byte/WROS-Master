"""
Message Queue Service - Redis/Celery backed task queueing.

This module provides a unified interface to queue async tasks using Celery with Redis.
All background jobs (candidate processing, Thunder intake, notifications) are routed through here.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class MessageQueueService:
    """Queue async tasks to Celery/Redis for background processing."""

    @staticmethod
    def enqueue(task_name: str, task_id: str = None, data: Dict[str, Any] = None, delay_seconds: int = 0) -> Dict[str, Any]:
        """
        Queue a task to Celery for async processing.

        Args:
            task_name: Name of the Celery task (e.g., 'process_candidate', 'send_notification')
            task_id: Optional task ID for tracking
            data: Task data/arguments
            delay_seconds: Optional delay before task execution (0 = immediate)

        Returns:
            dict: Task queue response with task_id, status, and polling info

        Raises:
            RuntimeError: If Celery/Redis connection fails
        """
        try:
            from app.celery_app import app
            from app.tasks.candidate_tasks import process_candidate, assign_thunder_agent
            from app.tasks.notification_tasks import send_notification

            data = data or {}
            logger.info(f"[MessageQueue] Enqueueing task: {task_name} with data: {data}")

            # Route to appropriate Celery task
            if task_name == 'process_candidate':
                candidate_id = data.get('candidate_id')
                tenant_id = data.get('tenant_id', 1)
                task = process_candidate.apply_async(
                    args=[candidate_id, tenant_id],
                    countdown=delay_seconds,
                    task_id=task_id
                )

            elif task_name == 'assign_thunder_agent':
                candidate_id = data.get('candidate_id')
                job_id = data.get('job_id')
                tenant_id = data.get('tenant_id', 1)
                task = assign_thunder_agent.apply_async(
                    args=[candidate_id, job_id, tenant_id],
                    countdown=delay_seconds,
                    task_id=task_id
                )

            elif task_name == 'send_notification':
                notification_type = data.get('notification_type', 'email')
                recipient_id = data.get('recipient_id')
                notification_data = data.get('data', {})
                task = send_notification.apply_async(
                    args=[notification_type, recipient_id, notification_data],
                    countdown=delay_seconds,
                    task_id=task_id
                )

            else:
                # Generic task execution
                celery_task = app.tasks.get(task_name)
                if not celery_task:
                    raise ValueError(f"Unknown task: {task_name}")
                task = celery_task.apply_async(
                    kwargs=data,
                    countdown=delay_seconds,
                    task_id=task_id
                )

            logger.info(f"[MessageQueue] Task queued successfully: {task.id} ({task_name})")

            return {
                "status": "queued",
                "message_id": task.id,
                "task_name": task_name,
                "polling_endpoint": f"/api/v1/tasks/{task.id}/status",
                "timestamp": __import__('datetime').datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"[MessageQueue] Failed to queue task {task_name}: {str(e)}", exc_info=True)
            raise RuntimeError(f"Failed to queue task {task_name}: {str(e)}")

    @staticmethod
    def get_task_status(task_id: str) -> Dict[str, Any]:
        """
        Get the status of a queued task.

        Args:
            task_id: Celery task ID

        Returns:
            dict: Task status info (state, result, progress, etc.)
        """
        try:
            from app.celery_app import app

            task = app.AsyncResult(task_id)

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

        except Exception as e:
            logger.error(f"[MessageQueue] Failed to get task status {task_id}: {str(e)}", exc_info=True)
            return {
                "task_id": task_id,
                "state": "UNKNOWN",
                "error": str(e)
            }
