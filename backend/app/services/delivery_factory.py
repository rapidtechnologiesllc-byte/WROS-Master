"""Delivery Service Factory

Returns appropriate delivery implementation based on environment configuration.
Supports: stub (logging), twilio (WhatsApp), sendgrid (email), azure (email).
"""

import os
import logging
from sqlalchemy.orm import Session
from app.services.delivery_service import DeliveryService

logger = logging.getLogger(__name__)

# Configuration
DELIVERY_PROVIDER = os.getenv("DELIVERY_PROVIDER", "stub").lower()  # stub | twilio | sendgrid | azure


def get_delivery_service(db: Session = None) -> DeliveryService:
    """
    Factory function to return appropriate delivery service.

    Args:
        db: Database session (optional, used for some implementations)

    Returns:
        DeliveryService implementation instance
    """
    if DELIVERY_PROVIDER == "stub":
        from app.services.stub_delivery import StubDeliveryService
        logger.info("[DeliveryFactory] Using Stub Delivery Service (logging to DB)")
        return StubDeliveryService(db=db)

    elif DELIVERY_PROVIDER == "twilio":
        from app.services.twilio_delivery import TwilioDeliveryService
        logger.info("[DeliveryFactory] Using Twilio Delivery Service")
        return TwilioDeliveryService(db=db)

    elif DELIVERY_PROVIDER in ("sendgrid", "azure"):
        from app.services.email_delivery import EmailDeliveryService
        logger.info(f"[DeliveryFactory] Using Email Delivery Service ({DELIVERY_PROVIDER.upper()})")
        return EmailDeliveryService(provider=DELIVERY_PROVIDER, db=db)

    else:
        logger.warning(f"[DeliveryFactory] Unknown provider: {DELIVERY_PROVIDER}, defaulting to Stub")
        from app.services.stub_delivery import StubDeliveryService
        return StubDeliveryService(db=db)
