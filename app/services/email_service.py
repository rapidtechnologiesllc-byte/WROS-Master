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

    # ------------------------------------------------------------------
    # Login Credentials Email
    # ------------------------------------------------------------------

    @staticmethod
    def _login_credentials_html(
        candidate_name: str,
        login_email: str,
        password: str,
        portal_link: str,
    ) -> str:
        body = f"""
        <p style="font-size:16px;color:#111827;margin:0 0 16px;">
          Dear <strong>{candidate_name}</strong>,
        </p>
        <p style="font-size:14px;color:#374151;line-height:1.6;">
          Welcome to <strong>BlitzenX HRMS</strong>! Your onboarding account has been created.
          Please use the credentials below to access the candidate portal.
        </p>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="background:#f0f4ff;border-radius:6px;padding:16px;margin:16px 0;">
          <tr><td style="padding:8px 0;">
            <p style="margin:0;font-size:14px;color:#374151;">
              <strong>Portal:</strong>
              <a href="{portal_link}" style="color:#1a56db;">{portal_link}</a>
            </p>
          </td></tr>
          <tr><td style="padding:8px 0;">
            <p style="margin:0;font-size:14px;color:#374151;">
              <strong>Login Email:</strong> {login_email}
            </p>
          </td></tr>
          <tr><td style="padding:8px 0;">
            <p style="margin:0;font-size:14px;color:#374151;">
              <strong>Password:</strong>
              <span style="font-family:monospace;background:#e0e7ff;padding:2px 8px;
                           border-radius:4px;letter-spacing:0.05em;">{password}</span>
            </p>
          </td></tr>
        </table>
        <p style="font-size:14px;color:#374151;line-height:1.6;">
          For security reasons, we strongly recommend changing your password after your first login.
          If you have any issues accessing the portal, please contact the HR team.
        </p>
        <p style="font-size:14px;color:#374151;margin-top:24px;">
          Warm regards,<br/><strong>BlitzenX HR Team</strong>
        </p>
        """
        return EmailService._base_html("Your Portal Login Credentials", body)

    @classmethod
    def send_login_credentials(
        cls,
        candidate_email: str,
        candidate_name: str,
        login_email: str,
        password: str,
        portal_link: str = "https://hrms.blitzenx.com/",
    ) -> Dict[str, Any]:
        """
        Send a branded welcome email containing the candidate's login credentials
        (email + password) and a direct link to the HRMS portal.
        """
        try:
            html = cls._login_credentials_html(
                candidate_name=candidate_name,
                login_email=login_email,
                password=password,
                portal_link=portal_link,
            )
            result = cls.send_email(
                to_email=candidate_email,
                subject="Welcome to BlitzenX HRMS — Your Login Credentials",
                body_content=html,
                is_html=True,
            )
            logger.info(
                f"[EmailService] Login credentials email sent to {candidate_email}"
            )
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[EmailService] send_login_credentials error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # ------------------------------------------------------------------
    # Offer Letter Workflow Emails
    # ------------------------------------------------------------------

    @classmethod
    def notify_hm_approval_requested(
        cls,
        hm_email: str,
        hm_name: str,
        candidate_name: str,
        position: str,
        offer_id: int,
    ) -> None:
        """
        Email sent to the Hiring Manager when an offer letter is submitted for their approval.
        Sent as a best-effort fire-and-forget (errors are logged, not re-raised).
        """
        try:
            body = f"""
            <p style="font-size:16px;color:#111827;margin:0 0 16px;">
              Dear <strong>{hm_name}</strong>,
            </p>
            <p style="font-size:14px;color:#374151;line-height:1.6;">
              An offer letter has been submitted and is awaiting your approval.
              Please review the details below and take action.
            </p>
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:#f0f4ff;border-radius:6px;padding:16px;margin:16px 0;">
              <tr><td style="padding:6px 0;">
                <p style="margin:0;font-size:14px;color:#374151;">
                  <strong>Candidate:</strong> {candidate_name}
                </p>
              </td></tr>
              <tr><td style="padding:6px 0;">
                <p style="margin:0;font-size:14px;color:#374151;">
                  <strong>Position:</strong> {position}
                </p>
              </td></tr>
              <tr><td style="padding:6px 0;">
                <p style="margin:0;font-size:14px;color:#374151;">
                  <strong>Offer ID:</strong> #{offer_id}
                </p>
              </td></tr>
            </table>
            <p style="font-size:14px;color:#374151;line-height:1.6;">
              Please log in to the HRMS portal and navigate to
              <strong>Offer Letters &rarr; Pending Approval</strong> to review and sign.
            </p>
            <p style="font-size:14px;color:#374151;margin-top:24px;">
              Best regards,<br/><strong>BlitzenX HR Team</strong>
            </p>
            """
            html = cls._base_html("Offer Letter Pending Your Approval", body)
            cls.send_email(
                to_email=hm_email,
                subject=f"[Action Required] Offer Letter Approval — {candidate_name} | #{offer_id}",
                body_content=html,
                is_html=True,
            )
            logger.info(f"[EmailService] HM approval-request email sent to {hm_email}")
        except Exception as exc:
            logger.warning(f"[EmailService] notify_hm_approval_requested failed: {exc}")

    @classmethod
    def notify_hr_hm_decision(
        cls,
        hr_email: str,
        hm_name: str,
        candidate_name: str,
        position: str,
        offer_id: int,
        decision: str,          # "Approved" or "Rejected"
        approval_notes: str = "",
    ) -> None:
        """
        Email sent to HR when the Hiring Manager approves or rejects an offer.
        """
        try:
            colour = "#16a34a" if decision == "Approved" else "#dc2626"
            badge = f'<span style="color:{colour};font-weight:700;">{decision}</span>'
            notes_section = ""
            if approval_notes:
                notes_section = f"""
                <tr><td style="padding:6px 0;">
                  <p style="margin:0;font-size:14px;color:#374151;">
                    <strong>Notes:</strong> {approval_notes}
                  </p>
                </td></tr>"""

            body = f"""
            <p style="font-size:16px;color:#111827;margin:0 0 16px;">
              The hiring manager has reviewed an offer letter.
            </p>
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:#f0f4ff;border-radius:6px;padding:16px;margin:16px 0;">
              <tr><td style="padding:6px 0;">
                <p style="margin:0;font-size:14px;color:#374151;">
                  <strong>Decision:</strong> {badge}
                </p>
              </td></tr>
              <tr><td style="padding:6px 0;">
                <p style="margin:0;font-size:14px;color:#374151;">
                  <strong>Hiring Manager:</strong> {hm_name}
                </p>
              </td></tr>
              <tr><td style="padding:6px 0;">
                <p style="margin:0;font-size:14px;color:#374151;">
                  <strong>Candidate:</strong> {candidate_name}
                </p>
              </td></tr>
              <tr><td style="padding:6px 0;">
                <p style="margin:0;font-size:14px;color:#374151;">
                  <strong>Position:</strong> {position}
                </p>
              </td></tr>
              <tr><td style="padding:6px 0;">
                <p style="margin:0;font-size:14px;color:#374151;">
                  <strong>Offer ID:</strong> #{offer_id}
                </p>
              </td></tr>
              {notes_section}
            </table>
            {"<p style='font-size:14px;color:#374151;'>The offer is ready to be released to the candidate.</p>" if decision == "Approved" else ""}
            <p style="font-size:14px;color:#374151;margin-top:24px;">
              Best regards,<br/><strong>BlitzenX HR Team</strong>
            </p>
            """
            html = cls._base_html(f"Offer Letter {decision} by Hiring Manager", body)
            cls.send_email(
                to_email=hr_email,
                subject=f"Offer #{offer_id} {decision} by {hm_name} — {candidate_name}",
                body_content=html,
                is_html=True,
            )
            logger.info(f"[EmailService] HR decision notification sent to {hr_email} — {decision}")
        except Exception as exc:
            logger.warning(f"[EmailService] notify_hr_hm_decision failed: {exc}")

    @classmethod
    def notify_candidate_offer_released(
        cls,
        candidate_email: str,
        candidate_name: str,
        position: str,
        company_name: str = "BlitzenX",
        joining_date: str = "",
        offer_expire_date: str = "",
    ) -> None:
        """
        Email sent to the candidate when HR releases the approved offer letter.
        """
        try:
            expire_row = ""
            if offer_expire_date:
                expire_row = f"""
                <tr><td style="padding:6px 0;">
                  <p style="margin:0;font-size:14px;color:#374151;">
                    <strong>Offer Valid Until:</strong> {offer_expire_date}
                  </p>
                </td></tr>"""
            joining_row = ""
            if joining_date:
                joining_row = f"""
                <tr><td style="padding:6px 0;">
                  <p style="margin:0;font-size:14px;color:#374151;">
                    <strong>Joining Date:</strong> {joining_date}
                  </p>
                </td></tr>"""

            body = f"""
            <p style="font-size:16px;color:#111827;margin:0 0 16px;">
              Dear <strong>{candidate_name}</strong>,
            </p>
            <p style="font-size:14px;color:#374151;line-height:1.6;">
              We are delighted to extend an offer of employment to you from
              <strong>{company_name}</strong>. Please log in to the candidate portal
              to view your offer letter, provide your signature, and formally accept.
            </p>
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:#f0f4ff;border-radius:6px;padding:16px;margin:16px 0;">
              <tr><td style="padding:6px 0;">
                <p style="margin:0;font-size:14px;color:#374151;">
                  <strong>Position:</strong> {position}
                </p>
              </td></tr>
              {joining_row}
              {expire_row}
            </table>
            <p style="font-size:14px;color:#374151;line-height:1.6;">
              Please review the offer carefully and respond before the expiry date.
            </p>
            <p style="font-size:14px;color:#374151;margin-top:24px;">
              Warm regards,<br/><strong>BlitzenX HR Team</strong>
            </p>
            """
            html = cls._base_html("Your Offer Letter is Ready", body)
            cls.send_email(
                to_email=candidate_email,
                subject=f"Congratulations! Your Offer Letter from {company_name}",
                body_content=html,
                is_html=True,
            )
            logger.info(f"[EmailService] Offer-released email sent to {candidate_email}")
        except Exception as exc:
            logger.warning(f"[EmailService] notify_candidate_offer_released failed: {exc}")

    @classmethod
    def notify_hr_candidate_responded(
        cls,
        hr_email: str,
        candidate_name: str,
        position: str,
        offer_id: int,
        decision: str,          # "Accepted" or "Rejected"
        response_message: str = "",
    ) -> None:
        """
        Email sent to HR when the candidate accepts or rejects the offer.
        """
        try:
            colour = "#16a34a" if decision == "Accepted" else "#dc2626"
            badge = f'<span style="color:{colour};font-weight:700;">{decision}</span>'
            msg_section = ""
            if response_message:
                msg_section = f"""
                <tr><td style="padding:6px 0;">
                  <p style="margin:0;font-size:14px;color:#374151;">
                    <strong>Candidate Message:</strong> {response_message}
                  </p>
                </td></tr>"""

            body = f"""
            <p style="font-size:16px;color:#111827;margin:0 0 16px;">
              A candidate has responded to their offer letter.
            </p>
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:#f0f4ff;border-radius:6px;padding:16px;margin:16px 0;">
              <tr><td style="padding:6px 0;">
                <p style="margin:0;font-size:14px;color:#374151;">
                  <strong>Decision:</strong> {badge}
                </p>
              </td></tr>
              <tr><td style="padding:6px 0;">
                <p style="margin:0;font-size:14px;color:#374151;">
                  <strong>Candidate:</strong> {candidate_name}
                </p>
              </td></tr>
              <tr><td style="padding:6px 0;">
                <p style="margin:0;font-size:14px;color:#374151;">
                  <strong>Position:</strong> {position}
                </p>
              </td></tr>
              <tr><td style="padding:6px 0;">
                <p style="margin:0;font-size:14px;color:#374151;">
                  <strong>Offer ID:</strong> #{offer_id}
                </p>
              </td></tr>
              {msg_section}
            </table>
            <p style="font-size:14px;color:#374151;margin-top:24px;">
              Best regards,<br/><strong>BlitzenX HRMS</strong>
            </p>
            """
            html = cls._base_html(f"Candidate {decision} the Offer", body)
            cls.send_email(
                to_email=hr_email,
                subject=f"Offer #{offer_id} {decision} by {candidate_name}",
                body_content=html,
                is_html=True,
            )
            logger.info(f"[EmailService] Candidate-response email sent to {hr_email} — {decision}")
        except Exception as exc:
            logger.warning(f"[EmailService] notify_hr_candidate_responded failed: {exc}")

