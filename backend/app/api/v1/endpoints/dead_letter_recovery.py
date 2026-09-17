"""
Dead-Letter Message Recovery Endpoint

Provides safe, auditable operations to retry messages that have been marked
as DEAD_LETTER (exhausted retries). Includes dry-run mode for safety.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_resource_permission
from app.models.channel_queue import ChannelQueueItem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/api/queue", tags=["dead-letter"])


@router.post(
    "/dead-letter/retry",
    dependencies=[Depends(require_resource_permission("queue_management", "manage"))],
)
def retry_dead_letter_messages(
    message_ids: List[str] = Query(..., description="List of message IDs to retry"),
    dry_run: bool = Query(True, description="If True, show what would happen without changes"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Retry specific dead-letter messages by resetting to PENDING status.

    This is safe because:
    1. It only resets status and clears error
    2. Message payload unchanged
    3. Queue processor will re-pick-up at normal retry delay
    4. Handler will re-run with fixed validation logic

    Args:
        message_ids: List of message IDs from channel_queue_item.id
        dry_run: If True, show what would be reset (no actual changes)

    Returns:
        Dict with action, count, and list of affected messages
    """
    try:
        if not message_ids:
            raise HTTPException(status_code=400, detail="message_ids list cannot be empty")

        if len(message_ids) > 100:
            raise HTTPException(
                status_code=400,
                detail="Cannot retry more than 100 messages at once (safety limit)"
            )

        updated = []
        failed = []

        for msg_id in message_ids:
            try:
                message = db.query(ChannelQueueItem).filter(
                    ChannelQueueItem.id == msg_id
                ).first()

                if not message:
                    failed.append({
                        "id": msg_id,
                        "error": "Message not found"
                    })
                    continue

                if message.status != "DEAD_LETTER":
                    failed.append({
                        "id": msg_id,
                        "error": f"Message has status {message.status}, not DEAD_LETTER"
                    })
                    continue

                # Prepare the retry
                old_status = message.status
                old_error = message.error
                old_retry_count = message.retry_count

                if not dry_run:
                    # Reset for retry
                    message.status = "PENDING"
                    message.retry_count = 0  # Reset retry count to allow retries
                    message.error = None  # Clear error message
                    message.processing_started_at = None  # Clear processing state
                    message.next_retry_at = datetime.utcnow()  # Immediate retry
                    message.last_attempted_at = None
                    db.add(message)

                updated.append({
                    "id": msg_id,
                    "type": message.type,
                    "previous_status": old_status,
                    "new_status": "PENDING" if not dry_run else "DEAD_LETTER (dry-run)",
                    "previous_error": old_error[:100] if old_error else None,
                    "previous_retry_count": old_retry_count,
                    "payload_sample": {
                        k: v for k, v in (message.payload or {}).items()
                        if k in ["candidate_id", "candidate_email", "type"]
                    }
                })

            except Exception as e:
                logger.error(f"Error processing message {msg_id}: {e}", exc_info=True)
                failed.append({
                    "id": msg_id,
                    "error": str(e)
                })

        # Commit all changes at once
        if not dry_run and updated:
            try:
                db.commit()
                logger.info(
                    f"[DL-Recovery] Retried {len(updated)} dead-letter messages, "
                    f"failed: {len(failed)}, user: {current_user.email}"
                )
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to commit dead-letter recovery: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Failed to commit changes: {str(e)}")

        return {
            "action": "retry_submitted" if not dry_run else "dry_run_preview",
            "mode": "actual" if not dry_run else "dry-run",
            "count": len(updated),
            "failed_count": len(failed),
            "messages": updated,
            "failures": failed if failed else None,
            "next_step": (
                "Messages will be retried by queue processor within 5-10 seconds. "
                "Monitor /admin/messagequeue for status updates."
                if not dry_run and updated else
                "Run again with dry_run=false to actually retry these messages."
            )
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in retry_dead_letter_messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.get(
    "/dead-letter/summary",
    dependencies=[Depends(require_resource_permission("queue_management", "view"))],
)
def get_dead_letter_summary(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get summary of dead-letter messages grouped by error type.

    Helps understand what went wrong and if all dead-letters have the same root cause.
    """
    try:
        # Get counts by error type
        dead_letters = db.query(ChannelQueueItem).filter(
            ChannelQueueItem.status == "DEAD_LETTER"
        ).all()

        if not dead_letters:
            return {
                "total": 0,
                "by_error_type": {},
                "oldest_message_age": None,
                "messages": []
            }

        # Group by error message
        by_error = {}
        for msg in dead_letters:
            error_key = (msg.error or "Unknown error")[:100]
            if error_key not in by_error:
                by_error[error_key] = {
                    "count": 0,
                    "message_ids": [],
                    "types": set()
                }
            by_error[error_key]["count"] += 1
            by_error[error_key]["message_ids"].append(msg.id)
            by_error[error_key]["types"].add(msg.type)

        # Convert sets to lists for JSON serialization
        for error_key in by_error:
            by_error[error_key]["types"] = list(by_error[error_key]["types"])

        return {
            "total": len(dead_letters),
            "by_error_type": by_error,
            "oldest_message_age_seconds": (
                (datetime.utcnow() - min([msg.created_at for msg in dead_letters])).total_seconds()
                if dead_letters else None
            ),
            "messages": [
                {
                    "id": msg.id,
                    "type": msg.type,
                    "error": msg.error[:100] if msg.error else None,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    "retry_count": msg.retry_count
                }
                for msg in dead_letters[:20]  # First 20 for preview
            ]
        }

    except Exception as e:
        logger.error(f"Error getting dead-letter summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
