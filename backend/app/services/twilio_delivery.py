"""Twilio Delivery Service - Production-Grade WhatsApp Integration

Sends WhatsApp messages via Twilio Messaging API (WhatsApp channel).
Production-ready with retry logic, error handling, and delivery tracking.
"""

import os
import logging
import time
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.services.delivery_service import DeliveryService, DeliveryResult, UnsupportedChannelError

logger = logging.getLogger(__name__)


class TwilioDeliveryService(DeliveryService):
    """Production-grade WhatsApp delivery via Twilio Messaging API."""

    def __init__(self, db: Session = None):
        """Initialize Twilio delivery service with credentials validation."""
        self.db = db
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
        self.client = None
        self.max_retries = 3
        self.retry_delay = 2  # seconds

        if not all([self.account_sid, self.auth_token, self.whatsapp_number]):
            logger.error(
                "[TwilioDelivery] Missing credentials. Required: TWILIO_ACCOUNT_SID, "
                "TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER"
            )
            raise RuntimeError(
                "Twilio WhatsApp not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
                "and TWILIO_WHATSAPP_NUMBER environment variables."
            )

        try:
            from twilio.rest import Client
            self.client = Client(self.account_sid, self.auth_token)
            logger.info("[TwilioDelivery] Initialized with production credentials")
        except ImportError:
            logger.error("[TwilioDelivery] twilio package not installed. Run: pip install twilio")
            raise RuntimeError("Twilio SDK not installed. Install with: pip install twilio")
        except Exception as e:
            logger.error(f"[TwilioDelivery] Failed to initialize Twilio client: {e}")
            raise RuntimeError(f"Twilio initialization failed: {str(e)}")

    def send_whatsapp(self, to_number: str, body: str, from_number: str = None) -> DeliveryResult:
        """
        Send WhatsApp message via Twilio API (production).

        Args:
            to_number: Recipient WhatsApp number (E.164 format, e.g., +1234567890)
            body: Message body (max 4096 characters)
            from_number: Sender WhatsApp number (uses TWILIO_WHATSAPP_NUMBER if not provided)

        Returns:
            DeliveryResult with Twilio message SID

        Raises:
            UnsupportedChannelError: If credentials missing or API call fails
        """
        if not to_number or not body:
            raise ValueError(f"Invalid WhatsApp parameters: to_number={to_number}, body_length={len(body) if body else 0}")

        if len(body) > 4096:
            logger.warning(f"[TwilioDelivery] Message exceeds 4096 chars ({len(body)}), truncating")
            body = body[:4096]

        from_number = from_number or self.whatsapp_number
        attempt = 0
        last_error = None

        while attempt < self.max_retries:
            try:
                attempt += 1
                logger.info(
                    f"[TwilioDelivery] Sending WhatsApp (attempt {attempt}/{self.max_retries}) "
                    f"to {to_number} from {from_number} (body_len={len(body)})"
                )

                message = self.client.messages.create(
                    from_=f"whatsapp:{from_number}",
                    body=body,
                    to=f"whatsapp:{to_number}"
                )

                logger.info(
                    f"[TwilioDelivery] WhatsApp sent successfully to {to_number}, "
                    f"SID: {message.sid}, Status: {message.status}"
                )

                return DeliveryResult(
                    status="sent",
                    delivery_id=message.sid,
                    external_id=message.sid,
                    error=None
                )

            except Exception as e:
                last_error = e
                logger.warning(
                    f"[TwilioDelivery] Attempt {attempt} failed for {to_number}: {str(e)}"
                )

                if attempt < self.max_retries:
                    logger.info(f"[TwilioDelivery] Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)

        logger.error(
            f"[TwilioDelivery] All {self.max_retries} attempts failed for {to_number}. "
            f"Last error: {str(last_error)}"
        )

        return DeliveryResult(
            status="failed",
            delivery_id=None,
            external_id=None,
            error=f"WhatsApp delivery failed after {self.max_retries} attempts: {str(last_error)}"
        )

    def send_email(self, to_email: str, subject: str, body: str, html: bool = True) -> DeliveryResult:
        """Twilio WhatsApp channel does not support email."""
        raise UnsupportedChannelError(
            "Twilio WhatsApp channel does not support email. "
            "Use DELIVERY_PROVIDER=sendgrid or azure for email delivery."
        )

    def get_delivery_status(self, delivery_id: str) -> str:
        """
        Check Twilio message delivery status.

        Args:
            delivery_id: Twilio message SID

        Returns:
            Status: queued, sent, delivered, failed, or undelivered
        """
        if not delivery_id:
            return "unknown"

        try:
            message = self.client.messages(delivery_id).fetch()
            status_map = {
                "queued": "pending",
                "sending": "pending",
                "sent": "sent",
                "delivered": "delivered",
                "failed": "failed",
                "undelivered": "failed",
            }
            return status_map.get(message.status, "unknown")
        except Exception as e:
            logger.error(f"[TwilioDelivery] Failed to fetch status for {delivery_id}: {e}")
            return "unknown"
