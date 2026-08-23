"""Email Template Models for dynamic candidate stage progression emails."""

from sqlalchemy import Column, String, Text, DateTime, UUID, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.models.base import Base


class EmailTemplateStage(str, enum.Enum):
    """Valid email template stages."""
    SCREENING = "screening"
    INTERVIEW = "interview"
    OFFER = "offer"
    HIRED = "hired"
    REJECTED = "rejected"


class EmailTemplate(Base):
    """Email template for candidate stage progression."""
    __tablename__ = "email_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stage = Column(String(50), nullable=False, unique=True)  # screening, interview, offer, hired, rejected
    subject = Column(String(255), nullable=False)
    body_html = Column(Text, nullable=False)
    
    created_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    deliveries = relationship("EmailDelivery", back_populates="template", cascade="all, delete-orphan")


class EmailDeliveryStatus(str, enum.Enum):
    """Email delivery status."""
    SENT = "sent"
    FAILED = "failed"
    OPENED = "opened"
    CLICKED = "clicked"


class EmailDelivery(Base):
    """Track email delivery status and engagement."""
    __tablename__ = "email_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), nullable=False)
    template_id = Column(UUID(as_uuid=True), nullable=False)
    
    stage = Column(String(50), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    
    status = Column(String(50), default="sent", nullable=False)  # sent, failed, opened, clicked
    error_message = Column(Text, nullable=True)
    
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    template = relationship("EmailTemplate", back_populates="deliveries")
