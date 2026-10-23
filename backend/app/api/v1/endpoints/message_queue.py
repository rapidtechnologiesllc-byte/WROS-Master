"""
Message Queue Monitoring Endpoints
===================================
Provides visibility into the PostgreSQL message queue (ChannelQueueItem table).
Used by frontend Message Queue Monitor for debugging and monitoring.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_resource_permission, get_current_user
from app.models.channel_queue import ChannelQueueItem
from datetime import datetime

from app.core.tenant_context import tenant_id_of

router = APIRouter(prefix="/message-queue", tags=["Message Queue Monitor"])


@router.get("/types", dependencies=[Depends(require_resource_permission("message-queue", "view"))])
def get_queue_types(db: Session = Depends(get_db)):
    """
    Get all unique queue types currently in the system.

    Returns a list of all message types that have been enqueued,
    allowing the UI to display them dynamically without hardcoding.
    """
    from sqlalchemy import distinct

    # Get all unique message types from ChannelQueueItem
    queue_types = db.query(distinct(ChannelQueueItem.type)).filter(
        ChannelQueueItem.type.isnot(None)
    ).all()

    # Extract type names and sort them
    types = sorted([row[0] for row in queue_types if row[0]])

    return {
        "queue_types": types,
        "count": len(types),
        "description": "All message queue types currently in the system"
    }



@router.get("/display", dependencies=[Depends(require_resource_permission("message-queue", "view"))])
def get_message_queue_display(
    status: str = Query("", description="Filter by status: PENDING, PROCESSING, COMPLETED, FAILED"),
    message_type: str = Query("", description="Filter by message type"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get message queue status for display/monitoring.

    Returns recent messages from ChannelQueueItem table with optional filtering.
    """
    query = db.query(ChannelQueueItem)

    # Apply filters
    if status:
        # Normalize status to uppercase (database stores PENDING, PROCESSING, COMPLETED, FAILED)
        query = query.filter(ChannelQueueItem.status == status.upper())
    if message_type:
        query = query.filter(ChannelQueueItem.type == message_type)

    # Get recent messages (newest first)
    messages = query.order_by(ChannelQueueItem.created_at.desc()).limit(limit).all()

    # Format for display
    return {
        "total": db.query(ChannelQueueItem).count(),
        "messages": [
            {
                "message_id": msg.message_id,  # FIXED: Show message_id (task_id), not internal db id
                "type": msg.type,
                "status": msg.status,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "completed_at": msg.completed_at.isoformat() if msg.completed_at else None,
                "result": msg.result,
                "error": msg.error,
                "payload": msg.payload,
                "retry_count": msg.retry_count or 0,  # Include retry count for UI display
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


@router.post("/{message_id}/retry", dependencies=[Depends(require_resource_permission("message-queue", "edit"))])
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


@router.post("/{message_id}/stop-and-retry", dependencies=[Depends(require_resource_permission("message-queue", "edit"))])
def stop_and_retry_message(message_id: str, db: Session = Depends(get_db)):
    """Stop a PROCESSING message and mark it for retry (fail current attempt, queue next)."""
    from app.services.queue_doctor_service import QueueDoctorService

    message = db.query(ChannelQueueItem).filter(ChannelQueueItem.id == message_id).first()
    if not message:
        raise ValueError("Message not found")

    if message.status != "PROCESSING":
        raise ValueError(f"Only PROCESSING messages can be stopped. Current status: {message.status}")

    # Mark as FAILED (stop current processing), then reset to PENDING for retry
    message.status = "PENDING"
    message.retry_count = (message.retry_count or 0) + 1
    message.error = "Manually stopped by user (stop-and-retry)"
    message.next_retry_at = datetime.utcnow()  # Pick up immediately

    db.commit()
    QueueDoctorService.record_retry(message, db)

    return {
        "status": "stopped_and_queued_for_retry",
        "message_id": message_id,
        "retry_count": message.retry_count,
        "message": f"Message stopped from PROCESSING and queued for immediate retry (attempt {message.retry_count})"
    }


@router.post("/{message_id}/fail", dependencies=[Depends(require_resource_permission("message-queue", "edit"))])
def fail_queue_message(message_id: str, reason: str = Query("Manual failure"), db: Session = Depends(get_db)):
    """Manually mark a message as FAILED (for PROCESSING messages stuck > 10 seconds)."""
    from app.services.queue_doctor_service import QueueDoctorService

    message = db.query(ChannelQueueItem).filter(ChannelQueueItem.id == message_id).first()
    if not message:
        raise ValueError("Message not found")

    if message.status != "PROCESSING":
        raise ValueError(f"Only PROCESSING messages can be failed. Current status: {message.status}")

    # Mark as FAILED
    message.status = "FAILED"
    message.error = f"User-initiated failure: {reason}"
    message.completed_at = datetime.utcnow()

    db.commit()
    QueueDoctorService.record_error(message, db)

    return {
        "status": "message_failed",
        "message_id": message_id,
        "error": message.error,
        "message": f"Message marked as FAILED. Can be retried with /retry endpoint."
    }


@router.post("/retry-failed", dependencies=[Depends(require_resource_permission("message-queue", "edit"))])
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


@router.get("/stats", dependencies=[Depends(require_resource_permission("message-queue", "view"))])
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


@router.get("/tasks/{task_id}/status")
def get_task_status(task_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Get the status of a queued task by message ID -- the polling_endpoint every queued create
    returns. Only tasks of the caller's own tenant are visible (another tenant's id is a 404).

    Returns: {status: "pending|processing|completed|failed", result: {...}, error: "..."}
    """
    message = db.query(ChannelQueueItem).filter(ChannelQueueItem.id == task_id,
                                                ChannelQueueItem.tenant_id == tenant_id_of(current_user)).first()

    if not message:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return {
        "task_id": message.id,
        "status": message.status.lower() if message.status else "unknown",
        "type": message.type,
        "result": message.result,
        "error": message.error,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "completed_at": message.completed_at.isoformat() if message.completed_at else None,
        "retry_count": message.retry_count or 0,
    }
