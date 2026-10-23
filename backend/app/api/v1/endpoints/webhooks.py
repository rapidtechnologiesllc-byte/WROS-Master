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
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.core.database import SessionLocal
from app.core.delivery_webhook_auth import (
    WebhookNotConfigured, WebhookSignatureInvalid, twilio_public_url,
    verify_mailgun, verify_sendgrid, verify_twilio,
)
from app.core.logging import logger
from app.services.thunder_delivery_outcome_handler import ThunderDeliveryOutcomeHandler

router = APIRouter(prefix="/webhooks", tags=["delivery-webhooks"])


def _reject(exc: Exception) -> None:
    """Fail closed: unconfigured secret -> 503, bad/missing signature -> 401."""
    if isinstance(exc, WebhookNotConfigured):
        logger.error(f"[DeliveryWebhook] Rejected: {exc}")
        raise HTTPException(status_code=503, detail="Webhook verification is not configured")
    logger.warning(f"[DeliveryWebhook] Rejected: {exc}")
    raise HTTPException(status_code=401, detail="Invalid webhook signature")


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
    - X-Twilio-Email-Event-Webhook-Signature / -Timestamp: ECDSA signature (Signed Event Webhook)

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
    raw_body = await request.body()
    try:
        verify_sendgrid(raw_body,
                        request.headers.get("X-Twilio-Email-Event-Webhook-Signature"),
                        request.headers.get("X-Twilio-Email-Event-Webhook-Timestamp"))
    except (WebhookNotConfigured, WebhookSignatureInvalid) as exc:
        _reject(exc)
    try:
        webhook_data = json.loads(raw_body)
        # SendGrid posts a JSON array of events; the processor reads {"events": [...]}
        if isinstance(webhook_data, list):
            webhook_data = {"events": webhook_data}
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
    - none: Mailgun signs in the JSON body ("signature": {timestamp, token, signature})

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
    raw_body = await request.body()
    try:
        webhook_data = json.loads(raw_body)
    except json.JSONDecodeError:
        _reject(WebhookSignatureInvalid("Mailgun payload is not JSON"))
    try:
        verify_mailgun(webhook_data.get("signature") if isinstance(webhook_data, dict) else None)
    except (WebhookNotConfigured, WebhookSignatureInvalid) as exc:
        _reject(exc)
    try:
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
    # Twilio sends form-encoded data and signs the public URL + parameters
    webhook_data = dict(await request.form())
    try:
        verify_twilio(twilio_public_url(request.url.path, request.url.query),
                      webhook_data, request.headers.get("X-Twilio-Signature"))
    except (WebhookNotConfigured, WebhookSignatureInvalid) as exc:
        _reject(exc)
    try:
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
    # Twilio sends form-encoded data and signs the public URL + parameters
    webhook_data = dict(await request.form())
    try:
        verify_twilio(twilio_public_url(request.url.path, request.url.query),
                      webhook_data, request.headers.get("X-Twilio-Signature"))
    except (WebhookNotConfigured, WebhookSignatureInvalid) as exc:
        _reject(exc)
    try:
        background_tasks.add_task(_process_twilio_whatsapp_webhook, webhook_data)
        return {"status": "received"}

    except Exception as e:
        logger.error(f"[TwilioWhatsAppWebhook] Webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
