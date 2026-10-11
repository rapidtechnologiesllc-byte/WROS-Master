"""Unified Webhook Integration Service - Single source for webhook processing

Consolidates functionality from:
- webhooks.py endpoint handlers (SendGrid, Mailgun, Twilio SMS, Twilio WhatsApp)
- whatsapp_webhook_service.py (WhatsApp processing pattern)
- thunder_delivery_outcome_handler.py (outcome processing)

Provides:
- Unified webhook processing for all providers
- Signature validation for each provider
- Event format normalization
- Background task integration
- Outcome routing to decision service
"""

import json
import hmac
import hashlib
import base64
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from urllib.parse import urlencode

from app.services.unified_decision_outcome_service import UnifiedDecisionOutcomeService

logger = logging.getLogger(__name__)


class UnifiedWebhookIntegrationService:
    """Unified service for processing webhooks from all providers"""

    # Provider event type mappings
    EVENT_TYPE_TO_OUTCOME = {
        "delivered": "delivered",
        "opened": "opened",
        "clicked": "clicked",
        "bounced": "bounced",
        "complained": "complained",
        "unsubscribed": "unsubscribed",
        "failed": "failed",
        "read": "opened",  # Twilio: read → opened
        "replied": "replied",
        "sent": "sent",
    }

    @staticmethod
    def process_sendgrid_webhook(
        db: Session,
        webhook_data: Dict[str, Any],
        validate_signature: bool = True,
        signature: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Process SendGrid email delivery webhook.

        Args:
            db: Database session
            webhook_data: Webhook payload
            validate_signature: Whether to validate HMAC signature
            signature: X-Twilio-Email-Event-Webhook-Signature header
            api_key: SendGrid API key for signature validation

        Returns:
            Processing result
        """
        try:
            # Validate signature if provided
            if validate_signature and signature and api_key:
                if not UnifiedWebhookIntegrationService.validate_sendgrid_signature(
                    webhook_data, signature, api_key
                ):
                    logger.warning("SendGrid webhook signature validation failed")
                    return {"status": "error", "reason": "Invalid signature"}

            events = webhook_data.get("events", [])
            processed = 0

            for event in events:
                event_type = event.get("event", "unknown")
                email = event.get("email", "")
                candidate_id = event.get("candidate_id")
                conversation_id = event.get("conversation_id")
                message_id = event.get("sg_message_id")
                tenant_id = event.get("tenant_id")

                if not tenant_id:
                    logger.warning("SendGrid webhook missing tenant_id")
                    continue

                # Record outcome
                result = UnifiedDecisionOutcomeService.record_outcome_from_webhook(
                    db=db,
                    tenant_id=tenant_id,
                    provider="sendgrid",
                    event_type=event_type,
                    event_data={
                        "email": email,
                        "message_id": message_id,
                        "sg_message_id": message_id,
                        "candidate_id": candidate_id,
                        "conversation_id": conversation_id,
                        "timestamp": event.get("timestamp"),
                    },
                )

                if result.get("status") == "recorded":
                    processed += 1
                    logger.info(
                        f"SendGrid outcome recorded: {result.get('decision_id')}"
                    )

            return {
                "status": "success",
                "provider": "sendgrid",
                "events_processed": processed,
            }

        except Exception as e:
            logger.error(f"Failed to process SendGrid webhook: {e}", exc_info=True)
            return {"status": "error", "reason": str(e)}

    @staticmethod
    def process_mailgun_webhook(
        db: Session,
        webhook_data: Dict[str, Any],
        validate_signature: bool = True,
        signature: Optional[Dict[str, str]] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Process Mailgun email delivery webhook.

        Args:
            db: Database session
            webhook_data: Webhook payload
            validate_signature: Whether to validate signature
            signature: Signature data {timestamp, token, signature}
            api_key: Mailgun API key for validation

        Returns:
            Processing result
        """
        try:
            # Validate signature if provided
            if validate_signature and signature and api_key:
                if not UnifiedWebhookIntegrationService.validate_mailgun_signature(
                    webhook_data, signature, api_key
                ):
                    logger.warning("Mailgun webhook signature validation failed")
                    return {"status": "error", "reason": "Invalid signature"}

            event_data = webhook_data.get("event-data", {})
            event_type = event_data.get("event", "unknown")
            recipient = event_data.get("recipient", "")
            custom_vars = event_data.get("user-variables", {})

            candidate_id = custom_vars.get("candidate_id")
            conversation_id = custom_vars.get("conversation_id")
            tenant_id = custom_vars.get("tenant_id")

            if not tenant_id:
                logger.warning("Mailgun webhook missing tenant_id")
                return {"status": "error", "reason": "Missing tenant_id"}

            # Record outcome
            result = UnifiedDecisionOutcomeService.record_outcome_from_webhook(
                db=db,
                tenant_id=tenant_id,
                provider="mailgun",
                event_type=event_type,
                event_data={
                    "email": recipient,
                    "message_id": event_data.get("message", {})
                    .get("headers", {})
                    .get("message-id"),
                    "candidate_id": candidate_id,
                    "conversation_id": conversation_id,
                    "timestamp": event_data.get("timestamp"),
                },
            )

            return {
                "status": "success" if result.get("status") == "recorded" else "unmatched",
                "provider": "mailgun",
            }

        except Exception as e:
            logger.error(f"Failed to process Mailgun webhook: {e}", exc_info=True)
            return {"status": "error", "reason": str(e)}

    @staticmethod
    def process_twilio_sms_webhook(
        db: Session,
        webhook_data: Dict[str, Any],
        validate_signature: bool = True,
        signature: Optional[str] = None,
        auth_token: Optional[str] = None,
        request_url: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Process Twilio SMS delivery webhook.

        Args:
            db: Database session
            webhook_data: Webhook payload (form-encoded)
            validate_signature: Whether to validate signature
            signature: X-Twilio-Signature header
            auth_token: Twilio auth token for validation
            request_url: Original request URL for signature validation

        Returns:
            Processing result
        """
        try:
            # Validate signature if provided
            if validate_signature and signature and auth_token and request_url:
                if not UnifiedWebhookIntegrationService.validate_twilio_signature(
                    request_url, webhook_data, signature, auth_token
                ):
                    logger.warning("Twilio webhook signature validation failed")
                    return {"status": "error", "reason": "Invalid signature"}

            event_type = webhook_data.get("MessageStatus", "unknown")
            phone = webhook_data.get("To", "")
            candidate_id = webhook_data.get("candidate_id")
            conversation_id = webhook_data.get("conversation_id")
            tenant_id = webhook_data.get("tenant_id")
            message_sid = webhook_data.get("MessageSid")

            if not tenant_id:
                logger.warning("Twilio SMS webhook missing tenant_id")
                return {"status": "error", "reason": "Missing tenant_id"}

            # Record outcome
            result = UnifiedDecisionOutcomeService.record_outcome_from_webhook(
                db=db,
                tenant_id=tenant_id,
                provider="twilio",
                event_type=event_type,
                event_data={
                    "phone": phone,
                    "message_id": message_sid,
                    "candidate_id": candidate_id,
                    "conversation_id": conversation_id,
                    "timestamp": webhook_data.get("timestamp"),
                    "reply_text": webhook_data.get("Body")
                    if event_type == "replied"
                    else None,
                },
            )

            return {
                "status": "success" if result.get("status") == "recorded" else "unmatched",
                "provider": "twilio_sms",
            }

        except Exception as e:
            logger.error(f"Failed to process Twilio SMS webhook: {e}", exc_info=True)
            return {"status": "error", "reason": str(e)}

    @staticmethod
    def process_twilio_whatsapp_webhook(
        db: Session,
        webhook_data: Dict[str, Any],
        validate_signature: bool = True,
        signature: Optional[str] = None,
        auth_token: Optional[str] = None,
        request_url: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Process Twilio WhatsApp delivery webhook.

        Args:
            db: Database session
            webhook_data: Webhook payload (form-encoded)
            validate_signature: Whether to validate signature
            signature: X-Twilio-Signature header
            auth_token: Twilio auth token
            request_url: Original request URL

        Returns:
            Processing result
        """
        try:
            # Validate signature if provided
            if validate_signature and signature and auth_token and request_url:
                if not UnifiedWebhookIntegrationService.validate_twilio_signature(
                    request_url, webhook_data, signature, auth_token
                ):
                    logger.warning("Twilio WhatsApp webhook signature validation failed")
                    return {"status": "error", "reason": "Invalid signature"}

            event_type = webhook_data.get("MessageStatus", "unknown")
            phone = webhook_data.get("To", "")
            candidate_id = webhook_data.get("candidate_id")
            conversation_id = webhook_data.get("conversation_id")
            tenant_id = webhook_data.get("tenant_id")
            message_sid = webhook_data.get("MessageSid")

            if not tenant_id:
                logger.warning("Twilio WhatsApp webhook missing tenant_id")
                return {"status": "error", "reason": "Missing tenant_id"}

            # Record outcome
            result = UnifiedDecisionOutcomeService.record_outcome_from_webhook(
                db=db,
                tenant_id=tenant_id,
                provider="twilio_whatsapp",
                event_type=event_type,
                event_data={
                    "phone": phone,
                    "message_id": message_sid,
                    "candidate_id": candidate_id,
                    "conversation_id": conversation_id,
                    "timestamp": webhook_data.get("timestamp"),
                    "message_text": webhook_data.get("Body")
                    if event_type == "replied"
                    else None,
                },
            )

            return {
                "status": "success" if result.get("status") == "recorded" else "unmatched",
                "provider": "twilio_whatsapp",
            }

        except Exception as e:
            logger.error(f"Failed to process Twilio WhatsApp webhook: {e}", exc_info=True)
            return {"status": "error", "reason": str(e)}

    @staticmethod
    def process_whatsapp_webhook(
        db: Session,
        webhook_data: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Process Meta WhatsApp Cloud API webhook.

        Args:
            db: Database session
            webhook_data: Webhook payload

        Returns:
            Processing result
        """
        try:
            # Extract message/delivery status info
            # WhatsApp webhook structure varies, handle common formats
            message_status = webhook_data.get("MessageStatus")
            phone = webhook_data.get("To") or webhook_data.get("phone")
            candidate_id = webhook_data.get("candidate_id")
            conversation_id = webhook_data.get("conversation_id")
            tenant_id = webhook_data.get("tenant_id")
            message_id = webhook_data.get("MessageSid") or webhook_data.get("message_id")

            if not tenant_id:
                logger.warning("WhatsApp webhook missing tenant_id")
                return {"status": "error", "reason": "Missing tenant_id"}

            # Record outcome
            result = UnifiedDecisionOutcomeService.record_outcome_from_webhook(
                db=db,
                tenant_id=tenant_id,
                provider="whatsapp",
                event_type=message_status or "unknown",
                event_data={
                    "phone": phone,
                    "message_id": message_id,
                    "candidate_id": candidate_id,
                    "conversation_id": conversation_id,
                    "timestamp": webhook_data.get("timestamp"),
                },
            )

            return {
                "status": "success" if result.get("status") == "recorded" else "unmatched",
                "provider": "whatsapp",
            }

        except Exception as e:
            logger.error(f"Failed to process WhatsApp webhook: {e}", exc_info=True)
            return {"status": "error", "reason": str(e)}

    # Signature validation methods

    @staticmethod
    def validate_sendgrid_signature(
        request_body: Dict[str, Any], signature: str, api_key: str
    ) -> bool:
        """Validate SendGrid HMAC-SHA256 signature."""
        try:
            timestamp = json.dumps(request_body)
            computed = hmac.new(
                api_key.encode(), timestamp.encode(), hashlib.sha256
            ).digest()
            expected = base64.b64encode(computed).decode()
            return hmac.compare_digest(signature, expected)
        except Exception as e:
            logger.error(f"SendGrid signature validation error: {e}")
            return False

    @staticmethod
    def validate_mailgun_signature(
        request_body: Dict[str, Any], signature: Dict[str, str], api_key: str
    ) -> bool:
        """Validate Mailgun HMAC-SHA256 signature."""
        try:
            timestamp = signature.get("timestamp", "")
            token = signature.get("token", "")
            computed = hmac.new(
                api_key.encode(),
                f"{timestamp}{token}".encode(),
                hashlib.sha256,
            ).hexdigest()
            expected_signature = signature.get("signature", "")
            return hmac.compare_digest(computed, expected_signature)
        except Exception as e:
            logger.error(f"Mailgun signature validation error: {e}")
            return False

    @staticmethod
    def validate_twilio_signature(
        request_url: str, request_body: Dict[str, Any], signature: str, auth_token: str
    ) -> bool:
        """Validate Twilio HMAC-SHA1 signature."""
        try:
            data = request_url + urlencode(sorted(request_body.items()))
            computed = hmac.new(
                auth_token.encode(), data.encode(), hashlib.sha1
            ).digest()
            expected = base64.b64encode(computed).decode()
            return hmac.compare_digest(signature, expected)
        except Exception as e:
            logger.error(f"Twilio signature validation error: {e}")
            return False
