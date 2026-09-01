"""Message Queue Service - Core queueing operations for all system messages

Implements FAIL FAST principle: All methods raise exceptions on error, never silent fail.
Message flow: PENDING → PROCESSING → COMPLETED/RETRYING/FAILED
"""
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, asc
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class MessageQueueService:
    """Service for managing message queue operations with fail-fast error handling."""

    # Message statuses
    STATUS_PENDING = "PENDING"
    STATUS_PROCESSING = "PROCESSING"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_RETRYING = "RETRYING"
    STATUS_FAILED = "FAILED"

    # Maximum retries before marking as failed
    MAX_RETRIES = 5

    # Retry delay in minutes
    RETRY_DELAY_MINUTES = 30

    @staticmethod
    def enqueue(
        message_type: str,
        payload: Dict[str, Any],
        resource_id: Optional[str] = None,
        created_by: str = "system",
        db: Optional[Session] = None,
        queue_type: Optional[str] = None,
    ) -> str:
        """
        Create and enqueue a new message.

        Args:
            message_type: Type of message (e.g., 'candidate_added', 'thunder_email_sent')
            payload: Message payload (JSON serializable dict)
            resource_id: Optional resource ID (e.g., candidate_id) for tracking
            created_by: User or system that created this message
            db: Database session

        Returns:
            Message ID (UUID string)

        Raises:
            ValueError: If payload is not JSON serializable
            RuntimeError: If database operation fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            # Import here to avoid circular imports
            from app.models.message_queue import MessageQueue

            # Validate payload is JSON serializable
            try:
                json.dumps(payload)
            except (TypeError, ValueError) as e:
                logger.error(f"Payload not JSON serializable: {e}")
                raise ValueError(f"Message payload must be JSON serializable: {str(e)}")

            # Determine queue_type from role templates if not provided
            if not queue_type:
                from app.core.queue_routing import QueueRouter
                queue_type = QueueRouter.get_queue_for_message(message_type, db)

            message_id = str(uuid.uuid4())
            message = MessageQueue(
                id=message_id,
                type=message_type,
                queue_type=queue_type,
                status=MessageQueueService.STATUS_PENDING,
                payload=payload,
                resource_id=resource_id,
                created_by=created_by,
                retry_count=0,
                error=None,
            )

            # Add to session
            db.add(message)

            # Commit the entire transaction (candidate + message together)
            db.commit()

            logger.info(
                f"Message enqueued: {message_id} type={message_type} "
                f"resource_id={resource_id} created_by={created_by}"
            )
            return message_id

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to enqueue message: {e}", exc_info=True)
            raise RuntimeError(f"Failed to enqueue message: {str(e)}")

    @staticmethod
    def get_pending(
        limit: int = 100,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch pending and ready-to-retry messages.

        Args:
            limit: Maximum number of messages to fetch
            db: Database session

        Returns:
            List of message dicts

        Raises:
            RuntimeError: If database query fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import MessageQueue

            now = datetime.utcnow()

            # Fetch PENDING messages and RETRYING messages that are ready
            messages = (
                db.query(MessageQueue)
                .filter(
                    and_(
                        MessageQueue.status.in_(
                            [MessageQueueService.STATUS_PENDING, MessageQueueService.STATUS_RETRYING]
                        ),
                        MessageQueue.next_retry_at <= now,
                    )
                )
                .order_by(asc(MessageQueue.created_at))
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": m.id,
                    "type": m.type,
                    "status": m.status,
                    "payload": m.payload,
                    "resource_id": m.resource_id,
                    "created_by": m.created_by,
                    "retry_count": m.retry_count,
                    "error": m.error,
                    "created_at": m.created_at,
                }
                for m in messages
            ]

        except Exception as e:
            logger.error(f"Failed to fetch pending messages: {e}", exc_info=True)
            raise RuntimeError(f"Failed to fetch pending messages: {str(e)}")

    @staticmethod
    def mark_processing(message_id: str, db: Optional[Session] = None) -> None:
        """
        Mark message as being processed.

        Args:
            message_id: Message ID
            db: Database session

        Raises:
            RuntimeError: If update fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import MessageQueue

            message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()
            if not message:
                raise ValueError(f"Message not found: {message_id}")

            message.status = MessageQueueService.STATUS_PROCESSING
            message.updated_at = datetime.utcnow()
            db.commit()

            logger.debug(f"Message marked as processing: {message_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark message as processing: {e}", exc_info=True)
            raise RuntimeError(f"Failed to mark message as processing: {str(e)}")

    @staticmethod
    def mark_completed(message_id: str, db: Optional[Session] = None) -> None:
        """
        Mark message as successfully processed.

        Args:
            message_id: Message ID
            db: Database session

        Raises:
            RuntimeError: If update fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import MessageQueue

            message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()
            if not message:
                raise ValueError(f"Message not found: {message_id}")

            message.status = MessageQueueService.STATUS_COMPLETED
            message.updated_at = datetime.utcnow()
            message.error = None
            db.commit()

            logger.info(f"Message completed successfully: {message_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark message as completed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to mark message as completed: {str(e)}")

    @staticmethod
    def mark_failed(
        message_id: str,
        error: str,
        should_retry: bool = True,
        db: Optional[Session] = None,
    ) -> bool:
        """
        Mark message as failed, optionally scheduling retry.

        Args:
            message_id: Message ID
            error: Error message
            should_retry: Whether to retry or mark as permanently failed
            db: Database session

        Returns:
            True if scheduled for retry, False if marked as failed

        Raises:
            RuntimeError: If update fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import MessageQueue

            message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()
            if not message:
                raise ValueError(f"Message not found: {message_id}")

            message.error = error
            message.updated_at = datetime.utcnow()

            if should_retry and message.retry_count < MessageQueueService.MAX_RETRIES:
                # Schedule retry
                message.status = MessageQueueService.STATUS_RETRYING
                message.retry_count += 1
                message.next_retry_at = datetime.utcnow() + timedelta(
                    minutes=MessageQueueService.RETRY_DELAY_MINUTES
                )
                db.commit()

                logger.info(
                    f"Message scheduled for retry: {message_id} "
                    f"(attempt {message.retry_count}/{MessageQueueService.MAX_RETRIES}) "
                    f"error: {error}"
                )
                return True
            else:
                # Permanently failed
                message.status = MessageQueueService.STATUS_FAILED
                db.commit()

                logger.error(
                    f"Message permanently failed: {message_id} "
                    f"(retries exhausted: {message.retry_count}) error: {error}"
                )
                return False

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark message as failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to mark message as failed: {str(e)}")

    @staticmethod
    def get_message_history(
        resource_id: str,
        limit: int = 100,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get full message history for a resource (audit trail).

        Args:
            resource_id: Resource ID (e.g., candidate_id)
            limit: Maximum messages to return
            db: Database session

        Returns:
            List of message dicts ordered by created_at DESC

        Raises:
            RuntimeError: If query fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import MessageQueue

            messages = (
                db.query(MessageQueue)
                .filter(MessageQueue.resource_id == resource_id)
                .order_by(desc(MessageQueue.created_at))
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": m.id,
                    "type": m.type,
                    "status": m.status,
                    "payload": m.payload,
                    "resource_id": m.resource_id,
                    "created_by": m.created_by,
                    "retry_count": m.retry_count,
                    "error": m.error,
                    "created_at": m.created_at,
                    "updated_at": m.updated_at,
                }
                for m in messages
            ]

        except Exception as e:
            logger.error(f"Failed to fetch message history: {e}", exc_info=True)
            raise RuntimeError(f"Failed to fetch message history: {str(e)}")

    @staticmethod
    def get_stats(db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Get queue statistics.

        Args:
            db: Database session

        Returns:
            Dict with queue stats

        Raises:
            RuntimeError: If query fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import MessageQueue
            from sqlalchemy import func

            stats = (
                db.query(
                    MessageQueue.status, func.count(MessageQueue.id).label("count")
                )
                .group_by(MessageQueue.status)
                .all()
            )

            result = {
                "total": sum(s.count for s in stats),
                "pending": 0,
                "processing": 0,
                "completed": 0,
                "retrying": 0,
                "failed": 0,
            }

            for status, count in stats:
                if status == MessageQueueService.STATUS_PENDING:
                    result["pending"] = count
                elif status == MessageQueueService.STATUS_PROCESSING:
                    result["processing"] = count
                elif status == MessageQueueService.STATUS_COMPLETED:
                    result["completed"] = count
                elif status == MessageQueueService.STATUS_RETRYING:
                    result["retrying"] = count
                elif status == MessageQueueService.STATUS_FAILED:
                    result["failed"] = count

            # Get oldest retry time
            oldest_retry = (
                db.query(MessageQueue.next_retry_at)
                .filter(MessageQueue.status == MessageQueueService.STATUS_RETRYING)
                .order_by(asc(MessageQueue.next_retry_at))
                .first()
            )

            result["oldest_retry_at"] = oldest_retry[0] if oldest_retry else None

            return result

        except Exception as e:
            logger.error(f"Failed to fetch queue statistics: {e}", exc_info=True)
            raise RuntimeError(f"Failed to fetch queue statistics: {str(e)}")
