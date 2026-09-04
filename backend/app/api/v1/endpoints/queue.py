from app.core.logging import logger
"""Queue Management Endpoints - Channel-based message queue API."""
import logging
from typing import Any, Dict, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.models.message_queue import MessageQueue, EmailTracking, EmailTrackingEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queues", tags=["queue"])

@router.get(
    "",
    dependencies=[Depends(require_resource_permission("unknown", "view"))]
)
def list_queue_messages(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    queue_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    message_type: Optional[str] = Query(None),
    created_after: Optional[str] = Query(None),
    retry_count_min: Optional[int] = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    List messages in queue with comprehensive filtering.

    Query parameters:
        skip: Pagination offset (default: 0)
        limit: Maximum items to return (default: 50, max: 1000)
        queue_type: Filter by channel (THUNDER_QUEUE, EMAIL_QUEUE, etc.)
        status: Filter by status (PENDING, SLM_PROCESSING, CHANNEL_QUEUED, COMPLETED, FAILED)
        message_type: Filter by message type (create_candidate, interview_scheduled, etc.)
        created_after: Filter by creation date (ISO format)
        retry_count_min: Filter by minimum retry count
    """
    query = db.query(MessageQueue)

    # Apply filters
    if queue_type:
        query = query.filter(MessageQueue.queue_type == queue_type)
    if status:
        query = query.filter(MessageQueue.status == status)
    if message_type:
        query = query.filter(MessageQueue.type == message_type)
    if created_after:
        try:
            after_dt = datetime.fromisoformat(created_after)
            query = query.filter(MessageQueue.created_at >= after_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid created_after format (use ISO format)")
    if retry_count_min is not None:
        query = query.filter(MessageQueue.retry_count >= retry_count_min)

    # Get total before pagination
    total = query.count()

    # Apply pagination and sort by created_at descending
    messages = query.order_by(desc(MessageQueue.created_at)).offset(skip).limit(limit).all()

    # Build response
    result = []
    for m in messages:
        result.append({
            "id": m.id,
            "type": m.type,
            "queue_type": m.queue_type,
            "status": m.status,
            "resource_id": m.resource_id,
            "retry_count": m.retry_count,
            "error": m.error,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            "created_by": m.created_by,
            "email_status": m.email_status,
            "opened_at": m.opened_at.isoformat() if m.opened_at else None,
            "clicked_at": m.clicked_at.isoformat() if m.clicked_at else None,
            "bounced_at": m.bounced_at.isoformat() if m.bounced_at else None,
            "email_provider": m.email_provider,
        })

    return {
        "data": result,
        "total": total,
        "skip": skip,
        "limit": limit,
    }

@router.get(
    "/stats",
    dependencies=[Depends(require_resource_permission("stat", "view"))]
)
def get_queue_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get queue statistics aggregated by queue type and status."""
    all_messages = db.query(MessageQueue).all()

    queue_stats = {}
    for queue_type in ["THUNDER_QUEUE", "EMAIL_QUEUE", "WHATSAPP_QUEUE", "SMS_QUEUE", "SLACK_QUEUE",
                       "APPROVAL_QUEUE", "COMMISSION_QUEUE", "CRM_QUEUE", "DASHBOARD_QUEUE", "CALENDAR_QUEUE", "SIGNATURE_QUEUE"]:
        queue_messages = [m for m in all_messages if m.queue_type == queue_type]
        if queue_messages:
            queue_stats[queue_type] = {
                "total": len(queue_messages),
                "pending": len([m for m in queue_messages if m.status == "PENDING"]),
                "processing": len([m for m in queue_messages if m.status == "SLM_PROCESSING"]),
                "completed": len([m for m in queue_messages if m.status == "COMPLETED"]),
                "failed": len([m for m in queue_messages if m.status == "FAILED"]),
            }

    # Email engagement metrics
    email_messages = [m for m in all_messages if m.queue_type == "EMAIL_QUEUE"]
    email_metrics = None
    if email_messages:
        opened = len([m for m in email_messages if m.opened_at])
        clicked = len([m for m in email_messages if m.clicked_at])
        bounced = len([m for m in email_messages if m.bounced_at])
        total = len(email_messages)

        email_metrics = {
            "total_sent": total,
            "opened": opened,
            "open_rate": (opened / total * 100) if total > 0 else 0,
            "clicked": clicked,
            "click_rate": (clicked / total * 100) if total > 0 else 0,
            "bounced": bounced,
            "bounce_rate": (bounced / total * 100) if total > 0 else 0,
        }

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "queues": queue_stats,
        "email_metrics": email_metrics,
    }

@router.get("/{message_id}", dependencies=[Depends(require_resource_permission("system", "manage"))])
def get_message_detail(message_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get detailed information about a specific message."""
    message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()

    if not message:
        raise HTTPException(status_code=404, detail=f"Message {message_id} not found")

    # Get any associated email tracking
    email_tracking = db.query(EmailTracking).filter(EmailTracking.message_id == message_id).all()

    # Get email events
    email_events = []
    for tracking in email_tracking:
        events = db.query(EmailTrackingEvent).filter(
            EmailTrackingEvent.tracking_id == tracking.id
        ).order_by(EmailTrackingEvent.created_at).all()

        email_events.extend([{
            "tracking_id": tracking.id,
            "recipient": tracking.recipient_email,
            "event_type": e.event_type,
            "event_data": e.event_data,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        } for e in events])

    return {
        "message": {
            "id": message.id,
            "type": message.type,
            "queue_type": message.queue_type,
            "status": message.status,
            "resource_id": message.resource_id,
            "payload": message.payload,
            "retry_count": message.retry_count,
            "error": message.error,
            "created_at": message.created_at.isoformat() if message.created_at else None,
            "updated_at": message.updated_at.isoformat() if message.updated_at else None,
            "created_by": message.created_by,
        },
        "email_tracking": [{
            "id": t.id,
            "recipient_email": t.recipient_email,
            "provider": t.provider,
            "status": t.status,
            "sent_at": t.sent_at.isoformat() if t.sent_at else None,
            "opened_at": t.opened_at.isoformat() if t.opened_at else None,
            "clicked_at": t.clicked_at.isoformat() if t.clicked_at else None,
            "bounced_at": t.bounced_at.isoformat() if t.bounced_at else None,
        } for t in email_tracking],
        "email_events": email_events,
    }

@router.post("/{message_id}/retry", dependencies=[Depends(require_resource_permission("system", "manage"))])
def retry_message(message_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retry a failed message."""
    message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()

    if not message:
        raise HTTPException(status_code=404, detail=f"Message {message_id} not found")

    if message.status != "FAILED":
        raise HTTPException(status_code=400, detail=f"Can only retry FAILED messages, current status: {message.status}")

    message.status = "PENDING"
    message.retry_count += 1
    message.error = None
    message.updated_at = datetime.utcnow()

    db.commit()
    logger.info(f"Retrying message {message_id} (attempt {message.retry_count})")

    return {
        "status": "success",
        "message_id": message_id,
        "new_status": "PENDING",
        "retry_count": message.retry_count,
    }

@router.post("/{message_id}/clear", dependencies=[Depends(require_resource_permission("system", "manage"))])
def clear_message(message_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Clear/delete a message from the queue."""
    message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()

    if not message:
        raise HTTPException(status_code=404, detail=f"Message {message_id} not found")

    db.query(EmailTracking).filter(EmailTracking.message_id == message_id).delete()
    db.delete(message)
    db.commit()

    logger.info(f"Cleared message {message_id}")

    return {
        "status": "success",
        "message_id": message_id,
        "action": "deleted",
    }

@router.post(
    "/{queue_type}/start",
    dependencies=[Depends(require_resource_permission("queue", "create"))]
)
def start_queue(queue_type: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Start processing a queue - mark all pending messages as active for processing."""
    try:
        messages = db.query(MessageQueue).filter(
            MessageQueue.queue_type == queue_type,
            MessageQueue.status == "PENDING"
        ).all()

        count = len(messages)
        logger.info(f"Starting queue {queue_type}: {count} pending messages will be processed")

        return {
            "status": "success",
            "queue_type": queue_type,
            "action": "started",
            "messages_queued": count,
            "message": f"Queue {queue_type} started. {count} pending messages will be processed.",
        }
    except Exception as e:
        logger.error(f"Failed to start queue {queue_type}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start queue: {str(e)}")

@router.post(
    "/{queue_type}/stop",
    dependencies=[Depends(require_resource_permission("queue", "create"))]
)
def stop_queue(queue_type: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Stop processing a queue - pause all pending messages."""
    try:
        messages = db.query(MessageQueue).filter(
            MessageQueue.queue_type == queue_type,
            MessageQueue.status.in_(["PENDING", "SLM_PROCESSING"])
        ).all()

        count = len(messages)
        logger.info(f"Stopping queue {queue_type}: {count} messages paused")

        return {
            "status": "success",
            "queue_type": queue_type,
            "action": "stopped",
            "messages_paused": count,
            "message": f"Queue {queue_type} stopped. {count} messages paused.",
        }
    except Exception as e:
        logger.error(f"Failed to stop queue {queue_type}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to stop queue: {str(e)}")

@router.post(
    "/{queue_type}/retry",
    dependencies=[Depends(require_resource_permission("queue", "create"))]
)
def retry_queue(queue_type: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retry all failed messages in a queue."""
    try:
        failed_messages = db.query(MessageQueue).filter(
            MessageQueue.queue_type == queue_type,
            MessageQueue.status == "FAILED"
        ).all()

        count = 0
        for message in failed_messages:
            if message.retry_count < 5:  # Max 5 retries
                message.status = "PENDING"
                message.retry_count += 1
                message.error = None
                message.updated_at = datetime.utcnow()
                count += 1

        db.commit()
        logger.info(f"Retrying queue {queue_type}: {count} failed messages reset to PENDING")

        return {
            "status": "success",
            "queue_type": queue_type,
            "action": "retry",
            "messages_retried": count,
            "message": f"Queue {queue_type} retry initiated. {count} failed messages queued for retry.",
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        logger.error(f"Failed to retry queue {queue_type}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retry queue: {str(e)}")

@router.get("/email/{message_id}/engagement", dependencies=[Depends(require_resource_permission("system", "manage"))])
def get_email_engagement_metrics(message_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get email engagement metrics for a specific message."""
    message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()

    if not message:
        raise HTTPException(status_code=404, detail=f"Message {message_id} not found")

    if message.queue_type != "EMAIL_QUEUE":
        raise HTTPException(status_code=400, detail="This endpoint only works with EMAIL_QUEUE messages")

    tracking_records = db.query(EmailTracking).filter(EmailTracking.message_id == message_id).all()

    total_sent = len(tracking_records)
    opened = len([t for t in tracking_records if t.opened_at])
    clicked = len([t for t in tracking_records if t.first_click_at])
    replied = len([t for t in tracking_records if t.replied_at])
    bounced = len([t for t in tracking_records if t.bounced_at])
    spam_marked = len([t for t in tracking_records if t.spam_marked_at])

    return {
        "message_id": message_id,
        "metrics": {
            "total_sent": total_sent,
            "opened": opened,
            "open_rate": (opened / total_sent * 100) if total_sent > 0 else 0,
            "clicked": clicked,
            "click_rate": (clicked / total_sent * 100) if total_sent > 0 else 0,
            "replied": replied,
            "reply_rate": (replied / total_sent * 100) if total_sent > 0 else 0,
            "bounced": bounced,
            "bounce_rate": (bounced / total_sent * 100) if total_sent > 0 else 0,
            "spam_marked": spam_marked,
            "spam_rate": (spam_marked / total_sent * 100) if total_sent > 0 else 0,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }
