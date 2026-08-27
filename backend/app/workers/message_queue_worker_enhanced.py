"""
Enhanced Message Queue Worker with Doctor Agent Integration

Example worker showing how to integrate Doctor Agent for self-healing.

Flow:
1. Worker processes message operation
2. On failure, Doctor Agent activates
3. Doctor tries fix strategies (SMS, data correction, retry)
4. At attempt 3, Doctor escalates to WROS ticket
5. Worker marks message as RESOLVED or ESCALATED

Usage:
    from app.workers.message_queue_worker_enhanced import process_queued_message

    # In your background job:
    for message in get_pending_messages():
        result = process_queued_message(db, message)
        if result["status"] == "resolved":
            # Success!
        elif result["status"] == "escalated_to_wros":
            # Check WROS ticket for manual resolution

Integration Points:
- Message queue table (customize schema as needed)
- Message operation handler (send_email, send_sms, etc.)
- WROS ticketing system (uses create_ticket from ticket_service)
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.services.doctor_service import DoctorService


# Message operation handlers - customize as needed
class MessageOperationHandler:
    """Handlers for different message types"""

    @staticmethod
    def send_email(db: Session, message_data: Dict) -> bool:
        """Send email - customize with your email service"""
        # Example implementation
        recipient = message_data.get("recipient")
        subject = message_data.get("subject")
        body = message_data.get("body")

        # TODO: Call your email service
        # result = email_service.send(recipient, subject, body)
        # return result.success

        logger.info(f"[MessageQueue] Sending email to {recipient}")
        return True

    @staticmethod
    def send_sms(db: Session, message_data: Dict) -> bool:
        """Send SMS - customize with your SMS service"""
        # Example implementation
        phone = message_data.get("phone")
        text = message_data.get("text")

        # TODO: Call your SMS service
        # result = sms_service.send(phone, text)
        # return result.success

        logger.info(f"[MessageQueue] Sending SMS to {phone}")
        return True

    @staticmethod
    def send_notification(db: Session, message_data: Dict) -> bool:
        """Send in-app notification"""
        # Example implementation
        user_id = message_data.get("user_id")
        title = message_data.get("title")

        # TODO: Save notification to database
        # notification = Notification(user_id=user_id, title=title)
        # db.add(notification)
        # db.commit()

        logger.info(f"[MessageQueue] Sending notification to user {user_id}")
        return True

    @staticmethod
    def schedule_interview(db: Session, message_data: Dict) -> bool:
        """Schedule interview with Calendly/Outlook integration"""
        # Example implementation
        candidate_id = message_data.get("candidate_id")
        job_id = message_data.get("job_id")
        datetime_str = message_data.get("datetime")

        # TODO: Call calendar service
        # result = calendar_service.schedule(candidate_id, job_id, datetime_str)
        # return result.success

        logger.info(f"[MessageQueue] Scheduling interview for candidate {candidate_id}")
        return True


def process_queued_message(
    db: Session,
    message_id: str,
    message_data: Dict[str, Any],
    message_type: str,
    max_doctor_attempts: int = 3,
    created_by_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process a single queued message with Doctor Agent integration.

    Args:
        db: Database session
        message_id: Unique message identifier
        message_data: Message payload (recipient, subject, body, etc.)
        message_type: Type of message (SEND_EMAIL, SEND_SMS, SCHEDULE_INTERVIEW, etc.)
        max_doctor_attempts: Max attempts before escalating to WROS (default 3)
        created_by_user_id: User who created the message

    Returns:
        {
            "status": "resolved" | "escalated_to_wros" | "error",
            "message_id": "...",
            "message_type": "...",
            "attempts": 1-3,
            "ticket_id": 123 (if escalated),
            "error": "..." (if error)
        }
    """
    logger.info(f"[MessageQueue] Processing message {message_id} (type: {message_type})")

    # Step 1: Try to execute the message operation
    try:
        result = _execute_message_operation(db, message_type, message_data)

        if result:
            logger.info(f"[MessageQueue] ✓ Message {message_id} delivered successfully")
            return {
                "status": "resolved",
                "message_id": message_id,
                "message_type": message_type,
                "attempts": 1,
            }

    except Exception as e:
        logger.warning(f"[MessageQueue] ✗ Message {message_id} failed: {e}")
        error_str = str(e)

    # Step 2: Doctor Agent activates on failure
    doctor = DoctorService(db)

    # Add message type to payload for WROS escalation
    message_data_with_type = {
        **message_data,
        "message_type": message_type,
        "resource_id": message_data.get("resource_id", "unknown"),
    }

    # Doctor handles failure (try strategies, escalate if needed)
    resolved = doctor.handle_failure(
        message_id=message_id,
        message_data=message_data_with_type,
        error=error_str,
        max_attempts_before_escalate=max_doctor_attempts,
        created_by_user_id=created_by_user_id,
    )

    if resolved:
        logger.info(f"[MessageQueue] ✓ Message {message_id} healed by Doctor Agent")
        return {
            "status": "resolved",
            "message_id": message_id,
            "message_type": message_type,
            "attempts": max_doctor_attempts,
        }
    else:
        # Doctor exhausted all strategies - get traces for response
        traces = doctor.get_traces_for_message(message_id)
        ticket_id = next((t.ticket_id for t in traces if t.ticket_id), None)

        logger.error(
            f"[MessageQueue] ✗ Message {message_id} escalated to WROS (Ticket #{ticket_id})"
        )
        return {
            "status": "escalated_to_wros",
            "message_id": message_id,
            "message_type": message_type,
            "attempts": len(traces),
            "ticket_id": ticket_id,
        }


def _execute_message_operation(db: Session, message_type: str, message_data: Dict) -> bool:
    """
    Execute the actual message operation.

    Dispatches to appropriate handler based on message_type.

    Args:
        db: Database session
        message_type: Type of operation (SEND_EMAIL, SEND_SMS, etc.)
        message_data: Operation parameters

    Returns:
        bool: True if successful, False if failed
        Raises: Exception with error details if failed

    Raises:
        ValueError: If message_type not recognized
    """
    handler_map = {
        "SEND_EMAIL": MessageOperationHandler.send_email,
        "SEND_SMS": MessageOperationHandler.send_sms,
        "SEND_NOTIFICATION": MessageOperationHandler.send_notification,
        "SCHEDULE_INTERVIEW": MessageOperationHandler.schedule_interview,
    }

    handler = handler_map.get(message_type)
    if not handler:
        raise ValueError(f"Unknown message type: {message_type}")

    # Call handler - must return True/False or raise exception
    return handler(db, message_data)


# Scheduler integration example
def run_message_queue_worker_cycle(db: Session) -> dict:
    """
    Run one cycle of the message queue worker.

    Called by APScheduler every 5 minutes (or on-demand).

    Returns:
        {
            "processed": 10,
            "resolved": 9,
            "escalated": 1,
            "errors": 0
        }
    """
    logger.info("[MessageQueue] Starting worker cycle")

    try:
        # TODO: Query your message queue table
        # pending_messages = db.query(MessageQueue).filter(
        #     MessageQueue.status.in_(["PENDING", "RETRYING"])
        # ).limit(50).all()

        # For demo - show the pattern
        pending_messages = []

        processed = 0
        resolved = 0
        escalated = 0
        errors = 0

        for message in pending_messages:
            try:
                result = process_queued_message(
                    db,
                    message_id=message.get("id"),
                    message_data=message.get("data"),
                    message_type=message.get("type"),
                    created_by_user_id=message.get("created_by"),
                )

                processed += 1
                if result["status"] == "resolved":
                    resolved += 1
                    # TODO: Update message queue status to DELIVERED
                elif result["status"] == "escalated_to_wros":
                    escalated += 1
                    # TODO: Update message queue status to ESCALATED

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                errors += 1

        logger.info(
            f"[MessageQueue] Cycle complete: "
            f"processed={processed}, resolved={resolved}, escalated={escalated}, errors={errors}"
        )

        return {
            "processed": processed,
            "resolved": resolved,
            "escalated": escalated,
            "errors": errors,
        }

    except Exception as e:
        logger.error(f"[MessageQueue] Worker cycle error: {e}", exc_info=True)
        return {
            "processed": 0,
            "resolved": 0,
            "escalated": 0,
            "errors": 1,
        }
