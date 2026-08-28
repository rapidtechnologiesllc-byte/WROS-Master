"""Queue Management Endpoints - Channel-based message queue API.

Provides comprehensive queue management with:
- Channel-based filtering (THUNDER_QUEUE, EMAIL_QUEUE, etc.)
- Email engagement metrics
- Queue health monitoring
- Message routing visualization
- Manual retry and error handling
"""
import logging
from typing import Any, Dict, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queues", tags=["queue"])


@router.get("")
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
        queue_type: Filter by channel (THUNDER_QUEUE, EMAIL_QUEUE, WHATSAPP_QUEUE, etc.)
        status: Filter by status (PENDING, SLM_PROCESSING, CHANNEL_QUEUED, COMPLETED, FAILED)
        message_type: Filter by message type (candidate_created, interview_scheduled, etc.)
        created_after: Filter by creation date (ISO format)
        retry_count_min: Filter by minimum retry count

    Returns:
        {
            "data": [...messages...],
            "total": 150,
            "skip": 0,
            "limit": 50
        }
    """
    try:
        from app.models.message_queue import MessageQueue

        # Build query
        query = db.query(MessageQueue)

        # Apply filters
        if queue_type:
            query = query.filter(MessageQueue.queue_type == queue_type.upper())
        if status:
            query = query.filter(MessageQueue.status == status.upper())
        if message_type:
            query = query.filter(MessageQueue.type == message_type)
        if created_after:
            try:
                created_date = datetime.fromisoformat(created_after)
                query = query.filter(MessageQueue.created_at >= created_date)
            except ValueError:
                raise ValueError(f"Invalid date format: {created_after}")
        if retry_count_min is not None:
            query = query.filter(MessageQueue.retry_count >= retry_count_min)

        # Get total count
        total = query.count()

        # Get paginated results
        messages = (
            query
            .order_by(MessageQueue.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        result = [
            {
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
                # Email-specific fields
                "email_status": m.email_status,
                "opened_at": m.opened_at.isoformat() if m.opened_at else None,
                "clicked_at": m.clicked_at.isoformat() if m.clicked_at else None,
                "bounced_at": m.bounced_at.isoformat() if m.bounced_at else None,
            }
            for m in messages
        ]

        return {
            "data": result,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    except Exception as e:
        logger.error(f"Failed to list queue messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list queue messages: {str(e)}")


@router.get("/stats")
def get_queue_stats(
    queue_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get comprehensive queue statistics.

    Returns status breakdown for all queues or specific queue type.

    Returns:
        {
            "total_messages": 500,
            "queues": {
                "EMAIL_QUEUE": {
                    "PENDING": 10,
                    "SLM_PROCESSING": 5,
                    "CHANNEL_QUEUED": 20,
                    "COMPLETED": 450,
                    "FAILED": 5,
                    "total": 490
                },
                "THUNDER_QUEUE": {...},
                ...
            },
            "email_metrics": {
                "total_sent": 490,
                "open_rate": 42.5,
                "click_rate": 18.2,
                "bounce_rate": 2.1,
                "reply_rate": 5.3
            }
        }
    """
    try:
        from app.models.message_queue import MessageQueue, MessageChannel
        from sqlalchemy import func

        stats = {
            "timestamp": datetime.utcnow().isoformat(),
            "queues": {},
            "email_metrics": None,
        }

        # Get stats per queue type
        if queue_type:
            # Get stats for specific queue
            channel_stats = (
                db.query(
                    MessageChannel.status,
                    func.count(MessageChannel.id).label("count"),
                )
                .filter(MessageChannel.queue_type == queue_type.upper())
                .group_by(MessageChannel.status)
                .all()
            )

            queue_stats_dict = {"total": 0}
            for status, count in channel_stats:
                queue_stats_dict[status] = count
                queue_stats_dict["total"] += count

            stats["queues"][queue_type.upper()] = queue_stats_dict
        else:
            # Get stats for all queues
            all_channel_stats = (
                db.query(
                    MessageChannel.queue_type,
                    MessageChannel.status,
                    func.count(MessageChannel.id).label("count"),
                )
                .group_by(MessageChannel.queue_type, MessageChannel.status)
                .all()
            )

            for queue_t, status, count in all_channel_stats:
                if queue_t not in stats["queues"]:
                    stats["queues"][queue_t] = {"total": 0}
                stats["queues"][queue_t][status] = count
                stats["queues"][queue_t]["total"] += count

            # Add email engagement metrics
            email_tracking_stats = (
                db.query(
                    func.count(MessageQueue.id).label("total_sent"),
                    func.count(func.nullif(MessageQueue.opened_at, None)).label("opened"),
                    func.count(func.nullif(MessageQueue.clicked_at, None)).label("clicked"),
                    func.count(func.nullif(MessageQueue.bounced_at, None)).label("bounced"),
                    func.count(func.nullif(MessageQueue.replied_at, None)).label("replied"),
                )
                .filter(MessageQueue.queue_type == "EMAIL_QUEUE")
                .first()
            )

            if email_tracking_stats and email_tracking_stats.total_sent > 0:
                total = email_tracking_stats.total_sent
                stats["email_metrics"] = {
                    "total_sent": total,
                    "opened": email_tracking_stats.opened or 0,
                    "clicked": email_tracking_stats.clicked or 0,
                    "bounced": email_tracking_stats.bounced or 0,
                    "replied": email_tracking_stats.replied or 0,
                    "open_rate": round((email_tracking_stats.opened or 0) / total * 100, 2),
                    "click_rate": round((email_tracking_stats.clicked or 0) / total * 100, 2),
                    "bounce_rate": round((email_tracking_stats.bounced or 0) / total * 100, 2),
                    "reply_rate": round((email_tracking_stats.replied or 0) / total * 100, 2),
                }

        return stats

    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get queue stats: {str(e)}")


@router.get("/{message_id}")
def get_message_detail(
    message_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed information about a message and its channel routes."""
    try:
        from app.models.message_queue import MessageQueue, MessageChannel, EmailTracking

        message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        # Get channel routes
        channels = db.query(MessageChannel).filter(MessageChannel.message_id == message_id).all()

        # Get email tracking if applicable
        email_trackings = db.query(EmailTracking).filter(EmailTracking.message_id == message_id).all()

        return {
            "message": {
                "id": message.id,
                "type": message.type,
                "queue_type": message.queue_type,
                "status": message.status,
                "payload": message.payload,
                "resource_id": message.resource_id,
                "retry_count": message.retry_count,
                "error": message.error,
                "created_at": message.created_at.isoformat() if message.created_at else None,
                "updated_at": message.updated_at.isoformat() if message.updated_at else None,
                "created_by": message.created_by,
            },
            "channels": [
                {
                    "id": c.id,
                    "queue_type": c.queue_type,
                    "status": c.status,
                    "error_details": c.error_details,
                    "processed_at": c.processed_at.isoformat() if c.processed_at else None,
                }
                for c in channels
            ],
            "email_tracking": [
                {
                    "id": et.id,
                    "recipient_email": et.recipient_email,
                    "provider": et.provider,
                    "status": et.status,
                    "open_count": et.open_count,
                    "click_count": et.click_count,
                    "opened_at": et.opened_at.isoformat() if et.opened_at else None,
                    "clicked_at": et.clicked_at.isoformat() if et.clicked_at else None,
                    "bounced_at": et.bounced_at.isoformat() if et.bounced_at else None,
                    "replied_at": et.replied_at.isoformat() if et.replied_at else None,
                }
                for et in email_trackings
            ],
        }

    except Exception as e:
        logger.error(f"Failed to get message detail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get message detail: {str(e)}")


@router.post("/{message_id}/retry")
def retry_message(
    message_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Manually retry a failed message."""
    try:
        from app.models.message_queue import MessageQueue

        message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        message.status = "PENDING"
        message.retry_count = 0
        message.error = None
        message.next_retry_at = None
        db.commit()

        logger.info(f"Message manually retried: {message_id}")

        return {
            "status": "success",
            "message": f"Message {message_id} queued for retry",
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to retry message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retry message: {str(e)}")


@router.post("/{message_id}/clear")
def clear_message(
    message_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Clear/dismiss a failed message."""
    try:
        from app.models.message_queue import MessageQueue

        message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        message.status = "FAILED"
        message.error = "Manually cleared by administrator"
        db.commit()

        logger.info(f"Message manually cleared: {message_id}")

        return {
            "status": "success",
            "message": f"Message {message_id} cleared",
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clear message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear message: {str(e)}")


@router.get("/email/{message_id}/engagement")
def get_email_engagement_metrics(
    message_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get email engagement metrics for a message."""
    try:
        from app.services.email_tracking_service import EmailTrackingService

        metrics = EmailTrackingService.get_engagement_metrics(message_id=message_id, db=db)

        return {
            "message_id": message_id,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get engagement metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get engagement metrics: {str(e)}")
