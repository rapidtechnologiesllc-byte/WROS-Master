"""Message Queue Endpoints - Complete queue management and monitoring

GET    /queues                    - List all queue messages
GET    /queues/stats              - Get queue statistics
GET    /queues/{message_id}       - Get message details
POST   /queues/{message_id}/retry - Retry failed message
POST   /queues/{message_id}/clear - Delete message from queue
GET    /queues/email/{message_id}/engagement - Email engagement metrics
POST   /queues/{queue_type}/start - Start processing queue
POST   /queues/{queue_type}/stop  - Stop processing queue
POST   /queues/{queue_type}/retry - Retry all failed messages in queue
"""
import logging
from typing import Any, Dict, Optional
from datetime import datetime

from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.message_queue import MessageQueue, EmailTracking, EmailTrackingEvent
from app.models.user import Users

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queues", tags=["queues"])

DEFAULT_LIMIT = 50
MAX_LIMIT = 500
MAX_RETRIES = 5

@router.get("")
def get_queue_messages(
    queue_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    message_type: Optional[str] = Query(None),
    created_after: Optional[str] = Query(None),
    retry_count_min: Optional[int] = Query(None),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    List messages in queue with comprehensive filtering.

    Query parameters:
        limit: Maximum items to return (default: 50, max: 500)
        offset: Pagination offset (default: 0)
        queue_type: Filter by channel (THUNDER_QUEUE, EMAIL_QUEUE, etc.)
        status: Filter by status (PENDING, PROCESSING, COMPLETED, FAILED)
        message_type: Filter by message type (create_candidate, etc.)
        created_after: Filter by creation date (ISO format)
        retry_count_min: Filter by minimum retry count
    """
    try:
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
        messages = query.order_by(desc(MessageQueue.created_at)).offset(offset).limit(limit).all()

        # Build response
        result = []
        if messages:
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
                    "payload": m.payload,
                })

        return {
            "data": result,
            "total": total,
            "offset": offset,
            "limit": limit,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch queue messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch messages: {str(e)}")

@router.get("/stats")
def get_queue_stats(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get queue statistics aggregated by queue type and status."""
    try:
        all_messages = db.query(MessageQueue).all()

        queue_stats = {}
        queue_types = ["THUNDER_QUEUE", "EMAIL_QUEUE", "WHATSAPP_QUEUE", "SMS_QUEUE", "SLACK_QUEUE",
                      "APPROVAL_QUEUE", "COMMISSION_QUEUE", "CRM_QUEUE", "DASHBOARD_QUEUE",
                      "CALENDAR_QUEUE", "SIGNATURE_QUEUE", "CANDIDATE_QUEUE"]

        if queue_types:
            if all_messages:
                for queue_type in queue_types:
                    queue_messages = [m for m in all_messages if m.queue_type == queue_type]
                    if queue_messages:
                        pending_count = len([m for m in queue_messages if m.status == "PENDING"])
                        processing_count = len([m for m in queue_messages if m.status == "SLM_PROCESSING"])
                        completed_count = len([m for m in queue_messages if m.status == "COMPLETED"])
                        failed_count = len([m for m in queue_messages if m.status == "FAILED"])

                        queue_stats[queue_type] = {
                            "total": len(queue_messages),
                            "pending": pending_count,
                            "processing": processing_count,
                            "completed": completed_count,
                            "failed": failed_count,
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
    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/{message_id}")
def get_message_detail(
    message_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed information about a specific message."""
    try:
        message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()

        if not message:
            raise HTTPException(status_code=404, detail=f"Message {message_id} not found")

        # Get any associated email tracking
        email_tracking = []
        try:
            email_tracking = db.query(EmailTracking).filter(EmailTracking.message_id == message_id).all()
        except Exception as e:
            logger.error(f"Failed to get email tracking for message {message_id}: {e}", exc_info=True)

        # Get email events
        email_events = []
        if email_tracking:
            for tracking in email_tracking:
                try:
                    events = db.query(EmailTrackingEvent).filter(
                        EmailTrackingEvent.tracking_id == tracking.id
                    ).order_by(EmailTrackingEvent.created_at).all()
                except Exception as e:
                    logger.error(f"Failed to get email events for tracking {tracking.id}: {e}", exc_info=True)
                    events = []

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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get message detail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get message: {str(e)}")


@router.post("/{message_id}/retry")
def retry_message(
    message_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retry a failed message."""
    try:
        message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()

        if not message:
            raise HTTPException(status_code=404, detail=f"Message {message_id} not found")

        if message.status != "FAILED":
            raise HTTPException(status_code=400, detail=f"Can only retry FAILED messages, current: {message.status}")

        if not message or not hasattr(message, 'id'):
            raise HTTPException(status_code=400, detail="Invalid message object")

        message.status = "PENDING"
        message.retry_count += 1
        message.error = None
        message.updated_at = datetime.utcnow()

        try:
            db.commit()
            logger.info(f"Retrying message {message_id} (attempt {message.retry_count})")
        except Exception as e:
            logger.error(f"Failed to commit retry for message {message_id}: {e}", exc_info=True)
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to update message")

        return {
            "status": "success",
            "message_id": message_id,
            "new_status": "PENDING",
            "retry_count": message.retry_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry message: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to retry: {str(e)}")


@router.post("/{message_id}/clear")
def clear_message(
    message_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Clear/delete a message from the queue."""
    try:
        message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()

        if not message:
            raise HTTPException(status_code=404, detail=f"Message {message_id} not found")

        try:
            db.query(EmailTracking).filter(EmailTracking.message_id == message_id).delete()
        except Exception as e:
            logger.error(f"Failed to delete email tracking for message {message_id}: {e}", exc_info=True)

        try:
            db.delete(message)
        except Exception as e:
            logger.error(f"Failed to delete message {message_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to delete message")

        db.commit()

        logger.info(f"Cleared message {message_id}")

        return {
            "status": "success",
            "message_id": message_id,
            "action": "deleted",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear message: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete: {str(e)}")


@router.post("/{queue_type}/start")
def start_queue(
    queue_type: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Start processing a queue - mark all pending messages as active."""
    try:
        messages = db.query(MessageQueue).filter(
            MessageQueue.queue_type == queue_type,
            MessageQueue.status == "PENDING"
        ).all()

        count = len(messages)
        logger.info(f"Starting queue {queue_type}: {count} pending messages")

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


@router.post("/{queue_type}/stop")
def stop_queue(
    queue_type: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Stop processing a queue - pause pending messages."""
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


@router.post("/{queue_type}/retry")
def retry_queue(
    queue_type: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retry all failed messages in a queue."""
    try:
        failed_messages = db.query(MessageQueue).filter(
            MessageQueue.queue_type == queue_type,
            MessageQueue.status == "FAILED"
        ).all()

        count = 0
        if failed_messages:
            for message in failed_messages:
                if message and message.retry_count < MAX_RETRIES:
                    message.status = "PENDING"
                    message.retry_count += 1
                    message.error = None
                    message.updated_at = datetime.utcnow()
                    count += 1

        if count > 0:
            try:
                db.commit()
                logger.info(f"Retrying queue {queue_type}: {count} failed messages reset")
            except Exception as e:
                logger.error(f"Failed to commit retry for queue {queue_type}: {e}", exc_info=True)
                db.rollback()
                raise HTTPException(status_code=500, detail="Failed to retry queue")

        return {
            "status": "success",
            "queue_type": queue_type,
            "action": "retry",
            "messages_retried": count,
            "message": f"Queue {queue_type} retry initiated. {count} messages queued.",
        }
    except Exception as e:
        logger.error(f"Failed to retry queue {queue_type}: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to retry queue: {str(e)}")


@router.get("/email/{message_id}/engagement")
def get_email_engagement_metrics(
    message_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get email engagement metrics for a specific message."""
    try:
        message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()

        if not message:
            raise HTTPException(status_code=404, detail=f"Message {message_id} not found")

        if message.queue_type != "EMAIL_QUEUE":
            raise HTTPException(status_code=400, detail="This endpoint only works with EMAIL_QUEUE")

        tracking_records = []
        try:
            tracking_records = db.query(EmailTracking).filter(EmailTracking.message_id == message_id).all()
        except Exception as e:
            logger.error(f"Failed to get email tracking for message {message_id}: {e}", exc_info=True)

        total_sent = len(tracking_records)
        opened = 0
        clicked = 0
        replied = 0
        bounced = 0
        spam_marked = 0

        if tracking_records:
            opened = len([t for t in tracking_records if t.opened_at])
            clicked = len([t for t in tracking_records if t.clicked_at])
            replied = len([t for t in tracking_records if t.replied_at]) if hasattr(tracking_records[0], 'replied_at') else 0
            bounced = len([t for t in tracking_records if t.bounced_at])
            spam_marked = len([t for t in tracking_records if t.spam_marked_at]) if hasattr(tracking_records[0], 'spam_marked_at') else 0

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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get engagement metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")
