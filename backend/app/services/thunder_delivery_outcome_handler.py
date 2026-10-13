"""Thunder Delivery Outcome Handler - Records actual outcomes for learning system

When Thunder messages get delivery/open/click events from external providers,
this handler records them back to the learning system so we can measure prediction accuracy.

Event flow:
1. Message sent (Thunder) → prediction recorded by thunder_learning_integration.py
2. Delivery provider sends webhook (email open, SMS read, WhatsApp read receipt, etc.)
3. This handler processes webhook → records actual outcome
4. Learning system compares: predicted vs actual → updates weights
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.thunder_learning_integration import ThunderLearningIntegration

logger = logging.getLogger(__name__)


class ThunderDeliveryOutcomeHandler:
    """Processes delivery events and records outcomes to learning system."""

    # Map external event types to outcome categories
    EVENT_TYPE_TO_OUTCOME = {
        # Email events
        "delivered": "delivered",
        "opened": "opened",
        "clicked": "clicked",
        "bounced": "bounced",
        "complained": "complained",
        "unsubscribed": "unsubscribed",

        # SMS/WhatsApp events
        "sent": "sent",
        "read": "opened",
        "replied": "replied",
        "failed": "failed",

        # Web chat events
        "message_read": "opened",
        "message_responded": "replied",

        # Generic
        "engaged": "engaged",
        "no_response": "no_response",
    }

    @staticmethod
    def handle_delivery_event(
        db: Session,
        tenant_id: str,
        candidate_id: str,
        conversation_id: str,
        event_type: str,
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process delivery/engagement event from external provider.

        Called by webhook handlers when:
        - Email is delivered/opened/clicked
        - SMS is delivered/read/replied
        - WhatsApp message is delivered/read/replied
        - Web chat message is read/replied

        Args:
            db: Database session
            tenant_id: Tenant ID
            candidate_id: Candidate ID from original message
            conversation_id: Conversation ID from original message
            event_type: Event type ("delivered", "opened", "clicked", "replied", etc.)
            event_data: Event details with timestamp, channel, etc.

        Returns:
            Outcome record with learning feedback
        """
        try:
            # Normalize event type to learning outcome
            outcome_type = ThunderDeliveryOutcomeHandler.EVENT_TYPE_TO_OUTCOME.get(
                event_type, event_type
            )

            # Record the outcome
            result = ThunderLearningIntegration.record_engagement_outcome(
                db=db,
                tenant_id=tenant_id,
                candidate_id=candidate_id,
                conversation_id=conversation_id,
                event_type=outcome_type,
                event_data=event_data,
            )

            logger.info(
                f"[ThunderOutcomeHandler] Recorded outcome: "
                f"candidate={candidate_id} "
                f"event={event_type} "
                f"outcome={outcome_type}"
            )

            return result

        except Exception as e:
            logger.error(
                f"[ThunderOutcomeHandler] Failed to record outcome: {e}",
                exc_info=True
            )
            return {"status": "error", "error": str(e)}

    @staticmethod
    def handle_email_delivery_webhook(
        db: Session,
        tenant_id: str,
        webhook_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process email delivery webhook from SendGrid/Mailgun/etc.

        Webhook structure (varies by provider):
        {
            "event": "open" | "click" | "delivered" | "bounce" | etc,
            "email": "candidate@example.com",
            "timestamp": "2026-10-11T15:30:00Z",
            "conversation_id": "...",
            "candidate_id": "...",
            "message_id": "...",
        }
        """
        try:
            event_type = webhook_data.get("event", "unknown")
            candidate_id = webhook_data.get("candidate_id")
            conversation_id = webhook_data.get("conversation_id")

            if not candidate_id or not conversation_id:
                logger.warning(f"[ThunderOutcomeHandler] Missing IDs in email webhook: {webhook_data}")
                return {"status": "error", "reason": "missing_candidate_or_conversation_id"}

            return ThunderDeliveryOutcomeHandler.handle_delivery_event(
                db=db,
                tenant_id=tenant_id,
                candidate_id=candidate_id,
                conversation_id=conversation_id,
                event_type=event_type,
                event_data={
                    "timestamp": webhook_data.get("timestamp", datetime.utcnow().isoformat()),
                    "channel": "email",
                    "message_id": webhook_data.get("message_id"),
                    "email": webhook_data.get("email"),
                    "provider": webhook_data.get("provider", "unknown"),
                },
            )

        except Exception as e:
            logger.error(f"[ThunderOutcomeHandler] Failed to handle email webhook: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    @staticmethod
    def handle_sms_delivery_webhook(
        db: Session,
        tenant_id: str,
        webhook_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process SMS delivery webhook from Twilio/etc.

        Webhook structure:
        {
            "event": "delivered" | "read" | "failed" | "replied",
            "phone": "+1234567890",
            "timestamp": "2026-10-11T15:30:00Z",
            "conversation_id": "...",
            "candidate_id": "...",
            "message_id": "...",
            "reply_text": "...",  # if event is "replied"
        }
        """
        try:
            event_type = webhook_data.get("event", "unknown")
            candidate_id = webhook_data.get("candidate_id")
            conversation_id = webhook_data.get("conversation_id")

            if not candidate_id or not conversation_id:
                logger.warning(f"[ThunderOutcomeHandler] Missing IDs in SMS webhook: {webhook_data}")
                return {"status": "error", "reason": "missing_candidate_or_conversation_id"}

            return ThunderDeliveryOutcomeHandler.handle_delivery_event(
                db=db,
                tenant_id=tenant_id,
                candidate_id=candidate_id,
                conversation_id=conversation_id,
                event_type=event_type,
                event_data={
                    "timestamp": webhook_data.get("timestamp", datetime.utcnow().isoformat()),
                    "channel": "sms",
                    "message_id": webhook_data.get("message_id"),
                    "phone": webhook_data.get("phone"),
                    "provider": webhook_data.get("provider", "twilio"),
                    "reply_text": webhook_data.get("reply_text") if event_type == "replied" else None,
                },
            )

        except Exception as e:
            logger.error(f"[ThunderOutcomeHandler] Failed to handle SMS webhook: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    @staticmethod
    def handle_whatsapp_delivery_webhook(
        db: Session,
        tenant_id: str,
        webhook_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process WhatsApp delivery webhook from Twilio/MessageBird/etc.

        Webhook structure:
        {
            "event": "sent" | "delivered" | "read" | "replied" | "failed",
            "phone": "+1234567890",
            "timestamp": "2026-10-11T15:30:00Z",
            "conversation_id": "...",
            "candidate_id": "...",
            "message_id": "...",
            "message_text": "...",  # if event is "replied"
        }
        """
        try:
            event_type = webhook_data.get("event", "unknown")
            candidate_id = webhook_data.get("candidate_id")
            conversation_id = webhook_data.get("conversation_id")

            if not candidate_id or not conversation_id:
                logger.warning(f"[ThunderOutcomeHandler] Missing IDs in WhatsApp webhook: {webhook_data}")
                return {"status": "error", "reason": "missing_candidate_or_conversation_id"}

            return ThunderDeliveryOutcomeHandler.handle_delivery_event(
                db=db,
                tenant_id=tenant_id,
                candidate_id=candidate_id,
                conversation_id=conversation_id,
                event_type=event_type,
                event_data={
                    "timestamp": webhook_data.get("timestamp", datetime.utcnow().isoformat()),
                    "channel": "whatsapp",
                    "message_id": webhook_data.get("message_id"),
                    "phone": webhook_data.get("phone"),
                    "provider": webhook_data.get("provider", "twilio"),
                    "message_text": webhook_data.get("message_text") if event_type == "replied" else None,
                },
            )

        except Exception as e:
            logger.error(f"[ThunderOutcomeHandler] Failed to handle WhatsApp webhook: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
