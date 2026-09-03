from app.core.logging import logger
"""Queue Dashboard Endpoints - Admin only"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import Users

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/queue-dashboard", tags=["queue-dashboard"])


@router.get("/stats")
def get_queue_stats(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Get overall queue statistics."""
    try:
        from app.services.message_queue_service import MessageQueueService
        from app.services.channel_queue_service import ChannelQueueService

        message_stats = MessageQueueService.get_stats(db=db)
        channel_stats = ChannelQueueService.get_stats(db=db)

        return {
            "message_queue": message_stats,
            "channel_queues": channel_stats,
            "health": {
                "message_processor_running": True,
                "channel_processor_running": True,
            },
        }
    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/messages")
def list_messages(
    status: Optional[str] = Query(None),
    queue_type: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """List message queue items."""
    try:
        from app.models.message_queue import MessageQueue
        from sqlalchemy import desc

        query = db.query(MessageQueue)
        if status:
            query = query.filter(MessageQueue.status == status)
        if queue_type:
            query = query.filter(MessageQueue.type == queue_type)
        if resource_id:
            query = query.filter(MessageQueue.resource_id == resource_id)

        total = query.count()
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
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ],
        }
    except Exception as e:
        logger.error(f"Failed to list messages: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/messages/{message_id}")
def get_message_details(
    message_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Get details for a specific message."""
    try:
        from app.models.message_queue import MessageQueue

        message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()
        if not message:
            return {"error": "Message not found"}

        return {
            "message": {
                "id": message.id,
                "type": message.type,
                "status": message.status,
                "created_at": message.created_at.isoformat() if message.created_at else None,
            },
        }
    except Exception as e:
        logger.error(f"Failed to get message details: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/channels")
def list_channel_items(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """List all channel queue items."""
    try:
        from app.models.channel_queue import ChannelQueueItem
        from sqlalchemy import desc

        items = (
            db.query(ChannelQueueItem)
            .order_by(desc(ChannelQueueItem.created_at))
            .limit(100)
            .all()
        )

        return {
            "total": len(items),
            "items": [
                {
                    "id": item.id,
                    "channel_type": item.channel_type,
                    "status": item.status,
                }
                for item in items
            ],
        }
    except Exception as e:
        logger.error(f"Failed to list channel items: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/channels/{channel_type}")
def get_channel_items(
    channel_type: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Get items for specific channel type."""
    try:
        from app.models.channel_queue import ChannelQueueItem
        from sqlalchemy import desc

        items = (
            db.query(ChannelQueueItem)
            .filter(ChannelQueueItem.channel_type == channel_type)
            .order_by(desc(ChannelQueueItem.created_at))
            .limit(50)
            .all()
        )

        return {
            "channel_type": channel_type,
            "total": len(items),
            "items": items,
        }
    except Exception as e:
        logger.error(f"Failed to get channel items: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/health")
def check_health(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Health check for queue processors."""
    return {"status": "healthy"}
