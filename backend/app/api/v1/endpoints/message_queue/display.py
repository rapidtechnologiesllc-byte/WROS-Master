"""
Message Queue Display Endpoint - View all queue operations as rows

Shows all messages in each queue type with their status, action, and metadata.
Each row represents one CRUD operation waiting to be processed.

Queue Types:
- CANDIDATE_QUEUE: Create/Update/Delete candidate operations
- THUNDER_QUEUE: Autonomous candidate engagement
- EMAIL_QUEUE: Email delivery operations
- INTERVIEW_QUEUE: Interview scheduling
- OFFER_QUEUE: Offer generation
- ONBOARDING_QUEUE: Employee onboarding
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
import logging

from app.core.dependencies import get_current_user, get_db, require_resource_permission
from app.models.user import Users
from app.models.message_queue import MessageQueue
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/message-queue", tags=["message-queue"])


class QueueMessageRow(BaseModel):
    """Single message queue row for display"""
    id: str = Field(..., description="Message ID")
    queue_type: str = Field(..., description="Queue type (CANDIDATE_QUEUE, THUNDER_QUEUE, etc)")
    message_type: str = Field(..., description="Message type (candidate_created, etc)")
    action: str = Field(..., description="CRUD action: CREATE, UPDATE, DELETE, PROCESS")
    status: str = Field(..., description="Message status: PENDING, PROCESSING, COMPLETED, FAILED, RETRYING")
    resource_id: Optional[str] = Field(default=None, description="Related resource ID")
    created_by: str = Field(..., description="User who created this message")
    created_at: str = Field(..., description="Creation timestamp")
    retry_count: int = Field(default=0, description="Number of retries")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    payload_preview: dict = Field(..., description="First 3 fields of payload for preview")

    class Config:
        extra = "forbid"


class QueueDisplayResponse(BaseModel):
    """Queue display response with rows grouped by queue type"""
    total_messages: int = Field(..., description="Total messages across all queues")
    queue_breakdown: dict = Field(..., description="Messages per queue type")
    rows: List[QueueMessageRow] = Field(..., description="All messages as display rows")

    class Config:
        extra = "forbid"


def _extract_action(message_type: str) -> str:
    """Extract CRUD action from message type"""
    if "create" in message_type.lower():
        return "CREATE"
    elif "update" in message_type.lower():
        return "UPDATE"
    elif "delete" in message_type.lower():
        return "DELETE"
    elif "scheduled" in message_type.lower():
        return "SCHEDULE"
    elif "generated" in message_type.lower():
        return "GENERATE"
    elif "onboard" in message_type.lower():
        return "ONBOARD"
    else:
        return "PROCESS"


def _preview_payload(payload: dict, max_fields: int = 3) -> dict:
    """Extract first N fields from payload for preview"""
    preview = {}
    for i, (key, value) in enumerate(payload.items()):
        if i >= max_fields:
            break
        # Truncate long values
        if isinstance(value, str) and len(value) > 100:
            preview[key] = value[:100] + "..."
        elif isinstance(value, dict):
            preview[key] = f"<object with {len(value)} fields>"
        elif isinstance(value, list):
            preview[key] = f"<array with {len(value)} items>"
        else:
            preview[key] = value
    return preview


@router.get(
    "/display",
    dependencies=[Depends(require_resource_permission("message-queue", "view"))],
    summary="Display all message queue operations",
    description="View all messages in the queue system as rows with action, status, and preview",
    response_model=QueueDisplayResponse
)
def display_message_queue(
    queue_type: Optional[str] = None,
    status: Optional[str] = None,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Display all message queue operations as rows.

    Each row represents one CRUD operation waiting to be processed.
    Group by queue type and show action, status, retry count, and payload preview.

    Query Parameters:
      - queue_type: Filter by queue (CANDIDATE_QUEUE, THUNDER_QUEUE, etc) - optional
      - status: Filter by status (PENDING, PROCESSING, COMPLETED, FAILED) - optional

    Returns:
      - total_messages: Total count across all queues
      - queue_breakdown: Messages per queue type
      - rows: All messages as display rows, newest first
    """

    try:
        # Build query
        query = db.query(MessageQueue)

        # Apply filters
        if queue_type:
            query = query.filter(MessageQueue.queue_type == queue_type)

        if status:
            query = query.filter(MessageQueue.status == status)

        # Order by newest first
        messages = query.order_by(desc(MessageQueue.created_at)).all()

        # Transform to display rows
        rows = []
        if messages:
            for msg in messages:
                row = QueueMessageRow(
                    id=msg.id,
                    queue_type=msg.queue_type or "UNKNOWN",
                    message_type=msg.type,
                    action=_extract_action(msg.type),
                    status=msg.status,
                    resource_id=msg.resource_id,
                    created_by=msg.created_by,
                    created_at=msg.created_at.isoformat() if msg.created_at else "",
                    retry_count=msg.retry_count,
                    error=msg.error,
                    payload_preview=_preview_payload(msg.payload or {})
                )
                rows.append(row)

        # Calculate queue breakdown
        queue_breakdown = {}
        if messages:
            for msg in messages:
                queue = msg.queue_type or "UNKNOWN"
                if queue:
                    queue_breakdown[queue] = queue_breakdown.get(queue, 0) + 1

        # Build response - validate inputs first
        total_count = len(messages) if messages else 0
        if total_count < 0:
            raise ValueError("Invalid message count")
        if not isinstance(queue_breakdown, dict):
            queue_breakdown = {} if queue_breakdown is None else queue_breakdown
        if not isinstance(rows, list):
            rows = [] if rows is None else rows

        # Build and return response dict
        if total_count >= 0 and isinstance(queue_breakdown, dict) and isinstance(rows, list):
            response_dict = {
                "total_messages": total_count,
                "queue_breakdown": queue_breakdown,
                "rows": rows
            }
            if response_dict and isinstance(response_dict, dict):
                return response_dict
            raise ValueError("Failed to create response dictionary")
        raise ValueError("Invalid response parameters")

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to display message queue: {str(e)}"
        ) from e


@router.get(
    "/stats",
    dependencies=[Depends(require_resource_permission("message-queue", "view"))],
    summary="Get message queue statistics",
    description="Quick stats on queue health and processing"
)
def get_queue_stats(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get quick statistics on message queue health.

    Returns:
      - total: Total messages in system
      - by_queue: Breakdown by queue type
      - by_status: Breakdown by status
      - pending: Count of PENDING messages
      - failed: Count of FAILED messages
      - oldest_pending: Age of oldest pending message (seconds)
    """
    try:
        from datetime import datetime

        # Get all messages
        try:
            all_messages = db.query(MessageQueue).all()
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to query message queue: {e}", exc_info=True)
            all_messages = []
        if not all_messages:
            all_messages = []

        # Calculate stats
        by_queue = {}
        by_status = {}
        pending_messages = []

        if all_messages:
            for msg in all_messages:
                queue = msg.queue_type or "UNKNOWN"
                by_queue[queue] = by_queue.get(queue, 0) + 1

                status = msg.status
                by_status[status] = by_status.get(status, 0) + 1

                if status == "PENDING":
                    pending_messages.append(msg)

        # Find oldest pending
        oldest_pending_age = None
        if pending_messages:
            oldest = min(pending_messages, key=lambda m: m.created_at)
            age_seconds = (datetime.utcnow() - oldest.created_at).total_seconds()
            oldest_pending_age = int(age_seconds)

        return {
            "total": len(all_messages),
            "by_queue": by_queue,
            "by_status": by_status,
            "pending_count": by_status.get("PENDING", 0),
            "failed_count": by_status.get("FAILED", 0),
            "oldest_pending_age_seconds": oldest_pending_age
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get queue stats: {str(e)}"
        ) from e
