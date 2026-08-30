"""Message Queue Endpoints - Display all queues and messages

GET  /queues              - List all queue messages (filterable by queue_type, status)
GET  /queues/stats        - Get queue statistics
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.message_queue import MessageQueue
from app.services.message_queue_service import MessageQueueService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queues", tags=["queues"])


@router.get("")
def get_queue_messages(
    queue_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Get all queue messages with optional filtering.

    Query Parameters:
        queue_type: Filter by queue type (e.g., THUNDER_QUEUE, EMAIL_QUEUE)
        status: Filter by status (PENDING, PROCESSING, COMPLETED, FAILED, RETRYING)
        limit: Number of messages to return (max 500)
        offset: Pagination offset

    Returns:
        {
            "data": [
                {
                    "id": "uuid",
                    "type": "candidate_created",
                    "queue_type": "THUNDER_QUEUE",
                    "status": "PENDING",
                    "resource_id": "uuid",
                    "created_by": "user-id",
                    "created_at": "2026-08-30T...",
                    "payload": {...}
                }
            ],
            "total": 100,
            "limit": 50,
            "offset": 0
        }
    """
    try:
        query = db.query(MessageQueue)

        # Apply filters
        if queue_type:
            query = query.filter(MessageQueue.queue_type == queue_type)
        if status:
            query = query.filter(MessageQueue.status == status)

        # Get total count
        total = query.count()

        # Apply pagination
        messages = query.order_by(MessageQueue.created_at.desc()).offset(offset).limit(limit).all()

        # Format response
        data = [
            {
                "id": m.id,
                "type": m.type,
                "queue_type": m.queue_type,
                "status": m.status,
                "resource_id": m.resource_id,
                "created_by": m.created_by,
                "retry_count": m.retry_count,
                "error": m.error,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None,
                "payload": m.payload,
            }
            for m in messages
        ]

        return {
            "data": data,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"Failed to fetch queue messages: {e}", exc_info=True)
        raise


@router.get("/stats")
def get_queue_stats(db: Session = Depends(get_db)):
    """
    Get queue statistics.

    Returns:
        {
            "total": 100,
            "by_queue_type": {
                "THUNDER_QUEUE": 50,
                "EMAIL_QUEUE": 30,
                "WHATSAPP_QUEUE": 20
            },
            "by_status": {
                "PENDING": 45,
                "PROCESSING": 5,
                "COMPLETED": 40,
                "FAILED": 10
            }
        }
    """
    try:
        # Get all messages
        messages = db.query(MessageQueue).all()
        total = len(messages)

        # Count by queue type
        by_queue_type = {}
        for m in messages:
            queue_type = m.queue_type or "UNKNOWN"
            by_queue_type[queue_type] = by_queue_type.get(queue_type, 0) + 1

        # Count by status
        by_status = {}
        for m in messages:
            status = m.status or "UNKNOWN"
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "total": total,
            "by_queue_type": by_queue_type,
            "by_status": by_status,
        }
    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}", exc_info=True)
        raise
