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
            "candidate_id": "...",  # optional, for tracking + recruiter assignment
            "email_type": "OFFER|INTERVIEW|ENGAGEMENT|TEST_EMAIL|...",  # optional
            "recruiter_id": "...",  # optional - explicit recruiter to send from
            "recruiter_email": "...",  # optional - explicit recruiter email
            "cc_emails": [...]  # optional - additional CC recipients (helpdesk always CCed)
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
                logger.error(f"[SendEmailHandler] Missing to_email in payload: {payload}")
                return {
                    "status": "failed",
                    "error": "Missing to_email in message payload",
                    "method": "validation"
                }

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
                                    # No recruiters available - fall back to helpdesk
                                    logger.warning(
                                        f"[SendEmailHandler] Could not auto-assign recruiter: {e}. "
                                        f"Will use helpdesk as sender."
                                    )
                except Exception as e:
                    logger.warning(f"[SendEmailHandler] Recruiter assignment failed: {e}. Continuing with helpdesk.")

            # Set default sender (helpdesk) if no recruiter email determined
            if not recruiter_email:
                recruiter_email = "helpdesk_hrms@blitzenx.com"

            # Always CC helpdesk for audit trail
            if "helpdesk_hrms@blitzenx.com" not in cc_emails:
                cc_emails.append("helpdesk_hrms@blitzenx.com")

            # Check if Azure credentials are configured
            if not GraphServiceAuth.is_configured():
                # Graceful fallback: log to database instead of failing
                logger.warning(
                    f"[SendEmailHandler] Azure credentials not configured. "
                    f"Email to {to_email} logged as stub (not actually sent). "
                    f"To send real emails, configure AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET"
                )
                return {
                    "status": "skipped",
                    "reason": "Azure credentials not configured",
                    "message": f"Email to {to_email} would be sent when Azure is configured",
                    "method": "stub",
                    "recipient": to_email,
                    "email_type": email_type,
                    "timestamp": datetime.utcnow().isoformat()
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
                is_html=is_html,
                sender_email=recruiter_email,
                cc_emails=cc_emails if cc_emails else None
            )

            # EmailService returns {status, message, ...}
            if result.get("status") == "success":
                logger.info(
                    f"[SendEmailHandler] Email sent successfully: "
                    f"to={to_email}, type={email_type}, candidate_id={candidate_id}, "
                    f"from={recruiter_email}, cc_count={len(cc_emails) if cc_emails else 0}"
                )
                return {
                    "status": "success",
                    "message": f"Email sent to {to_email}",
                    "method": "graph",
                    "recipient": to_email,
                    "email_type": email_type,
                    "candidate_id": candidate_id,
                    "recruiter_id": recruiter_id,
                    "recruiter_email": recruiter_email,
                    "was_auto_assigned": was_auto_assigned,
                    "cc_count": len(cc_emails) if cc_emails else 0,
                    "timestamp": datetime.utcnow().isoformat(),
                    "attachments_sent": result.get("attachments_sent", 0),
                    "message_sent": True,
                    "delivery_confirmed": True
                }
            else:
                # EmailService failed - MUST raise exception so queue processor marks as FAILED/RETRYABLE
                error_msg = result.get("message", "EmailService failed")
                logger.error(
                    f"[SendEmailHandler] Email send failed: "
                    f"to={to_email}, reason={error_msg}"
                )
                raise RuntimeError(f"Email delivery failed to {to_email}: {error_msg}")

        except Exception as e:
            logger.error(
                f"[SendEmailHandler] Exception processing email to {to_email}: {str(e)}",
                exc_info=True
            )
            import traceback
            error_detail = f"{str(e)}\n{traceback.format_exc()}"
            return {
                "status": "failed",
                "error": str(e),
                "error_detail": error_detail,
                "method": "handler",
                "recipient": to_email,
                "timestamp": datetime.utcnow().isoformat()
            }
