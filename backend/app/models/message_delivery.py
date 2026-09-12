"""Message Delivery Tracking Model

Tracks all message delivery attempts across channels (WhatsApp, Email).
Used to verify actual delivery and detect failures.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class MessageDeliveryLog(Base):
    """Tracks message delivery attempts and results."""
    __tablename__ = "message_delivery_log"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("candidate_conversations.id"), nullable=False)
    delivery_type = Column(String(50), nullable=False)  # "whatsapp" | "email"
    recipient = Column(String(512), nullable=False)  # Phone or email address
    subject = Column(String(255), nullable=True)  # For email only
    body = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="pending")  # "pending" | "sent" | "delivered" | "failed"

    # External service tracking
    external_message_id = Column(String(255), nullable=True)  # From Twilio/SendGrid/Graph
    delivery_id = Column(String(36), nullable=False, unique=True)  # Our tracking ID (UUID)

    # Error tracking
    error = Column(Text, nullable=True)  # Error message if delivery failed

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    sent_at = Column(DateTime, nullable=True)  # When delivery service confirmed send
    delivered_at = Column(DateTime, nullable=True)  # When recipient confirmed receipt

    # Relationships
    conversation = relationship("CandidateConversation", backref="delivery_logs")

    def __repr__(self):
        return (
            f"<MessageDeliveryLog(id={self.id}, type={self.delivery_type}, "
            f"recipient={self.recipient}, status={self.status})>"
        )
