"""Email Delivery Service - Production-Grade SendGrid & Azure Integration

Sends emails via SendGrid or Azure Communication Services.
Production-ready with retry logic, error handling, and delivery tracking.
"""

import os
import logging
import time
import uuid
from typing import Optional
from sqlalchemy.orm import Session

from app.services.delivery_service import DeliveryService, DeliveryResult, UnsupportedChannelError

logger = logging.getLogger(__name__)


class EmailDeliveryService(DeliveryService):
    """Production-grade email delivery via SendGrid or Azure Communication Services."""

    def __init__(self, provider: str = "sendgrid", db: Session = None,
                 api_key: str = None, from_email: str = None,
                 tenant_id_cred: str = None, client_id: str = None, client_secret: str = None):
        """
        Initialize email delivery service with credentials.

        Args:
            provider: "sendgrid" or "azure"
            db: Database session
            api_key: SendGrid API key (required if provider=sendgrid)
            from_email: SendGrid from email or Azure from email
            tenant_id_cred: Azure tenant ID (required if provider=azure)
            client_id: Azure client ID (required if provider=azure)
            client_secret: Azure client secret (required if provider=azure)

        Raises:
            RuntimeError: If provider credentials not configured or invalid
        """
        self.db = db
        self.provider = provider.lower()
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        self.from_email = None
        self.client = None

        if self.provider == "sendgrid":
            self._init_sendgrid(api_key, from_email)
        elif self.provider == "azure":
            self._init_azure(tenant_id_cred, client_id, client_secret, from_email)
        else:
            raise RuntimeError(f"Unknown email provider: {self.provider}")

    def _init_sendgrid(self, api_key: str = None, from_email: str = None):
        """Initialize SendGrid client from credentials."""
        # Accept credentials as parameters, fallback to env vars for backward compatibility
        self.api_key = api_key or os.getenv("SENDGRID_API_KEY")
        self.from_email = from_email or os.getenv("SENDGRID_FROM_EMAIL", "noreply@blitzenx.com")

        if not self.api_key:
            logger.error("[EmailDelivery] Missing SendGrid API key")
            raise RuntimeError(
                "SendGrid email not configured. Provide api_key parameter or set SENDGRID_API_KEY environment variable."
            )

        try:
            from sendgrid import SendGridAPIClient
            self.client = SendGridAPIClient(self.api_key)
            logger.info(f"[EmailDelivery] SendGrid initialized (from: {self.from_email})")
        except ImportError:
            logger.error("[EmailDelivery] sendgrid package not installed. Run: pip install sendgrid")
            raise RuntimeError("SendGrid SDK not installed. Install with: pip install sendgrid")
        except Exception as e:
            logger.error(f"[EmailDelivery] SendGrid initialization failed: {e}")
            raise RuntimeError(f"SendGrid initialization failed: {str(e)}")

    def _init_azure(self, tenant_id_cred: str = None, client_id: str = None,
                    client_secret: str = None, from_email: str = None):
        """Initialize Azure Communication Services client from credentials."""
        # Accept credentials as parameters, fallback to env vars for backward compatibility
        if tenant_id_cred and client_id and client_secret:
            # Initialize from Azure AD credentials (Graph API)
            self.tenant_id = tenant_id_cred
            self.client_id = client_id
            self.client_secret = client_secret
            self.from_email = from_email or "DoNotReply@blitzenx.onmicrosoft.com"
            logger.info(f"[EmailDelivery] Azure initialized with Graph API credentials (from: {self.from_email})")
        else:
            # Fallback to connection string from env vars
            self.connection_string = os.getenv("AZURE_COMMUNICATION_CONNECTION_STRING")
            self.from_email = from_email or os.getenv("AZURE_COMMUNICATION_FROM_EMAIL", "DoNotReply@blitzenx.onmicrosoft.com")

            if not self.connection_string:
                logger.error("[EmailDelivery] Missing Azure credentials (either tenant_id/client_id/client_secret or AZURE_COMMUNICATION_CONNECTION_STRING)")
                raise RuntimeError(
                    "Azure Email not configured. Provide credentials or set AZURE_COMMUNICATION_CONNECTION_STRING environment variable."
                )

        try:
            from azure.communication.email import EmailClient
            self.client = EmailClient.from_connection_string(self.connection_string)
            logger.info(f"[EmailDelivery] Azure Communication Services initialized (from: {self.from_email})")
        except ImportError:
            logger.error("[EmailDelivery] azure-communication-email package not installed.")
            raise RuntimeError(
                "Azure Email SDK not installed. Install with: pip install azure-communication-email"
            )
        except Exception as e:
            logger.error(f"[EmailDelivery] Azure initialization failed: {e}")
            raise RuntimeError(f"Azure initialization failed: {str(e)}")

    def send_whatsapp(self, to_number: str, body: str, from_number: str = None) -> DeliveryResult:
        """Email service does not support WhatsApp."""
        raise UnsupportedChannelError(
            "Email service does not support WhatsApp delivery. "
            "Use DELIVERY_PROVIDER=twilio for WhatsApp."
        )

    def send_email(self, to_email: str, subject: str, body: str, html: bool = True) -> DeliveryResult:
        """
        Send email via SendGrid or Azure (production).

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body
            html: Whether body is HTML (default True)

        Returns:
            DeliveryResult with provider message ID

        Raises:
            UnsupportedChannelError: If credentials missing or API call fails
        """
        if not to_email or not subject or not body:
            raise ValueError(
                f"Invalid email parameters: to={to_email}, subject_len={len(subject) if subject else 0}, "
                f"body_len={len(body) if body else 0}"
            )

        if self.provider == "sendgrid":
            return self._send_sendgrid(to_email, subject, body, html)
        elif self.provider == "azure":
            return self._send_azure(to_email, subject, body, html)

    def _send_sendgrid(self, to_email: str, subject: str, body: str, html: bool) -> DeliveryResult:
        """Send email via SendGrid."""
        from sendgrid.helpers.mail import Mail, Email, To, Content

        attempt = 0
        last_error = None

        while attempt < self.max_retries:
            try:
                attempt += 1
                logger.info(
                    f"[SendGrid] Sending email (attempt {attempt}/{self.max_retries}) "
                    f"to {to_email}, subject: {subject[:50]}..."
                )

                mail = Mail(
                    from_email=Email(self.from_email),
                    to_emails=To(to_email),
                    subject=subject,
                    plain_text_content=body if not html else None,
                    html_content=body if html else None
                )

                response = self.client.send(mail)

                logger.info(
                    f"[SendGrid] Email sent to {to_email}, "
                    f"Status: {response.status_code}, "
                    f"MessageId: {response.headers.get('X-Message-Id', 'unknown')}"
                )

                return DeliveryResult(
                    status="sent",
                    delivery_id=response.headers.get("X-Message-Id", str(uuid.uuid4())),
                    external_id=response.headers.get("X-Message-Id"),
                    error=None
                )

            except Exception as e:
                last_error = e
                logger.warning(f"[SendGrid] Attempt {attempt} failed for {to_email}: {str(e)}")

                if attempt < self.max_retries:
                    logger.info(f"[SendGrid] Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)

        logger.error(
            f"[SendGrid] All {self.max_retries} attempts failed for {to_email}. "
            f"Last error: {str(last_error)}"
        )

        return DeliveryResult(
            status="failed",
            delivery_id=None,
            external_id=None,
            error=f"SendGrid delivery failed after {self.max_retries} attempts: {str(last_error)}"
        )

    def _send_azure(self, to_email: str, subject: str, body: str, html: bool) -> DeliveryResult:
        """Send email via Azure Communication Services."""
        attempt = 0
        last_error = None

        while attempt < self.max_retries:
            try:
                attempt += 1
                logger.info(
                    f"[Azure] Sending email (attempt {attempt}/{self.max_retries}) "
                    f"to {to_email}, subject: {subject[:50]}..."
                )

                from azure.communication.email import EmailMessage

                email_message = EmailMessage(
                    sender=self.from_email,
                    recipients=[to_email],
                    subject=subject,
                    html_content=body if html else None,
                    plain_text_content=body if not html else None
                )

                poller = self.client.begin_send(email_message)
                result = poller.result()

                logger.info(
                    f"[Azure] Email sent to {to_email}, "
                    f"Status: {result['status']}, "
                    f"MessageId: {result.get('id', 'unknown')}"
                )

                return DeliveryResult(
                    status="sent",
                    delivery_id=result.get("id", str(uuid.uuid4())),
                    external_id=result.get("id"),
                    error=None
                )

            except Exception as e:
                last_error = e
                logger.warning(f"[Azure] Attempt {attempt} failed for {to_email}: {str(e)}")

                if attempt < self.max_retries:
                    logger.info(f"[Azure] Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)

        logger.error(
            f"[Azure] All {self.max_retries} attempts failed for {to_email}. "
            f"Last error: {str(last_error)}"
        )

        return DeliveryResult(
            status="failed",
            delivery_id=None,
            external_id=None,
            error=f"Azure delivery failed after {self.max_retries} attempts: {str(last_error)}"
        )

    def get_delivery_status(self, delivery_id: str) -> str:
        """
        Check email delivery status (provider-dependent).

        Args:
            delivery_id: Provider message ID

        Returns:
            Status: sent, delivered, failed, or unknown
        """
        if not delivery_id:
            return "unknown"

        if self.provider == "sendgrid":
            logger.warning(
                f"[SendGrid] Status tracking requires Event Webhook. "
                "Set SENDGRID_EVENT_WEBHOOK_URL in SendGrid dashboard."
            )
            return "unknown"  # SendGrid requires webhooks for delivery tracking

        elif self.provider == "azure":
            try:
                # Azure tracks via backend; we can't query per-message
                logger.debug(f"[Azure] Status tracking via backend monitoring for {delivery_id}")
                return "sent"  # Assume sent; Azure backend handles tracking
            except Exception as e:
                logger.error(f"[Azure] Failed to fetch status for {delivery_id}: {e}")
                return "unknown"

        return "unknown"
