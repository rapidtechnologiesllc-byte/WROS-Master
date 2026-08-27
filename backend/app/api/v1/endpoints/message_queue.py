"""Message Queue API Endpoints - Admin and operational APIs for message queue management.

Endpoints:
- GET /admin/message-queue - List messages with filters
- GET /admin/message-queue/{message_id} - Get message details
- POST /admin/message-queue/{message_id}/retry - Manually retry a message
- POST /admin/message-queue/{message_id}/skip - Skip a message without processing
- GET /admin/message-queue/stats - Dashboard statistics
- POST /admin/message-queue/flush - Flush messages of a type
- GET /health/message-queue - Health check
"""

import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin_role
from app.services.message_queue_service import MessageQueueService, STATUS_PENDING, STATUS_FAILED
from app.models.message_queue import MessageQueue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/message-queue", tags=["message-queue"])


@router.get("")
def list_messages(
    status: Optional[str] = Query(None, description="Filter by status (PENDING, PROCESSING, COMPLETED, FAILED, RETRYING)"),
    message_type: Optional[str] = Query(None, description="Filter by message type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    limit: int = Query(50, ge=1, le=1000, description="Number of messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin_role),
) -> dict:
    """
    List message queue items with optional filters.

    Query Parameters:
    - status: Filter by status (PENDING, PROCESSING, COMPLETED, FAILED, RETRYING)
    - message_type: Filter by message type (candidate_added, thunder_email, etc.)
    - resource_id: Filter by resource ID (candidate_id, job_id, etc.)
    - limit: Number of results (1-1000, default 50)
    - offset: Pagination offset (default 0)

    Returns:
    - messages: List of message queue items
    - total: Total count (before pagination)
    - limit/offset: Pagination info
    """
    try:
        # Build query
        query = db.query(MessageQueue)

        # Apply filters
        if status:
            query = query.filter(MessageQueue.status == status)
        if message_type:
            query = query.filter(MessageQueue.type == message_type)
        if resource_id:
            query = query.filter(MessageQueue.resource_id == resource_id)

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        messages = (
            query.order_by(MessageQueue.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "messages": [
                {
                    "id": msg.id,
                    "type": msg.type,
                    "status": msg.status,
                    "resource_id": msg.resource_id,
                    "created_at": msg.created_at,
                    "updated_at": msg.updated_at,
                    "retry_count": msg.retry_count,
                    "error_message": msg.error_message,
                    "created_by": msg.created_by,
                }
                for msg in messages
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"Failed to list messages: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list messages: {str(e)}"
        )


@router.get("/{message_id}")
def get_message(
    message_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin_role),
) -> dict:
    """
    Get detailed information about a specific message.

    Includes:
    - Message payload and status
    - Full error message if failed
    - Complete processing history/logs
    - Retry information

    Path Parameters:
    - message_id: Message UUID

    Returns:
    - id: Message ID
    - type: Message type
    - status: Current status
    - payload: Full message payload
    - retry_count: Number of retry attempts
    - error_message: Full error description if failed
    - logs: Complete processing history with timestamps
    """
    try:
        # Get message
        message = MessageQueueService.get_message_by_id(db, message_id)

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message not found: {message_id}"
            )

        # Get logs for this message
        logs = [
            {
                "status": log.status,
                "error": log.error,
                "timestamp": log.timestamp,
                "duration_ms": log.duration_ms,
                "retry_attempt": log.retry_attempt,
            }
            for log in message.logs
        ]

        return {
            "id": message.id,
            "type": message.type,
            "status": message.status,
            "resource_id": message.resource_id,
            "payload": message.payload,
            "retry_count": message.retry_count,
            "error_message": message.error_message,
            "created_at": message.created_at,
            "updated_at": message.updated_at,
            "processing_started_at": message.processing_started_at,
            "completed_at": message.completed_at,
            "next_retry_at": message.next_retry_at,
            "created_by": message.created_by,
            "logs": logs,
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to get message {message_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get message: {str(e)}"
        )


@router.post("/{message_id}/retry")
def retry_message(
    message_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin_role),
) -> dict:
    """
    Manually retry a failed message.

    Resets retry_count to 0 if max retries exceeded,
    allowing manual recovery of stuck messages.

    Path Parameters:
    - message_id: Message UUID

    Returns:
    - status: "success" or "error"
    - message_id: ID of retried message
    - next_retry_at: When the message will be processed
    """
    try:
        message = MessageQueueService.get_message_by_id(db, message_id)

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message not found: {message_id}"
            )

        # If message already succeeded, can't retry
        if message.status == "COMPLETED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot retry a completed message"
            )

        # Reset retry count and schedule retry
        message.retry_count = 0
        MessageQueueService.schedule_retry(db, message_id, "Manual retry requested")

        updated_message = MessageQueueService.get_message_by_id(db, message_id)

        return {
            "status": "success",
            "message_id": message_id,
            "next_retry_at": updated_message.next_retry_at,
            "message": "Message scheduled for retry",
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to retry message {message_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry message: {str(e)}"
        )


@router.post("/{message_id}/skip")
def skip_message(
    message_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin_role),
) -> dict:
    """
    Skip processing a message without retrying.

    Marks message as COMPLETED without running handler,
    useful for ignoring problematic or obsolete messages.

    Path Parameters:
    - message_id: Message UUID

    Returns:
    - status: "success" or "error"
    - message_id: ID of skipped message
    """
    try:
        message = MessageQueueService.get_message_by_id(db, message_id)

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message not found: {message_id}"
            )

        # Skip the message
        MessageQueueService.mark_completed(db, message_id)

        return {
            "status": "success",
            "message_id": message_id,
            "message": "Message skipped and marked as completed",
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to skip message {message_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to skip message: {str(e)}"
        )


@router.get("/stats/dashboard")
def get_queue_stats(
    db: Session = Depends(get_db),
    current_user = Depends(require_admin_role),
) -> dict:
    """
    Get message queue statistics for dashboard display.

    Returns overview of queue health and performance metrics.

    Returns:
    - pending: Count of PENDING messages
    - processing: Count of PROCESSING messages
    - completed: Count of COMPLETED messages
    - failed: Count of FAILED messages
    - retrying: Count of RETRYING messages
    - total: Total message count
    - success_rate: Percentage of successfully processed messages
    - oldest_pending_created_at: When the oldest pending message was created
    """
    try:
        # Get tenant ID from current user
        tenant_id = getattr(current_user, 'tenant_id', 1)

        stats = MessageQueueService.get_queue_stats(db, tenant_id)

        return {
            "status": "success",
            "data": stats,
            "timestamp": datetime.utcnow(),
        }

    except Exception as e:
        logger.error(f"Failed to get queue stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get queue stats: {str(e)}"
        )


@router.post("/flush")
def flush_messages(
    message_type: str = Query(..., description="Message type to flush (candidate_added, thunder_email, etc.)"),
    dry_run: bool = Query(False, description="If true, show what would be deleted without deleting"),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin_role),
) -> dict:
    """
    Flush all messages of a specific type from the queue.

    Useful for cleaning up stuck messages or test data.

    Query Parameters:
    - message_type: Type of messages to flush
    - dry_run: If true, returns count without deleting (default false)

    Returns:
    - status: "success"
    - message_type: Type that was flushed
    - count: Number of messages deleted
    - dry_run: Whether this was a dry run
    """
    try:
        if dry_run:
            # Just count
            count = db.query(MessageQueue).filter(MessageQueue.type == message_type).count()

            return {
                "status": "success",
                "message_type": message_type,
                "count": count,
                "dry_run": True,
                "message": f"Dry run: would delete {count} messages of type '{message_type}'",
            }

        else:
            # Actually delete
            count = db.query(MessageQueue).filter(MessageQueue.type == message_type).delete()
            db.commit()

            logger.info(f"Flushed {count} messages of type '{message_type}'")

            return {
                "status": "success",
                "message_type": message_type,
                "count": count,
                "dry_run": False,
                "message": f"Deleted {count} messages of type '{message_type}'",
            }

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to flush messages: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to flush messages: {str(e)}"
        )


@router.get("/health/check")
def health_check(db: Session = Depends(get_db)) -> dict:
    """
    Health check for message queue system.

    Returns status of queue operations and any issues.

    Returns:
    - status: "healthy", "degraded", or "unhealthy"
    - pending_count: Number of pending messages
    - oldest_pending_age_seconds: Age of oldest pending message
    - failed_count: Number of failed messages
    """
    try:
        tenant_id = 1  # Default tenant

        # Get stats
        pending = db.query(MessageQueue).filter(
            MessageQueue.status == STATUS_PENDING
        ).count()

        failed = db.query(MessageQueue).filter(
            MessageQueue.status == STATUS_FAILED
        ).count()

        # Get oldest pending
        oldest = db.query(MessageQueue).filter(
            MessageQueue.status == STATUS_PENDING
        ).order_by(MessageQueue.created_at.asc()).first()

        oldest_age = None
        if oldest:
            oldest_age = (datetime.utcnow() - oldest.created_at).total_seconds()

        # Determine health status
        if failed > 100 or (oldest_age and oldest_age > 3600):
            health_status = "degraded"
        elif failed > 500 or (oldest_age and oldest_age > 7200):
            health_status = "unhealthy"
        else:
            health_status = "healthy"

        return {
            "status": health_status,
            "pending_count": pending,
            "failed_count": failed,
            "oldest_pending_age_seconds": oldest_age,
            "timestamp": datetime.utcnow(),
        }

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow(),
        }
