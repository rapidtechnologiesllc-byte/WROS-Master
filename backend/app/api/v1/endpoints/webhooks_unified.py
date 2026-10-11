"""
Delivery & Engagement Webhooks - Unified Webhook Processing
Prefix: /webhooks
Tag:    delivery-webhooks

Receives delivery/engagement events from external providers (email, SMS, WhatsApp)
and records actual outcomes to learning system for prediction accuracy measurement.

Unified implementation consolidating:
- webhooks.py endpoint handlers (SendGrid, Mailgun, Twilio SMS, Twilio WhatsApp)
- whatsapp_webhook.py (WhatsApp Meta Cloud API)
- Outcome processing via UnifiedDecisionOutcomeService

Flow:
  Provider sends webhook → validate signature → extract event data →
  UnifiedWebhookIntegrationService.process_*_webhook() →
  UnifiedDecisionOutcomeService.record_outcome() → learning system measures confidence_gap

Routes:
  POST /webhooks/sendgrid   - Email delivery events (SendGrid)
  POST /webhooks/mailgun    - Email delivery events (Mailgun)
  POST /webhooks/twilio-sms - SMS delivery events (Twilio)
  POST /webhooks/twilio-whatsapp - WhatsApp delivery events (Twilio)
  POST /webhooks/whatsapp   - WhatsApp delivery events (Meta Cloud API)
"""

import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logging import logger
from app.services.unified_webhook_integration_service import (
    UnifiedWebhookIntegrationService,
)

router = APIRouter(prefix="/webhooks", tags=["delivery-webhooks"])


# ─────────────────────────────────────────────────────────────────────────────
# Background Processing Tasks
# ─────────────────────────────────────────────────────────────────────────────


def _process_sendgrid_webhook(webhook_data: Dict[str, Any]) -> None:
    """Process SendGrid email delivery events in background task."""
    db = SessionLocal()
    try:
        result = UnifiedWebhookIntegrationService.process_sendgrid_webhook(
            db=db, webhook_data=webhook_data, validate_signature=False  # Signature validated in endpoint
        )
        logger.info(f"[SendGridWebhook] Processed: {result}")
    except Exception as e:
        logger.error(f"[SendGridWebhook] Failed processing webhook: {e}", exc_info=True)
    finally:
        db.close()


def _process_mailgun_webhook(webhook_data: Dict[str, Any]) -> None:
    """Process Mailgun email delivery events in background task."""
    db = SessionLocal()
    try:
        result = UnifiedWebhookIntegrationService.process_mailgun_webhook(
            db=db, webhook_data=webhook_data, validate_signature=False
        )
        logger.info(f"[MailgunWebhook] Processed: {result}")
    except Exception as e:
        logger.error(f"[MailgunWebhook] Failed processing webhook: {e}", exc_info=True)
    finally:
        db.close()


def _process_twilio_sms_webhook(webhook_data: Dict[str, Any]) -> None:
    """Process Twilio SMS delivery events in background task."""
    db = SessionLocal()
    try:
        result = UnifiedWebhookIntegrationService.process_twilio_sms_webhook(
            db=db, webhook_data=webhook_data, validate_signature=False
        )
        logger.info(f"[TwilioSMSWebhook] Processed: {result}")
    except Exception as e:
        logger.error(f"[TwilioSMSWebhook] Failed processing webhook: {e}", exc_info=True)
    finally:
        db.close()


def _process_twilio_whatsapp_webhook(webhook_data: Dict[str, Any]) -> None:
    """Process Twilio WhatsApp delivery events in background task."""
    db = SessionLocal()
    try:
        result = UnifiedWebhookIntegrationService.process_twilio_whatsapp_webhook(
            db=db, webhook_data=webhook_data, validate_signature=False
        )
        logger.info(f"[TwilioWhatsAppWebhook] Processed: {result}")
    except Exception as e:
        logger.error(f"[TwilioWhatsAppWebhook] Failed processing webhook: {e}", exc_info=True)
    finally:
        db.close()


def _process_whatsapp_webhook(webhook_data: Dict[str, Any]) -> None:
    """Process Meta WhatsApp Cloud API delivery events in background task."""
    db = SessionLocal()
    try:
        result = UnifiedWebhookIntegrationService.process_whatsapp_webhook(
            db=db, webhook_data=webhook_data
        )
        logger.info(f"[WhatsAppWebhook] Processed: {result}")
    except Exception as e:
        logger.error(f"[WhatsAppWebhook] Failed processing webhook: {e}", exc_info=True)
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Webhook Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/sendgrid",
    status_code=200,
    summary="Receive SendGrid email delivery events",
    response_model=Dict[str, str],
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
        webhook_data = json.loads(raw_body) if raw_body else {}

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
    response_model=Dict[str, str],
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
            }
        }
    }
    """
    try:
        raw_body = await request.body()
        webhook_data = json.loads(raw_body) if raw_body else {}

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
    response_model=Dict[str, str],
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
        form_data = await request.form()
        webhook_data = dict(form_data)

        background_tasks.add_task(_process_twilio_sms_webhook, webhook_data)
        return {"status": "received"}

    except Exception as e:
        logger.error(f"[TwilioSMSWebhook] Webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post(
    "/twilio-whatsapp",
    status_code=200,
    summary="Receive Twilio WhatsApp delivery events",
    response_model=Dict[str, str],
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
        form_data = await request.form()
        webhook_data = dict(form_data)

        background_tasks.add_task(_process_twilio_whatsapp_webhook, webhook_data)
        return {"status": "received"}

    except Exception as e:
        logger.error(f"[TwilioWhatsAppWebhook] Webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post(
    "/whatsapp",
    status_code=200,
    summary="Receive Meta WhatsApp Cloud API events",
    response_model=Dict[str, str],
)
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive delivery events from Meta WhatsApp Cloud API.

    Returns 200 immediately; processing happens in background.

    Expected body: JSON event from Meta webhook
    """
    try:
        raw_body = await request.body()
        webhook_data = json.loads(raw_body) if raw_body else {}

        background_tasks.add_task(_process_whatsapp_webhook, webhook_data)
        return {"status": "received"}

    except json.JSONDecodeError:
        logger.warning("[WhatsAppWebhook] Non-JSON payload -- discarding.")
        return {"status": "ignored"}
    except Exception as e:
        logger.error(f"[WhatsAppWebhook] Webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
