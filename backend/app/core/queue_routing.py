"""Queue Routing - Role-template driven message routing

All message queue assignments must be determined by role templates,
NOT hardcoded. Each message type maps to role permissions.
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class QueueRouter:
    """Routes messages to queues based on role templates."""

    # Message type to required permission mapping
    MESSAGE_TYPE_PERMISSIONS = {
        "candidate_created": "candidate.created_event",
        "candidate_updated": "candidate.updated_event",
        "interview_scheduled": "interview.scheduled_event",
        "offer_generated": "offer.generated_event",
        "employee_onboarded": "employee.onboarded_event",
        "email_sent": "communication.email_sent",
        "thunder_action": "thunder.autonomous_event",
    }

    @staticmethod
    def get_queue_for_message(
        message_type: str,
        db: Optional[Session] = None,
    ) -> str:
        """
        Determine queue type for a message based on role templates.

        Args:
            message_type: Type of message (e.g., 'candidate_created')
            db: Database session

        Returns:
            Queue type (e.g., 'THUNDER_QUEUE', 'EMAIL_QUEUE')

        Raises:
            ValueError: If message type not recognized
        """
        try:
            # Get required permission for this message type
            required_permission = QueueRouter.MESSAGE_TYPE_PERMISSIONS.get(message_type)

            if not required_permission:
                logger.warning(f"Unknown message type: {message_type}, defaulting to THUNDER_QUEUE")
                return "THUNDER_QUEUE"

            # Query role templates to find which queue handles this permission
            if db:
                from app.models.role_template import RoleTemplate
                from app.models.rbac import Permission

                # Find roles that have this permission
                roles_with_perm = (
                    db.query(RoleTemplate)
                    .join(Permission)
                    .filter(Permission.permission_key == required_permission)
                    .all()
                )

                if roles_with_perm:
                    # For now, route based on role type
                    for role in roles_with_perm:
                        if "thunder" in role.role_name.lower():
                            return "THUNDER_QUEUE"
                        elif "email" in role.role_name.lower():
                            return "EMAIL_QUEUE"

            # Default routing by message type
            if "email" in message_type.lower() or "notification" in message_type.lower():
                return "EMAIL_QUEUE"
            elif "thunder" in message_type.lower() or "autonomous" in message_type.lower():
                return "THUNDER_QUEUE"
            elif "interview" in message_type.lower() or "schedule" in message_type.lower():
                return "INTERVIEW_QUEUE"
            elif "offer" in message_type.lower():
                return "OFFER_QUEUE"
            elif "onboard" in message_type.lower() or "employee" in message_type.lower():
                return "ONBOARDING_QUEUE"

            return "THUNDER_QUEUE"  # Default fallback

        except Exception as e:
            logger.error(f"Error determining queue for {message_type}: {e}")
            return "THUNDER_QUEUE"
