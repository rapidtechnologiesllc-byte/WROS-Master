"""Inbound Message Handler - Process incoming candidate responses via email/WhatsApp

Handles:
- Inbound email responses from candidates
- Inbound WhatsApp messages from candidates
- Updates candidate profile with response data
- Tracks candidate engagement
"""
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime

logger = logging.getLogger(__name__)


class InboundMessageHandler:
    """Handle incoming candidate messages"""

    @staticmethod
    def handle_email_response(
        sender_email: str,
        subject: str,
        body: str,
        db: Session,
    ) -> bool:
        """
        Process incoming email response from candidate.

        Args:
            sender_email: Candidate's email address
            subject: Email subject
            body: Email body text
            db: Database session

        Returns:
            True if processed successfully
        """
        try:
            from app.models.candidates import Candidates
            from app.models.channel_queue import ChannelQueueItem

            logger.info(f"Processing inbound email from {sender_email}")

            # Find candidate by email
            candidate = db.query(Candidates).filter(
                Candidates.email == sender_email
            ).first()

            if not candidate:
                logger.warning(f"Candidate not found for email: {sender_email}")
                return False

            # Log the email response in candidate engagement
            logger.info(
                f"Recorded email response from candidate {candidate.id} ({sender_email}): "
                f"subject={subject[:50]}..."
            )

            # Update candidate's last_contact timestamp
            candidate.last_contacted_at = datetime.utcnow()
            candidate.engagement_status = "responded_email"

            # Store response data
            if not candidate.custom_fields:
                candidate.custom_fields = {}

            candidate.custom_fields["last_email_response"] = {
                "timestamp": datetime.utcnow().isoformat(),
                "subject": subject,
                "body": body[:500],  # Store first 500 chars
                "sender": sender_email,
            }

            db.commit()
            logger.info(f"Updated candidate {candidate.id} with email response")
            return True

        except Exception as e:
            logger.error(f"Failed to process email response from {sender_email}: {e}", exc_info=True)
            db.rollback()
            return False

    @staticmethod
    def handle_whatsapp_response(
        phone_number: str,
        message_text: str,
        db: Session,
    ) -> bool:
        """
        Process incoming WhatsApp message from candidate.

        Args:
            phone_number: Candidate's WhatsApp phone number
            message_text: Message content
            db: Database session

        Returns:
            True if processed successfully
        """
        try:
            from app.models.candidates import Candidates

            logger.info(f"Processing inbound WhatsApp from {phone_number}")

            # Find candidate by phone
            candidate = db.query(Candidates).filter(
                Candidates.mobile == phone_number
            ).first()

            if not candidate:
                logger.warning(f"Candidate not found for phone: {phone_number}")
                return False

            # Log the WhatsApp response in candidate engagement
            logger.info(
                f"Recorded WhatsApp response from candidate {candidate.id} ({phone_number}): "
                f"{message_text[:50]}..."
            )

            # Update candidate's last_contact timestamp
            candidate.last_contacted_at = datetime.utcnow()
            candidate.engagement_status = "responded_whatsapp"

            # Store response data
            if not candidate.custom_fields:
                candidate.custom_fields = {}

            candidate.custom_fields["last_whatsapp_response"] = {
                "timestamp": datetime.utcnow().isoformat(),
                "message": message_text[:500],  # Store first 500 chars
                "phone": phone_number,
            }

            db.commit()
            logger.info(f"Updated candidate {candidate.id} with WhatsApp response")
            return True

        except Exception as e:
            logger.error(f"Failed to process WhatsApp response from {phone_number}: {e}", exc_info=True)
            db.rollback()
            return False
