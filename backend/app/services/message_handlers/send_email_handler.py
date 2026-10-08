"""
Email Message Handler - Processes send_email_to_candidate messages through Thunder queue.

Sends through Microsoft Graph from the HRMS mailbox (settings.THUNDER_MAILBOX).
If delivery is not possible (credentials or permission missing), raises
DeliveryDeferred: the queue keeps the message PENDING as "not sent".

Message type: send_email_to_candidate
Queue: EMAIL_QUEUE
Status flow: PENDING → PROCESSING → COMPLETED, back to PENDING when not sent, FAILED after retries
"""

import logging
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session

from fastapi import HTTPException

from app.core.config import settings
from app.core.graph_auth import GraphServiceAuth
from app.services.delivery_errors import DeliveryDeferred
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


class SendEmailHandler:
    """Handles email delivery through Thunder queue."""

    TIMEOUT_SECONDS = 30

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
            "candidate_id": "...",  # optional, for tracking + recruiter assignment
            "email_type": "OFFER|INTERVIEW|ENGAGEMENT|TEST_EMAIL|...",  # optional
            "recruiter_id": "...",  # optional - explicit recruiter to send from
            "recruiter_email": "...",  # optional - explicit recruiter email
            "cc_emails": [...]  # optional - additional CC recipients
        }

        Returns:
        {
            "status": "success|skipped|failed",
            "message_id": "external_id_from_provider",
            "method": "graph|stub",
            "recipient": "email@domain.com",
            "timestamp": "2026-09-17T15:30:00Z",
            "recruiter_id": "recruiter_assigned",
            "was_auto_assigned": bool
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
            recruiter_id = payload.get("recruiter_id")
            recruiter_email = payload.get("recruiter_email")
            cc_emails = list(payload.get("cc_emails", []))

            # Validate required fields
            if not to_email:
                raise ValueError(f"Missing to_email in message payload: {payload}")

            # ─────────────────────────────────────────────────────────────
            # RECRUITER ASSIGNMENT: Auto-assign if candidate has no recruiter
            # ─────────────────────────────────────────────────────────────
            was_auto_assigned = False

            if candidate_id and not recruiter_email:
                try:
                    from app.models.candidate import Candidate
                    from app.services.recruiter_assignment_service import RecruiterAssignmentServiceForCandidates

                    # Check if we have explicit recruiter in payload
                    if recruiter_id:
                        # Use provided recruiter
                        from app.models.user import Users
                        recruiter = db.query(Users).filter(Users.UserID == recruiter_id).first()
                        if recruiter:
                            recruiter_email = recruiter.UserEmail
                    else:
                        # Auto-assign if candidate has no recruiter
                        candidate = db.query(Candidate).filter(
                            Candidate.candidateID == candidate_id
                        ).first()

                        if candidate:
                            if candidate.assigned_recruiter_id:
                                # Use existing assignment
                                from app.models.user import Users
                                recruiter = db.query(Users).filter(
                                    Users.UserID == candidate.assigned_recruiter_id
                                ).first()
                                if recruiter:
                                    recruiter_email = recruiter.UserEmail
                                    recruiter_id = recruiter.UserID
                            else:
                                # Auto-assign new recruiter
                                try:
                                    assignment = RecruiterAssignmentServiceForCandidates.assign_recruiter_to_candidate(
                                        candidate_id, candidate.tenant_id, db
                                    )
                                    recruiter_email = assignment['recruiter_email']
                                    recruiter_id = assignment['recruiter_id']
                                    was_auto_assigned = assignment['is_new_assignment']

                                    logger.info(
                                        f"[SendEmailHandler] Auto-assigned recruiter {recruiter_id} "
                                        f"to candidate {candidate_id}"
                                    )
                                except RuntimeError as e:
                                    logger.warning(f"[SendEmailHandler] Could not auto-assign recruiter: {e}")
                except Exception as e:
                    logger.warning(f"[SendEmailHandler] Recruiter assignment failed: {e}")

            # All candidate email goes from the one HRMS mailbox (replies land where
            # Thunder reads them); recruiter assignment above is ownership only.
            sender_email = settings.THUNDER_MAILBOX
            cc_emails = [c for c in cc_emails if c and c.lower() != sender_email.lower()]

            if not GraphServiceAuth.is_configured():
                raise DeliveryDeferred(
                    "Azure Graph credentials not configured (AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET)"
                )

            logger.info(
                f"[SendEmailHandler] Sending via Graph from {sender_email}: "
                f"to={to_email}, subject={subject[:50]}..., type={email_type}"
            )
            try:
                result = EmailService.send_email(
                    to_email=to_email,
                    subject=subject,
                    body_content=body,
                    is_html=is_html,
                    sender_email=sender_email,
                    cc_emails=cc_emails or None,
                )
            except HTTPException as exc:
                if exc.status_code in (401, 403):
                    raise DeliveryDeferred(f"Graph refused send from {sender_email} (HTTP {exc.status_code}): {exc.detail}")
                raise RuntimeError(f"Email delivery failed to {to_email}: {exc.detail}") from exc

            if result.get("status") != "success":
                raise RuntimeError(f"Email delivery failed to {to_email}: {result.get('message', 'EmailService failed')}")

            logger.info(
                f"[SendEmailHandler] Email sent: to={to_email}, type={email_type}, "
                f"candidate_id={candidate_id}, from={sender_email}, cc_count={len(cc_emails)}"
            )
            return {
                "status": "success",
                "message": f"Email sent to {to_email}",
                "method": "graph",
                "recipient": to_email,
                "email_type": email_type,
                "candidate_id": candidate_id,
                "recruiter_id": recruiter_id,
                "sender_email": sender_email,
                "was_auto_assigned": was_auto_assigned,
                "cc_count": len(cc_emails),
                "timestamp": datetime.utcnow().isoformat(),
                "attachments_sent": result.get("attachments_sent", 0),
                "message_sent": True,
                "delivery_confirmed": True,
            }

        except DeliveryDeferred:
            raise
        except Exception as e:
            logger.error(f"[SendEmailHandler] Failed to send email: {e}", exc_info=True)
            raise
