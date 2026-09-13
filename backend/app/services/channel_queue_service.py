"""Channel Queue Service - Manage channel queue item lifecycle

Handles status transitions (PENDING → PROCESSING → COMPLETED/FAILED),
error classification (transient vs permanent), and idempotency checking.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.channel_queue import ChannelQueueItem

logger = logging.getLogger(__name__)


class ChannelQueueService:
    """Service for managing channel queue items"""

    # Channel type constants
    CHANNEL_EMAIL = "EMAIL"
    CHANNEL_WHATSAPP = "WHATSAPP"
    CHANNEL_SMS = "SMS"
    CHANNEL_SLACK = "SLACK"
    CHANNEL_THUNDER = "THUNDER"
    CHANNEL_APPROVAL = "APPROVAL"
    CHANNEL_COMMISSION = "COMMISSION"
    CHANNEL_CRM = "CRM"
    CHANNEL_DASHBOARD = "DASHBOARD"
    CHANNEL_CALENDAR = "CALENDAR"
    CHANNEL_SIGNATURE = "SIGNATURE"

    # Status constants
    STATUS_PENDING = "PENDING"
    STATUS_PROCESSING = "PROCESSING"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"

    @staticmethod
    def mark_completed(item_id: str, db: Session, result: Optional[Dict[str, Any]] = None) -> bool:
        """
        Mark a channel queue item as COMPLETED.

        Args:
            item_id: ID of the channel queue item
            db: Database session
            result: Optional result data to store (e.g., {'email_id': '...', 'timestamp': '...'})

        Returns:
            True if marked successfully, False if item not found
        """
        try:
            item = db.query(ChannelQueueItem).filter(ChannelQueueItem.id == item_id).first()
            if not item:
                logger.warning(f"Channel queue item not found: {item_id}")
                return False

            item.status = ChannelQueueService.STATUS_COMPLETED
            item.result = result or {}
            item.last_attempted_at = datetime.utcnow()

            db.commit()
            logger.info(f"Marked channel queue item as COMPLETED: {item_id} (channel={item.channel_type})")
            return True

        except Exception as e:
            logger.error(f"Failed to mark channel queue item completed: {e}", exc_info=True)
            db.rollback()
            return False

    @staticmethod
    def mark_failed(
        item_id: str,
        error_message: str,
        should_retry: bool = True,
        db: Optional[Session] = None,
        retry_delay_seconds: int = 300,  # 5 minutes default
    ) -> bool:
        """
        Mark a channel queue item as FAILED.

        Args:
            item_id: ID of the channel queue item
            error_message: Error message explaining the failure
            should_retry: Whether to retry this item (True = transient error, False = permanent)
            db: Database session
            retry_delay_seconds: How long to wait before next retry

        Returns:
            True if marked successfully, False if item not found
        """
        try:
            item = db.query(ChannelQueueItem).filter(ChannelQueueItem.id == item_id).first()
            if not item:
                logger.warning(f"Channel queue item not found: {item_id}")
                return False

            item.status = ChannelQueueService.STATUS_FAILED
            item.error = error_message
            item.last_attempted_at = datetime.utcnow()

            if should_retry:
                item.retry_count += 1
                item.next_retry_at = datetime.utcnow() + timedelta(seconds=retry_delay_seconds)
                logger.info(
                    f"Marked channel queue item as FAILED (will retry): {item_id} "
                    f"(attempt={item.retry_count}, next_retry={item.next_retry_at}) - Error: {error_message}"
                )
            else:
                item.next_retry_at = None  # No retry
                logger.warning(
                    f"Marked channel queue item as FAILED (no retry): {item_id} "
                    f"(channel={item.channel_type}) - Error: {error_message}"
                )

            db.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to mark channel queue item failed: {e}", exc_info=True)
            db.rollback()
            return False

    @staticmethod
    def get_pending_items(db: Session, channel_type: Optional[str] = None, limit: int = 100) -> list:
        """
        Get pending channel queue items ready for processing.

        Args:
            db: Database session
            channel_type: Optional filter by channel type
            limit: Maximum items to return

        Returns:
            List of ChannelQueueItem objects
        """
        try:
            query = db.query(ChannelQueueItem).filter(
                ChannelQueueItem.status == ChannelQueueService.STATUS_PENDING
            )

            if channel_type:
                query = query.filter(ChannelQueueItem.channel_type == channel_type)

            # Also include items ready for retry
            from sqlalchemy import or_
            query = db.query(ChannelQueueItem).filter(
                or_(
                    ChannelQueueItem.status == ChannelQueueService.STATUS_PENDING,
                    and_(
                        ChannelQueueItem.status == ChannelQueueService.STATUS_FAILED,
                        ChannelQueueItem.next_retry_at <= datetime.utcnow(),
                    ),
                )
            )

            if channel_type:
                query = query.filter(ChannelQueueItem.channel_type == channel_type)

            items = query.order_by(ChannelQueueItem.created_at).limit(limit).all()
            return items

        except Exception as e:
            logger.error(f"Failed to get pending channel queue items: {e}", exc_info=True)
            return []

    @staticmethod
    def is_idempotent_duplicate(
        item_data: Dict[str, Any],
        db: Session,
    ) -> bool:
        """
        Check if this message was already processed (idempotency check).

        Uses idempotency_key if present in item_data.

        Args:
            item_data: Channel queue item payload
            db: Database session

        Returns:
            True if this is a duplicate (already processed), False if new
        """
        idempotency_key = item_data.get("idempotency_key")
        if not idempotency_key:
            return False  # No idempotency key, proceed with processing

        try:
            existing = db.query(ChannelQueueItem).filter(
                and_(
                    ChannelQueueItem.payload["idempotency_key"].astext == idempotency_key,
                    ChannelQueueItem.status == ChannelQueueService.STATUS_COMPLETED,
                )
            ).first()

            if existing:
                logger.info(f"Idempotency check: Message already processed: {idempotency_key}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to check idempotency: {e}", exc_info=True)
            return False  # On error, proceed (safer than blocking)

    @staticmethod
    def mark_processing(item_id: str, db: Session) -> bool:
        """
        Mark a channel queue item as PROCESSING (started processing).

        Args:
            item_id: ID of the channel queue item
            db: Database session

        Returns:
            True if marked successfully, False if item not found
        """
        try:
            item = db.query(ChannelQueueItem).filter(ChannelQueueItem.id == item_id).first()
            if not item:
                logger.warning(f"Channel queue item not found: {item_id}")
                return False

            item.status = ChannelQueueService.STATUS_PROCESSING
            item.last_attempted_at = datetime.utcnow()

            db.commit()
            logger.debug(f"Marked channel queue item as PROCESSING: {item_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to mark channel queue item processing: {e}", exc_info=True)
            db.rollback()
            return False
