"""Email Tracking Service - Multi-provider email engagement tracking.

Supports:
- Gmail (Gmail API webhooks for real-time updates)
- Outlook (Microsoft Graph change notifications)
- Yahoo, Apple Mail (pixel tracking + link tracking fallback)
- Generic SMTP (pixel tracking, link tracking, bounce detection)

Status flow: PENDING → SENDING → SENT → DELIVERED → (OPENED/CLICKED/REPLIED or BOUNCED/SPAM/DELETED)
Continuous polling every 5 minutes for non-webhook providers.
All errors logged to message queue with retry attempts.

Implements FAIL FAST: All methods raise exceptions on error.
"""
import logging
import uuid
from typing import Any, Dict, Optional
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class EmailTrackingService:
    """Service for tracking email engagement across multiple providers."""

    # Email status constants
    STATUS_PENDING = "PENDING"
    STATUS_SENDING = "SENDING"
    STATUS_SENT = "SENT"
    STATUS_DELIVERED = "DELIVERED"
    STATUS_OPENED = "OPENED"
    STATUS_CLICKED = "CLICKED"
    STATUS_REPLIED = "REPLIED"
    STATUS_BOUNCED = "BOUNCED"
    STATUS_SPAM = "SPAM"
    STATUS_DELETED = "DELETED"

    # Provider constants
    PROVIDER_GMAIL = "gmail"
    PROVIDER_OUTLOOK = "outlook"
    PROVIDER_YAHOO = "yahoo"
    PROVIDER_APPLE = "apple"
    PROVIDER_SMTP = "smtp"

    # Polling interval (5 minutes)
    POLLING_INTERVAL_SECONDS = 300

    @staticmethod
    def create_tracking(
        message_id: str,
        recipient_email: str,
        provider: str,
        db: Optional[Session] = None,
    ) -> str:
        """
        Create email tracking record.

        Args:
            message_id: ID of the message being sent
            recipient_email: Email address of recipient
            provider: Email provider (gmail, outlook, yahoo, apple, smtp)
            db: Database session

        Returns:
            Tracking ID

        Raises:
            ValueError: If inputs invalid
            RuntimeError: If database operation fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            if not recipient_email or "@" not in recipient_email:
                raise ValueError(f"Invalid recipient email: {recipient_email}")

            if provider not in [
                EmailTrackingService.PROVIDER_GMAIL,
                EmailTrackingService.PROVIDER_OUTLOOK,
                EmailTrackingService.PROVIDER_YAHOO,
                EmailTrackingService.PROVIDER_APPLE,
                EmailTrackingService.PROVIDER_SMTP,
            ]:
                raise ValueError(f"Unknown provider: {provider}")

            from app.models.message_queue import EmailTracking

            tracking_id = str(uuid.uuid4())
            tracking = EmailTracking(
                id=tracking_id,
                message_id=message_id,
                recipient_email=recipient_email,
                provider=provider,
                status=EmailTrackingService.STATUS_PENDING,
            )

            db.add(tracking)
            db.commit()

            logger.info(
                f"Email tracking created: {tracking_id} "
                f"message={message_id} provider={provider} recipient={recipient_email}"
            )

            return tracking_id

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create email tracking: {e}", exc_info=True)
            raise RuntimeError(f"Failed to create email tracking: {str(e)}")

    @staticmethod
    def mark_sent(tracking_id: str, message_id_external: Optional[str] = None, db: Optional[Session] = None) -> None:
        """Mark email as sent."""
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import EmailTracking

            tracking = db.query(EmailTracking).filter(EmailTracking.id == tracking_id).first()
            if not tracking:
                raise ValueError(f"Tracking not found: {tracking_id}")

            tracking.status = EmailTrackingService.STATUS_SENT
            tracking.sent_at = datetime.utcnow()
            if message_id_external:
                tracking.message_id_external = message_id_external
            db.commit()

            logger.debug(f"Email tracking marked as sent: {tracking_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark email as sent: {e}", exc_info=True)
            raise RuntimeError(f"Failed to mark email as sent: {str(e)}")

    @staticmethod
    def mark_delivered(tracking_id: str, db: Optional[Session] = None) -> None:
        """Mark email as delivered."""
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import EmailTracking, EmailTrackingEvent

            tracking = db.query(EmailTracking).filter(EmailTracking.id == tracking_id).first()
            if not tracking:
                raise ValueError(f"Tracking not found: {tracking_id}")

            tracking.status = EmailTrackingService.STATUS_DELIVERED
            tracking.delivered_at = datetime.utcnow()

            # Log event
            event = EmailTrackingEvent(
                tracking_id=tracking_id,
                event_type="delivered",
                event_data={"timestamp": datetime.utcnow().isoformat()},
            )
            db.add(event)
            db.commit()

            logger.debug(f"Email tracking marked as delivered: {tracking_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark email as delivered: {e}", exc_info=True)
            raise RuntimeError(f"Failed to mark email as delivered: {str(e)}")

    @staticmethod
    def mark_opened(tracking_id: str, db: Optional[Session] = None) -> None:
        """Mark email as opened."""
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import EmailTracking, EmailTrackingEvent

            tracking = db.query(EmailTracking).filter(EmailTracking.id == tracking_id).first()
            if not tracking:
                raise ValueError(f"Tracking not found: {tracking_id}")

            # Only update if not already opened
            if tracking.status not in [
                EmailTrackingService.STATUS_OPENED,
                EmailTrackingService.STATUS_CLICKED,
                EmailTrackingService.STATUS_REPLIED,
            ]:
                tracking.status = EmailTrackingService.STATUS_OPENED
                tracking.opened_at = datetime.utcnow()
                tracking.open_count = (tracking.open_count or 0) + 1

            # Log event (always log, even if already opened)
            event = EmailTrackingEvent(
                tracking_id=tracking_id,
                event_type="opened",
                event_data={
                    "timestamp": datetime.utcnow().isoformat(),
                    "open_count": tracking.open_count + 1,
                },
            )
            db.add(event)
            db.commit()

            logger.debug(f"Email tracking marked as opened: {tracking_id} (count={tracking.open_count})")

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark email as opened: {e}", exc_info=True)
            raise RuntimeError(f"Failed to mark email as opened: {str(e)}")

    @staticmethod
    def mark_clicked(tracking_id: str, link_url: Optional[str] = None, db: Optional[Session] = None) -> None:
        """Mark email as clicked."""
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import EmailTracking, EmailTrackingEvent

            tracking = db.query(EmailTracking).filter(EmailTracking.id == tracking_id).first()
            if not tracking:
                raise ValueError(f"Tracking not found: {tracking_id}")

            # Update to clicked status if not already replied
            if tracking.status != EmailTrackingService.STATUS_REPLIED:
                tracking.status = EmailTrackingService.STATUS_CLICKED
                if not tracking.first_click_at:
                    tracking.first_click_at = datetime.utcnow()
                tracking.last_click_at = datetime.utcnow()
                tracking.click_count = (tracking.click_count or 0) + 1

            # Log event
            event = EmailTrackingEvent(
                tracking_id=tracking_id,
                event_type="clicked",
                event_data={
                    "timestamp": datetime.utcnow().isoformat(),
                    "link_url": link_url,
                    "click_count": tracking.click_count + 1,
                },
            )
            db.add(event)
            db.commit()

            logger.debug(f"Email tracking marked as clicked: {tracking_id} url={link_url}")

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark email as clicked: {e}", exc_info=True)
            raise RuntimeError(f"Failed to mark email as clicked: {str(e)}")

    @staticmethod
    def mark_replied(tracking_id: str, reply_subject: Optional[str] = None, db: Optional[Session] = None) -> None:
        """Mark email as replied to."""
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import EmailTracking, EmailTrackingEvent

            tracking = db.query(EmailTracking).filter(EmailTracking.id == tracking_id).first()
            if not tracking:
                raise ValueError(f"Tracking not found: {tracking_id}")

            tracking.status = EmailTrackingService.STATUS_REPLIED
            tracking.replied_at = datetime.utcnow()

            # Log event
            event = EmailTrackingEvent(
                tracking_id=tracking_id,
                event_type="replied",
                event_data={
                    "timestamp": datetime.utcnow().isoformat(),
                    "reply_subject": reply_subject,
                },
            )
            db.add(event)
            db.commit()

            logger.info(f"Email tracking marked as replied: {tracking_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark email as replied: {e}", exc_info=True)
            raise RuntimeError(f"Failed to mark email as replied: {str(e)}")

    @staticmethod
    def mark_bounced(tracking_id: str, bounce_reason: Optional[str] = None, db: Optional[Session] = None) -> None:
        """Mark email as bounced."""
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import EmailTracking, EmailTrackingEvent

            tracking = db.query(EmailTracking).filter(EmailTracking.id == tracking_id).first()
            if not tracking:
                raise ValueError(f"Tracking not found: {tracking_id}")

            tracking.status = EmailTrackingService.STATUS_BOUNCED
            tracking.bounced_at = datetime.utcnow()
            tracking.bounce_reason = bounce_reason

            # Log event
            event = EmailTrackingEvent(
                tracking_id=tracking_id,
                event_type="bounced",
                event_data={
                    "timestamp": datetime.utcnow().isoformat(),
                    "bounce_reason": bounce_reason,
                },
            )
            db.add(event)
            db.commit()

            logger.warning(f"Email tracking marked as bounced: {tracking_id} reason={bounce_reason}")

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark email as bounced: {e}", exc_info=True)
            raise RuntimeError(f"Failed to mark email as bounced: {str(e)}")

    @staticmethod
    def mark_spam(tracking_id: str, db: Optional[Session] = None) -> None:
        """Mark email as spam."""
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import EmailTracking, EmailTrackingEvent

            tracking = db.query(EmailTracking).filter(EmailTracking.id == tracking_id).first()
            if not tracking:
                raise ValueError(f"Tracking not found: {tracking_id}")

            tracking.status = EmailTrackingService.STATUS_SPAM
            tracking.spam_marked_at = datetime.utcnow()

            # Log event
            event = EmailTrackingEvent(
                tracking_id=tracking_id,
                event_type="spam",
                event_data={"timestamp": datetime.utcnow().isoformat()},
            )
            db.add(event)
            db.commit()

            logger.warning(f"Email tracking marked as spam: {tracking_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark email as spam: {e}", exc_info=True)
            raise RuntimeError(f"Failed to mark email as spam: {str(e)}")

    @staticmethod
    def mark_deleted(tracking_id: str, db: Optional[Session] = None) -> None:
        """Mark email as deleted."""
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import EmailTracking, EmailTrackingEvent

            tracking = db.query(EmailTracking).filter(EmailTracking.id == tracking_id).first()
            if not tracking:
                raise ValueError(f"Tracking not found: {tracking_id}")

            tracking.status = EmailTrackingService.STATUS_DELETED
            tracking.deleted_at = datetime.utcnow()

            # Log event
            event = EmailTrackingEvent(
                tracking_id=tracking_id,
                event_type="deleted",
                event_data={"timestamp": datetime.utcnow().isoformat()},
            )
            db.add(event)
            db.commit()

            logger.debug(f"Email tracking marked as deleted: {tracking_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark email as deleted: {e}", exc_info=True)
            raise RuntimeError(f"Failed to mark email as deleted: {str(e)}")

    @staticmethod
    def get_pending_to_track(limit: int = 100, db: Optional[Session] = None) -> list:
        """
        Get email tracking records that need polling.

        Returns emails that:
        - Have status SENT or DELIVERED (not yet opened/clicked/replied/bounced)
        - Haven't been checked in the last 5 minutes
        - Are from non-webhook providers (yahoo, apple, smtp)

        Args:
            limit: Maximum records to return
            db: Database session

        Returns:
            List of tracking records

        Raises:
            RuntimeError: If query fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import EmailTracking

            now = datetime.utcnow()
            check_deadline = now - timedelta(seconds=EmailTrackingService.POLLING_INTERVAL_SECONDS)

            # Get emails that need tracking update
            trackings = (
                db.query(EmailTracking)
                .filter(
                    EmailTracking.status.in_([
                        EmailTrackingService.STATUS_SENT,
                        EmailTrackingService.STATUS_DELIVERED,
                    ]),
                    EmailTracking.provider.in_([
                        EmailTrackingService.PROVIDER_YAHOO,
                        EmailTrackingService.PROVIDER_APPLE,
                        EmailTrackingService.PROVIDER_SMTP,
                    ]),
                    (EmailTracking.last_checked_at == None) | (EmailTracking.last_checked_at <= check_deadline),
                )
                .order_by(EmailTracking.last_checked_at.asc())
                .limit(limit)
                .all()
            )

            logger.debug(f"Found {len(trackings)} email tracking records to poll")
            return trackings

        except Exception as e:
            logger.error(f"Failed to fetch pending email trackings: {e}", exc_info=True)
            raise RuntimeError(f"Failed to fetch pending email trackings: {str(e)}")

    @staticmethod
    def update_last_check(tracking_id: str, error: Optional[str] = None, db: Optional[Session] = None) -> None:
        """
        Update last_checked_at timestamp after polling.

        Args:
            tracking_id: Tracking ID
            error: Optional error message from polling
            db: Database session

        Raises:
            RuntimeError: If update fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import EmailTracking

            tracking = db.query(EmailTracking).filter(EmailTracking.id == tracking_id).first()
            if not tracking:
                raise ValueError(f"Tracking not found: {tracking_id}")

            tracking.last_checked_at = datetime.utcnow()
            tracking.check_count = (tracking.check_count or 0) + 1
            if error:
                tracking.last_error = error
            db.commit()

            logger.debug(f"Email tracking check updated: {tracking_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update tracking check: {e}", exc_info=True)
            raise RuntimeError(f"Failed to update tracking check: {str(e)}")

    @staticmethod
    def get_engagement_metrics(message_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Get email engagement metrics for a message.

        Args:
            message_id: Message ID
            db: Database session

        Returns:
            Metrics dict with open_rate, click_rate, bounce_rate, etc.

        Raises:
            RuntimeError: If query fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.models.message_queue import EmailTracking
            from sqlalchemy import func

            trackings = db.query(EmailTracking).filter(EmailTracking.message_id == message_id).all()

            if not trackings:
                return {
                    "total_recipients": 0,
                    "open_count": 0,
                    "click_count": 0,
                    "bounce_count": 0,
                    "spam_count": 0,
                    "reply_count": 0,
                }

            total = len(trackings)
            opened = sum(1 for t in trackings if t.opened_at)
            clicked = sum(1 for t in trackings if t.first_click_at)
            bounced = sum(1 for t in trackings if t.bounced_at)
            spam = sum(1 for t in trackings if t.spam_marked_at)
            replied = sum(1 for t in trackings if t.replied_at)

            return {
                "total_recipients": total,
                "open_count": opened,
                "click_count": clicked,
                "bounce_count": bounced,
                "spam_count": spam,
                "reply_count": replied,
                "open_rate": round(opened / total * 100, 2) if total > 0 else 0,
                "click_rate": round(clicked / total * 100, 2) if total > 0 else 0,
                "bounce_rate": round(bounced / total * 100, 2) if total > 0 else 0,
                "reply_rate": round(replied / total * 100, 2) if total > 0 else 0,
            }

        except Exception as e:
            logger.error(f"Failed to get engagement metrics: {e}", exc_info=True)
            raise RuntimeError(f"Failed to get engagement metrics: {str(e)}")
