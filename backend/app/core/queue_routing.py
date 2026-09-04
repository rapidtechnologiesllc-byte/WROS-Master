"""Queue Routing - Maps message types to appropriate queue channels.

This module routes messages to the correct queue based on message type and system configuration.
Queue types: THUNDER_QUEUE, EMAIL_QUEUE, WHATSAPP_QUEUE, SMS_QUEUE, SLACK_QUEUE,
APPROVAL_QUEUE, COMMISSION_QUEUE, CRM_QUEUE, DASHBOARD_QUEUE, CALENDAR_QUEUE, SIGNATURE_QUEUE
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class QueueRouter:
    """Route messages to appropriate queue channels based on message type."""

    # Message type to queue type mapping
    MESSAGE_TYPE_ROUTING = {
        # Candidate workflow messages
        "create_candidate": "CANDIDATE_QUEUE",
        "candidate_created": "THUNDER_QUEUE",
        "candidate_matched": "THUNDER_QUEUE",
        "candidate_contacted": "THUNDER_QUEUE",
        "candidate_engaged": "THUNDER_QUEUE",

        # Interview workflow messages
        "interview_scheduled": "EMAIL_QUEUE",
        "interview_completed": "EMAIL_QUEUE",
        "interview_feedback": "DASHBOARD_QUEUE",
        "interview_rescheduled": "EMAIL_QUEUE",

        # Offer workflow messages
        "offer_generated": "SIGNATURE_QUEUE",
        "offer_sent": "EMAIL_QUEUE",
        "offer_accepted": "COMMISSION_QUEUE",
        "offer_rejected": "EMAIL_QUEUE",

        # Hiring workflow messages
        "candidate_hired": "DASHBOARD_QUEUE",
        "onboarding_initiated": "EMAIL_QUEUE",
        "onboarding_completed": "DASHBOARD_QUEUE",

        # Approval workflow messages
        "approval_required": "APPROVAL_QUEUE",
        "approval_submitted": "APPROVAL_QUEUE",
        "approval_completed": "DASHBOARD_QUEUE",

        # Email and communication messages
        "email_to_send": "EMAIL_QUEUE",
        "whatsapp_to_send": "WHATSAPP_QUEUE",
        "sms_to_send": "SMS_QUEUE",
        "slack_notification": "SLACK_QUEUE",

        # Calendar and scheduling
        "calendar_event_created": "CALENDAR_QUEUE",
        "calendar_event_updated": "CALENDAR_QUEUE",
        "calendar_reminder": "CALENDAR_QUEUE",

        # CRM integration
        "sync_to_crm": "CRM_QUEUE",
        "crm_updated": "DASHBOARD_QUEUE",

        # Commission and billing
        "commission_calculated": "COMMISSION_QUEUE",
        "invoice_generated": "EMAIL_QUEUE",

        # Timesheet workflow
        "timesheet_submitted": "APPROVAL_QUEUE",
        "timesheet_approved": "DASHBOARD_QUEUE",
        "timesheet_rejected": "EMAIL_QUEUE",

        # KPI and dashboard
        "kpi_updated": "DASHBOARD_QUEUE",
        "sales_deal_created": "DASHBOARD_QUEUE",
        "sales_deal_updated": "DASHBOARD_QUEUE",

        # Default fallback
        "default": "EMAIL_QUEUE",
    }

    @staticmethod
    def get_queue_for_message(message_type: str, db: Optional[Session] = None) -> str:
        """
        Get the appropriate queue type for a message type.

        Args:
            message_type: The type of message (e.g., 'create_candidate', 'interview_scheduled')
            db: Optional database session (for future dynamic routing)

        Returns:
            Queue type (e.g., 'THUNDER_QUEUE', 'EMAIL_QUEUE')

        Raises:
            ValueError: If message_type is invalid
        """
        if not message_type:
            logger.error("Message type cannot be empty")
            raise ValueError("Message type cannot be empty")

        if not isinstance(message_type, str):
            logger.error(f"Message type must be string, got {type(message_type)}")
            raise ValueError(f"Message type must be string, got {type(message_type)}")

        # Get queue type from mapping (case-insensitive lookup)
        message_type_lower = message_type.lower().strip()
        queue_type = QueueRouter.MESSAGE_TYPE_ROUTING.get(
            message_type_lower,
            QueueRouter.MESSAGE_TYPE_ROUTING.get("default", "EMAIL_QUEUE")
        )

        logger.debug(f"Routed message type '{message_type}' to queue '{queue_type}'")
        return queue_type

    @staticmethod
    def add_custom_routing(message_type: str, queue_type: str) -> None:
        """
        Add or override a message type to queue type mapping.

        Args:
            message_type: The message type to map
            queue_type: The queue type to route to
        """
        if not message_type or not queue_type:
            raise ValueError("Both message_type and queue_type are required")

        message_type_lower = message_type.lower().strip()
        QueueRouter.MESSAGE_TYPE_ROUTING[message_type_lower] = queue_type
        logger.info(f"Added routing: {message_type_lower} → {queue_type}")

    @staticmethod
    def get_all_routing_rules() -> dict:
        """Get all current routing rules."""
        return QueueRouter.MESSAGE_TYPE_ROUTING.copy()

    @staticmethod
    def validate_queue_type(queue_type: str) -> bool:
        """
        Validate that a queue type is recognized.

        Args:
            queue_type: Queue type to validate

        Returns:
            True if queue_type is valid, False otherwise
        """
        valid_queues = {
            "CANDIDATE_QUEUE",
            "THUNDER_QUEUE",
            "EMAIL_QUEUE",
            "WHATSAPP_QUEUE",
            "SMS_QUEUE",
            "SLACK_QUEUE",
            "APPROVAL_QUEUE",
            "COMMISSION_QUEUE",
            "CRM_QUEUE",
            "DASHBOARD_QUEUE",
            "CALENDAR_QUEUE",
            "SIGNATURE_QUEUE",
        }
        return queue_type in valid_queues
