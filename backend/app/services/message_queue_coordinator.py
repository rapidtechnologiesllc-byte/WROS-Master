"""Message Queue Coordinator - Orchestrates message lifecycle through channel routing.

This service coordinates the complete message lifecycle:
1. PENDING: Message created, waiting for SLM orchestration
2. SLM_PROCESSING: SLM decides which channels to route to
3. CHANNEL_QUEUED: Message routed to specific channels
4. COMPLETED: All channel processing complete
5. FAILED: Processing failed and retries exhausted

Implements FAIL FAST: All methods raise exceptions on error.
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from app.core.logging import logger

logger = logging.getLogger(__name__)


class MessageQueueCoordinator:
    """Coordinates message routing through SLM orchestration to channel processors."""

    # Status constants
    STATUS_PENDING = "PENDING"
    STATUS_SLM_PROCESSING = "SLM_PROCESSING"
    STATUS_CHANNEL_QUEUED = "CHANNEL_QUEUED"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"

    MAX_RETRIES = 5
    RETRY_DELAY_MINUTES = 5  # Faster retry for channel processing

    @staticmethod
    def process_pending_messages(limit: int = 100, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Process pending messages through SLM orchestration.

        Workflow:
        1. Fetch PENDING messages
        2. For each message, call SLMOrchestrationService to decide channels
        3. Create MessageChannel entries for each channel
        4. Update message status to SLM_PROCESSING → CHANNEL_QUEUED

        Args:
            limit: Max messages to process
            db: Database session

        Returns:
            Stats dict with messages_processed, channels_created, errors

        Raises:
            RuntimeError: If processing fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import MessageQueue
            from app.services.slm_orchestration import SLMOrchestrationService

            stats = {
                "messages_processed": 0,
                "channels_created": 0,
                "errors": 0,
            }

            # Fetch PENDING messages
            messages = (
                db.query(MessageQueue)
                .filter(MessageQueue.status == MessageQueueCoordinator.STATUS_PENDING)
                .order_by(MessageQueue.created_at.asc())
                .limit(limit)
                .all()
            )

            logger.info(f"Processing {len(messages)} pending messages")

            for message in messages:
                try:
                    # Orchestrate message routing
                    result = SLMOrchestrationService.orchestrate(
                        message_id=message.id,
                        message_type=message.type,
                        payload=message.payload,
                        db=db,
                    )

                    # Update message status
                    message.status = MessageQueueCoordinator.STATUS_CHANNEL_QUEUED
                    db.commit()

                    stats["messages_processed"] += 1
                    stats["channels_created"] += result.get("channel_count", 0)

                    logger.info(
                        f"Message {message.id} processed: "
                        f"type={message.type} channels={result.get('channel_count', 0)}"
                    )

                except Exception as e:
                    logger.error(f"Error: {str(e)}", exc_info=True)
                    stats["errors"] += 1
                    logger.error(f"Failed to process message {message.id}: {e}", exc_info=True)
                    # Mark message as failed if too many retries
                    if message.retry_count >= MessageQueueCoordinator.MAX_RETRIES:
                        message.status = MessageQueueCoordinator.STATUS_FAILED
                        message.error = str(e)
                        db.commit()
                    else:
                        # Schedule retry
                        message.retry_count += 1
                        message.next_retry_at = datetime.utcnow() + timedelta(
                            minutes=MessageQueueCoordinator.RETRY_DELAY_MINUTES
                        )
                        db.commit()

                    logger.info(f"Message processing complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Failed to process pending messages: {e}", exc_info=True)
            raise RuntimeError(f"Failed to process pending messages: {str(e)}")

    @staticmethod
    def process_channel_messages(queue_type: str, limit: int = 50, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Process messages for a specific channel queue.

        Workflow:
        1. Fetch PENDING message channels for this queue type
        2. For each channel, call the appropriate processor
        3. Update channel status
        4. Update message status if all channels complete

        Args:
            queue_type: Channel queue type (EMAIL_QUEUE, THUNDER_QUEUE, etc.)
            limit: Max channels to process
            db: Database session

        Returns:
            Stats dict

        Raises:
            RuntimeError: If processing fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import MessageQueue, MessageChannel
            from app.services.channel_processors import get_processor

            stats = {
                "queue_type": queue_type,
                "channels_processed": 0,
                "channels_failed": 0,
                "errors": 0,
            }

            # Get processor for this queue type
            processor = get_processor(queue_type)
            if not processor:
                raise ValueError(f"No processor found for queue type: {queue_type}")

            # Fetch pending channels for this queue type
            channels = (
                db.query(MessageChannel)
                .filter(
                    MessageChannel.queue_type == queue_type,
                    MessageChannel.status == "PENDING",
                )
                .order_by(MessageChannel.created_at.asc())
                .limit(limit)
                .all()
            )

            logger.info(f"Processing {len(channels)} messages for {queue_type}")

            for channel in channels:
                try:
                    # Get the message
                    message = db.query(MessageQueue).filter(MessageQueue.id == channel.message_id).first()
                    if not message:
                        logger.warning(f"Message not found for channel: {channel.id}")
                        channel.status = "FAILED"
                        channel.error_details = "Message not found"
                        db.commit()
                        continue

                    # Process with appropriate processor
                    result = processor.process(
                        message_id=message.id,
                        message_type=message.type,
                        payload=message.payload,
                        db=db,
                    )

                    # Mark channel as completed
                    channel.status = "COMPLETED"
                    channel.processed_at = datetime.utcnow()
                    db.commit()

                    stats["channels_processed"] += 1
                    logger.debug(f"Channel {channel.id} processed for {queue_type}")

                except Exception as e:
                    logger.error(f"Error: {str(e)}", exc_info=True)
                    stats["channels_failed"] += 1
                    stats["errors"] += 1
                    logger.error(f"Failed to process channel {channel.id}: {e}", exc_info=True)

                    # Mark channel as failed
                    channel.status = "FAILED"
                    channel.error_details = str(e)
                    db.commit()

                    logger.info(f"{queue_type} processing complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Failed to process channel messages for {queue_type}: {e}", exc_info=True)
            raise RuntimeError(f"Failed to process channel messages: {str(e)}")

    @staticmethod
    def complete_messages(db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Mark messages as COMPLETED when all channels are processed.

        Workflow:
        1. Find messages in CHANNEL_QUEUED status
        2. Check if all their channels are COMPLETED
        3. If all complete, mark message as COMPLETED

        Args:
            db: Database session

        Returns:
            Stats dict

        Raises:
            RuntimeError: If processing fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import MessageQueue, MessageChannel

            stats = {
                "messages_completed": 0,
                "messages_with_failures": 0,
            }

            # Find messages in CHANNEL_QUEUED status
            messages = (
                db.query(MessageQueue)
                .filter(MessageQueue.status == MessageQueueCoordinator.STATUS_CHANNEL_QUEUED)
                .all()
            )

            logger.info(f"Checking completion status for {len(messages)} messages")

            for message in messages:
                # Check all channels
                channels = db.query(MessageChannel).filter(MessageChannel.message_id == message.id).all()

                if not channels:
                    # No channels created (shouldn't happen, but handle gracefully)
                    message.status = MessageQueueCoordinator.STATUS_COMPLETED
                    db.commit()
                    stats["messages_completed"] += 1
                    continue

                # Check if all channels completed
                all_complete = all(c.status in ["COMPLETED", "FAILED"] for c in channels)
                has_failures = any(c.status == "FAILED" for c in channels)

                if all_complete:
                    if has_failures:
                        message.status = MessageQueueCoordinator.STATUS_FAILED
                        message.error = "One or more channels failed processing"
                        stats["messages_with_failures"] += 1
                    else:
                        message.status = MessageQueueCoordinator.STATUS_COMPLETED
                        stats["messages_completed"] += 1

                    db.commit()

            logger.info(f"Message completion check done: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Failed to complete messages: {e}", exc_info=True)
            raise RuntimeError(f"Failed to complete messages: {str(e)}")

    @staticmethod
    def get_queue_health(db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Get health status of all queues.

        Returns stats for each queue type showing pending, processing, completed, failed counts.

        Args:
            db: Database session

        Returns:
            Health dict

        Raises:
            RuntimeError: If query fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import MessageChannel
            from sqlalchemy import func

            health = {
                "timestamp": datetime.utcnow().isoformat(),
                "queues": {},
            }

            # Get stats per queue type
            queue_stats = (
                db.query(
                    MessageChannel.queue_type,
                    MessageChannel.status,
                    func.count(MessageChannel.id).label("count"),
                )
                .group_by(MessageChannel.queue_type, MessageChannel.status)
                .all()
            )

            for queue_type, status, count in queue_stats:
                if queue_type not in health["queues"]:
                    health["queues"][queue_type] = {
                        "PENDING": 0,
                        "COMPLETED": 0,
                        "FAILED": 0,
                        "total": 0,
                    }

                health["queues"][queue_type][status] = count
                health["queues"][queue_type]["total"] += count

            logger.debug(f"Queue health: {health}")
            return health

        except Exception as e:
            logger.error(f"Failed to get queue health: {e}", exc_info=True)
            raise RuntimeError(f"Failed to get queue health: {str(e)}")
