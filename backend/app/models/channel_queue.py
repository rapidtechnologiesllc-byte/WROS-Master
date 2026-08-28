"""Channel Queue Models - Specific channel processing queues

Channel-based queues for different delivery mechanisms:
- EMAIL_QUEUE: Email delivery
- WHATSAPP_QUEUE: WhatsApp messages
- SMS_QUEUE: SMS delivery
- SLACK_QUEUE: Slack notifications
- THUNDER_QUEUE: Thunder autonomous actions
- APPROVAL_QUEUE: Approval workflow routing
- COMMISSION_QUEUE: Commission calculations
- CRM_QUEUE: CRM data sync
- DASHBOARD_QUEUE: Real-time dashboard updates
- CALENDAR_QUEUE: Calendar event creation
- SIGNATURE_QUEUE: E-signature requests
- TIMESHEET_QUEUE: Timesheet processing
- KPI_QUEUE: KPI updates
- SALES_QUEUE: Sales deal processing
- CLIENT_QUEUE: Client updates
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, func, Index, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class ChannelQueueItem(Base):
    """Queue item for specific channel processing"""

    __tablename__ = "channel_queue_item"

    # Primary key
    id = Column(String(36), primary_key=True, default=_new_uuid)

    # Link to original message
    message_id = Column(String(36), nullable=False, index=True)  # FK to message_queue.id

    # Channel configuration
    channel_type = Column(
        String(100),
        nullable=False,
        index=True,
        comment="EMAIL, WHATSAPP, SMS, SLACK, THUNDER, APPROVAL, COMMISSION, CRM, DASHBOARD, CALENDAR, SIGNATURE, TIMESHEET, KPI, SALES, CLIENT"
    )

    # Status tracking
    status = Column(
        String(50),
        nullable=False,
        index=True,
        comment="PENDING, PROCESSING, COMPLETED, FAILED"
    )

    # Channel-specific payload
    payload = Column(JSON(), nullable=False)  # Channel-specific data (recipient, template vars, etc.)
    recipient = Column(String(200), nullable=True)  # Email, phone, user_id, channel_id, etc.

    # Retry logic
    retry_count = Column(Integer, nullable=False, default=0)
    error = Column(Text(), nullable=True)
    next_retry_at = Column(DateTime(timezone=False), nullable=True, index=True)

    # Timestamps
    processed_at = Column(DateTime(timezone=False), nullable=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Indexes
    __table_args__ = (
        Index("ix_channel_queue_item_channel_status", "channel_type", "status"),
        Index("ix_channel_queue_item_retry", "status", "next_retry_at"),
        Index("ix_channel_queue_item_message", "message_id"),
    )


class ChannelQueueLog(Base):
    """Audit trail for channel queue processing"""

    __tablename__ = "channel_queue_log"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    channel_item_id = Column(String(36), nullable=False, index=True)  # FK to channel_queue_item.id
    status = Column(String(50), nullable=False)  # PENDING, PROCESSING, COMPLETED, FAILED
    message = Column(Text(), nullable=True)  # Status message or error
    processing_time_ms = Column(Integer, nullable=True)  # How long it took
    timestamp = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)


class SLMChannelDecision(Base):
    """SLM's decision on which channels to trigger for a message"""

    __tablename__ = "slm_channel_decision"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    slm_decision_id = Column(String(36), nullable=False, index=True)  # FK to slm_decision.id
    message_id = Column(String(36), nullable=False, index=True)  # FK to message_queue.id

    # Channels to trigger: [{ "channel": "EMAIL", "action": "send_offer" }, ...]
    channels_to_trigger = Column(JSON(), nullable=False)

    # Reasoning and metadata
    reasoning = Column(Text(), nullable=True)  # Why these channels?
    confidence_score = Column(Integer, nullable=True)  # 0-100 confidence in decision

    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
