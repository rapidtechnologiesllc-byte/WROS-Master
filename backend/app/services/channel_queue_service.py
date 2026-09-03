"""Channel Queue Service - Manages specific channel queue processing

Channels:
- EMAIL_QUEUE: Email delivery via email provider
- WHATSAPP_QUEUE: WhatsApp messages
- SMS_QUEUE: SMS delivery
- SLACK_QUEUE: Slack notifications to team
- THUNDER_QUEUE: Thunder autonomous actions
- APPROVAL_QUEUE: Approval workflow routing
- COMMISSION_QUEUE: Commission calculations
- CRM_QUEUE: CRM data sync
- DASHBOARD_QUEUE: Real-time dashboard updates
- CALENDAR_QUEUE: Calendar event creation
- SIGNATURE_QUEUE: E-signature requests
- TIMESHEET_QUEUE: Timesheet processing
- KPI_QUEUE: KPI updates
- SALES_QUEUE: Sales deal processing
- CLIENT_QUEUE: Client updates

Implements FAIL FAST: All methods raise exceptions on error.
"""
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, asc, desc
from sqlalchemy.orm import Session
from app.core.logging import logger

logger = logging.getLogger(__name__)


class ChannelQueueService:
    """Service for channel queue operations"""

    # Channel types
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
    CHANNEL_TIMESHEET = "TIMESHEET"
    CHANNEL_KPI = "KPI"
    CHANNEL_SALES = "SALES"
    CHANNEL_CLIENT = "CLIENT"

    # Status values
    STATUS_PENDING = "PENDING"
    STATUS_PROCESSING = "PROCESSING"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"

    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 5

    @staticmethod
    def create_channel_queue_item(
        message_id: str,
        channel_type: str,
        payload: Dict[str, Any],
        recipient: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> str:
        """
        Create a channel queue item (SLM creates these after analyzing message).

        Args:
            message_id: ID of original message_queue entry
            channel_type: Channel type (EMAIL, WHATSAPP, etc.)
            payload: Channel-specific payload
            recipient: Channel recipient (email, phone, user_id, etc.)
            db: Database session

        Returns:
            Channel queue item ID

        Raises:
            ValueError: If inputs invalid
            RuntimeError: If database operation fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.channel_queue import ChannelQueueItem

            # Validate JSON
            try:
                json.dumps(payload)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Payload not JSON serializable: {str(e)}")

            item_id = str(uuid.uuid4())
            item = ChannelQueueItem(
                id=item_id,
                message_id=message_id,
                channel_type=channel_type,
                status=ChannelQueueService.STATUS_PENDING,
                payload=payload,
                recipient=recipient,
                retry_count=0,
                error=None,
            )

            db.add(item)
            db.commit()

            logger.info(
                f"Channel queue item created: {item_id} "
                f"channel={channel_type} recipient={recipient}"
            )
            return item_id

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to create channel queue item: {e}", exc_info=True)
            raise RuntimeError(f"Failed to create channel queue item: {str(e)}")

    @staticmethod
    def get_pending_by_channel(
        channel_type: str,
        limit: int = 50,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get pending items for specific channel.

        Args:
            channel_type: Channel type to fetch
            limit: Max items to return
            db: Database session

        Returns:
            List of pending channel queue items

        Raises:
            RuntimeError: If query fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.channel_queue import ChannelQueueItem

            now = datetime.utcnow()

            items = (
                db.query(ChannelQueueItem)
                .filter(
                    and_(
                        ChannelQueueItem.channel_type == channel_type,
                        ChannelQueueItem.status.in_(
                            [ChannelQueueService.STATUS_PENDING]
                        ),
                    )
                )
                .order_by(asc(ChannelQueueItem.created_at))
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": item.id,
                    "message_id": item.message_id,
                    "channel_type": item.channel_type,
                    "status": item.status,
                    "payload": item.payload,
                    "recipient": item.recipient,
                    "retry_count": item.retry_count,
                    "error": item.error,
                    "created_at": item.created_at,
                }
                for item in items
            ]

        except Exception as e:
            logger.error(f"Failed to fetch pending items for channel {channel_type}: {e}", exc_info=True)
            raise RuntimeError(f"Failed to fetch pending items: {str(e)}")

    @staticmethod
    def mark_processing(item_id: str, db: Optional[Session] = None) -> None:
        """Mark channel queue item as processing."""
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.channel_queue import ChannelQueueItem

            item = db.query(ChannelQueueItem).filter(ChannelQueueItem.id == item_id).first()
            if not item:
                raise ValueError(f"Channel queue item not found: {item_id}")

            item.status = ChannelQueueService.STATUS_PROCESSING
            item.updated_at = datetime.utcnow()
            db.commit()

            logger.debug(f"Channel queue item marked as processing: {item_id}")

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to mark as processing: {e}", exc_info=True)
            raise RuntimeError(f"Failed to mark as processing: {str(e)}")

    @staticmethod
    def mark_completed(item_id: str, db: Optional[Session] = None) -> None:
        """Mark channel queue item as completed."""
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.channel_queue import ChannelQueueItem

            item = db.query(ChannelQueueItem).filter(ChannelQueueItem.id == item_id).first()
            if not item:
                raise ValueError(f"Channel queue item not found: {item_id}")

            item.status = ChannelQueueService.STATUS_COMPLETED
            item.processed_at = datetime.utcnow()
            item.updated_at = datetime.utcnow()
            item.error = None
            db.commit()

            logger.info(f"Channel queue item completed: {item_id}")

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to mark as completed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to mark as completed: {str(e)}")

    @staticmethod
    def mark_failed(
        item_id: str,
        error: str,
        should_retry: bool = True,
        db: Optional[Session] = None,
    ) -> bool:
        """
        Mark channel queue item as failed, optionally schedule retry.

        Returns:
            True if scheduled for retry, False if permanently failed
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.channel_queue import ChannelQueueItem

            item = db.query(ChannelQueueItem).filter(ChannelQueueItem.id == item_id).first()
            if not item:
                raise ValueError(f"Channel queue item not found: {item_id}")

            item.error = error
            item.updated_at = datetime.utcnow()

            if should_retry and item.retry_count < ChannelQueueService.MAX_RETRIES:
                # Schedule retry
                item.status = ChannelQueueService.STATUS_PENDING
                item.retry_count += 1
                item.next_retry_at = datetime.utcnow() + timedelta(
                    minutes=ChannelQueueService.RETRY_DELAY_MINUTES
                )
                db.commit()

                logger.info(
                    f"Channel queue item scheduled for retry: {item_id} "
                    f"(attempt {item.retry_count}/{ChannelQueueService.MAX_RETRIES})"
                )
                return True
            else:
                # Permanently failed
                item.status = ChannelQueueService.STATUS_FAILED
                db.commit()

                logger.error(
                    f"Channel queue item permanently failed: {item_id} "
                    f"(retries exhausted: {item.retry_count})"
                )
                return False

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to mark as failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to mark as failed: {str(e)}")

    @staticmethod
    def get_stats(db: Optional[Session] = None) -> Dict[str, Any]:
        """Get channel queue statistics"""
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.channel_queue import ChannelQueueItem
            from sqlalchemy import func

            # Overall stats
            total = db.query(func.count(ChannelQueueItem.id)).scalar() or 0
            pending = (
                db.query(func.count(ChannelQueueItem.id))
                .filter(ChannelQueueItem.status == ChannelQueueService.STATUS_PENDING)
                .scalar()
                or 0
            )
            processing = (
                db.query(func.count(ChannelQueueItem.id))
                .filter(ChannelQueueItem.status == ChannelQueueService.STATUS_PROCESSING)
                .scalar()
                or 0
            )
            completed = (
                db.query(func.count(ChannelQueueItem.id))
                .filter(ChannelQueueItem.status == ChannelQueueService.STATUS_COMPLETED)
                .scalar()
                or 0
            )
            failed = (
                db.query(func.count(ChannelQueueItem.id))
                .filter(ChannelQueueItem.status == ChannelQueueService.STATUS_FAILED)
                .scalar()
                or 0
            )

            # Per-channel stats
            channel_stats = (
                db.query(
                    ChannelQueueItem.channel_type,
                    ChannelQueueItem.status,
                    func.count(ChannelQueueItem.id).label("count"),
                )
                .group_by(ChannelQueueItem.channel_type, ChannelQueueItem.status)
                .all()
            )

            channels = {}
            for channel_type, status, count in channel_stats:
                if channel_type not in channels:
                    channels[channel_type] = {
                        "pending": 0,
                        "processing": 0,
                        "completed": 0,
                        "failed": 0,
                    }
                channels[channel_type][status.lower()] = count

            return {
                "total": total,
                "pending": pending,
                "processing": processing,
                "completed": completed,
                "failed": failed,
                "channels": channels,
            }

        except Exception as e:
            logger.error(f"Failed to fetch stats: {e}", exc_info=True)
            raise RuntimeError(f"Failed to fetch stats: {str(e)}")
