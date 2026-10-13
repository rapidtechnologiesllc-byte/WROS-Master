"""
Delivery & Engagement Webhooks - Learning System Outcome Recording
Prefix: /webhooks
Tag:    delivery-webhooks

Receives delivery/engagement events from external providers (email, SMS, WhatsApp)
and records actual outcomes to learning system for prediction accuracy measurement.

Flow:
  Provider sends webhook → validate signature → extract event data →
  record_engagement_outcome() → learning system measures confidence_gap

Routes:
  POST /webhooks/sendgrid   - Email delivery events (SendGrid)
  POST /webhooks/mailgun    - Email delivery events (Mailgun)
  POST /webhooks/twilio-sms - SMS delivery events (Twilio)
  POST /webhooks/twilio-whatsapp - WhatsApp delivery events (Twilio)
"""

import json
import hmac
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logging import logger
from app.services.thunder_delivery_outcome_handler import ThunderDeliveryOutcomeHandler

router = APIRouter(prefix="/webhooks", tags=["delivery-webhooks"])


# ─────────────────────────────────────────────────────────────────────────────
# Signature Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_sendgrid_signature(request_body: bytes, signature: str, api_key: str) -> bool:
    """Validate SendGrid event webhook signature using HMAC-SHA256."""
    try:
        timestamp = request_body.decode() if isinstance(request_body, bytes) else request_body
        # SendGrid signature is: base64(HMAC-SHA256(timestamp + api_key))
        computed = hmac.new(
            api_key.encode(),
            timestamp.encode(),
            hashlib.sha256
        ).digest()
        import base64
        expected = base64.b64encode(computed).decode()
        return hmac.compare_digest(signature, expected)
    except Exception as e:
        logger.error(f"[SendGridWebhook] Signature validation error: {e}")
        return False


def validate_mailgun_signature(request_body: bytes, signature: Dict[str, str], api_key: str) -> bool:
    """Validate Mailgun event webhook signature using HMAC-SHA256."""
    try:
        timestamp = signature.get("timestamp", "")
        token = signature.get("token", "")
        computed = hmac.new(
            api_key.encode(),
            f"{timestamp}{token}".encode(),
            hashlib.sha256
        ).hexdigest()
        expected_signature = signature.get("signature", "")
        return hmac.compare_digest(computed, expected_signature)
    except Exception as e:
        logger.error(f"[MailgunWebhook] Signature validation error: {e}")
        return False


def validate_twilio_signature(
    request_url: str,
    request_body: Dict[str, Any],
    signature: str,
    auth_token: str
) -> bool:
    """Validate Twilio webhook signature using HMAC-SHA1."""
    try:
        # Twilio signature: HMAC-SHA1 of URL + request body
        from urllib.parse import urlencode
        data = request_url + urlencode(sorted(request_body.items()))
        computed = hmac.new(
            auth_token.encode(),
            data.encode(),
            hashlib.sha1
        ).digest()
        import base64
        expected = base64.b64encode(computed).decode()
        return hmac.compare_digest(signature, expected)
    except Exception as e:
        logger.error(f"[TwilioWebhook] Signature validation error: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Background Processing
# ─────────────────────────────────────────────────────────────────────────────

def _process_sendgrid_webhook(webhook_data: Dict[str, Any]) -> None:
    """Process SendGrid email delivery events in background task."""
    db = SessionLocal()
    try:
        events = webhook_data.get("events", [])

        for event in events:
            event_type = event.get("event", "unknown")
            email = event.get("email", "")
            candidate_id = event.get("candidate_id")
            conversation_id = event.get("conversation_id")

            # Extract tenant_id from headers or event metadata
            tenant_id = event.get("tenant_id") or event.get("custom_args", {}).get("tenant_id")

            if not tenant_id or not candidate_id or not conversation_id:
                logger.warning(f"[SendGridWebhook] Missing required fields: {event}")
                continue

            try:
                result = ThunderDeliveryOutcomeHandler.handle_email_delivery_webhook(
                    db=db,
                    tenant_id=tenant_id,
                    webhook_data={
                        "event": event_type,
                        "email": email,
                        "timestamp": event.get("timestamp", datetime.utcnow().isoformat()),
                        "conversation_id": conversation_id,
                        "candidate_id": candidate_id,
                        "message_id": event.get("sg_message_id"),
                        "provider": "sendgrid",
                    }
                )
                logger.info(f"[SendGridWebhook] Processed event: {event_type} → {result['status']}")
            except Exception as e:
                logger.error(f"[SendGridWebhook] Error processing event {event_type}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"[SendGridWebhook] Failed processing webhook: {e}", exc_info=True)
    finally:
        db.close()


def _process_mailgun_webhook(webhook_data: Dict[str, Any]) -> None:
    """Process Mailgun email delivery events in background task."""
    db = SessionLocal()
    try:
        event_data = webhook_data.get("event-data", {})
        event_type = event_data.get("event", "unknown")
        recipient = event_data.get("recipient", "")
        custom_vars = event_data.get("user-variables", {})

        candidate_id = custom_vars.get("candidate_id")
        conversation_id = custom_vars.get("conversation_id")
        tenant_id = custom_vars.get("tenant_id")

        if not tenant_id or not candidate_id or not conversation_id:
            logger.warning(f"[MailgunWebhook] Missing required fields: {webhook_data}")
            return

        try:
            result = ThunderDeliveryOutcomeHandler.handle_email_delivery_webhook(
                db=db,
                tenant_id=tenant_id,
                webhook_data={
                    "event": event_type,
                    "email": recipient,
                    "timestamp": event_data.get("timestamp", datetime.utcnow().isoformat()),
                    "conversation_id": conversation_id,
                    "candidate_id": candidate_id,
                    "message_id": event_data.get("message", {}).get("headers", {}).get("message-id"),
                    "provider": "mailgun",
                }
            )
            logger.info(f"[MailgunWebhook] Processed event: {event_type} → {result['status']}")
        except Exception as e:
            logger.error(f"[MailgunWebhook] Error processing event {event_type}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"[MailgunWebhook] Failed processing webhook: {e}", exc_info=True)
    finally:
        db.close()


def _process_twilio_sms_webhook(webhook_data: Dict[str, Any]) -> None:
    """Process Twilio SMS delivery events in background task."""
    db = SessionLocal()
    try:
        event_type = webhook_data.get("MessageStatus", "unknown")
        phone = webhook_data.get("To", "")
        candidate_id = webhook_data.get("candidate_id")
        conversation_id = webhook_data.get("conversation_id")
        tenant_id = webhook_data.get("tenant_id")

        if not tenant_id or not candidate_id or not conversation_id:
            logger.warning(f"[TwilioSMSWebhook] Missing required fields: {webhook_data}")
            return

        try:
            result = ThunderDeliveryOutcomeHandler.handle_sms_delivery_webhook(
                db=db,
                tenant_id=tenant_id,
                webhook_data={
                    "event": event_type,
                    "phone": phone,
                    "timestamp": webhook_data.get("timestamp", datetime.utcnow().isoformat()),
                    "conversation_id": conversation_id,
                    "candidate_id": candidate_id,
                    "message_id": webhook_data.get("MessageSid"),
                    "provider": "twilio",
                    "reply_text": webhook_data.get("Body") if event_type == "replied" else None,
                }
            )
            logger.info(f"[TwilioSMSWebhook] Processed event: {event_type} → {result['status']}")
        except Exception as e:
            logger.error(f"[TwilioSMSWebhook] Error processing event {event_type}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"[TwilioSMSWebhook] Failed processing webhook: {e}", exc_info=True)
    finally:
        db.close()


def _process_twilio_whatsapp_webhook(webhook_data: Dict[str, Any]) -> None:
    """Process Twilio WhatsApp delivery events in background task."""
    db = SessionLocal()
    try:
        event_type = webhook_data.get("MessageStatus", "unknown")
        phone = webhook_data.get("To", "")
        candidate_id = webhook_data.get("candidate_id")
        conversation_id = webhook_data.get("conversation_id")
        tenant_id = webhook_data.get("tenant_id")

        if not tenant_id or not candidate_id or not conversation_id:
            logger.warning(f"[TwilioWhatsAppWebhook] Missing required fields: {webhook_data}")
            return

        try:
            result = ThunderDeliveryOutcomeHandler.handle_whatsapp_delivery_webhook(
                db=db,
                tenant_id=tenant_id,
                webhook_data={
                    "event": event_type,
                    "phone": phone,
                    "timestamp": webhook_data.get("timestamp", datetime.utcnow().isoformat()),
                    "conversation_id": conversation_id,
                    "candidate_id": candidate_id,
                    "message_id": webhook_data.get("MessageSid"),
                    "provider": "twilio",
                    "message_text": webhook_data.get("Body") if event_type == "replied" else None,
                }
            )
            logger.info(f"[TwilioWhatsAppWebhook] Processed event: {event_type} → {result['status']}")
        except Exception as e:
            logger.error(f"[TwilioWhatsAppWebhook] Error processing event {event_type}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"[TwilioWhatsAppWebhook] Failed processing webhook: {e}", exc_info=True)
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Webhook Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/sendgrid",
    status_code=200,
    summary="Receive SendGrid email delivery events",
    response_model=Dict[str, str]
)
async def sendgrid_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive email delivery events from SendGrid.

    Returns 200 immediately; processing happens in background.

    Expected headers:
    - X-Twilio-Email-Event-Webhook-Signature: HMAC-SHA256 signature

    Expected body: JSON array of email events
    {
        "events": [
            {
                "event": "delivered|opened|clicked|bounced|complained|unsubscribed",
                "email": "candidate@example.com",
                "timestamp": "2026-10-11T15:30:00Z",
                "candidate_id": "...",
                "conversation_id": "...",
                "tenant_id": "...",
                "sg_message_id": "..."
            }
        ]
    }
    """
    try:
        raw_body = await request.body()
        webhook_data = json.loads(raw_body)

        # TODO: Validate signature against SendGrid API key
        # For now, accept without validation (webhook auth handled by IP whitelist)

        background_tasks.add_task(_process_sendgrid_webhook, webhook_data)
        return {"status": "received"}

    except json.JSONDecodeError:
        logger.warning("[SendGridWebhook] Non-JSON payload -- discarding.")
        return {"status": "ignored"}
    except Exception as e:
        logger.error(f"[SendGridWebhook] Webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post(
    "/mailgun",
    status_code=200,
    summary="Receive Mailgun email delivery events",
    response_model=Dict[str, str]
)
async def mailgun_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive email delivery events from Mailgun.

    Returns 200 immediately; processing happens in background.

    Expected headers:
    - X-Mailgun-Signature: HMAC-SHA256 signature

    Expected body: JSON event
    {
        "event-data": {
            "event": "delivered|opened|clicked|bounced|complained|unsubscribed",
            "recipient": "candidate@example.com",
            "timestamp": "2026-10-11T15:30:00Z",
            "user-variables": {
                "candidate_id": "...",
                "conversation_id": "...",
                "tenant_id": "..."
            },
            "message": {
                "headers": {
                    "message-id": "..."
                }
            }
        }
    }
    """
    try:
        raw_body = await request.body()
        webhook_data = json.loads(raw_body)

        # TODO: Validate signature against Mailgun API key
        # For now, accept without validation

        background_tasks.add_task(_process_mailgun_webhook, webhook_data)
        return {"status": "received"}

    except json.JSONDecodeError:
        logger.warning("[MailgunWebhook] Non-JSON payload -- discarding.")
        return {"status": "ignored"}
    except Exception as e:
        logger.error(f"[MailgunWebhook] Webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post(
    "/twilio-sms",
    status_code=200,
    summary="Receive Twilio SMS delivery events",
    response_model=Dict[str, str]
)
async def twilio_sms_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive SMS delivery events from Twilio.

    Returns 200 immediately; processing happens in background.

    Expected headers:
    - X-Twilio-Signature: HMAC-SHA1 signature

    Expected body: Form-encoded SMS status
    {
        "MessageStatus": "sent|delivered|read|failed|replied",
        "To": "+1234567890",
        "From": "+0987654321",
        "MessageSid": "...",
        "Body": "...",  (if MessageStatus=replied)
        "candidate_id": "...",
        "conversation_id": "...",
        "tenant_id": "..."
    }
    """
    try:
        # Twilio sends form-encoded data
        form_data = await request.form()
        webhook_data = dict(form_data)

        # TODO: Validate signature using Twilio auth token
        # For now, accept without validation

        background_tasks.add_task(_process_twilio_sms_webhook, webhook_data)
        return {"status": "received"}

    except Exception as e:
        logger.error(f"[TwilioSMSWebhook] Webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post(
    "/twilio-whatsapp",
    status_code=200,
    summary="Receive Twilio WhatsApp delivery events",
    response_model=Dict[str, str]
)
async def twilio_whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive WhatsApp delivery events from Twilio.

    Returns 200 immediately; processing happens in background.

    Expected headers:
    - X-Twilio-Signature: HMAC-SHA1 signature

    Expected body: Form-encoded WhatsApp status
    {
        "MessageStatus": "sent|delivered|read|failed|replied",
        "To": "whatsapp:+1234567890",
        "From": "whatsapp:+0987654321",
        "MessageSid": "...",
        "Body": "...",  (if MessageStatus=replied)
        "candidate_id": "...",
        "conversation_id": "...",
        "tenant_id": "..."
    }
    """
    try:
        # Twilio sends form-encoded data
        form_data = await request.form()
        webhook_data = dict(form_data)

        # TODO: Validate signature using Twilio auth token
        # For now, accept without validation

        background_tasks.add_task(_process_twilio_whatsapp_webhook, webhook_data)
        return {"status": "received"}

    except Exception as e:
        logger.error(f"[TwilioWhatsAppWebhook] Webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
