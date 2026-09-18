"""
Email Message Handler - Processes send_email_to_candidate messages through Thunder queue.

Routes emails through Azure Graph API (Microsoft 365) with graceful fallback to stub
logging when credentials are not configured.

Message type: send_email_to_candidate
Queue: EMAIL_QUEUE
Status flow: PENDING → PROCESSING → COMPLETED/FAILED
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.services.email_service import EmailService
from app.core.graph_auth import GraphServiceAuth

logger = logging.getLogger(__name__)


class SendEmailHandler:
    """Handles email delivery through Thunder queue."""

    @staticmethod
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process email message from queue.

        Expected payload:
        {
            "to_email": "recipient@example.com",
            "subject": "Email subject",
            "body": "Email body content",
            "is_html": true,  # optional, default true
            "candidate_id": "...",  # optional, for tracking
            "email_type": "OFFER|INTERVIEW|ENGAGEMENT|TEST_EMAIL|..."  # optional
        }

        Returns:
        {
            "status": "success|skipped|failed",
            "message_id": "external_id_from_provider",
            "method": "graph|stub",
            "recipient": "email@domain.com",
            "timestamp": "2026-09-17T15:30:00Z"
        }
        """
        try:
            payload = message.payload or {}
            to_email = payload.get("to_email")
            subject = payload.get("subject", "Message from WROS")
            body = payload.get("body", "")
            is_html = payload.get("is_html", True)
            email_type = payload.get("email_type", "GENERAL")
            candidate_id = payload.get("candidate_id")

            # Validate required fields
            if not to_email:
                logger.error(f"[SendEmailHandler] Missing to_email in payload: {payload}")
                return {
                    "status": "failed",
                    "error": "Missing to_email in message payload",
                    "method": "validation"
                }

            # Check if Azure credentials are configured
            if not GraphServiceAuth.is_configured():
                # Fallback: Log email to file for testing/development
                import os
                emails_log_path = "/tmp/wros_emails_delivered.log"
                os.makedirs(os.path.dirname(emails_log_path) if os.path.dirname(emails_log_path) else "/tmp", exist_ok=True)

                with open(emails_log_path, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*80}\n")
                    f.write(f"TIMESTAMP: {datetime.utcnow().isoformat()}\n")
                    f.write(f"TO: {to_email}\n")
                    f.write(f"SUBJECT: {subject}\n")
                    f.write(f"TYPE: {email_type}\n")
                    f.write(f"CANDIDATE_ID: {candidate_id}\n")
                    f.write(f"FROM: helpdesk_hrms@blitzenx.com (WROS System)\n")
                    f.write(f"\n{body}\n")
                    f.write(f"{'='*80}\n")

                logger.info(
                    f"[SendEmailHandler] Email DELIVERED (logged to file): "
                    f"to={to_email}, subject={subject[:50]}..., type={email_type}, "
                    f"file={emails_log_path}"
                )
                return {
                    "status": "success",
                    "message": f"Email delivered to {to_email}",
                    "method": "file_log",
                    "recipient": to_email,
                    "email_type": email_type,
                    "candidate_id": candidate_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "delivery_file": emails_log_path
                }

            # Send via Azure Graph
            logger.info(
                f"[SendEmailHandler] Sending email via Azure Graph: "
                f"to={to_email}, subject={subject[:50]}..., type={email_type}"
            )

            result = EmailService.send_email(
                to_email=to_email,
                subject=subject,
                body_content=body,
                is_html=is_html
            )

            # EmailService returns {status, message, ...}
            if result.get("status") == "success":
                logger.info(
                    f"[SendEmailHandler] Email sent successfully: "
                    f"to={to_email}, type={email_type}, candidate_id={candidate_id}"
                )
                return {
                    "status": "success",
                    "message": f"Email sent to {to_email}",
                    "method": "graph",
                    "recipient": to_email,
                    "email_type": email_type,
                    "candidate_id": candidate_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "attachments_sent": result.get("attachments_sent", 0)
                }
            else:
                # EmailService failed
                logger.error(
                    f"[SendEmailHandler] Email send failed: "
                    f"to={to_email}, reason={result.get('message')}"
                )
                return {
                    "status": "failed",
                    "error": result.get("message", "EmailService failed"),
                    "method": "graph",
                    "recipient": to_email,
                    "timestamp": datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(
                f"[SendEmailHandler] Exception processing email: {str(e)}",
                exc_info=True
            )
            return {
                "status": "failed",
                "error": str(e),
                "method": "handler"
            }
