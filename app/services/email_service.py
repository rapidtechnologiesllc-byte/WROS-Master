import base64
import requests
from typing import List, Optional, Dict, Any
from fastapi import HTTPException
from app.core.graph_auth import get_graph_token
from app.core.logging import logger


class EmailService:
    """
    Production email service for HRMS.
    Sends all system emails from the helpdesk_hrms@blitzenx.com service mailbox
    using Microsoft Graph API (Application permissions — no user sign-in required).
    """

    SERVICE_EMAIL = "helpdesk_hrms@blitzenx.com"
    SERVICE_NAME = "BlitzenX HRMS"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_token() -> str:
        return get_graph_token()

    @staticmethod
    def _graph_post(endpoint: str, payload: Dict, access_token: str) -> requests.Response:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        response = requests.post(endpoint, headers=headers, json=payload, timeout=15)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            detail = "Unknown error"
            try:
                detail = e.response.json().get("error", {}).get("message", str(e))
            except Exception:
                detail = str(e)
            raise HTTPException(status_code=502, detail=f"Microsoft Graph error: {detail}")
        return response

    # ------------------------------------------------------------------
    # HTML templates
    # ------------------------------------------------------------------

    @staticmethod
    def _base_html(title: str, body_inner: str) -> str:
        return f"""
        <html><body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:30px 0;">
          <tr><td align="center">
            <table width="600" cellpadding="0" cellspacing="0"
                   style="background:#ffffff;border-radius:8px;overflow:hidden;
                          box-shadow:0 2px 8px rgba(0,0,0,0.08);">
              <!-- Header -->
              <tr><td style="background:#1a56db;padding:28px 32px;">
                <p style="margin:0;color:#ffffff;font-size:22px;font-weight:700;">
                  {EmailService.SERVICE_NAME}
                </p>
                <p style="margin:6px 0 0;color:#bfdbfe;font-size:13px;">{title}</p>
              </td></tr>
              <!-- Body -->
              <tr><td style="padding:32px;">
                {body_inner}
              </td></tr>
              <!-- Footer -->
              <tr><td style="background:#f9fafb;padding:16px 32px;border-top:1px solid #e5e7eb;">
                <p style="margin:0;color:#9ca3af;font-size:12px;">
                  This is an automated message from BlitzenX HRMS.
                  Please do not reply to this email.
                </p>
              </td></tr>
            </table>
          </td></tr>
        </table>
        </body></html>
        """

    @staticmethod
    def _interview_invite_html(
        candidate_name: str,
        round_name: str,
        start_time: str,
        end_time: str,
        join_url: Optional[str],
        extra_notes: str = "",
    ) -> str:
        join_section = ""
        if join_url:
            join_section = f"""
            <tr><td style="padding:8px 0;">
              <p style="margin:0;font-size:14px;color:#374151;"><strong>Teams Link:</strong>
                <a href="{join_url}" style="color:#1a56db;">Join Interview</a>
              </p>
            </td></tr>"""

        notes_section = ""
        if extra_notes:
            notes_section = f"""
            <tr><td style="padding:16px 0 0;">
              <p style="margin:0;font-size:14px;color:#374151;"><strong>Notes:</strong></p>
              <p style="margin:6px 0 0;font-size:14px;color:#6b7280;">{extra_notes}</p>
            </td></tr>"""

        body = f"""
        <p style="font-size:16px;color:#111827;margin:0 0 16px;">
          Dear <strong>{candidate_name}</strong>,
        </p>
        <p style="font-size:14px;color:#374151;line-height:1.6;">
          You have been scheduled for an interview. Please find the details below:
        </p>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="background:#f0f4ff;border-radius:6px;padding:16px;margin:16px 0;">
          <tr><td style="padding:8px 0;">
            <p style="margin:0;font-size:14px;color:#374151;">
              <strong>Round:</strong> {round_name}
            </p>
          </td></tr>
          <tr><td style="padding:8px 0;">
            <p style="margin:0;font-size:14px;color:#374151;">
              <strong>Start:</strong> {start_time}
            </p>
          </td></tr>
          <tr><td style="padding:8px 0;">
            <p style="margin:0;font-size:14px;color:#374151;">
              <strong>End:</strong> {end_time}
            </p>
          </td></tr>
          {join_section}
          {notes_section}
        </table>
        <p style="font-size:14px;color:#374151;line-height:1.6;">
          Please ensure you are available at the scheduled time. If you have any
          questions, contact our HR team.
        </p>
        <p style="font-size:14px;color:#374151;margin-top:24px;">
          Best regards,<br/><strong>BlitzenX HR Team</strong>
        </p>
        """
        return EmailService._base_html("Interview Invitation", body)

    @staticmethod
    def _generic_notification_html(heading: str, message: str) -> str:
        body = f"""
        <p style="font-size:16px;color:#111827;margin:0 0 12px;">
          <strong>{heading}</strong>
        </p>
        <p style="font-size:14px;color:#374151;line-height:1.8;">{message}</p>
        <p style="font-size:14px;color:#374151;margin-top:24px;">
          Best regards,<br/><strong>BlitzenX HR Team</strong>
        </p>
        """
        return EmailService._base_html(heading, body)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def send_email(
        cls,
        to_email: str,
        subject: str,
        body_content: str,
        is_html: bool = True,
        sender_email: str = None,
        cc_emails: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Send a plain or HTML email from the HRMS service mailbox.

        attachments: optional list of dicts with keys —
            name         (str)   filename shown to recipient
            content      (bytes) raw file bytes
            content_type (str)   MIME type, e.g. "application/pdf"
        """
        sender = sender_email or cls.SERVICE_EMAIL
        try:
            token = cls._get_token()

            to_recipients = [{"emailAddress": {"address": to_email}}]
            cc_recipients = [{"emailAddress": {"address": e}} for e in (cc_emails or [])]

            # Build message object first so attachments can be injected into it
            message: Dict[str, Any] = {
                "subject": subject,
                "body": {
                    "contentType": "HTML" if is_html else "Text",
                    "content": body_content,
                },
                "toRecipients": to_recipients,
            }

            if cc_recipients:
                message["ccRecipients"] = cc_recipients

            # ── Attachments ─────────────────────────────────────────────────
            # Files are base64-encoded and embedded inline in the message payload.
            # Microsoft Graph limit for inline attachments is ~3 MB total.
            if attachments:
                message["attachments"] = [
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": att["name"],
                        "contentType": att.get("content_type", "application/octet-stream"),
                        "contentBytes": base64.b64encode(att["content"]).decode("utf-8"),
                    }
                    for att in attachments
                ]
                logger.info(
                    f"[EmailService] Attaching {len(attachments)} file(s): "
                    f"{[a['name'] for a in attachments]}"
                )

            payload: Dict[str, Any] = {
                "message": message,       # message now contains attachments if any
                "saveToSentItems": "true",
            }

            cls._graph_post(
                f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail",
                payload,
                token,
            )

            att_count = len(attachments) if attachments else 0
            logger.info(
                f"[EmailService] Sent -> {to_email} | Subject: {subject} | Attachments: {att_count}"
            )
            return {
                "status": "success",
                "message": f"Email sent to {to_email}",
                "attachments_sent": att_count,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[EmailService] Unexpected error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @classmethod
    def send_notification(
        cls,
        to_email: str,
        heading: str,
        message: str,
        cc_emails: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Send a styled HTML notification email (general purpose).
        """
        html = cls._generic_notification_html(heading, message)
        return cls.send_email(
            to_email=to_email,
            subject=heading,
            body_content=html,
            is_html=True,
            cc_emails=cc_emails,
        )

    @classmethod
    def send_interview_invite(
        cls,
        candidate_email: str,
        candidate_name: str,
        round_name: str,
        start_time_iso: str,
        end_time_iso: str,
        interviewer_emails: List[str],
        extra_notes: str = "",
        timezone: str = "Asia/Kolkata",
        create_teams_event: bool = True,
    ) -> Dict[str, Any]:
        """
        Full interview invitation flow:
        1. Create a Teams calendar event via Graph (organiser = service mailbox).
        2. Send a styled HTML email invitation to the candidate (+ interviewers as CC).

        Returns event details including the Teams join URL.
        """
        try:
            token = cls._get_token()

            # Step 1: Create calendar event
            all_attendees = [candidate_email] + interviewer_emails
            attendees_payload = [
                {"emailAddress": {"address": e}, "type": "required"}
                for e in all_attendees
            ]

            event_payload: Dict[str, Any] = {
                "subject": f"Interview - {round_name} | {candidate_name}",
                "body": {
                    "contentType": "HTML",
                    "content": cls._interview_invite_html(
                        candidate_name, round_name,
                        start_time_iso, end_time_iso,
                        join_url=None,
                        extra_notes=extra_notes,
                    ),
                },
                "start": {"dateTime": start_time_iso, "timeZone": timezone},
                "end":   {"dateTime": end_time_iso,   "timeZone": timezone},
                "attendees": attendees_payload,
            }

            join_url = None
            event_id = None
            web_link = None

            if create_teams_event:
                event_payload["isOnlineMeeting"] = True
                event_payload["onlineMeetingProvider"] = "teamsForBusiness"

                resp = cls._graph_post(
                    f"https://graph.microsoft.com/v1.0/users/{cls.SERVICE_EMAIL}/events",
                    event_payload,
                    token,
                )
                event_data = resp.json()
                event_id = event_data.get("id")
                web_link = event_data.get("webLink")
                if event_data.get("onlineMeeting"):
                    join_url = event_data["onlineMeeting"].get("joinUrl")

                logger.info(
                    f"[EmailService] Calendar event created. ID={event_id} | Teams={join_url is not None}"
                )

            # Step 2: Send styled email to candidate
            email_html = cls._interview_invite_html(
                candidate_name, round_name,
                start_time_iso, end_time_iso,
                join_url=join_url,
                extra_notes=extra_notes,
            )
            cls.send_email(
                to_email=candidate_email,
                subject=f"Interview Invitation - {round_name} | {candidate_name}",
                body_content=email_html,
                is_html=True,
                cc_emails=interviewer_emails,
            )

            logger.info(
                f"[EmailService] Interview invite sent to {candidate_email} | Round: {round_name}"
            )
            return {
                "status": "success",
                "message": "Interview invite sent and calendar event created.",
                "eventId": event_id,
                "joinUrl": join_url,
                "webLink": web_link,
                "emailSentTo": candidate_email,
                "ccRecipients": interviewer_emails,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[EmailService] send_interview_invite error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
