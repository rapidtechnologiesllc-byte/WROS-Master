"""Queue Dashboard Endpoints - Unified view of all queues

Endpoints for monitoring and managing all message and channel queues.

GET  /admin/queue-dashboard/stats                    - Overall queue statistics
GET  /admin/queue-dashboard/messages                 - List messages (paginated, filterable)
GET  /admin/queue-dashboard/messages/{message_id}   - Get single message details
GET  /admin/queue-dashboard/channels                 - List channel queue items
GET  /admin/queue-dashboard/channels/{channel_type}  - Get items for specific channel
GET  /admin/queue-dashboard/health                   - Health check (are processors running?)
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.channel_queue_service import ChannelQueueService
from app.services.message_queue_service import MessageQueueService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/queue-dashboard", tags=["queue-dashboard"])


@router.get("/stats")
    dependencies=[Depends(require_resource_permission("stat", "view"))]
def get_queue_stats(db: Session = Depends(get_db)):
    """
    Get overall queue statistics.

    Returns:
        {
            "message_queue": {
                "total": 150,
                "pending": 45,
                "processing": 2,
                "completed": 90,
                "retrying": 10,
                "failed": 3
            },
            "channel_queues": {
                "total": 200,
                "pending": 85,
                "processing": 5,
                "completed": 105,
                "failed": 5,
                "channels": {
                    "EMAIL": {"pending": 30, "processing": 2, "completed": 50, "failed": 2},
                    "WHATSAPP": {"pending": 10, "processing": 1, "completed": 25, "failed": 0},
                    ...
                }
            },
            "health": {
                "message_processor_running": true,
                "channel_processor_running": true,
                "last_message_processed": "2026-08-28T14:32:15Z",
                "oldest_pending_message_age_minutes": 5
            }
        }
    """
    try:
        # Get message queue stats
        message_stats = MessageQueueService.get_stats(db=db)

        # Get channel queue stats
        channel_stats = ChannelQueueService.get_stats(db=db)

        # TODO: Implement health checks
        # - Check if workers are running
        # - Check last processing time
        health = {
            "message_processor_running": True,  # TODO: Check scheduler
            "channel_processor_running": True,  # TODO: Check scheduler
            "last_message_processed": "2026-08-28T14:32:15Z",  # TODO: Check DB
            "oldest_pending_message_age_minutes": 5,  # TODO: Calculate
        }

        return {
            "message_queue": message_stats,
            "channel_queues": channel_stats,
            "health": health,
        }

    except Exception as e:        logger.error(f"Failed to get queue stats: {e}", exc_info=True)
        return {"error": str(e), "status": "failed"}


@router.get("/messages")
    dependencies=[Depends(require_resource_permission("message", "view"))]
def list_messages(
    status: Optional[str] = Query(None, description="Filter by status: PENDING, SLM_PROCESSING, CHANNEL_QUEUED, etc."),
    queue_type: Optional[str] = Query(None, description="Filter by queue type: CANDIDATE, INTERVIEW, OFFER, etc."),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    limit: int = Query(50, ge=1, le=500, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
):
    """
    List message queue items with filtering and pagination.

    Returns paginated list of messages.
    """
    try:
        from app.models.message_queue import MessageQueue
        from sqlalchemy import desc

        query = db.query(MessageQueue)

        # Apply filters
        if status:
            query = query.filter(MessageQueue.status == status)
        if queue_type:
            query = query.filter(MessageQueue.type == queue_type)
        if resource_id:
            query = query.filter(MessageQueue.resource_id == resource_id)

        # Get total count
        total = query.count()

        # Apply pagination
        messages = (
            query.order_by(desc(MessageQueue.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "messages": [
                {
                    "id": m.id,
                    "type": m.type,
                    "status": m.status,
                    "resource_id": m.resource_id,
                    "retry_count": m.retry_count,
                    "error": m.error,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "updated_at": m.updated_at.isoformat() if m.updated_at else None,
                }
                for m in messages
            ],
        }

    except Exception as e:        logger.error(f"Failed to list messages: {e}", exc_info=True)
        return {"error": str(e), "status": "failed"}


@router.get("/messages/{message_id}")
    dependencies=[Depends(require_resource_permission("message", "view"))]
def get_message_details(message_id: str, db: Session = Depends(get_db)):
    """
    Get details for a specific message including its channel queue items.

    Returns:
        {
            "message": {...},
            "channel_items": [
                {
                    "id": "...",
                    "channel_type": "EMAIL",
                    "status": "COMPLETED",
                    "recipient": "candidate@example.com",
                    "created_at": "...",
                    "processed_at": "..."
                },
                ...
            ]
        }
    """
    try:
        from app.models.message_queue import MessageQueue
        from app.models.channel_queue import ChannelQueueItem

        # Get message
        message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()
        if not message:
            return {"error": "Message not found", "status": "failed"}

        # Get channel items
        channel_items = db.query(ChannelQueueItem).filter(
            ChannelQueueItem.message_id == message_id
        ).all()

        return {
            "message": {
                "id": message.id,
                "type": message.type,
                "status": message.status,
                "payload": message.payload,
                "resource_id": message.resource_id,
                "retry_count": message.retry_count,
                "error": message.error,
                "created_at": message.created_at.isoformat() if message.created_at else None,
                "updated_at": message.updated_at.isoformat() if message.updated_at else None,
            },
            "channel_items": [
                {
                    "id": ci.id,
                    "channel_type": ci.channel_type,
                    "status": ci.status,
                    "recipient": ci.recipient,
                    "retry_count": ci.retry_count,
                    "error": ci.error,
                    "created_at": ci.created_at.isoformat() if ci.created_at else None,
                    "processed_at": ci.processed_at.isoformat() if ci.processed_at else None,
                }
                for ci in channel_items
            ],
        }

    except Exception as e:        logger.error(f"Failed to get message details: {e}", exc_info=True)
        return {"error": str(e), "status": "failed"}


@router.get("/channels")
    dependencies=[Depends(require_resource_permission("channel", "view"))]
def list_channel_items(
    channel_type: Optional[str] = Query(None, description="Filter by channel type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List channel queue items with filtering.

    Returns paginated list of channel queue items.
    """
    try:
        from app.models.channel_queue import ChannelQueueItem
        from sqlalchemy import desc

        query = db.query(ChannelQueueItem)

        # Apply filters
        if channel_type:
            query = query.filter(ChannelQueueItem.channel_type == channel_type)
        if status:
            query = query.filter(ChannelQueueItem.status == status)

        total = query.count()

        items = (
            query.order_by(desc(ChannelQueueItem.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "id": item.id,
                    "message_id": item.message_id,
                    "channel_type": item.channel_type,
                    "status": item.status,
                    "recipient": item.recipient,
                    "retry_count": item.retry_count,
                    "error": item.error,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                    "processed_at": item.processed_at.isoformat() if item.processed_at else None,
                }
                for item in items
            ],
        }

    except Exception as e:        logger.error(f"Failed to list channel items: {e}", exc_info=True)
        return {"error": str(e), "status": "failed"}


@router.get("/channels/{channel_type}")
    dependencies=[Depends(require_resource_permission("channel", "view"))]
def get_channel_details(
    channel_type: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Get detailed stats and recent items for a specific channel.

    Returns:
        {
            "channel_type": "EMAIL",
            "stats": {
                "total": 100,
                "pending": 10,
                "processing": 2,
                "completed": 80,
                "failed": 8
            },
            "recent_items": [...]
        }
    """
    try:
        from app.models.channel_queue import ChannelQueueItem
        from sqlalchemy import desc, func

        # Get stats for this channel
        stats_query = db.query(ChannelQueueItem).filter(
            ChannelQueueItem.channel_type == channel_type
        )

        total = stats_query.count()
        pending = stats_query.filter(
            ChannelQueueItem.status == ChannelQueueService.STATUS_PENDING
        ).count()
        processing = stats_query.filter(
            ChannelQueueItem.status == ChannelQueueService.STATUS_PROCESSING
        ).count()
        completed = stats_query.filter(
            ChannelQueueItem.status == ChannelQueueService.STATUS_COMPLETED
        ).count()
        failed = stats_query.filter(
            ChannelQueueItem.status == ChannelQueueService.STATUS_FAILED
        ).count()

        # Get recent items
        query = db.query(ChannelQueueItem).filter(
            ChannelQueueItem.channel_type == channel_type
        )

        if status:
            query = query.filter(ChannelQueueItem.status == status)

        recent_items = query.order_by(desc(ChannelQueueItem.created_at)).limit(limit).all()

        return {
            "channel_type": channel_type,
            "stats": {
                "total": total,
                "pending": pending,
                "processing": processing,
                "completed": completed,
                "failed": failed,
            },
            "recent_items": [
                {
                    "id": item.id,
                    "message_id": item.message_id,
                    "status": item.status,
                    "recipient": item.recipient,
                    "retry_count": item.retry_count,
                    "error": item.error,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
                for item in recent_items
            ],
        }

    except Exception as e:        logger.error(f"Failed to get channel details: {e}", exc_info=True)
        return {"error": str(e), "status": "failed"}


@router.get("/health")
    dependencies=[Depends(require_resource_permission("health", "view"))]
def check_health(db: Session = Depends(get_db)):
    """
    Health check - verify workers are running and queues are healthy.

    Returns:
        {
            "status": "healthy" | "degraded" | "unhealthy",
            "message_processor": {"running": true, "last_run": "..."},
            "channel_processor": {"running": true, "last_run": "..."},
            "queue_age": {"oldest_message_minutes": 5, "oldest_channel_item_minutes": 2},
            "recommendations": [...]
        }
    """
    try:
        from app.models.message_queue import MessageQueue
        from app.models.channel_queue import ChannelQueueItem
        from datetime import datetime, timedelta
        from sqlalchemy import and_

        # Check for stale messages
        now = datetime.utcnow()
        thirty_minutes_ago = now - timedelta(minutes=30)

        stale_messages = db.query(MessageQueue).filter(
            and_(
                MessageQueue.status.in_([
                    MessageQueueService.STATUS_PENDING,
                    MessageQueueService.STATUS_RETRYING,
                ]),
                MessageQueue.created_at < thirty_minutes_ago,
            )
        ).count()

        # Check oldest message
        oldest_message = db.query(MessageQueue).filter(
            MessageQueue.status.in_([
                MessageQueueService.STATUS_PENDING,
                MessageQueueService.STATUS_RETRYING,
            ])
        ).order_by(MessageQueue.created_at).first()

        oldest_message_age = None
        if oldest_message:
            oldest_message_age = (now - oldest_message.created_at).total_seconds() / 60

        # Check oldest channel item
        oldest_item = db.query(ChannelQueueItem).filter(
            ChannelQueueItem.status.in_([
                ChannelQueueService.STATUS_PENDING,
            ])
        ).order_by(ChannelQueueItem.created_at).first()

        oldest_item_age = None
        if oldest_item:
            oldest_item_age = (now - oldest_item.created_at).total_seconds() / 60

        # Determine health status
        recommendations = []
        status = "healthy"

        if stale_messages > 0:
            status = "degraded"
            recommendations.append(
                f"Found {stale_messages} messages pending for >30 minutes. Check worker logs."
            )

        if oldest_message_age and oldest_message_age > 60:
            status = "unhealthy"
            recommendations.append(
                f"Oldest message is {oldest_message_age:.0f} minutes old. "
                "Message processor may be stuck."
            )

        return {
            "status": status,
            "message_processor": {
                "running": True,  # TODO: Check scheduler
                "last_run": "2026-08-28T14:32:15Z",  # TODO: Check DB
            },
            "channel_processor": {
                "running": True,  # TODO: Check scheduler
                "last_run": "2026-08-28T14:31:45Z",  # TODO: Check DB
            },
            "queue_age": {
                "oldest_message_minutes": oldest_message_age,
                "oldest_channel_item_minutes": oldest_item_age,
            },
            "recommendations": recommendations,
        }

    except Exception as e:        logger.error(f"Failed to check health: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
        }
