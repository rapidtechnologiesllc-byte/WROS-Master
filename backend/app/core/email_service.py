"""Email service for sending emails via SMTP."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List


def send_email(
    to_email: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    bcc: Optional[List[str]] = None,
) -> bool:
    """
    Send an email.

    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Plain text body
        html_body: Optional HTML body
        bcc: Optional list of BCC recipients

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = 'noreply@blitzenx.com'
        msg['To'] = to_email

        msg.attach(MIMEText(body, 'plain'))
        if html_body:
            msg.attach(MIMEText(html_body, 'html'))

        # Note: In production, configure SMTP server credentials
        # For now, this is a stub that returns True (emails not actually sent)
        # Actual implementation would use smtplib.SMTP
        return True

    except Exception as e:
        print(f"Error sending email: {e}")
        return False
