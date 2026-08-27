"""Message Queue Service - Central service for managing system messages.

Handles:
- Creating message queue items for all system operations
- Processing pending/retrying messages
- Retry scheduling and management
- Message history and audit trail
- Fail-fast error handling (raises exceptions, never silent failures)
"""

import logging
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.message_queue import MessageQueue, MessageQueueLog
from app.core.database import Base

logger = logging.getLogger(__name__)

# Status constants
STATUS_PENDING = "PENDING"
STATUS_PROCESSING = "PROCESSING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_RETRYING = "RETRYING"

# Maximum retry attempts
MAX_RETRIES = 5

# Retry interval in minutes
RETRY_INTERVAL_MINUTES = 30


class MessageQueueService:
    """Service for message queue operations."""

    @staticmethod
    def enqueue_message(
        db: Session,
        message_type: str,
        payload: Dict[str, Any],
        tenant_id: int,
        resource_id: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> str:
        """
        Create a new message in the queue.

        Args:
            db: Database session
            message_type: Type of message (e.g., 'candidate_added', 'thunder_email', 'flash_agent_action')
            payload: Message payload as dictionary
            tenant_id: Tenant ID for multi-tenancy
            resource_id: ID of related resource (candidate_id, job_id, etc.)
            created_by: User ID who triggered the message

        Returns:
            Message ID

        Raises:
            ValueError: If payload is not valid
            Exception: On database error
        """
        try:
            if not message_type:
                raise ValueError("message_type is required")
            if not isinstance(payload, dict):
                raise ValueError("payload must be a dictionary")

            message_id = str(uuid.uuid4())

            message = MessageQueue(
                id=message_id,
                tenant_id=tenant_id,
                type=message_type,
                payload=payload,
                status=STATUS_PENDING,
                resource_id=resource_id,
                created_by=created_by,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            db.add(message)
            db.commit()

            logger.info(
                f"Message queued: type={message_type}, id={message_id}, "
                f"resource_id={resource_id}, payload_size={len(json.dumps(payload))}"
            )

            return message_id

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to enqueue message: {str(e)}", exc_info=True)
            raise Exception(f"Failed to enqueue message: {str(e)}")

    @staticmethod
    def get_pending_messages(
        db: Session, tenant_id: int, limit: int = 100
    ) -> List[MessageQueue]:
        """
        Fetch pending and retrying messages ready for processing.

        Args:
            db: Database session
            tenant_id: Tenant ID
            limit: Maximum number of messages to fetch

        Returns:
            List of message queue items

        Raises:
            Exception: On database error
        """
        try:
            now = datetime.utcnow()

            messages = (
                db.query(MessageQueue)
                .filter(
                    and_(
                        MessageQueue.tenant_id == tenant_id,
                        or_(
                            MessageQueue.status == STATUS_PENDING,
                            and_(
                                MessageQueue.status == STATUS_RETRYING,
                                MessageQueue.next_retry_at <= now,
                            ),
                        ),
                    )
                )
                .order_by(MessageQueue.created_at.asc())
                .limit(limit)
                .all()
            )

            return messages

        except Exception as e:
            logger.error(f"Failed to fetch pending messages: {str(e)}", exc_info=True)
            raise Exception(f"Failed to fetch pending messages: {str(e)}")

    @staticmethod
    def mark_processing(db: Session, message_id: str) -> None:
        """
        Mark a message as currently being processed.

        Args:
            db: Database session
            message_id: Message ID

        Returns:
            None

        Raises:
            Exception: If message not found or database error
        """
        try:
            message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()

            if not message:
                raise Exception(f"Message not found: {message_id}")

            message.status = STATUS_PROCESSING
            message.processing_started_at = datetime.utcnow()
            message.updated_at = datetime.utcnow()

            db.commit()

            logger.info(f"Message marked as PROCESSING: {message_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark message as processing: {str(e)}", exc_info=True)
            raise Exception(f"Failed to mark message as processing: {str(e)}")

    @staticmethod
    def mark_completed(db: Session, message_id: str) -> None:
        """
        Mark a message as successfully completed.

        Args:
            db: Database session
            message_id: Message ID

        Returns:
            None

        Raises:
            Exception: If message not found or database error
        """
        try:
            message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()

            if not message:
                raise Exception(f"Message not found: {message_id}")

            message.status = STATUS_COMPLETED
            message.completed_at = datetime.utcnow()
            message.retry_count = 0  # Clear retry count
            message.next_retry_at = None
            message.error_message = None
            message.updated_at = datetime.utcnow()

            db.commit()

            # Log the completion
            MessageQueueService._log_message_status(
                db, message_id, STATUS_COMPLETED, None
            )

            logger.info(f"Message marked as COMPLETED: {message_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark message as completed: {str(e)}", exc_info=True)
            raise Exception(f"Failed to mark message as completed: {str(e)}")

    @staticmethod
    def mark_failed(db: Session, message_id: str, error: str) -> None:
        """
        Mark a message as permanently failed (exceeded max retries).

        Args:
            db: Database session
            message_id: Message ID
            error: Error message describing why it failed

        Returns:
            None

        Raises:
            Exception: If message not found or database error
        """
        try:
            message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()

            if not message:
                raise Exception(f"Message not found: {message_id}")

            message.status = STATUS_FAILED
            message.error_message = error
            message.updated_at = datetime.utcnow()
            message.next_retry_at = None

            db.commit()

            # Log the failure
            MessageQueueService._log_message_status(
                db, message_id, STATUS_FAILED, error
            )

            logger.error(
                f"Message marked as FAILED (exceeded max retries): "
                f"message_id={message_id}, error={error}"
            )

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark message as failed: {str(e)}", exc_info=True)
            raise Exception(f"Failed to mark message as failed: {str(e)}")

    @staticmethod
    def schedule_retry(db: Session, message_id: str, error: Optional[str] = None) -> None:
        """
        Schedule a message for retry after 30 minutes.

        Args:
            db: Database session
            message_id: Message ID
            error: Optional error message to store

        Returns:
            None

        Raises:
            Exception: If message not found, max retries exceeded, or database error
        """
        try:
            message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()

            if not message:
                raise Exception(f"Message not found: {message_id}")

            # Check if we've exceeded max retries
            if message.retry_count >= MAX_RETRIES:
                raise Exception(
                    f"Message has exceeded maximum retry attempts ({MAX_RETRIES}): {message_id}"
                )

            # Increment retry count
            message.retry_count += 1

            # Schedule next retry
            message.next_retry_at = datetime.utcnow() + timedelta(minutes=RETRY_INTERVAL_MINUTES)
            message.status = STATUS_RETRYING
            if error:
                message.error_message = error
            message.updated_at = datetime.utcnow()

            db.commit()

            # Log the retry
            MessageQueueService._log_message_status(
                db, message_id, STATUS_RETRYING, error, attempt=message.retry_count
            )

            logger.warning(
                f"Message scheduled for retry: message_id={message_id}, "
                f"retry_attempt={message.retry_count}, next_retry={message.next_retry_at}"
            )

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to schedule message retry: {str(e)}", exc_info=True)
            raise Exception(f"Failed to schedule message retry: {str(e)}")

    @staticmethod
    def get_message_history(
        db: Session, resource_id: str, message_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail of all messages for a resource.

        Args:
            db: Database session
            resource_id: Resource ID to query
            message_type: Optional filter by message type

        Returns:
            List of message records with history

        Raises:
            Exception: On database error
        """
        try:
            query = db.query(MessageQueue).filter(MessageQueue.resource_id == resource_id)

            if message_type:
                query = query.filter(MessageQueue.type == message_type)

            messages = query.order_by(MessageQueue.created_at.desc()).all()

            result = []
            for msg in messages:
                # Get logs for this message
                logs = (
                    db.query(MessageQueueLog)
                    .filter(MessageQueueLog.message_id == msg.id)
                    .order_by(MessageQueueLog.timestamp.asc())
                    .all()
                )

                result.append(
                    {
                        "id": msg.id,
                        "type": msg.type,
                        "status": msg.status,
                        "resource_id": msg.resource_id,
                        "created_at": msg.created_at,
                        "updated_at": msg.updated_at,
                        "retry_count": msg.retry_count,
                        "error_message": msg.error_message,
                        "payload": msg.payload,
                        "created_by": msg.created_by,
                        "log_entries": [
                            {
                                "status": log.status,
                                "error": log.error,
                                "timestamp": log.timestamp,
                                "duration_ms": log.duration_ms,
                                "retry_attempt": log.retry_attempt,
                            }
                            for log in logs
                        ],
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Failed to get message history: {str(e)}", exc_info=True)
            raise Exception(f"Failed to get message history: {str(e)}")

    @staticmethod
    def get_message_by_id(db: Session, message_id: str) -> Optional[MessageQueue]:
        """
        Get a specific message by ID.

        Args:
            db: Database session
            message_id: Message ID

        Returns:
            MessageQueue object or None if not found

        Raises:
            Exception: On database error
        """
        try:
            message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()
            return message

        except Exception as e:
            logger.error(f"Failed to get message: {str(e)}", exc_info=True)
            raise Exception(f"Failed to get message: {str(e)}")

    @staticmethod
    def get_failed_messages(
        db: Session, tenant_id: int, limit: int = 100
    ) -> List[MessageQueue]:
        """
        Get all failed messages.

        Args:
            db: Database session
            tenant_id: Tenant ID
            limit: Maximum number of messages to fetch

        Returns:
            List of failed message queue items

        Raises:
            Exception: On database error
        """
        try:
            messages = (
                db.query(MessageQueue)
                .filter(
                    and_(
                        MessageQueue.tenant_id == tenant_id,
                        MessageQueue.status == STATUS_FAILED,
                    )
                )
                .order_by(MessageQueue.created_at.desc())
                .limit(limit)
                .all()
            )

            return messages

        except Exception as e:
            logger.error(f"Failed to get failed messages: {str(e)}", exc_info=True)
            raise Exception(f"Failed to get failed messages: {str(e)}")

    @staticmethod
    def get_queue_stats(db: Session, tenant_id: int) -> Dict[str, Any]:
        """
        Get queue statistics for dashboard.

        Args:
            db: Database session
            tenant_id: Tenant ID

        Returns:
            Dictionary with queue stats

        Raises:
            Exception: On database error
        """
        try:
            from sqlalchemy import func

            # Count messages by status
            stats = (
                db.query(
                    MessageQueue.status, func.count(MessageQueue.id).label("count")
                )
                .filter(MessageQueue.tenant_id == tenant_id)
                .group_by(MessageQueue.status)
                .all()
            )

            stats_dict = {stat[0]: stat[1] for stat in stats}

            # Get oldest pending message
            oldest_pending = (
                db.query(MessageQueue)
                .filter(
                    and_(
                        MessageQueue.tenant_id == tenant_id,
                        MessageQueue.status == STATUS_PENDING,
                    )
                )
                .order_by(MessageQueue.created_at.asc())
                .first()
            )

            # Calculate success rate
            total_completed = stats_dict.get(STATUS_COMPLETED, 0)
            total_failed = stats_dict.get(STATUS_FAILED, 0)
            total_processed = total_completed + total_failed

            success_rate = (
                (total_completed / total_processed * 100)
                if total_processed > 0
                else 0
            )

            return {
                "pending": stats_dict.get(STATUS_PENDING, 0),
                "processing": stats_dict.get(STATUS_PROCESSING, 0),
                "completed": stats_dict.get(STATUS_COMPLETED, 0),
                "failed": stats_dict.get(STATUS_FAILED, 0),
                "retrying": stats_dict.get(STATUS_RETRYING, 0),
                "total": sum(stats_dict.values()),
                "success_rate": round(success_rate, 2),
                "oldest_pending_created_at": (
                    oldest_pending.created_at if oldest_pending else None
                ),
            }

        except Exception as e:
            logger.error(f"Failed to get queue stats: {str(e)}", exc_info=True)
            raise Exception(f"Failed to get queue stats: {str(e)}")

    @staticmethod
    def _log_message_status(
        db: Session,
        message_id: str,
        status: str,
        error: Optional[str] = None,
        attempt: Optional[int] = None,
    ) -> None:
        """
        Log a message status change to audit trail.

        Args:
            db: Database session
            message_id: Message ID
            status: New status
            error: Optional error message
            attempt: Optional retry attempt number

        Raises:
            Exception: On database error (but should not fail main operation)
        """
        try:
            log_entry = MessageQueueLog(
                id=str(uuid.uuid4()),
                message_id=message_id,
                status=status,
                error=error,
                timestamp=datetime.utcnow(),
                retry_attempt=attempt,
            )

            db.add(log_entry)
            db.commit()

        except Exception as e:
            logger.warning(
                f"Failed to log message status: {str(e)} "
                f"(message_id={message_id}, status={status})"
            )
            db.rollback()
