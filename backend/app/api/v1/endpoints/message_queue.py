"""
Message Queue Monitoring Endpoints
===================================
Provides visibility into the PostgreSQL message queue (ChannelQueueItem table).
Used by frontend Message Queue Monitor for debugging and monitoring.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_role_template_permission
from app.core.permission_registry import Permissions
from app.models.channel_queue import ChannelQueueItem
from datetime import datetime

router = APIRouter(prefix="/message-queue", tags=["Message Queue Monitor"])


@router.get("/display", dependencies=[Depends(require_role_template_permission(*Permissions.ROLE_TEMPLATES_EDIT))])
def get_message_queue_display(
    status: str = Query("", description="Filter by status: PENDING, PROCESSING, COMPLETED, FAILED"),
    message_type: str = Query("", description="Filter by message type"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Get message queue status for display/monitoring.

    Returns recent messages from ChannelQueueItem table with optional filtering.
    """
    query = db.query(ChannelQueueItem)

    # Apply filters
    if status:
        query = query.filter(ChannelQueueItem.status == status)
    if message_type:
        query = query.filter(ChannelQueueItem.type == message_type)

    # Get recent messages (newest first)
    messages = query.order_by(ChannelQueueItem.created_at.desc()).limit(limit).all()

    # Format for display
    return {
        "total": db.query(ChannelQueueItem).count(),
        "messages": [
            {
                "id": msg.id,
                "type": msg.type,
                "status": msg.status,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "completed_at": msg.completed_at.isoformat() if msg.completed_at else None,
                "result": msg.result,
                "error": msg.error,
                "payload": msg.payload,
            }
            for msg in messages
        ],
        "status_counts": {
            "pending": db.query(ChannelQueueItem).filter(ChannelQueueItem.status == "PENDING").count(),
            "processing": db.query(ChannelQueueItem).filter(ChannelQueueItem.status == "PROCESSING").count(),
            "completed": db.query(ChannelQueueItem).filter(ChannelQueueItem.status == "COMPLETED").count(),
            "failed": db.query(ChannelQueueItem).filter(ChannelQueueItem.status == "FAILED").count(),
        }
    }


@router.post("/{message_id}/retry", dependencies=[Depends(require_role_template_permission(*Permissions.ROLE_TEMPLATES_EDIT))])
def retry_queue_message(message_id: str, db: Session = Depends(get_db)):
    """Retry a failed queue message."""
    from app.services.queue_doctor_service import QueueDoctorService

    message = db.query(ChannelQueueItem).filter(ChannelQueueItem.id == message_id).first()
    if not message:
        raise ValueError("Message not found")

    if message.status != "FAILED":
        raise ValueError("Only FAILED messages can be retried")

    # Reset message to PENDING for immediate retry
    message.status = "PENDING"
    message.retry_count = (message.retry_count or 0) + 1
    message.error = None
    message.next_retry_at = datetime.utcnow()  # Pick up immediately in queue worker

    db.commit()

    # Track retry in QueueDoctor (Phase 2)
    QueueDoctorService.record_retry(message, db)

    return {
        "status": "retry_queued",
        "message_id": message_id,
        "retry_count": message.retry_count
    }


@router.post("/retry-failed", dependencies=[Depends(require_role_template_permission(*Permissions.ROLE_TEMPLATES_EDIT))])
def retry_failed_messages(
    queue_type: str = Query("", description="Filter by queue type (optional)"),
    db: Session = Depends(get_db),
):
    """
    Retry all failed messages of a specific queue type.

    If queue_type is empty, retries ALL failed messages across all types.
    """
    from app.services.queue_doctor_service import QueueDoctorService

    # Query failed messages
    query = db.query(ChannelQueueItem).filter(ChannelQueueItem.status == "FAILED")

    if queue_type:
        query = query.filter(ChannelQueueItem.type == queue_type)

    failed_messages = query.all()

    if not failed_messages:
        return {
            "status": "no_failed_messages",
            "retried_count": 0,
            "message": f"No failed messages found for queue type: {queue_type or 'all'}"
        }

    # Reset all failed messages to PENDING
    retried_count = 0
    for message in failed_messages:
        message.status = "PENDING"
        message.error = None
        message.retry_count = (message.retry_count or 0) + 1
        message.next_retry_at = datetime.utcnow()  # Pick up immediately
        QueueDoctorService.record_retry(message, db)
        retried_count += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise ValueError(f"Failed to retry messages: {str(e)}")

    return {
        "status": "success",
        "retried_count": retried_count,
        "queue_type": queue_type or "all",
        "message": f"Reset {retried_count} failed messages to PENDING for immediate retry"
    }


@router.get("/stats", dependencies=[Depends(require_role_template_permission(*Permissions.ROLE_TEMPLATES_EDIT))])
def get_queue_stats(db: Session = Depends(get_db)):
    """Get overall queue statistics."""
    total = db.query(ChannelQueueItem).count()
    pending = db.query(ChannelQueueItem).filter(ChannelQueueItem.status == "PENDING").count()
    processing = db.query(ChannelQueueItem).filter(ChannelQueueItem.status == "PROCESSING").count()
    completed = db.query(ChannelQueueItem).filter(ChannelQueueItem.status == "COMPLETED").count()
    failed = db.query(ChannelQueueItem).filter(ChannelQueueItem.status == "FAILED").count()

    # Count messages by queue type
    from sqlalchemy import func
    queue_counts = db.query(ChannelQueueItem.type, func.count(ChannelQueueItem.id)).group_by(ChannelQueueItem.type).all()
    by_queue = {queue_type: count for queue_type, count in queue_counts}

    return {
        "total_messages": total,
        "pending": pending,
        "processing": processing,
        "completed": completed,
        "failed": failed,
        "by_queue": by_queue,
        "timestamp": datetime.utcnow().isoformat(),
    }
