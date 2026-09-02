"""
S-002/HRMS-0402 -- WhatsApp Webhook (Meta Cloud API)
=======================================================
Prefix: /webhooks
import logging
Tag:    whatsapp-webhook

Public (no auth possible -- Meta calls this, not a logged-in user).
Security is Meta's own X-Hub-Signature-256 HMAC scheme on the POST
route, and the hub.verify_token handshake on the GET route -- see
app.services.whatsapp_webhook_service and
app.middleware.auth_middleware.PUBLIC_ROUTES.

Routes:
  GET  /webhooks/whatsapp   Meta's one-time subscription verification.
  POST /webhooks/whatsapp   Inbound messages + delivery status updates.
      Returns HTTP 200 within milliseconds (BR-03) -- all storage work
      happens in a FastAPI background task after the response is sent.
"""
import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.core.database import SessionLocal
from app.core.logging import logger
from app.services.whatsapp_webhook_service import (
    process_delivery_status,
    store_inbound_whatsapp_message,
    validate_signature,
    verify_webhook_challenge,
)

router = APIRouter(prefix="/webhooks", tags=["whatsapp-webhook"])


@router.get(
    dependencies=[Depends(get_current_user)]
    "/whatsapp",
    summary="Meta WhatsApp Cloud API webhook verification handshake",
)
def whatsapp_webhook_verify(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    result = verify_webhook_challenge(mode, token, challenge)
    if result is None:
        raise HTTPException(status_code=403, detail="Verification failed")
    return PlainTextResponse(result)


def _process_webhook_payload(payload: dict) -> None:
    """Runs after the HTTP response is already sent (BR-03). Uses its
    own DB session -- the request-scoped one from Depends(get_db) is
    closed by the time a background task runs."""
    db = SessionLocal()
    try:
        entries = payload.get("entry") or []
        for entry in entries:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                for message in value.get("messages") or []:
                    store_inbound_whatsapp_message(db, message)
                for status in value.get("statuses") or []:
                    process_delivery_status(db, status)
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[WhatsAppWebhook] Failed processing payload: {exc}", exc_info=True)
    finally:
        db.close()


@router.post(
    dependencies=[Depends(get_current_user)]
    "/whatsapp",
    status_code=200,
    summary="Receive inbound WhatsApp messages and delivery status updates",
)
async def whatsapp_webhook_receive(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not validate_signature(raw_body, signature):
        logger.warning("[WhatsAppWebhook] INVALID_SIGNATURE -- discarding without processing.")
        # Still 200: Meta retries on non-200, and a bad signature won't
        # get better on retry -- discard quietly rather than trigger a
        # retry storm, same call the spec's own BR-03 intends.
        return {"status": "ignored"}

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("[WhatsAppWebhook] Non-JSON payload -- discarding.")
        return {"status": "ignored"}

    background_tasks.add_task(_process_webhook_payload, payload)
    return {"status": "received"}
