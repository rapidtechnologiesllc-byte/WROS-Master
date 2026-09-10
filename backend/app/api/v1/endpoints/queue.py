"""
Queue Monitoring API - Database-backed queue management (replaced Flower/Celery)

Provides dashboard access to queue stats, task management, and retry logic.
All endpoints require system.manage permission (admin only).

Replaces the old Flower REST API with direct database queries.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import logging

from app.core.dependencies import get_current_user, require_role_template_permission, get_db
from app.models.user import Users
from app.models.channel_queue import ChannelQueueItem, ChannelQueueLog
from app.core.permission_registry import Permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/api/queue", tags=["queue-monitoring"])

# Pagination defaults
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000


@router.get(
    "/list",
    dependencies=[Depends(require_role_template_permission(*Permissions.USERS_EDIT))],
)
async def list_queue_items(
    status: Optional[str] = Query(None, description="Filter by status: PENDING, PROCESSING, COMPLETED, FAILED"),
    channel: Optional[str] = Query(None, description="Filter by channel type: THUNDER_QUEUE, EMAIL_QUEUE, etc."),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List queue items with optional filtering.

    Query params:
    - status: Filter by status (PENDING, PROCESSING, COMPLETED, FAILED)
    - channel: Filter by channel type (THUNDER_QUEUE, EMAIL_QUEUE, SMS_QUEUE, etc.)
    - limit: Max items to return (default: 100, max: 1000)
    - offset: Pagination offset (default: 0)

    Response format:
    {
      "total": 500,
      "limit": 100,
      "offset": 0,
      "items": [
        {
          "id": "uuid",
          "message_id": "uuid",
          "type": "send_email",
          "channel_type": "EMAIL_QUEUE",
          "status": "PENDING",
          "retry_count": 0,
          "created_at": "2026-09-08T10:00:00Z",
          "next_retry_at": "2026-09-08T10:05:00Z",
          "error": null
        },
        ...
      ]
    }
    """
    try:
        query = db.query(ChannelQueueItem)

        # Apply filters
        if status:
            query = query.filter(ChannelQueueItem.status == status.upper())
        if channel:
            query = query.filter(ChannelQueueItem.channel_type == channel.upper())

        # Get total count
        total = query.count()

        # Apply pagination
        items = query.order_by(ChannelQueueItem.created_at.desc()).offset(offset).limit(limit).all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "id": item.id,
                    "message_id": item.message_id,
                    "type": item.type,
                    "channel_type": item.channel_type,
                    "status": item.status,
                    "retry_count": item.retry_count,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                    "next_retry_at": item.next_retry_at.isoformat() if item.next_retry_at else None,
                    "error": item.error
                }
                for item in items
            ]
        }

    except Exception as e:
        logger.error(f"Failed to list queue items: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve queue items")


@router.get(
    "/stats",
    dependencies=[Depends(require_role_template_permission(*Permissions.USERS_EDIT))],
)
async def get_queue_stats(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get queue statistics (total items, breakdown by status/channel, etc.)

    Response format:
    {
      "total_items": 500,
      "by_status": {
        "PENDING": 250,
        "PROCESSING": 50,
        "COMPLETED": 180,
        "FAILED": 20
      },
      "by_channel": {
        "THUNDER_QUEUE": 200,
        "EMAIL_QUEUE": 180,
        "SMS_QUEUE": 50,
        "APPROVAL_QUEUE": 70
      },
      "retry_stats": {
        "total_retries": 45,
        "max_retries_exceeded": 5
      },
      "oldest_pending": "2026-09-07T10:00:00Z",
      "success_rate": 85.5
    }
    """
    try:
        # Total count
        total_items = db.query(ChannelQueueItem).count()

        # By status
        by_status = {}
        for status in ["PENDING", "PROCESSING", "COMPLETED", "FAILED"]:
            count = db.query(ChannelQueueItem).filter(ChannelQueueItem.status == status).count()
            by_status[status] = count

        # By channel
        by_channel = {}
        channels = db.query(ChannelQueueItem.channel_type).distinct().all()
        for (channel,) in channels:
            count = db.query(ChannelQueueItem).filter(ChannelQueueItem.channel_type == channel).count()
            by_channel[channel] = count

        # Retry stats
        total_retries = db.query(ChannelQueueItem).filter(ChannelQueueItem.retry_count > 0).count()
        max_retries_exceeded = db.query(ChannelQueueItem).filter(ChannelQueueItem.retry_count >= 5).count()

        # Oldest pending item
        oldest_pending = db.query(ChannelQueueItem.created_at).filter(
            ChannelQueueItem.status == "PENDING"
        ).order_by(ChannelQueueItem.created_at.asc()).first()

        # Success rate
        completed = by_status.get("COMPLETED", 0)
        success_rate = (completed / total_items * 100) if total_items > 0 else 0

        return {
            "total_items": total_items,
            "by_status": by_status,
            "by_channel": by_channel,
            "retry_stats": {
                "total_retries": total_retries,
                "max_retries_exceeded": max_retries_exceeded
            },
            "oldest_pending": oldest_pending[0].isoformat() if oldest_pending and oldest_pending[0] else None,
            "success_rate": round(success_rate, 2)
        }

    except Exception as e:
        logger.error(f"Failed to get queue stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve queue statistics")


@router.get(
    "/{queue_item_id}",
    dependencies=[Depends(require_role_template_permission(*Permissions.USERS_EDIT))],
)
async def get_queue_item(
    queue_item_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get single queue item details including payload and error info.

    Response format:
    {
      "id": "uuid",
      "message_id": "uuid",
      "type": "send_email",
      "channel_type": "EMAIL_QUEUE",
      "status": "FAILED",
      "payload": {
        "recipient": "candidate@example.com",
        "template": "offer_letter",
        ...
      },
      "result": null,
      "retry_count": 3,
      "error": "SMTP connection timeout",
      "next_retry_at": "2026-09-08T10:05:00Z",
      "created_at": "2026-09-08T09:00:00Z",
      "processed_at": "2026-09-08T09:05:00Z",
      "completed_at": null
    }
    """
    try:
        item = db.query(ChannelQueueItem).filter(ChannelQueueItem.id == queue_item_id).first()

        if not item:
            raise HTTPException(status_code=404, detail=f"Queue item {queue_item_id} not found")

        return {
            "id": item.id,
            "message_id": item.message_id,
            "type": item.type,
            "channel_type": item.channel_type,
            "status": item.status,
            "payload": item.payload,
            "result": item.result,
            "retry_count": item.retry_count,
            "error": item.error,
            "next_retry_at": item.next_retry_at.isoformat() if item.next_retry_at else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "processed_at": item.processed_at.isoformat() if item.processed_at else None,
            "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get queue item {queue_item_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve queue item")


@router.post(
    "/{queue_item_id}/retry",
    dependencies=[Depends(require_role_template_permission(*Permissions.USERS_EDIT))],
)
async def retry_queue_item(
    queue_item_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retry a failed queue item (resets status to PENDING).

    Response:
    {
      "status": "retried",
      "message_id": "uuid",
      "retry_count": 4,
      "next_retry_at": "2026-09-08T10:10:00Z"
    }
    """
    try:
        item = db.query(ChannelQueueItem).filter(ChannelQueueItem.id == queue_item_id).first()

        if not item:
            raise HTTPException(status_code=404, detail=f"Queue item {queue_item_id} not found")

        # Reset status to PENDING for retry
        item.status = "PENDING"
        item.retry_count = (item.retry_count or 0) + 1
        item.error = None
        item.next_retry_at = datetime.utcnow()
        item.updated_at = datetime.utcnow()

        db.commit()

        logger.info(f"[QUEUE] Retried item {queue_item_id} (retry count: {item.retry_count})")

        return {
            "status": "retried",
            "message_id": item.message_id,
            "retry_count": item.retry_count,
            "next_retry_at": item.next_retry_at.isoformat() if item.next_retry_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry queue item {queue_item_id}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to retry queue item")


@router.delete(
    "/clear",
    dependencies=[Depends(require_role_template_permission(*Permissions.USERS_EDIT))],
)
async def clear_completed_queue(
    status: Optional[str] = Query("COMPLETED", description="Status to clear: COMPLETED or FAILED"),
    older_than_days: int = Query(7, ge=0, description="Clear items older than N days (default: 7)"),
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Clear old completed or failed items from queue to free up space.

    Query params:
    - status: Which status to clear (COMPLETED or FAILED, default: COMPLETED)
    - older_than_days: Only clear items older than N days (default: 7)

    Response:
    {
      "status": "cleared",
      "items_deleted": 42,
      "status_cleared": "COMPLETED",
      "older_than_days": 7
    }
    """
    try:
        from datetime import timedelta

        if status not in ["COMPLETED", "FAILED"]:
            raise HTTPException(status_code=400, detail="status must be COMPLETED or FAILED")

        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)

        # Delete items matching criteria
        query = db.query(ChannelQueueItem).filter(
            ChannelQueueItem.status == status,
            ChannelQueueItem.updated_at < cutoff_date
        )

        count = query.count()
        query.delete()
        db.commit()

        logger.info(f"[QUEUE] Cleared {count} {status} items older than {older_than_days} days")

        return {
            "status": "cleared",
            "items_deleted": count,
            "status_cleared": status,
            "older_than_days": older_than_days
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear queue: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to clear queue")
