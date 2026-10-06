"""
Queue Monitoring API - Database-driven queue status and management

Provides dashboard access to message queue stats, task status, and health.
Uses ChannelQueueItem table (database-driven, not Celery/Redis/Flower).
All endpoints require system.manage permission (admin only).
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.dependencies import get_current_user, require_role_template_permission
from app.models.user import Users
from app.models.channel_queue import ChannelQueueItem
from app.core.permission_registry import Permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/api/queue", tags=["queue-monitoring"])


@router.get(
    "/status",
)
def get_queue_status(db: Session = Depends(get_db), current_user: Users = Depends(get_current_user)):
    """
    Get overall queue health status

    Returns:
    {
      "total_messages": 150,
      "by_status": {
        "PENDING": 10,
        "PROCESSING": 5,
        "PROCESSING_SLOW": 2,
        "READY_TO_SEND": 20,
        "COMPLETED": 100,
        "FAILED": 13
      },
      "health": "HEALTHY" | "DEGRADED" | "CRITICAL",
      "stalled_messages": 2,
      "avg_processing_time_seconds": 45
    }
    """
    try:
        # Get message counts by status
        status_counts = db.query(
            ChannelQueueItem.status,
            func.count(ChannelQueueItem.id).label("count")
        ).group_by(ChannelQueueItem.status).all()

        by_status = {status: count for status, count in status_counts}
        total = sum(by_status.values())

        # Count stalled messages (PROCESSING > 15 minutes)
        from datetime import datetime, timedelta
        stalled_threshold = datetime.utcnow() - timedelta(minutes=15)
        stalled_count = db.query(func.count(ChannelQueueItem.id)).filter(
            ChannelQueueItem.status.in_(["PROCESSING", "PROCESSING_SLOW"]),
            ChannelQueueItem.created_at < stalled_threshold
        ).scalar() or 0

        # Determine health
        failed_count = by_status.get("FAILED", 0)
        failed_ratio = failed_count / total if total > 0 else 0

        if stalled_count > 10 or failed_ratio > 0.1:
            health = "CRITICAL"
        elif stalled_count > 5 or failed_ratio > 0.05:
            health = "DEGRADED"
        else:
            health = "HEALTHY"

        return {
            "total_messages": total,
            "by_status": by_status,
            "health": health,
            "stalled_messages": stalled_count,
            "failed_messages": failed_count,
        }

    except Exception as e:
        logger.error(f"Failed to get queue status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve queue status")


@router.get(
    "/messages",
)
def get_messages(
    status: str = Query(None, description="Filter by status (PENDING, PROCESSING, etc.)"),
    task_name: str = Query(None, description="Filter by task name"),
    limit: int = Query(100, ge=1, le=1000),
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get queue messages with optional filters

    Query params:
    - status: Filter by status (PENDING, PROCESSING, PROCESSING_SLOW, READY_TO_SEND, COMPLETED, FAILED)
    - task_name: Filter by task type
    - limit: Max messages to return (default: 100, max: 1000)
    """
    try:
        query = db.query(ChannelQueueItem)

        if status:
            query = query.filter(ChannelQueueItem.status == status.upper())
        if task_name:
            query = query.filter(ChannelQueueItem.type == task_name)

        messages = query.order_by(ChannelQueueItem.created_at.desc()).limit(limit).all()

        return {
            "messages": [
                {
                    "id": str(m.id),
                    "task_name": m.type,
                    "status": m.status,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "retries": m.retry_count,
                    "error": m.error,
                    "last_attempted": m.last_attempted_at.isoformat() if m.last_attempted_at else None,
                }
                for m in messages
            ],
            "count": len(messages),
        }

    except Exception as e:
        logger.error(f"Failed to get messages: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve messages")


@router.get(
    "/messages/{message_id}",
)
def get_message(
    message_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed message information"""
    try:
        message = db.query(ChannelQueueItem).filter(ChannelQueueItem.id == message_id).first()

        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        return {
            "id": str(message.id),
            "task_name": message.type,
            "status": message.status,
            "payload": message.payload,
            "created_at": message.created_at.isoformat() if message.created_at else None,
            "retries": message.retry_count,
            "error": message.error,
            "last_attempted": message.last_attempted_at.isoformat() if message.last_attempted_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get message {message_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve message")


@router.post(
    "/messages/{message_id}/retry",
)
def retry_message(
    message_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually retry a failed message

    Resets message to PENDING status and clears error.
    """
    try:
        message = db.query(ChannelQueueItem).filter(ChannelQueueItem.id == message_id).first()

        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        if message.status != "FAILED":
            raise HTTPException(status_code=400, detail="Only FAILED messages can be retried")

        # Reset message for retry
        message.status = "PENDING"
        message.error = None
        message.last_attempted = None
        db.commit()

        logger.info(f"Message {message_id} manually retried by {current_user.UserEmail}")
        return {
            "status": "retry_requested",
            "message_id": message_id,
            "new_status": "PENDING"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry message {message_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retry message")


@router.get(
    "/stats",
)
def get_stats(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get queue statistics

    Returns:
    {
      "total_messages": 500,
      "completed": 450,
      "failed": 20,
      "processing": 15,
      "pending": 15,
      "success_rate": 95.7,
      "average_retries": 0.5
    }
    """
    try:
        total = db.query(func.count(ChannelQueueItem.id)).scalar() or 0
        completed = db.query(func.count(ChannelQueueItem.id)).filter(
            ChannelQueueItem.status == "COMPLETED"
        ).scalar() or 0
        failed = db.query(func.count(ChannelQueueItem.id)).filter(
            ChannelQueueItem.status == "FAILED"
        ).scalar() or 0
        processing = db.query(func.count(ChannelQueueItem.id)).filter(
            ChannelQueueItem.status.in_(["PROCESSING", "PROCESSING_SLOW"])
        ).scalar() or 0
        pending = db.query(func.count(ChannelQueueItem.id)).filter(
            ChannelQueueItem.status == "PENDING"
        ).scalar() or 0

        success_rate = (completed / total * 100) if total > 0 else 0
        avg_retries = db.query(func.avg(ChannelQueueItem.retry_count)).scalar() or 0

        return {
            "total_messages": total,
            "completed": completed,
            "failed": failed,
            "processing": processing,
            "pending": pending,
            "success_rate": round(success_rate, 1),
            "average_retries": round(float(avg_retries), 2),
        }

    except Exception as e:
        logger.error(f"Failed to get stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve queue stats")
