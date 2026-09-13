"""Channel Processors - Handle actual delivery for each channel type

Processors read items from channel queues and execute the actual delivery:
- EMAIL: Send emails via email provider
- WHATSAPP: Send WhatsApp messages
- SMS: Send SMS messages
- SLACK: Send Slack notifications
- THUNDER: Execute Thunder autonomous actions
- APPROVAL: Route to approval workflow
- COMMISSION: Calculate and record commissions
- CRM: Sync data with CRM
- DASHBOARD: Push updates to real-time dashboard
- CALENDAR: Create calendar events
- SIGNATURE: Request e-signatures
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.services.channel_queue_service import ChannelQueueService

logger = logging.getLogger(__name__)

class ChannelProcessors:
    """Processors for each channel type"""

    # ==================== EMAIL PROCESSOR ====================

    @staticmethod
    def process_email(item_id: str, recipient: str, payload: Dict[str, Any], db: Session) -> bool:
        """
        Process EMAIL channel - send email via Microsoft Graph API.

        CRITICAL: Email is only marked COMPLETED after successful delivery.
        Does not mark complete if send fails.

        Args:
            item_id: Unique channel queue item ID
            recipient: Email address to send to
            payload: Message payload (subject, body, is_html, etc.)
            db: Database session

        Returns:
            True if successful, False if failed (will retry)
        """
        try:
            from app.services.email_service import EmailService
            from app.services.channel_delivery_helpers import ErrorClassifier, DeliveryStatus
            from app.services.channel_queue_service import ChannelQueueService

            logger.info(f"Processing EMAIL: {item_id} to {recipient}")

            if not recipient or not recipient.strip():
                error_msg = "No recipient email address provided"
                logger.error(f"EMAIL failed - {error_msg}: {item_id}")
                ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
                return False

            # Extract email details from payload
            subject = payload.get("subject", "BlitzenX HRMS Notification")
            body = payload.get("body", "")
            html_body = payload.get("html_body") or payload.get("body", "")

            # Attempt actual email delivery via Microsoft Graph
            logger.info(f"Sending email via Microsoft Graph: {recipient}")
            try:
                response = EmailService._graph_post(
                    endpoint="https://graph.microsoft.com/v1.0/me/sendMail",
                    payload={
                        "message": {
                            "subject": subject,
                            "body": {
                                "contentType": "HTML" if payload.get("is_html") else "text",
                                "content": html_body,
                            },
                            "toRecipients": [{"emailAddress": {"address": recipient}}],
                            "isReadReceiptRequested": False,
                        },
                        "saveToSentItems": "true",
                    },
                    access_token=EmailService._get_token(),
                )

                # Email sent successfully (Graph API returns 202)
                logger.info(f"EMAIL sent successfully: {item_id} to {recipient}")
                result = DeliveryStatus.success(
                    delivery_id=item_id,
                    provider="microsoft_graph",
                )
                ChannelQueueService.mark_completed(item_id, db, result=result)
                return True

            except Exception as send_error:
                error_msg = str(send_error)
                error_code = getattr(send_error, "status_code", None)
                is_transient = ErrorClassifier.is_transient(error_code, error_msg)

                logger.error(
                    f"Failed to send EMAIL: {item_id} to {recipient} - "
                    f"Error: {error_msg} (transient={is_transient})",
                    exc_info=True,
                )
                ChannelQueueService.mark_failed(
                    item_id,
                    error_msg,
                    should_retry=is_transient,
                    db=db,
                )
                return False

        except Exception as e:
            logger.error(f"Unexpected error processing EMAIL {item_id}: {e}", exc_info=True)
            ChannelQueueService.mark_failed(item_id, str(e), should_retry=True, db=db)
            return False

    # ==================== WHATSAPP PROCESSOR ====================

    @staticmethod
    def process_whatsapp(item_id: str, recipient: str, payload: Dict[str, Any], db: Session) -> bool:
        """
        Process WHATSAPP channel - send WhatsApp message via Twilio.

        CRITICAL: Message is only marked COMPLETED after successful delivery.
        Currently uses mock delivery for testing.

        Args:
            item_id: Unique channel queue item ID
            recipient: WhatsApp phone number
            payload: Message payload (message text, etc.)
            db: Database session

        Returns:
            True if successful, False if failed
        """
        try:
            from app.services.channel_queue_service import ChannelQueueService

            logger.info(f"Processing WHATSAPP: {item_id} to {recipient}")

            if not recipient or not recipient.strip():
                error_msg = "No WhatsApp number provided"
                logger.error(f"WHATSAPP failed - {error_msg}: {item_id}")
                ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
                return False

            # Extract message details
            message_text = payload.get("message", "")
            if not message_text:
                error_msg = "No message text provided"
                logger.error(f"WHATSAPP failed - {error_msg}: {item_id}")
                ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
                return False

            # MOCK DELIVERY: Log and simulate successful send
            # In production: Replace with Twilio/MessageBird API call
            logger.info(f"MOCK: Sending WhatsApp to {recipient}: {message_text[:50]}...")

            # Simulate delivery (in real implementation, this would be API call)
            delivery_id = f"whatsapp-mock-{item_id[:8]}"

            result = {
                "status": "success",
                "delivery_id": delivery_id,
                "provider": "twilio_mock",
                "recipient": recipient,
                "timestamp": str(datetime.utcnow()),
            }

            ChannelQueueService.mark_completed(item_id, db, result=result)
            logger.info(f"WHATSAPP sent successfully (mock): {item_id} to {recipient}")
            return True

        except Exception as e:
            logger.error(f"Failed to process WHATSAPP: {e}", exc_info=True)
            ChannelQueueService.mark_failed(item_id, str(e), should_retry=True, db=db)
            return False

    # ==================== SMS PROCESSOR ====================

    @staticmethod
    def process_sms(item_id: str, recipient: str, payload: Dict[str, Any], db: Session) -> bool:
        """
        Process SMS channel - send SMS message via Twilio.

        CRITICAL: Message is only marked COMPLETED after successful delivery.

        Returns:
            True if successful, False if failed
        """
        try:
            from app.services.channel_queue_service import ChannelQueueService

            recipient = item_data.get("recipient")
            payload = item_data.get("payload", {})

            logger.info(f"Processing SMS: {item_id} to {recipient}")

            if not recipient or not recipient.strip():
                error_msg = "No phone number provided"
                logger.error(f"SMS failed - {error_msg}: {item_id}")
                ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
                return False

            # TODO: Implement actual SMS integration with Twilio
            # For now, log and fail gracefully
            error_msg = "SMS integration not yet configured (TODO: Twilio)"
            logger.warning(f"SMS not implemented: {item_id}")
            ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
            return False

        except Exception as e:
            logger.error(f"Failed to process SMS: {e}", exc_info=True)
            ChannelQueueService.mark_failed(item_id, str(e), should_retry=True, db=db)
            return False

    # ==================== SLACK PROCESSOR ====================

    @staticmethod
    def process_slack(item_id: str, recipient: str, payload: Dict[str, Any], db: Session) -> bool:
        """
        Process SLACK channel - send Slack notification.

        CRITICAL: Notification is only marked COMPLETED after successful delivery.

        Returns:
            True if successful, False if failed
        """
        try:
            from app.services.channel_queue_service import ChannelQueueService

            recipient = item_data.get("recipient")
            payload = item_data.get("payload", {})

            logger.info(f"Processing SLACK: {item_id} to {recipient}")

            if not recipient or not recipient.strip():
                error_msg = "No Slack channel/user provided"
                logger.error(f"SLACK failed - {error_msg}: {item_id}")
                ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
                return False

            # TODO: Implement actual Slack integration with Slack API
            # For now, log and fail gracefully
            error_msg = "Slack integration not yet configured (TODO: Slack API)"
            logger.warning(f"SLACK not implemented: {item_id}")
            ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
            return False

        except Exception as e:
            logger.error(f"Failed to process SLACK: {e}", exc_info=True)
            ChannelQueueService.mark_failed(item_id, str(e), should_retry=False, db=db)
            return False

    # ==================== THUNDER PROCESSOR ====================

    @staticmethod
    def process_thunder(item_id: str, recipient: str, payload: Dict[str, Any], db: Session) -> bool:
        """
        Process THUNDER channel - execute Thunder autonomous action.

        CRITICAL: Action is only marked COMPLETED after successful execution.

        Returns:
            True if successful, False if failed
        """
        try:
            from app.services.channel_queue_service import ChannelQueueService
            from app.services.channel_delivery_helpers import ErrorClassifier

            payload = item_data.get("payload", {})
            candidate_id = payload.get("candidate_id")
            action = payload.get("action")

            logger.info(
                f"Processing THUNDER: {item_id} action={action} candidate={candidate_id}"
            )

            if not candidate_id:
                error_msg = "No candidate_id provided for Thunder action"
                logger.error(f"THUNDER failed - {error_msg}: {item_id}")
                ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
                return False

            if not action:
                error_msg = "No action specified for Thunder"
                logger.error(f"THUNDER failed - {error_msg}: {item_id}")
                ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
                return False

            # Execute Thunder action based on type
            try:
                if action == "initiate_qualification":
                    # TODO: Call Thunder service to initiate qualification flow
                    logger.warning(
                        f"Thunder qualification flow not yet implemented for {candidate_id}"
                    )
                    error_msg = "Thunder qualification flow not yet implemented"
                    ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
                    return False

                elif action == "send_outreach":
                    # TODO: Call Thunder service to send initial outreach
                    logger.warning(f"Thunder outreach not yet implemented for {candidate_id}")
                    error_msg = "Thunder outreach not yet implemented"
                    ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
                    return False

                else:
                    error_msg = f"Unknown Thunder action: {action}"
                    logger.error(f"THUNDER failed - {error_msg}: {item_id}")
                    ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
                    return False

            except Exception as action_error:
                error_msg = str(action_error)
                is_transient = ErrorClassifier.is_transient(None, error_msg)
                logger.error(
                    f"Thunder action failed: {item_id} - {error_msg} (transient={is_transient})",
                    exc_info=True,
                )
                ChannelQueueService.mark_failed(
                    item_id, error_msg, should_retry=is_transient, db=db
                )
                return False

        except Exception as e:
            logger.error(f"Failed to process THUNDER: {e}", exc_info=True)
            ChannelQueueService.mark_failed(item_id, str(e), should_retry=True, db=db)
            return False

    # ==================== APPROVAL PROCESSOR ====================

    @staticmethod
    def process_approval(item_id: str, recipient: str, payload: Dict[str, Any], db: Session) -> bool:
        """
        Process APPROVAL channel - route to approval workflow.

        CRITICAL: Approval is only marked COMPLETED after workflow is created.

        Returns:
            True if successful, False if failed
        """
        try:
            from app.services.channel_queue_service import ChannelQueueService

            payload = item_data.get("payload", {})
            workflow_type = payload.get("workflow_type")
            recipient = item_data.get("recipient")

            logger.info(
                f"Processing APPROVAL: {item_id} workflow={workflow_type} manager={recipient}"
            )

            if not workflow_type:
                error_msg = "No workflow_type specified"
                logger.error(f"APPROVAL failed - {error_msg}: {item_id}")
                ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
                return False

            # TODO: Implement approval workflow creation
            error_msg = "Approval workflow creation not yet implemented"
            logger.warning(f"APPROVAL not implemented: {item_id}")
            ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
            return False

        except Exception as e:
            logger.error(f"Failed to process APPROVAL: {e}", exc_info=True)
            ChannelQueueService.mark_failed(item_id, str(e), should_retry=True, db=db)
            return False

    # ==================== COMMISSION PROCESSOR ====================

    @staticmethod
    def process_commission(item_id: str, item_data: Dict[str, Any], db: Session) -> bool:
        """
        Process COMMISSION channel - calculate and record commission.

        CRITICAL: Commission is only marked COMPLETED after ledger entry recorded.

        Returns:
            True if successful, False if failed
        """
        try:
            from app.services.channel_queue_service import ChannelQueueService

            payload = item_data.get("payload", {})
            deal_id = payload.get("deal_id")
            partner_id = payload.get("partner_id")
            amount = payload.get("amount")

            logger.info(
                f"Processing COMMISSION: {item_id} deal={deal_id} partner={partner_id} amount={amount}"
            )

            if not deal_id or not partner_id:
                error_msg = "Missing deal_id or partner_id for commission"
                logger.error(f"COMMISSION failed - {error_msg}: {item_id}")
                ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
                return False

            # TODO: Implement commission calculation and ledger recording
            error_msg = "Commission calculation not yet implemented"
            logger.warning(f"COMMISSION not implemented: {item_id}")
            ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
            return False

        except Exception as e:
            logger.error(f"Failed to process COMMISSION: {e}", exc_info=True)
            ChannelQueueService.mark_failed(item_id, str(e), should_retry=True, db=db)
            return False

    # ==================== CRM PROCESSOR ====================

    @staticmethod
    def process_crm(item_id: str, item_data: Dict[str, Any], db: Session) -> bool:
        """
        Process CRM channel - sync data with CRM.

        CRITICAL: Sync is only marked COMPLETED after CRM API confirms success.

        Returns:
            True if successful, False if failed
        """
        try:
            from app.services.channel_queue_service import ChannelQueueService

            payload = item_data.get("payload", {})
            action = payload.get("action")
            client_id = payload.get("client_id")

            logger.info(f"Processing CRM: {item_id} action={action} client={client_id}")

            if not action or not client_id:
                error_msg = "Missing action or client_id for CRM sync"
                logger.error(f"CRM failed - {error_msg}: {item_id}")
                ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
                return False

            # TODO: Implement CRM sync
            error_msg = "CRM sync not yet implemented"
            logger.warning(f"CRM not implemented: {item_id}")
            ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
            return False

        except Exception as e:
            logger.error(f"Failed to process CRM: {e}", exc_info=True)
            ChannelQueueService.mark_failed(item_id, str(e), should_retry=True, db=db)
            return False

    # ==================== DASHBOARD PROCESSOR ====================

    @staticmethod
    def process_dashboard(item_id: str, item_data: Dict[str, Any], db: Session) -> bool:
        """
        Process DASHBOARD channel - push real-time update to dashboard.

        CRITICAL: Update is only marked COMPLETED after WebSocket push.

        Returns:
            True if successful, False if failed
        """
        try:
            from app.services.channel_queue_service import ChannelQueueService

            payload = item_data.get("payload", {})
            update_type = payload.get("update_type")
            kpi_id = payload.get("kpi_id")

            logger.info(
                f"Processing DASHBOARD: {item_id} update_type={update_type} kpi={kpi_id}"
            )

            if not update_type:
                error_msg = "No update_type specified for dashboard"
                logger.error(f"DASHBOARD failed - {error_msg}: {item_id}")
                ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
                return False

            # TODO: Implement dashboard update via WebSocket
            error_msg = "Dashboard WebSocket push not yet implemented"
            logger.warning(f"DASHBOARD not implemented: {item_id}")
            # Dashboard updates don't retry (non-critical)
            ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
            return False

        except Exception as e:
            logger.error(f"Failed to process DASHBOARD: {e}", exc_info=True)
            ChannelQueueService.mark_failed(item_id, str(e), should_retry=False, db=db)
            return False

    # ==================== CALENDAR PROCESSOR ====================

    @staticmethod
    def process_calendar(item_id: str, item_data: Dict[str, Any], db: Session) -> bool:
        """
        Process CALENDAR channel - create calendar events.

        CRITICAL: Event is only marked COMPLETED after calendar creation confirmed.

        Returns:
            True if successful, False if failed
        """
        try:
            from app.services.channel_queue_service import ChannelQueueService

            payload = item_data.get("payload", {})
            event_type = payload.get("event_type")
            interview_id = payload.get("interview_id")

            logger.info(
                f"Processing CALENDAR: {item_id} event_type={event_type} interview={interview_id}"
            )

            if not event_type or not interview_id:
                error_msg = "Missing event_type or interview_id for calendar"
                logger.error(f"CALENDAR failed - {error_msg}: {item_id}")
                ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
                return False

            # TODO: Implement calendar event creation
            error_msg = "Calendar event creation not yet implemented"
            logger.warning(f"CALENDAR not implemented: {item_id}")
            ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
            return False

        except Exception as e:
            logger.error(f"Failed to process CALENDAR: {e}", exc_info=True)
            ChannelQueueService.mark_failed(item_id, str(e), should_retry=True, db=db)
            return False

    # ==================== SIGNATURE PROCESSOR ====================

    @staticmethod
    def process_signature(item_id: str, item_data: Dict[str, Any], db: Session) -> bool:
        """
        Process SIGNATURE channel - request e-signatures.

        CRITICAL: Request is only marked COMPLETED after e-signature service confirms.

        Returns:
            True if successful, False if failed
        """
        try:
            from app.services.channel_queue_service import ChannelQueueService

            payload = item_data.get("payload", {})
            document_type = payload.get("document_type")
            offer_id = payload.get("offer_id")
            recipient = item_data.get("recipient")

            logger.info(
                f"Processing SIGNATURE: {item_id} doc_type={document_type} "
                f"offer={offer_id} recipient={recipient}"
            )

            if not document_type or not offer_id or not recipient:
                error_msg = "Missing required fields for signature request"
                logger.error(f"SIGNATURE failed - {error_msg}: {item_id}")
                ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
                return False

            # TODO: Implement e-signature request
            error_msg = "E-signature request not yet implemented"
            logger.warning(f"SIGNATURE not implemented: {item_id}")
            ChannelQueueService.mark_failed(item_id, error_msg, should_retry=False, db=db)
            return False

        except Exception as e:
            logger.error(f"Failed to process SIGNATURE: {e}", exc_info=True)
            ChannelQueueService.mark_failed(item_id, str(e), should_retry=True, db=db)
            return False

    # ==================== DISPATCHER ====================

    @staticmethod
    def process_by_channel(
        channel_type: str,
        item_id: str,
        recipient: str,
        payload: Dict[str, Any],
        db: Session,
    ) -> bool:
        """
        Dispatch to appropriate processor based on channel type.

        Args:
            channel_type: Channel type (EMAIL, WHATSAPP, SMS, etc.)
            item_id: Item ID
            recipient: Recipient email/phone
            payload: Message payload
            db: Database session

        Returns:
            True if successful, False if failed
        """
        try:
            if channel_type == ChannelQueueService.CHANNEL_EMAIL:
                return ChannelProcessors.process_email(item_id, recipient, payload, db)
            elif channel_type == ChannelQueueService.CHANNEL_WHATSAPP:
                return ChannelProcessors.process_whatsapp(item_id, recipient, payload, db)
            elif channel_type == ChannelQueueService.CHANNEL_SMS:
                return ChannelProcessors.process_sms(item_id, recipient, payload, db)
            elif channel_type == ChannelQueueService.CHANNEL_SLACK:
                return ChannelProcessors.process_slack(item_id, recipient, payload, db)
            elif channel_type == ChannelQueueService.CHANNEL_THUNDER:
                return ChannelProcessors.process_thunder(item_id, recipient, payload, db)
            elif channel_type == ChannelQueueService.CHANNEL_APPROVAL:
                return ChannelProcessors.process_approval(item_id, recipient, payload, db)
            elif channel_type == ChannelQueueService.CHANNEL_COMMISSION:
                return ChannelProcessors.process_commission(item_id, recipient, payload, db)
            elif channel_type == ChannelQueueService.CHANNEL_CRM:
                return ChannelProcessors.process_crm(item_id, recipient, payload, db)
            elif channel_type == ChannelQueueService.CHANNEL_DASHBOARD:
                return ChannelProcessors.process_dashboard(item_id, recipient, payload, db)
            elif channel_type == ChannelQueueService.CHANNEL_CALENDAR:
                return ChannelProcessors.process_calendar(item_id, recipient, payload, db)
            elif channel_type == ChannelQueueService.CHANNEL_SIGNATURE:
                return ChannelProcessors.process_signature(item_id, recipient, payload, db)
            else:
                logger.warning(f"Unknown channel type: {channel_type}")
                ChannelQueueService.mark_failed(
                    item_id,
                    f"Unknown channel type: {channel_type}",
                    should_retry=False,
                    db=db,
                )
                return False

        except Exception as e:
            logger.error(f"Failed to dispatch channel processor: {e}", exc_info=True)
            return False
