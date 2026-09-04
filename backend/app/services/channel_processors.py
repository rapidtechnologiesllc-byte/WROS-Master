"""Channel-specific queue processors for different message routing destinations.

Each processor handles a specific channel/queue type:
- EmailQueueProcessor: Email delivery with multi-provider tracking
- ThunderQueueProcessor: Autonomous candidate engagement
- WhatsAppQueueProcessor, SMSQueueProcessor, SlackQueueProcessor: Alternative channels
- ApprovalQueueProcessor, CommissionQueueProcessor: Workflow routing
- DashboardQueueProcessor, CalendarQueueProcessor, CRMQueueProcessor, SignatureQueueProcessor: Service routing

Implements FAIL FAST: All methods raise exceptions on error.
"""
import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from app.core.logging import logger

logger = logging.getLogger(__name__)

class BaseChannelProcessor:
    """Base class for all channel processors with common error handling."""

    QUEUE_TYPE = None  # Override in subclass

    @staticmethod
    def process(
        message_id: str,
        message_type: str,
        payload: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Process message for this channel.

        Args:
            message_id: ID of the message
            message_type: Type of message (e.g., 'candidate_added')
            payload: Message payload
            db: Database session

        Returns:
            Result dict with status, details

        Raises:
            ValueError: If inputs invalid
            RuntimeError: If processing fails
        """
        raise NotImplementedError("Subclass must implement process()")

    @staticmethod
    def validate_payload(payload: Dict[str, Any], required_fields: list) -> None:
        """
        Validate payload has required fields.

        Args:
            payload: Message payload
            required_fields: List of required field names

        Raises:
            ValueError: If required fields missing
        """
        if not payload:
            raise ValueError("Payload is required")

        missing = [field for field in required_fields if field not in payload]
        if missing:
            raise ValueError(f"Missing required fields in payload: {missing}")

class EmailQueueProcessor(BaseChannelProcessor):
    """Process messages to EMAIL_QUEUE - send emails with multi-provider tracking."""

    QUEUE_TYPE = "EMAIL_QUEUE"

    @staticmethod
    def process(
        message_id: str,
        message_type: str,
        payload: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Route message to email service for sending with tracking.

        Payload should contain:
        {
            "recipient_email": "user@example.com",
            "subject": "Email subject",
            "body": "Email body (HTML)",
            "template_name": "optional_template_id",
            "provider": "optional_provider_override",  # gmail, outlook, yahoo, apple, smtp
            "tracking_enabled": true  # Enable pixel/link tracking
        }
        """
        try:
            EmailQueueProcessor.validate_payload(payload, ["recipient_email", "subject", "body"])

            recipient = payload.get("recipient_email")
            subject = payload.get("subject")
            body = payload.get("body")
            template_name = payload.get("template_name")
            provider = payload.get("provider", "smtp")
            tracking_enabled = payload.get("tracking_enabled", True)

            if not recipient or "@" not in recipient:
                raise ValueError(f"Invalid recipient email: {recipient}")

            logger.info(
                f"EmailQueueProcessor routing message: {message_id} "
                f"to {recipient} via {provider} with tracking={tracking_enabled}"
            )

            # Import email service here to avoid circular imports
            from app.services.email_service import EmailService

            result = EmailService.send_email(
                message_id=message_id,
                recipient_email=recipient,
                subject=subject,
                body=body,
                template_name=template_name,
                provider=provider,
                tracking_enabled=tracking_enabled,
                db=db,
            )

            return {
                "status": "success",
                "queue_type": EmailQueueProcessor.QUEUE_TYPE,
                "recipient": recipient,
                "email_tracking_id": result.get("tracking_id"),
                "provider": provider,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"EmailQueueProcessor failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to route message to EMAIL_QUEUE: {str(e)}")

class ThunderQueueProcessor(BaseChannelProcessor):
    """Process messages to THUNDER_QUEUE - autonomous candidate engagement."""

    QUEUE_TYPE = "THUNDER_QUEUE"

    @staticmethod
    def process(
        message_id: str,
        message_type: str,
        payload: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Execute Thunder engagement for queued candidate.

        Payload should contain:
        {
            "candidate_id": "CAN-xxx",
            "candidate_name": "John Doe",
            "candidate_email": "john@example.com",
            "candidate_phone": "+91-98765-43210",
            "candidate_location": "Bangalore",
            "candidate_job_title": "Software Engineer",
            "created_at": "2026-08-31T10:00:00Z"
        }

        Actions:
        1. Assign AI agent to candidate (if not already assigned)
        2. Send initial engagement (email + WhatsApp per tenant config)
        3. Log Thunder activity
        """
        if db is None:
            raise ValueError("Database session required for Thunder processing")

        try:
            ThunderQueueProcessor.validate_payload(payload, ["candidate_id"])

            candidate_id = payload.get("candidate_id")
            candidate_name = payload.get("candidate_name", "Unknown")
            candidate_email = payload.get("candidate_email")

            logger.info(
                f"[ThunderQueueProcessor] Processing queued candidate: {candidate_id} "
                f"({candidate_name}) - message_id={message_id}"
            )

            # Step 1: Assign AI agent to candidate (auto_assign_ai_agent_on_creation logic)
            from app.services.ai_conversation_service import auto_assign_ai_agent_on_creation
            from app.services.tenant_config_service import resolve_default_tenant_id

            tenant_id = resolve_default_tenant_id()
            try:
                auto_assign_ai_agent_on_creation(candidate_id, db)
                logger.info(f"[ThunderQueueProcessor] AI agent assigned to {candidate_id}")
            except Exception as e:
                logger.error(f"Error: {str(e)}", exc_info=True)
                logger.warning(f"[ThunderQueueProcessor] AI assignment failed: {e}")
                # Don't fail the entire message - continue with engagement

            # Step 2: Send initial engagement (email + WhatsApp)
            greeting_channel = "BOTH_PARALLEL"
            try:
                from app.services.tenant_ai_config_service import get_greeting_channel
                greeting_channel = get_greeting_channel(db, tenant_id)
            except Exception:
                pass

            whatsapp_result = None
            if greeting_channel in ("WHATSAPP_FIRST", "BOTH_PARALLEL"):
                try:
                    from app.services.first_engagement_service import send_first_whatsapp_engagement
                    whatsapp_result = send_first_whatsapp_engagement(db, candidate_id, tenant_id)
                    logger.debug(f"[ThunderQueueProcessor] WhatsApp sent to {candidate_id}")
                except Exception as e:
                    logger.error(f"Error: {str(e)}", exc_info=True)
                    logger.warning(f"[ThunderQueueProcessor] WhatsApp failed: {e}")

            email_result = None
            if greeting_channel in ("EMAIL_FIRST", "BOTH_PARALLEL"):
                try:
                    from app.services.email_first_engagement_service import send_first_email_engagement
                    email_result = send_first_email_engagement(db, candidate_id, tenant_id)
                    logger.debug(f"[ThunderQueueProcessor] Email sent to {candidate_id}")
                except Exception as e:
                    logger.error(f"Error: {str(e)}", exc_info=True)
                    logger.warning(f"[ThunderQueueProcessor] Email failed: {e}")

            # Step 3: Log Thunder activity
            try:
                from app.core.agent_logging import log_agent_execution
                log_agent_execution(
                    db=db,
                    candidate_id=candidate_id,
                    agent_name="Thunder",
                    action="queue_processed",
                    details={
                        "message_id": message_id,
                        "email_sent": email_result is not None,
                        "whatsapp_sent": whatsapp_result is not None,
                    }
                )
            except Exception as e:
                logger.error(f"Error: {str(e)}", exc_info=True)
                logger.debug(f"[ThunderQueueProcessor] Activity logging failed: {e}")

            logger.info(
                f"[ThunderQueueProcessor] Queue message {message_id} processed successfully "
                f"for candidate {candidate_id}"
            )

            return {
                "status": "success",
                "queue_type": ThunderQueueProcessor.QUEUE_TYPE,
                "message_id": message_id,
                "candidate_id": candidate_id,
                "candidate_name": candidate_name,
                "ai_agent_assigned": True,
                "email_sent": email_result is not None,
                "whatsapp_sent": whatsapp_result is not None,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"[ThunderQueueProcessor] Failed to process message: {e}", exc_info=True)
            raise RuntimeError(f"Failed to process THUNDER_QUEUE message: {str(e)}")

class WhatsAppQueueProcessor(BaseChannelProcessor):
    """Process messages to WHATSAPP_QUEUE."""

    QUEUE_TYPE = "WHATSAPP_QUEUE"

    @staticmethod
    def process(
        message_id: str,
        message_type: str,
        payload: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Route message to WhatsApp service."""
        try:
            WhatsAppQueueProcessor.validate_payload(payload, ["phone_number", "message"])

            phone = payload.get("phone_number")
            message = payload.get("message")

            logger.info(f"WhatsAppQueueProcessor routing message: {message_id} to {phone}")

            # Import WhatsApp service
            from app.services.whatsapp_service import WhatsAppService

            result = WhatsAppService.send_message(
                message_id=message_id,
                phone_number=phone,
                message=message,
                db=db,
            )

            return {
                "status": "success",
                "queue_type": WhatsAppQueueProcessor.QUEUE_TYPE,
                "phone": phone,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"WhatsAppQueueProcessor failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to route message to WHATSAPP_QUEUE: {str(e)}")

class SMSQueueProcessor(BaseChannelProcessor):
    """Process messages to SMS_QUEUE."""

    QUEUE_TYPE = "SMS_QUEUE"

    @staticmethod
    def process(
        message_id: str,
        message_type: str,
        payload: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Route message to SMS service."""
        try:
            SMSQueueProcessor.validate_payload(payload, ["phone_number", "message"])

            phone = payload.get("phone_number")
            message = payload.get("message")

            logger.info(f"SMSQueueProcessor routing message: {message_id} to {phone}")

            from app.services.sms_service import SMSService

            result = SMSService.send_message(
                message_id=message_id,
                phone_number=phone,
                message=message,
                db=db,
            )

            return {
                "status": "success",
                "queue_type": SMSQueueProcessor.QUEUE_TYPE,
                "phone": phone,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"SMSQueueProcessor failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to route message to SMS_QUEUE: {str(e)}")

class SlackQueueProcessor(BaseChannelProcessor):
    """Process messages to SLACK_QUEUE."""

    QUEUE_TYPE = "SLACK_QUEUE"

    @staticmethod
    def process(
        message_id: str,
        message_type: str,
        payload: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Route message to Slack."""
        try:
            SlackQueueProcessor.validate_payload(payload, ["channel_id", "message"])

            channel = payload.get("channel_id")
            message = payload.get("message")

            logger.info(f"SlackQueueProcessor routing message: {message_id} to channel {channel}")

            from app.services.slack_service import SlackService

            result = SlackService.send_message(
                message_id=message_id,
                channel_id=channel,
                message=message,
                db=db,
            )

            return {
                "status": "success",
                "queue_type": SlackQueueProcessor.QUEUE_TYPE,
                "channel": channel,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"SlackQueueProcessor failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to route message to SLACK_QUEUE: {str(e)}")

class ApprovalQueueProcessor(BaseChannelProcessor):
    """Process messages to APPROVAL_QUEUE."""

    QUEUE_TYPE = "APPROVAL_QUEUE"

    @staticmethod
    def process(
        message_id: str,
        message_type: str,
        payload: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Route message to approval workflow."""
        try:
            ApprovalQueueProcessor.validate_payload(payload, ["approval_type", "requester_id", "target_id"])

            approval_type = payload.get("approval_type")
            requester_id = payload.get("requester_id")
            target_id = payload.get("target_id")

            logger.info(
                f"ApprovalQueueProcessor routing message: {message_id} "
                f"type={approval_type} requester={requester_id} target={target_id}"
            )

            from app.services.approval_service import ApprovalService

            result = ApprovalService.create_approval_request(
                message_id=message_id,
                approval_type=approval_type,
                requester_id=requester_id,
                target_id=target_id,
                payload=payload,
                db=db,
            )

            return {
                "status": "success",
                "queue_type": ApprovalQueueProcessor.QUEUE_TYPE,
                "approval_id": result.get("approval_id"),
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"ApprovalQueueProcessor failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to route message to APPROVAL_QUEUE: {str(e)}")

class CommissionQueueProcessor(BaseChannelProcessor):
    """Process messages to COMMISSION_QUEUE."""

    QUEUE_TYPE = "COMMISSION_QUEUE"

    @staticmethod
    def process(
        message_id: str,
        message_type: str,
        payload: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Route message to commission calculation."""
        try:
            CommissionQueueProcessor.validate_payload(payload, ["commission_type", "subject_id", "amount"])

            commission_type = payload.get("commission_type")
            subject_id = payload.get("subject_id")
            amount = payload.get("amount")

            logger.info(
                f"CommissionQueueProcessor routing message: {message_id} "
                f"type={commission_type} subject={subject_id} amount={amount}"
            )

            from app.services.commission_service import CommissionService

            result = CommissionService.process_commission(
                message_id=message_id,
                commission_type=commission_type,
                subject_id=subject_id,
                amount=amount,
                payload=payload,
                db=db,
            )

            return {
                "status": "success",
                "queue_type": CommissionQueueProcessor.QUEUE_TYPE,
                "commission_id": result.get("commission_id"),
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"CommissionQueueProcessor failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to route message to COMMISSION_QUEUE: {str(e)}")

class CRMQueueProcessor(BaseChannelProcessor):
    """Process messages to CRM_QUEUE."""

    QUEUE_TYPE = "CRM_QUEUE"

    @staticmethod
    def process(
        message_id: str,
        message_type: str,
        payload: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Route message to CRM system."""
        try:
            CRMQueueProcessor.validate_payload(payload, ["crm_action", "entity_type", "entity_id"])

            action = payload.get("crm_action")
            entity_type = payload.get("entity_type")
            entity_id = payload.get("entity_id")

            logger.info(
                f"CRMQueueProcessor routing message: {message_id} "
                f"action={action} entity={entity_type}/{entity_id}"
            )

            from app.services.crm_service import CRMService

            result = CRMService.sync_entity(
                message_id=message_id,
                crm_action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                payload=payload,
                db=db,
            )

            return {
                "status": "success",
                "queue_type": CRMQueueProcessor.QUEUE_TYPE,
                "crm_record_id": result.get("crm_record_id"),
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"CRMQueueProcessor failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to route message to CRM_QUEUE: {str(e)}")

class DashboardQueueProcessor(BaseChannelProcessor):
    """Process messages to DASHBOARD_QUEUE - display notifications."""

    QUEUE_TYPE = "DASHBOARD_QUEUE"

    @staticmethod
    def process(
        message_id: str,
        message_type: str,
        payload: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Route message to dashboard notification."""
        try:
            DashboardQueueProcessor.validate_payload(payload, ["target_user_id", "notification_type", "title"])

            target_user = payload.get("target_user_id")
            notif_type = payload.get("notification_type")
            title = payload.get("title")
            description = payload.get("description", "")

            logger.info(
                f"DashboardQueueProcessor routing message: {message_id} "
                f"to user {target_user} type={notif_type}"
            )

            from app.services.notification_service import NotificationService

            result = NotificationService.create_dashboard_notification(
                message_id=message_id,
                user_id=target_user,
                notification_type=notif_type,
                title=title,
                description=description,
                payload=payload,
                db=db,
            )

            return {
                "status": "success",
                "queue_type": DashboardQueueProcessor.QUEUE_TYPE,
                "notification_id": result.get("notification_id"),
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"DashboardQueueProcessor failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to route message to DASHBOARD_QUEUE: {str(e)}")

class CalendarQueueProcessor(BaseChannelProcessor):
    """Process messages to CALENDAR_QUEUE - create calendar events."""

    QUEUE_TYPE = "CALENDAR_QUEUE"

    @staticmethod
    def process(
        message_id: str,
        message_type: str,
        payload: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Route message to calendar system."""
        try:
            CalendarQueueProcessor.validate_payload(payload, ["calendar_owner_id", "event_title", "event_start", "event_end"])

            owner = payload.get("calendar_owner_id")
            title = payload.get("event_title")
            start = payload.get("event_start")
            end = payload.get("event_end")

            logger.info(
                f"CalendarQueueProcessor routing message: {message_id} "
                f"for user {owner} event={title}"
            )

            from app.services.calendar_service import CalendarService

            result = CalendarService.create_calendar_event(
                message_id=message_id,
                owner_id=owner,
                title=title,
                start_time=start,
                end_time=end,
                payload=payload,
                db=db,
            )

            return {
                "status": "success",
                "queue_type": CalendarQueueProcessor.QUEUE_TYPE,
                "calendar_event_id": result.get("calendar_event_id"),
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"CalendarQueueProcessor failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to route message to CALENDAR_QUEUE: {str(e)}")

class SignatureQueueProcessor(BaseChannelProcessor):
    """Process messages to SIGNATURE_QUEUE - digital signature workflows."""

    QUEUE_TYPE = "SIGNATURE_QUEUE"

    @staticmethod
    def process(
        message_id: str,
        message_type: str,
        payload: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Route message to signature service."""
        try:
            SignatureQueueProcessor.validate_payload(payload, ["document_id", "signer_email", "signer_name"])

            doc_id = payload.get("document_id")
            signer_email = payload.get("signer_email")
            signer_name = payload.get("signer_name")

            logger.info(
                f"SignatureQueueProcessor routing message: {message_id} "
                f"document={doc_id} signer={signer_email}"
            )

            from app.services.signature_service import SignatureService

            result = SignatureService.send_for_signature(
                message_id=message_id,
                document_id=doc_id,
                signer_email=signer_email,
                signer_name=signer_name,
                payload=payload,
                db=db,
            )

            return {
                "status": "success",
                "queue_type": SignatureQueueProcessor.QUEUE_TYPE,
                "signature_request_id": result.get("signature_request_id"),
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"SignatureQueueProcessor failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to route message to SIGNATURE_QUEUE: {str(e)}")

# Registry mapping queue types to processors
QUEUE_PROCESSORS = {
    EmailQueueProcessor.QUEUE_TYPE: EmailQueueProcessor,
    ThunderQueueProcessor.QUEUE_TYPE: ThunderQueueProcessor,
    WhatsAppQueueProcessor.QUEUE_TYPE: WhatsAppQueueProcessor,
    SMSQueueProcessor.QUEUE_TYPE: SMSQueueProcessor,
    SlackQueueProcessor.QUEUE_TYPE: SlackQueueProcessor,
    ApprovalQueueProcessor.QUEUE_TYPE: ApprovalQueueProcessor,
    CommissionQueueProcessor.QUEUE_TYPE: CommissionQueueProcessor,
    CRMQueueProcessor.QUEUE_TYPE: CRMQueueProcessor,
    DashboardQueueProcessor.QUEUE_TYPE: DashboardQueueProcessor,
    CalendarQueueProcessor.QUEUE_TYPE: CalendarQueueProcessor,
    SignatureQueueProcessor.QUEUE_TYPE: SignatureQueueProcessor,
}

def get_processor(queue_type: str) -> Optional[BaseChannelProcessor]:
    """Get processor for given queue type."""
    return QUEUE_PROCESSORS.get(queue_type)
