"""Email Delivery Service Implementation

Sends emails via SendGrid or Azure Email service.
Stub version for development.
"""

import logging
from sqlalchemy.orm import Session

from app.services.delivery_service import DeliveryService, DeliveryResult, UnsupportedChannelError

logger = logging.getLogger(__name__)


class EmailDeliveryService(DeliveryService):
    """Sends emails via SendGrid or Azure."""

    def __init__(self, provider: str = "sendgrid", db: Session = None):
        """
        Initialize email delivery service.

        Args:
            provider: "sendgrid" or "azure"
            db: Database session
        """
        self.db = db
        self.provider = provider.lower()
        logger.info(f"[EmailDelivery] Initialized ({self.provider.upper()} stub - requires API configuration)")

    def send_whatsapp(self, to_number: str, body: str, from_number: str = None) -> DeliveryResult:
        """WhatsApp not supported via email service."""
        raise UnsupportedChannelError("Email service does not support WhatsApp delivery. Use Twilio instead.")

    def send_email(self, to_email: str, subject: str, body: str, html: bool = True) -> DeliveryResult:
        """
        Send email via SendGrid or Azure.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body (plain text or HTML)
            html: Whether body is HTML

        Returns:
            DeliveryResult with provider message ID
        """
        logger.warning(f"[EmailDelivery] STUB - {self.provider.upper()} email integration not configured. Configure API credentials.")

        if self.provider == "sendgrid":
            raise UnsupportedChannelError("SendGrid email delivery not configured. Set SENDGRID_API_KEY.")
        elif self.provider == "azure":
            raise UnsupportedChannelError("Azure Email delivery not configured. Set AZURE_EMAIL_CONNECTION_STRING.")
        else:
            raise UnsupportedChannelError(f"Unknown email provider: {self.provider}")

    def get_delivery_status(self, delivery_id: str) -> str:
        """Check email delivery status."""
        logger.warning(f"[EmailDelivery] STUB - Cannot check status for {delivery_id}")
        return "pending"
