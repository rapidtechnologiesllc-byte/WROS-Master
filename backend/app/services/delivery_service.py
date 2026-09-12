"""
Abstract Delivery Service Interface

Unified interface for sending messages across channels (WhatsApp, Email).
Supports multiple implementations: stub (logging), real (Twilio/SendGrid/Graph).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class DeliveryResult:
    """Result from a delivery attempt."""
    delivery_id: str  # UUID for tracking
    status: str  # "pending" | "sent" | "failed"
    error: Optional[str] = None
    external_id: Optional[str] = None  # From Twilio/SendGrid/Graph


class DeliveryService(ABC):
    """Abstract base for message delivery implementations."""

    @abstractmethod
    def send_whatsapp(self, to_number: str, body: str, from_number: str = None) -> DeliveryResult:
        """Send WhatsApp message."""
        pass

    @abstractmethod
    def send_email(self, to_email: str, subject: str, body: str, html: bool = True) -> DeliveryResult:
        """Send email."""
        pass

    @abstractmethod
    def get_delivery_status(self, delivery_id: str) -> str:
        """Check delivery status by ID."""
        pass


class UnsupportedChannelError(Exception):
    """Raised when delivery channel not configured."""
    pass


class DeliveryFailed(Exception):
    """Raised when delivery attempt fails."""
    pass
