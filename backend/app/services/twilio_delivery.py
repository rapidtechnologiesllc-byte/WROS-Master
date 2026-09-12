"""Twilio Delivery Service Implementation

Sends WhatsApp messages via Twilio API.
Stub version for development when DELIVERY_PROVIDER=twilio.
"""

import logging
from sqlalchemy.orm import Session

from app.services.delivery_service import DeliveryService, DeliveryResult, UnsupportedChannelError

logger = logging.getLogger(__name__)


class TwilioDeliveryService(DeliveryService):
    """Sends WhatsApp messages via Twilio API."""

    def __init__(self, db: Session = None):
        """Initialize Twilio delivery service."""
        self.db = db
        logger.info("[TwilioDelivery] Initialized (stub - requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER)")

    def send_whatsapp(self, to_number: str, body: str, from_number: str = None) -> DeliveryResult:
        """
        Send WhatsApp message via Twilio.

        Args:
            to_number: Recipient WhatsApp number (E.164 format)
            body: Message body
            from_number: Sender WhatsApp number (from Twilio sandbox)

        Returns:
            DeliveryResult with Twilio message SID
        """
        logger.warning("[TwilioDelivery] STUB - Twilio integration not configured. Configure TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN.")
        raise UnsupportedChannelError("Twilio WhatsApp delivery not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_WHATSAPP_NUMBER.")

    def send_email(self, to_email: str, subject: str, body: str, html: bool = True) -> DeliveryResult:
        """Email not supported via Twilio."""
        raise UnsupportedChannelError("Twilio does not support email delivery. Use SendGrid or Azure instead.")

    def get_delivery_status(self, delivery_id: str) -> str:
        """Check Twilio message status."""
        logger.warning(f"[TwilioDelivery] STUB - Cannot check status for {delivery_id}")
        return "pending"
