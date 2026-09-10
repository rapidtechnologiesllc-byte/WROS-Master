"""Message Queue model - Core message queue for all system operations with channel-based routing"""
import uuid
import logging
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, func, Index, Boolean
from sqlalchemy.orm import relationship

from app.models.base import Base

def _new_uuid() -> str:
    return str(uuid.uuid4())

logger = logging.getLogger(__name__)

class ChannelMessage(Base):
    """
    Central message queue for all system operations with channel-based routing.

    Queue Types:
    - default: Default queue
    - thunder: Autonomous candidate engagement
    - email: Email delivery with tracking
    - whatsapp, sms, slack: Alternative channels
    - approval: Approval workflows
    - commission: Commission processing

    Message flow: PENDING → PROCESSING → COMPLETED/FAILED
    """

    __tablename__ = "channel_message"

    # Primary key and identifiers
    id = Column(String(512), primary_key=True, default=_new_uuid)
    type = Column(String(512), nullable=False, index=True)
    queue_type = Column(String(512), nullable=True, index=True)
    status = Column(String(512), nullable=False, index=True)

    # Message content
    payload = Column(JSON(), nullable=False)
    resource_id = Column(String(512), nullable=True, index=True)

    # Tracking and audit
    created_by = Column(String(512), nullable=False)
    retry_count = Column(Integer, nullable=False, default=0)
    error = Column(Text(), nullable=True)

    # Retry scheduling
    next_retry_at = Column(DateTime(timezone=False), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_channel_message_status_retry", "status", "next_retry_at"),
        Index("ix_channel_message_type_resource", "type", "resource_id"),
        Index("ix_channel_message_created_at", "created_at"),
        Index("ix_channel_message_queue_type_status", "queue_type", "status"),
    )


class EmailTracking(Base):
    """Track email delivery status for each sent email"""
    __tablename__ = "email_tracking"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    candidate_id = Column(String(512), nullable=False, index=True)
    email_type = Column(String(100), nullable=False)  # FIRST_ENGAGEMENT, INTERVIEW, OFFER, etc.
    recipient_email = Column(String(512), nullable=False)
    graph_message_id = Column(String(512), nullable=True)  # Microsoft Graph message ID
    status = Column(String(50), nullable=False, default="PENDING")  # PENDING, SENDING, SENT, BOUNCED, FAILED, OPENED
    retry_count = Column(Integer, default=0)
    failure_reason = Column(Text(), nullable=True)
    sent_at = Column(DateTime(timezone=False), nullable=True)
    delivered_at = Column(DateTime(timezone=False), nullable=True)
    opened_at = Column(DateTime(timezone=False), nullable=True)
    bounced_at = Column(DateTime(timezone=False), nullable=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_email_tracking_candidate", "candidate_id"),
        Index("ix_email_tracking_status", "status"),
        Index("ix_email_tracking_created", "created_at"),
    )


class EmailTrackingEvent(Base):
    """Track email events (bounce, open, click) from webhooks"""
    __tablename__ = "email_tracking_event"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    email_tracking_id = Column(String(512), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # BOUNCE, OPEN, CLICK, DELIVERY
    event_data = Column(JSON(), nullable=True)
    received_at = Column(DateTime(timezone=False), nullable=False)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_email_tracking_event_tracking", "email_tracking_id"),
        Index("ix_email_tracking_event_type", "event_type"),
    )
