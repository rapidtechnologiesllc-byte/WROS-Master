"""Admin Queue Management Endpoints

Provides API for dashboard to view and manage message queue.
Frontend MessageQueueDashboard calls these endpoints to display queue status.
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.message_queue_service import MessageQueueService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/queue", tags=["queue"])


@router.get("/tasks")
def get_queue_tasks(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get all queue tasks for dashboard display.

    Returns:
        {
            "data": {
                "tasks": [
                    {
                        "task_id": "message-id",
                        "type": "candidate_added",
                        "status": "completed",
                        "created_at": "2026-08-27T10:00:00",
                        "error": null,
                        "retry_count": 0
                    },
                    ...
                ]
            }
        }

    Raises:
        HTTPException: If query fails
    """
    try:
        from app.models.message_queue import MessageQueue

        # Fetch all messages, ordered by created_at DESC (most recent first)
        messages = (
            db.query(MessageQueue)
            .order_by(MessageQueue.created_at.desc())
            .limit(1000)
            .all()
        )

        tasks = [
            {
                "task_id": m.id,
                "type": m.type,
                "status": m.status.lower(),
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "error": m.error,
                "retry_count": m.retry_count,
                "resource_id": m.resource_id,
            }
            for m in messages
        ]

        return {"data": {"tasks": tasks}}

    except Exception as e:
        logger.error(f"Failed to get queue tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get queue tasks: {str(e)}")


@router.post("/tasks/{task_id}/retry")
def retry_task(
    task_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Manually retry a failed task.

    Args:
        task_id: Message ID to retry

    Returns:
        {"status": "success", "message": "Task queued for retry"}

    Raises:
        HTTPException: If task not found or retry fails
    """
    try:
        from app.models.message_queue import MessageQueue

        message = db.query(MessageQueue).filter(MessageQueue.id == task_id).first()
        if not message:
            raise HTTPException(status_code=404, detail="Task not found")

        # Reset to PENDING and clear retry count
        message.status = MessageQueueService.STATUS_PENDING
        message.retry_count = 0
        message.error = None
        message.next_retry_at = None
        db.commit()

        logger.info(f"Task manually retried: {task_id}")

        return {
            "status": "success",
            "message": f"Task {task_id} queued for retry",
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to retry task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retry task: {str(e)}")


@router.post("/tasks/{task_id}/clear")
def clear_task(
    task_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Clear/dismiss a failed task (don't retry).

    Args:
        task_id: Message ID to clear

    Returns:
        {"status": "success", "message": "Task cleared"}

    Raises:
        HTTPException: If task not found or clear fails
    """
    try:
        from app.models.message_queue import MessageQueue

        message = db.query(MessageQueue).filter(MessageQueue.id == task_id).first()
        if not message:
            raise HTTPException(status_code=404, detail="Task not found")

        # Mark as FAILED and don't retry
        message.status = MessageQueueService.STATUS_FAILED
        message.error = "Manually cleared by admin"
        db.commit()

        logger.info(f"Task manually cleared: {task_id}")

        return {
            "status": "success",
            "message": f"Task {task_id} cleared",
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clear task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear task: {str(e)}")


@router.get("/stats")
def get_queue_stats(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get queue statistics.

    Returns:
        {
            "total": 150,
            "pending": 5,
            "processing": 1,
            "completed": 140,
            "failed": 4,
            "oldest_retry_at": "2026-08-27T11:00:00"
        }

    Raises:
        HTTPException: If stats fetch fails
    """
    try:
        stats = MessageQueueService.get_stats(db)
        return stats

    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get queue stats: {str(e)}")
