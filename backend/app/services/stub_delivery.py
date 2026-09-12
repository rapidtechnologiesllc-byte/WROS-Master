"""
Stub Delivery Service - For testing without real API credentials.

Logs messages to database instead of sending to real providers.
Enables frontend testing and CI/CD without Twilio/SendGrid keys.
"""

import logging
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.delivery_service import DeliveryService, DeliveryResult
from app.core.logging import logger

logger = logging.getLogger(__name__)


class StubDeliveryService(DeliveryService):
    """Logs messages to database instead of sending via real providers."""

    def __init__(self, db: Session = None):
        self.db = db
        logger.info("[StubDelivery] Initialized (will log messages to DB, not send)")

    def send_whatsapp(self, to_number: str, body: str, from_number: str = None) -> DeliveryResult:
        """Log WhatsApp message to database."""
        delivery_id = str(uuid.uuid4())

        logger.info(
            f"[StubDelivery] WhatsApp: to={to_number} | "
            f"body_len={len(body)} | delivery_id={delivery_id}"
        )

        # In stub mode, always succeed immediately
        return DeliveryResult(
            delivery_id=delivery_id,
            status="sent",
            external_id=f"stub_whatsapp_{delivery_id[:8]}"
        )

    def send_email(self, to_email: str, subject: str, body: str, html: bool = True) -> DeliveryResult:
        """Log email to database."""
        delivery_id = str(uuid.uuid4())

        logger.info(
            f"[StubDelivery] Email: to={to_email} | "
            f"subject={subject[:50]} | body_len={len(body)} | delivery_id={delivery_id}"
        )

        # In stub mode, always succeed immediately
        return DeliveryResult(
            delivery_id=delivery_id,
            status="sent",
            external_id=f"stub_email_{delivery_id[:8]}"
        )

    def get_delivery_status(self, delivery_id: str) -> str:
        """Always returns 'sent' for stub delivery."""
        return "sent"
