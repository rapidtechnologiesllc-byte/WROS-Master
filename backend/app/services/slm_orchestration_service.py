"""SLM Orchestration Service - Decides which channels to trigger for each message

After a message is processed (PENDING → SLM_PROCESSING), SLM analyzes it and creates
channel queue items for specific channels to handle.

Examples:
- Candidate created → Create THUNDER_QUEUE entry
- Offer generated → Create EMAIL_QUEUE + SIGNATURE_QUEUE entries
- Interview scheduled → Create EMAIL_QUEUE + WHATSAPP_QUEUE + CALENDAR_QUEUE entries
- Timesheet submitted → Create APPROVAL_QUEUE entry
- KPI updated → Create DASHBOARD_QUEUE entry

Implements FAIL FAST: All methods raise exceptions on error.
"""
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.channel_queue_service import ChannelQueueService

logger = logging.getLogger(__name__)


class SLMOrchestrationService:
    """Orchestrates channel creation based on message type and context"""

    @staticmethod
    def orchestrate_message(
        message_id: str,
        queue_type: str,
        payload: Dict[str, Any],
        resource_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Analyze message and create appropriate channel queue items.

        Args:
            message_id: ID of message_queue entry
            queue_type: Type of primary message (CANDIDATE, INTERVIEW, OFFER, TIMESHEET, KPI, SALES, CLIENT)
            payload: Message payload
            resource_id: Resource ID (candidate_id, interview_id, etc.)
            db: Database session

        Returns:
            Orchestration result with channels created

        Raises:
            ValueError: If inputs invalid
            RuntimeError: If orchestration fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            logger.info(f"Orchestrating message: {message_id} queue_type={queue_type}")

            channels_created = []

            # Route to type-specific orchestrator
            if queue_type == "CANDIDATE":
                channels_created = SLMOrchestrationService._orchestrate_candidate_created(
                    message_id, payload, db
                )
            elif queue_type == "INTERVIEW":
                channels_created = SLMOrchestrationService._orchestrate_interview_scheduled(
                    message_id, payload, db
                )
            elif queue_type == "OFFER":
                channels_created = SLMOrchestrationService._orchestrate_offer_generated(
                    message_id, payload, db
                )
            elif queue_type == "TIMESHEET":
                channels_created = SLMOrchestrationService._orchestrate_timesheet_submitted(
                    message_id, payload, db
                )
            elif queue_type == "KPI":
                channels_created = SLMOrchestrationService._orchestrate_kpi_updated(
                    message_id, payload, db
                )
            elif queue_type == "SALES":
                channels_created = SLMOrchestrationService._orchestrate_sales_deal(
                    message_id, payload, db
                )
            elif queue_type == "CLIENT":
                channels_created = SLMOrchestrationService._orchestrate_client_contact(
                    message_id, payload, db
                )
            else:
                logger.warning(f"Unknown queue type: {queue_type}")
                channels_created = []

            logger.info(
                f"Orchestration complete: {len(channels_created)} channels created "
                f"for message {message_id}"
            )

            return {
                "message_id": message_id,
                "queue_type": queue_type,
                "channels_created": channels_created,
                "channel_count": len(channels_created),
            }

        except Exception as e:            logger.error(f"Failed to orchestrate message: {e}", exc_info=True)
            raise RuntimeError(f"Failed to orchestrate message: {str(e)}")

    @staticmethod
    def _orchestrate_candidate_created(
        message_id: str,
        payload: Dict[str, Any],
        db: Session,
    ) -> List[str]:
        """
        Candidate created → THUNDER_QUEUE (to contact candidate autonomously)

        SLM Decision:
        - Every new candidate should be contacted by Thunder (autonomous)
        - Thunder will initiate qualification flow
        """
        channels = []

        try:
            # Create THUNDER_QUEUE entry
            thunder_payload = {
                "candidate_id": payload.get("candidate_id"),
                "action": "initiate_qualification",
                "source": "candidate_intake",
            }

            channel_id = ChannelQueueService.create_channel_queue_item(
                message_id=message_id,
                channel_type=ChannelQueueService.CHANNEL_THUNDER,
                payload=thunder_payload,
                recipient=payload.get("candidate_id"),
                db=db,
            )
            channels.append(channel_id)

            logger.info(f"Created THUNDER_QUEUE for candidate: {channel_id}")

        except Exception as e:            logger.error(f"Failed to create THUNDER_QUEUE: {e}", exc_info=True)
            raise

        return channels

    @staticmethod
    def _orchestrate_interview_scheduled(
        message_id: str,
        payload: Dict[str, Any],
        db: Session,
    ) -> List[str]:
        """
        Interview scheduled → EMAIL_QUEUE + WHATSAPP_QUEUE + CALENDAR_QUEUE

        SLM Decision:
        - Email: Candidate interview confirmation + panel members
        - WhatsApp: Quick reminder to candidate (optional, based on consent)
        - Calendar: Add to candidate and panel member calendars
        """
        channels = []

        try:
            candidate_email = payload.get("candidate_email")
            candidate_phone = payload.get("candidate_phone")

            # EMAIL_QUEUE: Interview confirmation
            email_payload = {
                "template": "interview_confirmation",
                "candidate_id": payload.get("candidate_id"),
                "interview_id": payload.get("interview_id"),
                "interview_date": payload.get("interview_date"),
                "interview_time": payload.get("interview_time"),
                "panel_members": payload.get("panel_members", []),
            }

            email_id = ChannelQueueService.create_channel_queue_item(
                message_id=message_id,
                channel_type=ChannelQueueService.CHANNEL_EMAIL,
                payload=email_payload,
                recipient=candidate_email,
                db=db,
            )
            channels.append(email_id)

            # WHATSAPP_QUEUE: Optional quick reminder
            if candidate_phone and payload.get("consent_whatsapp"):
                whatsapp_payload = {
                    "template": "interview_reminder",
                    "candidate_id": payload.get("candidate_id"),
                    "interview_id": payload.get("interview_id"),
                    "interview_date": payload.get("interview_date"),
                }

                whatsapp_id = ChannelQueueService.create_channel_queue_item(
                    message_id=message_id,
                    channel_type=ChannelQueueService.CHANNEL_WHATSAPP,
                    payload=whatsapp_payload,
                    recipient=candidate_phone,
                    db=db,
                )
                channels.append(whatsapp_id)

            # CALENDAR_QUEUE: Add to calendars
            calendar_payload = {
                "event_type": "interview",
                "interview_id": payload.get("interview_id"),
                "candidate_id": payload.get("candidate_id"),
                "panel_members": payload.get("panel_members", []),
                "interview_date": payload.get("interview_date"),
                "interview_time": payload.get("interview_time"),
            }

            calendar_id = ChannelQueueService.create_channel_queue_item(
                message_id=message_id,
                channel_type=ChannelQueueService.CHANNEL_CALENDAR,
                payload=calendar_payload,
                recipient="system",
                db=db,
            )
            channels.append(calendar_id)

            logger.info(
                f"Created {len(channels)} channels for interview: "
                f"EMAIL, WHATSAPP, CALENDAR"
            )

        except Exception as e:            logger.error(f"Failed to create interview channels: {e}", exc_info=True)
            raise

        return channels

    @staticmethod
    def _orchestrate_offer_generated(
        message_id: str,
        payload: Dict[str, Any],
        db: Session,
    ) -> List[str]:
        """
        Offer generated → EMAIL_QUEUE + SIGNATURE_QUEUE

        SLM Decision:
        - Email: Send offer letter to candidate
        - Signature: Request e-signature on offer
        """
        channels = []

        try:
            candidate_email = payload.get("candidate_email")

            # EMAIL_QUEUE: Offer letter
            email_payload = {
                "template": "offer_letter",
                "candidate_id": payload.get("candidate_id"),
                "offer_id": payload.get("offer_id"),
                "position": payload.get("position"),
                "salary": payload.get("salary"),
            }

            email_id = ChannelQueueService.create_channel_queue_item(
                message_id=message_id,
                channel_type=ChannelQueueService.CHANNEL_EMAIL,
                payload=email_payload,
                recipient=candidate_email,
                db=db,
            )
            channels.append(email_id)

            # SIGNATURE_QUEUE: E-signature request
            signature_payload = {
                "document_type": "offer_letter",
                "offer_id": payload.get("offer_id"),
                "candidate_id": payload.get("candidate_id"),
            }

            signature_id = ChannelQueueService.create_channel_queue_item(
                message_id=message_id,
                channel_type=ChannelQueueService.CHANNEL_SIGNATURE,
                payload=signature_payload,
                recipient=candidate_email,
                db=db,
            )
            channels.append(signature_id)

            logger.info(f"Created offer channels: EMAIL, SIGNATURE")

        except Exception as e:            logger.error(f"Failed to create offer channels: {e}", exc_info=True)
            raise

        return channels

    @staticmethod
    def _orchestrate_timesheet_submitted(
        message_id: str,
        payload: Dict[str, Any],
        db: Session,
    ) -> List[str]:
        """
        Timesheet submitted → APPROVAL_QUEUE

        SLM Decision:
        - Route to manager for approval
        """
        channels = []

        try:
            approval_payload = {
                "workflow_type": "timesheet_approval",
                "timesheet_id": payload.get("timesheet_id"),
                "employee_id": payload.get("employee_id"),
                "manager_id": payload.get("manager_id"),
                "week": payload.get("week"),
                "total_hours": payload.get("total_hours"),
            }

            approval_id = ChannelQueueService.create_channel_queue_item(
                message_id=message_id,
                channel_type=ChannelQueueService.CHANNEL_APPROVAL,
                payload=approval_payload,
                recipient=payload.get("manager_id"),
                db=db,
            )
            channels.append(approval_id)

            logger.info("Created APPROVAL_QUEUE for timesheet")

        except Exception as e:            logger.error(f"Failed to create timesheet approval: {e}", exc_info=True)
            raise

        return channels

    @staticmethod
    def _orchestrate_kpi_updated(
        message_id: str,
        payload: Dict[str, Any],
        db: Session,
    ) -> List[str]:
        """
        KPI updated → DASHBOARD_QUEUE + EMAIL_QUEUE (if threshold breached)

        SLM Decision:
        - Always update dashboard
        - Send email alert if KPI falls below threshold
        """
        channels = []

        try:
            # DASHBOARD_QUEUE: Real-time update
            dashboard_payload = {
                "update_type": "kpi_update",
                "kpi_id": payload.get("kpi_id"),
                "metric_type": payload.get("metric_type"),
                "current_value": payload.get("current_value"),
                "target_value": payload.get("target_value"),
                "threshold_triggered": payload.get("threshold_triggered", False),
            }

            dashboard_id = ChannelQueueService.create_channel_queue_item(
                message_id=message_id,
                channel_type=ChannelQueueService.CHANNEL_DASHBOARD,
                payload=dashboard_payload,
                recipient="system",
                db=db,
            )
            channels.append(dashboard_id)

            # EMAIL_QUEUE: Alert if threshold breached
            if payload.get("threshold_triggered"):
                email_payload = {
                    "template": "kpi_alert",
                    "kpi_id": payload.get("kpi_id"),
                    "metric_type": payload.get("metric_type"),
                    "current_value": payload.get("current_value"),
                    "threshold": payload.get("threshold"),
                }

                email_id = ChannelQueueService.create_channel_queue_item(
                    message_id=message_id,
                    channel_type=ChannelQueueService.CHANNEL_EMAIL,
                    payload=email_payload,
                    recipient=payload.get("manager_email"),
                    db=db,
                )
                channels.append(email_id)

            logger.info(f"Created KPI channels: {len(channels)}")

        except Exception as e:            logger.error(f"Failed to create KPI channels: {e}", exc_info=True)
            raise

        return channels

    @staticmethod
    def _orchestrate_sales_deal(
        message_id: str,
        payload: Dict[str, Any],
        db: Session,
    ) -> List[str]:
        """
        Sales deal → SALES_QUEUE + COMMISSION_QUEUE + EMAIL_QUEUE

        SLM Decision:
        - Sales queue for deal processing
        - Commission queue for calculation
        - Email for notifications
        """
        channels = []

        try:
            # SALES_QUEUE
            sales_payload = {
                "action": payload.get("action", "deal_update"),
                "deal_id": payload.get("deal_id"),
                "value": payload.get("value"),
                "stage": payload.get("stage"),
            }

            sales_id = ChannelQueueService.create_channel_queue_item(
                message_id=message_id,
                channel_type=ChannelQueueService.CHANNEL_SALES,
                payload=sales_payload,
                recipient=payload.get("partner_id"),
                db=db,
            )
            channels.append(sales_id)

            # COMMISSION_QUEUE (if deal closed)
            if payload.get("action") == "deal_closed":
                commission_payload = {
                    "deal_id": payload.get("deal_id"),
                    "partner_id": payload.get("partner_id"),
                    "amount": payload.get("value"),
                }

                commission_id = ChannelQueueService.create_channel_queue_item(
                    message_id=message_id,
                    channel_type=ChannelQueueService.CHANNEL_COMMISSION,
                    payload=commission_payload,
                    recipient=payload.get("partner_id"),
                    db=db,
                )
                channels.append(commission_id)

            logger.info(f"Created sales channels: {len(channels)}")

        except Exception as e:            logger.error(f"Failed to create sales channels: {e}", exc_info=True)
            raise

        return channels

    @staticmethod
    def _orchestrate_client_contact(
        message_id: str,
        payload: Dict[str, Any],
        db: Session,
    ) -> List[str]:
        """
        Client contact → CRM_QUEUE + EMAIL_QUEUE

        SLM Decision:
        - Sync with CRM
        - Send follow-up email if new contact
        """
        channels = []

        try:
            # CRM_QUEUE: Sync client data
            crm_payload = {
                "action": "sync_client",
                "client_id": payload.get("client_id"),
                "contact_name": payload.get("contact_name"),
                "contact_email": payload.get("contact_email"),
                "company": payload.get("company"),
            }

            crm_id = ChannelQueueService.create_channel_queue_item(
                message_id=message_id,
                channel_type=ChannelQueueService.CHANNEL_CRM,
                payload=crm_payload,
                recipient=payload.get("client_id"),
                db=db,
            )
            channels.append(crm_id)

            # EMAIL_QUEUE: Follow-up
            if payload.get("is_new_contact"):
                email_payload = {
                    "template": "client_welcome",
                    "client_id": payload.get("client_id"),
                    "contact_name": payload.get("contact_name"),
                }

                email_id = ChannelQueueService.create_channel_queue_item(
                    message_id=message_id,
                    channel_type=ChannelQueueService.CHANNEL_EMAIL,
                    payload=email_payload,
                    recipient=payload.get("contact_email"),
                    db=db,
                )
                channels.append(email_id)

            logger.info(f"Created client channels: {len(channels)}")

        except Exception as e:            logger.error(f"Failed to create client channels: {e}", exc_info=True)
            raise

        return channels
