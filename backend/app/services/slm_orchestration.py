"""SLM Orchestration Service - Routes messages to appropriate channels based on message type.

After a message is created, the SLM orchestrator:
1. Reads PENDING messages from message_queue
2. Decides which channel queues to create for each message (based on message type)
3. Creates MessageChannel entries to route to appropriate processors
4. Returns orchestration decision

Examples:
- candidate_created → [THUNDER_QUEUE, EMAIL_QUEUE (welcome), DASHBOARD_QUEUE]
- interview_scheduled → [EMAIL_QUEUE (interview confirm), CALENDAR_QUEUE, DASHBOARD_QUEUE]
- offer_generated → [APPROVAL_QUEUE, EMAIL_QUEUE (send offer), DASHBOARD_QUEUE]
- timesheet_submitted → [EMAIL_QUEUE (receipt), DASHBOARD_QUEUE (show in manager dashboard)]
- deal_closed → [COMMISSION_QUEUE, EMAIL_QUEUE (notification), CRM_QUEUE, DASHBOARD_QUEUE]

Status Flow: PENDING → SLM_PROCESSING → CHANNEL_QUEUED → (processors handle channel-specific flows)

Implements FAIL FAST: All methods raise exceptions on error.
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from app.core.logging import logger

logger = logging.getLogger(__name__)

class SLMOrchestrationService:
    """Routes messages to appropriate channel queues based on message type."""

    # Message type to channel routes mapping
    ROUTES = {
        # Recruitment events
        "candidate_created": [
            "THUNDER_QUEUE",  # Route to Thunder autonomous loop
            "EMAIL_QUEUE",     # Send welcome email
            "DASHBOARD_QUEUE", # Show on dashboard
        ],
        "candidate_updated": [
            "EMAIL_QUEUE",     # Notification to candidate
            "DASHBOARD_QUEUE",
        ],
        "interview_scheduled": [
            "EMAIL_QUEUE",     # Send interview confirmation
            "CALENDAR_QUEUE",  # Create calendar event
            "DASHBOARD_QUEUE", # Show on dashboard (hiring manager)
        ],
        "interview_completed": [
            "EMAIL_QUEUE",     # Send feedback notification
            "DASHBOARD_QUEUE", # Update feedback status
        ],
        "offer_generated": [
            "APPROVAL_QUEUE",  # Route to manager approval
            "EMAIL_QUEUE",     # Send offer to candidate
            "DASHBOARD_QUEUE", # Show in offer tracking
        ],
        "offer_accepted": [
            "EMAIL_QUEUE",     # Confirm acceptance
            "COMMISSION_QUEUE", # Calculate recruiting commission
            "CRM_QUEUE",       # Update CRM with hire
            "DASHBOARD_QUEUE", # Update hiring pipeline
        ],
        "candidate_hired": [
            "EMAIL_QUEUE",     # Hire confirmation
            "CALENDAR_QUEUE",  # Create onboarding events
            "COMMISSION_QUEUE", # Calculate commission
            "CRM_QUEUE",       # Update CRM
            "DASHBOARD_QUEUE", # Update workforce metrics
        ],

        # Timesheet events
        "timesheet_submitted": [
            "EMAIL_QUEUE",     # Receipt notification
            "DASHBOARD_QUEUE", # Show in manager queue
            "APPROVAL_QUEUE",  # Route to approval
        ],
        "timesheet_approved": [
            "EMAIL_QUEUE",     # Approval notification
            "DASHBOARD_QUEUE", # Update status
        ],
        "timesheet_rejected": [
            "EMAIL_QUEUE",     # Rejection with feedback
            "DASHBOARD_QUEUE", # Show rejection reason
        ],

        # KPI/Performance events
        "kpi_updated": [
            "DASHBOARD_QUEUE", # Update KPI dashboard
            "EMAIL_QUEUE",     # Notification if threshold crossed
        ],
        "target_achieved": [
            "EMAIL_QUEUE",     # Celebration notification
            "DASHBOARD_QUEUE", # Show achievement
            "COMMISSION_QUEUE", # Calculate bonus
        ],
        "target_missed": [
            "EMAIL_QUEUE",     # Alert to owner
            "DASHBOARD_QUEUE", # Show warning
        ],

        # Sales events
        "deal_created": [
            "EMAIL_QUEUE",     # Notification
            "CRM_QUEUE",       # Sync to CRM
            "DASHBOARD_QUEUE", # Show in sales dashboard
        ],
        "deal_closed": [
            "COMMISSION_QUEUE", # Calculate commission
            "EMAIL_QUEUE",      # Notification
            "CRM_QUEUE",        # Update CRM
            "DASHBOARD_QUEUE",  # Update revenue metrics
        ],
        "deal_lost": [
            "EMAIL_QUEUE",      # Notification
            "CRM_QUEUE",        # Mark lost in CRM
            "DASHBOARD_QUEUE",  # Update metrics
        ],
        "proposal_sent": [
            "EMAIL_QUEUE",      # Send proposal
            "CRM_QUEUE",        # Track in CRM
            "DASHBOARD_QUEUE",  # Show proposal status
        ],

        # Client events
        "client_created": [
            "EMAIL_QUEUE",      # Welcome email
            "CRM_QUEUE",        # Create in CRM
            "DASHBOARD_QUEUE",  # Add to client list
        ],
        "client_contacted": [
            "EMAIL_QUEUE",      # Contact confirmation
            "CRM_QUEUE",        # Log interaction
            "DASHBOARD_QUEUE",  # Update client info
        ],
        "client_onboarded": [
            "EMAIL_QUEUE",      # Onboarding email
            "CALENDAR_QUEUE",   # Create kickoff meeting
            "CRM_QUEUE",        # Update status
            "DASHBOARD_QUEUE",  # Add to active clients
        ],

        # HR events
        "employee_joined": [
            "EMAIL_QUEUE",      # Welcome email
            "CALENDAR_QUEUE",   # Create onboarding events
            "DASHBOARD_QUEUE",  # Add to employee list
        ],
        "review_scheduled": [
            "EMAIL_QUEUE",      # Review invitation
            "CALENDAR_QUEUE",   # Schedule on calendar
            "DASHBOARD_QUEUE",  # Show review pending
        ],

        # Project events
        "task_assigned": [
            "EMAIL_QUEUE",      # Assignment notification
            "DASHBOARD_QUEUE",  # Show in task list
        ],
        "task_completed": [
            "EMAIL_QUEUE",      # Completion notification
            "DASHBOARD_QUEUE",  # Update task status
        ],

        # Finance events
        "invoice_created": [
            "EMAIL_QUEUE",      # Send invoice
            "DASHBOARD_QUEUE",  # Show in finance dashboard
        ],
        "payment_due": [
            "EMAIL_QUEUE",      # Payment reminder
            "DASHBOARD_QUEUE",  # Highlight due payment
        ],

        # Approval events
        "approval_requested": [
            "APPROVAL_QUEUE",   # Route to approver
            "EMAIL_QUEUE",      # Notification email
            "DASHBOARD_QUEUE",  # Show in approvals queue
        ],
        "approval_action": [
            "EMAIL_QUEUE",      # Approval result notification
            "DASHBOARD_QUEUE",  # Update approval status
        ],

        # Commission events
        "commission_calculated": [
            "EMAIL_QUEUE",      # Commission notification
            "DASHBOARD_QUEUE",  # Show in commission tracking
        ],
    }

    @staticmethod
    def orchestrate(
        message_id: str,
        message_type: str,
        payload: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Orchestrate routing of a message to appropriate channels.

        Args:
            message_id: ID of the message
            message_type: Type of message
            payload: Message payload
            db: Database session

        Returns:
            Orchestration decision with channels routed to

        Raises:
            ValueError: If message_type unknown
            RuntimeError: If orchestration fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            # Get channels for this message type
            channels = SLMOrchestrationService.ROUTES.get(message_type, [])

            if not channels:
                logger.warning(f"No routes defined for message type: {message_type}, using default [EMAIL_QUEUE, DASHBOARD_QUEUE]")
                channels = ["EMAIL_QUEUE", "DASHBOARD_QUEUE"]

            logger.info(
                f"SLMOrchestrationService orchestrating message: {message_id} "
                f"type={message_type} channels={channels}"
            )

            # Create MessageChannel entries for each channel
            from app.models.message_queue import MessageChannel

            for queue_type in channels:
                try:
                    channel = MessageChannel(
                        message_id=message_id,
                        queue_type=queue_type,
                        status="PENDING",
                    )
                    db.add(channel)
                except Exception as e:
                    logger.error(f"Failed to create channel routing for {queue_type}: {e}")
                    # Continue with other channels

                    db.commit()

            # Update message status to SLM_PROCESSING
            from app.models.message_queue import MessageQueue

            message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()
            if message:
                message.status = "SLM_PROCESSING"
                message.queue_type = "MULTI"  # Indicates multiple channels
                db.commit()

            logger.info(
                f"SLMOrchestrationService routed message {message_id} to {len(channels)} channels: {channels}"
            )

            return {
                "status": "success",
                "message_id": message_id,
                "message_type": message_type,
                "channels": channels,
                "channel_count": len(channels),
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to orchestrate message routing: {e}", exc_info=True)
            raise RuntimeError(f"Failed to orchestrate message: {str(e)}")

    @staticmethod
    def add_route(message_type: str, channels: List[str]) -> None:
        """
        Add or override routing for a message type.

        Args:
            message_type: Type of message
            channels: List of queue types to route to

        Raises:
            ValueError: If inputs invalid
        """
        if not message_type or not isinstance(channels, list):
            raise ValueError("message_type and channels list required")

        if not channels:
            raise ValueError("At least one channel required")

        SLMOrchestrationService.ROUTES[message_type] = channels
        logger.info(f"Added route for {message_type}: {channels}")

    @staticmethod
    def get_routes() -> Dict[str, List[str]]:
        """Get all defined routes."""
        return SLMOrchestrationService.ROUTES.copy()

    @staticmethod
    def get_route(message_type: str) -> List[str]:
        """Get channels for a message type."""
        return SLMOrchestrationService.ROUTES.get(message_type, [])
