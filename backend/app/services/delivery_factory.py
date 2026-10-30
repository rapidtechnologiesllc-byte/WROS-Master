"""Delivery Service Factory

Returns appropriate delivery implementation based on API Keys database configuration per tenant.
Reads active provider and credentials from APIKeysConfig database table.
Supports: twilio (WhatsApp), sendgrid (email), azure (email).
"""

import os
import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.services.delivery_service import DeliveryService

logger = logging.getLogger(__name__)

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
STUB_MODE = os.getenv("STUB_DELIVERY_MODE", "false").lower() == "true"


def get_delivery_service(db: Session, tenant_id: int) -> DeliveryService:
    """
    Factory function to return appropriate delivery service based on tenant's API Keys config.

    PRODUCTION-GRADE: Reads active provider and credentials from APIKeysConfig database.
    Credentials are decrypted on demand. Requires active provider to be configured and tested.

    Args:
        db: Database session (required to query API Keys config)
        tenant_id: Tenant ID for multi-tenant credential isolation

    Returns:
        DeliveryService implementation instance (Twilio, SendGrid, or Azure)

    Raises:
        RuntimeError: If no active provider configured, or credentials invalid/untested
    """
    # PHASE 4: Stub mode for development/testing (no real email sending)
    if STUB_MODE:
        from app.services.stub_delivery import StubDeliveryService
        logger.info(f"[DeliveryFactory] STUB MODE ENABLED - returning logging-only service for tenant {tenant_id}")
        return StubDeliveryService(db=db)

    if not db:
        raise ValueError("Database session required to get delivery service")

    if not tenant_id:
        raise ValueError("Tenant ID required for credential isolation")

    from app.models.api_keys_config import APIKeysConfig

    # Query for active provider
    active_config = db.query(APIKeysConfig).filter(
        APIKeysConfig.tenant_id == tenant_id,
        APIKeysConfig.is_active == True
    ).first()

    if not active_config:
        msg = f"[DeliveryFactory] Tenant {tenant_id}: No active delivery provider configured. User must configure and test credentials in API Keys settings."
        logger.error(msg)
        raise RuntimeError(msg)

    provider = active_config.provider.lower()

    # Validate provider has been tested and passed
    if active_config.last_tested_status != "success":
        msg = f"[DeliveryFactory] Tenant {tenant_id}: Active provider '{provider}' has not passed test. Status: {active_config.last_tested_status}. Must test credentials first."
        logger.error(msg)
        raise RuntimeError(msg)

    logger.info(f"[DeliveryFactory] Tenant {tenant_id}: Loading delivery provider '{provider}'")

    try:
        if provider == "twilio":
            from app.services.twilio_delivery import TwilioDeliveryService
            creds = active_config.get_twilio_creds()
            logger.info(f"[DeliveryFactory] Tenant {tenant_id}: Using Twilio Delivery Service (WhatsApp)")
            return TwilioDeliveryService(
                account_sid=creds.get("account_sid"),
                auth_token=creds.get("auth_token"),
                whatsapp_number=creds.get("whatsapp_number"),
                db=db
            )

        elif provider == "sendgrid":
            from app.services.email_delivery import EmailDeliveryService
            creds = active_config.get_sendgrid_creds()
            logger.info(f"[DeliveryFactory] Tenant {tenant_id}: Using SendGrid Delivery Service")
            return EmailDeliveryService(
                provider="sendgrid",
                api_key=creds.get("api_key"),
                from_email=creds.get("from_email"),
                db=db
            )

        elif provider == "azure":
            from app.services.email_delivery import EmailDeliveryService
            creds = active_config.get_azure_creds()
            logger.info(f"[DeliveryFactory] Tenant {tenant_id}: Using Azure Delivery Service")
            return EmailDeliveryService(
                provider="azure",
                tenant_id_cred=creds.get("tenant_id"),
                client_id=creds.get("client_id"),
                client_secret=creds.get("client_secret"),
                db=db
            )

        else:
            msg = f"[DeliveryFactory] Tenant {tenant_id}: Unknown provider '{provider}'. Must be: twilio, sendgrid, or azure"
            logger.error(msg)
            raise RuntimeError(msg)

    except RuntimeError:
        raise  # Re-raise runtime errors
    except Exception as e:
        msg = f"[DeliveryFactory] Tenant {tenant_id}: Failed to initialize delivery service for '{provider}': {str(e)}"
        logger.error(msg, exc_info=True)
        raise RuntimeError(msg)


def whatsapp_delivery_ready(db: Session, tenant_id: int) -> bool:
    """True when get_delivery_service would hand back a WhatsApp transport for this tenant: stub
    mode, or an active Twilio provider whose credentials passed their test. Callers that add
    WhatsApp to something that already works (the email cadence) check this first, so a tenant
    that never set up WhatsApp is skipped instead of failing every send."""
    if STUB_MODE:
        return True
    from app.models.api_keys_config import APIKeysConfig

    active_config = db.query(APIKeysConfig).filter(
        APIKeysConfig.tenant_id == tenant_id,
        APIKeysConfig.is_active == True  # noqa: E712 -- SQL comparison
    ).first()
    return bool(active_config and (active_config.provider or "").lower() == "twilio"
                and active_config.last_tested_status == "success")


def validate_delivery_provider_health(db: Session, tenant_id: int) -> dict:
    """
    Health check: Verify tenant's delivery provider is configured, tested, and ready.

    Returns:
        {"status": "ok" | "error", "provider": str, "message": str}
    """
    try:
        from app.models.api_keys_config import APIKeysConfig

        active_config = db.query(APIKeysConfig).filter(
            APIKeysConfig.tenant_id == tenant_id,
            APIKeysConfig.is_active == True
        ).first()

        if not active_config:
            return {
                "status": "error",
                "provider": None,
                "message": f"Tenant {tenant_id}: No active delivery provider configured"
            }

        provider = active_config.provider.lower()
        test_status = active_config.last_tested_status or "never_tested"

        if test_status != "success":
            return {
                "status": "error",
                "provider": provider,
                "message": f"Tenant {tenant_id}: Provider '{provider}' not tested or test failed (status: {test_status})"
            }

        return {
            "status": "ok",
            "provider": provider,
            "message": f"Tenant {tenant_id}: {provider.upper()} configured and tested successfully"
        }

    except Exception as e:
        return {
            "status": "error",
            "provider": None,
            "message": f"Error checking provider health: {str(e)}"
        }
