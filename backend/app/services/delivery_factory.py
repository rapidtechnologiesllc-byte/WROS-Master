"""Delivery Service Factory

Returns appropriate delivery implementation based on environment configuration.
Supports: stub (logging), twilio (WhatsApp), sendgrid (email), azure (email).
"""

import os
import logging
from sqlalchemy.orm import Session
from app.services.delivery_service import DeliveryService

logger = logging.getLogger(__name__)

# Configuration - PRODUCTION-GRADE: No stub default
DELIVERY_PROVIDER = os.getenv("DELIVERY_PROVIDER", "").lower()  # twilio | sendgrid | azure (required)
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()


def _validate_delivery_provider_configured():
    """Validate that delivery provider is properly configured for production."""
    if not DELIVERY_PROVIDER:
        msg = (
            "🚨 CRITICAL: DELIVERY_PROVIDER environment variable not set.\n"
            "Candidate communication will fail silently. Configure one of:\n"
            "  - DELIVERY_PROVIDER=twilio (WhatsApp via Twilio)\n"
            "  - DELIVERY_PROVIDER=sendgrid (Email via SendGrid)\n"
            "  - DELIVERY_PROVIDER=azure (Email via Azure Communication Services)\n"
            "  - DELIVERY_PROVIDER=stub (TESTING ONLY - logs to DB, doesn't send)\n"
            "Startup aborted."
        )
        logger.critical(msg)
        raise RuntimeError(msg)

    if DELIVERY_PROVIDER == "stub" and ENVIRONMENT == "production":
        msg = (
            "🚨 CRITICAL: Running PRODUCTION with DELIVERY_PROVIDER=stub.\n"
            "All candidate messages will be logged but NOT SENT.\n"
            "This is not acceptable for production. Set proper provider."
        )
        logger.critical(msg)
        raise RuntimeError(msg)

    if DELIVERY_PROVIDER == "stub" and ENVIRONMENT != "production":
        logger.warning(
            f"[DeliveryFactory] Running in TEST MODE ({ENVIRONMENT}): "
            "Using Stub Delivery (messages logged to DB, not sent). "
            "To use real delivery, set DELIVERY_PROVIDER=twilio|sendgrid|azure"
        )


def get_delivery_service(db: Session = None) -> DeliveryService:
    """
    Factory function to return appropriate delivery service.

    PRODUCTION-GRADE: All stubs are TEST-ONLY. Production must use real provider.

    Args:
        db: Database session (optional, used for some implementations)

    Returns:
        DeliveryService implementation instance

    Raises:
        RuntimeError: If provider not configured or invalid for environment
    """
    _validate_delivery_provider_configured()

    if DELIVERY_PROVIDER == "stub":
        from app.services.stub_delivery import StubDeliveryService
        logger.info("[DeliveryFactory] Using Stub Delivery Service (TEST MODE - logging to DB)")
        return StubDeliveryService(db=db)

    elif DELIVERY_PROVIDER == "twilio":
        from app.services.twilio_delivery import TwilioDeliveryService
        logger.info("[DeliveryFactory] Using Twilio Delivery Service (PRODUCTION - WhatsApp)")
        return TwilioDeliveryService(db=db)

    elif DELIVERY_PROVIDER in ("sendgrid", "azure"):
        from app.services.email_delivery import EmailDeliveryService
        logger.info(f"[DeliveryFactory] Using Email Delivery Service ({DELIVERY_PROVIDER.upper()}) (PRODUCTION)")
        return EmailDeliveryService(provider=DELIVERY_PROVIDER, db=db)

    else:
        msg = f"🚨 Invalid DELIVERY_PROVIDER: '{DELIVERY_PROVIDER}'. Must be: twilio, sendgrid, azure, or stub (test only)"
        logger.critical(msg)
        raise RuntimeError(msg)


def validate_delivery_provider_health() -> dict:
    """
    Health check: Verify delivery provider is configured and has required credentials.

    Returns:
        {"status": "ok" | "error", "provider": str, "message": str}
    """
    if not DELIVERY_PROVIDER:
        return {"status": "error", "provider": None, "message": "DELIVERY_PROVIDER not configured"}

    if DELIVERY_PROVIDER == "stub":
        return {"status": "warning", "provider": "stub", "message": "Running in TEST MODE (messages not sent)"}

    if DELIVERY_PROVIDER == "twilio":
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
        if not all([account_sid, auth_token, whatsapp_number]):
            return {
                "status": "error",
                "provider": "twilio",
                "message": "Missing Twilio credentials (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER)"
            }
        return {"status": "ok", "provider": "twilio", "message": "Twilio configured"}

    if DELIVERY_PROVIDER == "sendgrid":
        api_key = os.getenv("SENDGRID_API_KEY")
        if not api_key:
            return {
                "status": "error",
                "provider": "sendgrid",
                "message": "Missing SendGrid credentials (SENDGRID_API_KEY)"
            }
        return {"status": "ok", "provider": "sendgrid", "message": "SendGrid configured"}

    if DELIVERY_PROVIDER == "azure":
        connection_string = os.getenv("AZURE_COMMUNICATION_CONNECTION_STRING")
        if not connection_string:
            return {
                "status": "error",
                "provider": "azure",
                "message": "Missing Azure credentials (AZURE_COMMUNICATION_CONNECTION_STRING)"
            }
        return {"status": "ok", "provider": "azure", "message": "Azure configured"}

    return {"status": "error", "provider": DELIVERY_PROVIDER, "message": f"Unknown provider: {DELIVERY_PROVIDER}"}
