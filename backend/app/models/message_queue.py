"""Message Queue model - Core message queue for all system operations with channel-based routing"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, func, Index, Boolean
from sqlalchemy.orm import relationship

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class MessageQueue(Base):
    """
    Central message queue for all system operations with channel-based routing.

    Queue Types:
    - THUNDER_QUEUE: Autonomous candidate engagement
    - EMAIL_QUEUE: Email delivery with tracking
    - WHATSAPP_QUEUE, SMS_QUEUE, SLACK_QUEUE: Alternative channels
    - APPROVAL_QUEUE: Approval workflows
    - COMMISSION_QUEUE: Commission processing
    - CRM_QUEUE: CRM integration
    - DASHBOARD_QUEUE: Dashboard notifications
    - CALENDAR_QUEUE: Calendar events
    - SIGNATURE_QUEUE: Digital signature workflows

    Message flow: PENDING → SLM_PROCESSING → CHANNEL_QUEUED → COMPLETED/FAILED
    Retries: Max 5 retries with exponential backoff
    """

    __tablename__ = "message_queue"

    # Primary key and identifiers
    id = Column(String(256), primary_key=True, default=_new_uuid)
    type = Column(String(256), nullable=False, index=True)  # e.g., 'candidate_added', 'interview_scheduled'
    queue_type = Column(String(256), nullable=True, index=True)  # Channel-based: THUNDER_QUEUE, EMAIL_QUEUE, etc.
    status = Column(String(256), nullable=False, index=True)  # PENDING, SLM_PROCESSING, CHANNEL_QUEUED, COMPLETED, FAILED

    # Message content
    payload = Column(JSON(), nullable=False)  # Serialized message data
    resource_id = Column(String(256), nullable=True, index=True)  # FK to resource (candidate_id, etc.)

    # Tracking and audit
    created_by = Column(String(256), nullable=False)  # User or system that created message
    retry_count = Column(Integer, nullable=False, default=0)  # Number of retry attempts
    error = Column(Text(), nullable=True)  # Error message if failed

    # Retry scheduling
    next_retry_at = Column(DateTime(timezone=False), nullable=True, index=True)  # When to retry

    # Email-specific fields (for EMAIL_QUEUE messages)
    email_status = Column(String(256), nullable=True)  # PENDING, SENDING, SENT, DELIVERED, OPENED, CLICKED, REPLIED, BOUNCED, SPAM, DELETED
    opened_at = Column(DateTime(timezone=False), nullable=True)  # When email was opened
    clicked_at = Column(DateTime(timezone=False), nullable=True)  # When email link was clicked
    replied_at = Column(DateTime(timezone=False), nullable=True)  # When email was replied to
    bounced_at = Column(DateTime(timezone=False), nullable=True)  # When email bounced
    spam_marked_at = Column(DateTime(timezone=False), nullable=True)  # When marked as spam
    deleted_at = Column(DateTime(timezone=False), nullable=True)  # When deleted by recipient

    # Email provider and tracking
    email_provider = Column(String(256), nullable=True)  # gmail, outlook, yahoo, apple, smtp
    last_tracked_at = Column(DateTime(timezone=False), nullable=True)  # Last time tracking was checked
    tracking_error = Column(Text(), nullable=True)  # Error from email tracking service

    # Timestamps
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships - Removed for now to avoid ORM mapping issues
    # These can be loaded via explicit queries if needed
    # channels = relationship("MessageChannel", back_populates="message", cascade="all, delete-orphan")
    # email_tracking = relationship("EmailTracking", back_populates="message", cascade="all, delete-orphan")

    # Composite indexes for common queries
    __table_args__ = (
        Index("ix_message_queue_status_retry", "status", "next_retry_at"),
        Index("ix_message_queue_type_resource", "type", "resource_id"),
        Index("ix_message_queue_created_at", "created_at"),
        Index("ix_message_queue_queue_type_status", "queue_type", "status"),
        Index("ix_message_queue_email_status_tracking", "email_status", "last_tracked_at"),
    )


class MessageChannel(Base):
    """
    Junction table: Routes a single message to multiple channel queues.

    Example: A single message (candidate_added) can be routed to:
    - THUNDER_QUEUE (send to Thunder autonomous loop)
    - EMAIL_QUEUE (send welcome email)
    - DASHBOARD_QUEUE (show on dashboard)
    """

    __tablename__ = "message_channels"

    id = Column(String(256), primary_key=True, default=_new_uuid)
    message_id = Column(String(256), nullable=False, index=True)
    queue_type = Column(String(256), nullable=False, index=True)  # Which channel to route to
    status = Column(String(256), nullable=False, default="PENDING")  # PENDING, PROCESSING, COMPLETED, FAILED
    error_details = Column(Text(), nullable=True)  # Error details if processing failed
    processed_at = Column(DateTime(timezone=False), nullable=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    # Relationships - Disabled to avoid ORM mapping issues
    # message = relationship("MessageQueue", back_populates="channels")

    __table_args__ = (
        Index("ix_message_channels_message_queue_type", "message_id", "queue_type"),
    )


class EmailTracking(Base):
    """
    Detailed email engagement tracking for multi-provider support.

    Supports: Gmail (API webhooks), Outlook (Graph webhooks), Yahoo/Apple/SMTP (pixel tracking + link tracking)
    """

    __tablename__ = "email_tracking"

    id = Column(String(256), primary_key=True, default=_new_uuid)
    message_id = Column(String(256), nullable=False, index=True)
    recipient_email = Column(String(256), nullable=False, index=True)
    provider = Column(String(256), nullable=False)  # gmail, outlook, yahoo, apple, smtp
    message_id_external = Column(String(256), nullable=True)  # External message ID from provider
    thread_id = Column(String(256), nullable=True)  # Gmail thread ID
    status = Column(String(256), nullable=False, default="PENDING")  # PENDING, SENT, DELIVERED, OPENED, CLICKED, REPLIED, BOUNCED, SPAM, DELETED

    # Engagement timestamps
    sent_at = Column(DateTime(timezone=False), nullable=True)
    delivered_at = Column(DateTime(timezone=False), nullable=True)
    opened_at = Column(DateTime(timezone=False), nullable=True)
    first_click_at = Column(DateTime(timezone=False), nullable=True)
    last_click_at = Column(DateTime(timezone=False), nullable=True)
    replied_at = Column(DateTime(timezone=False), nullable=True)
    bounced_at = Column(DateTime(timezone=False), nullable=True)
    spam_marked_at = Column(DateTime(timezone=False), nullable=True)
    deleted_at = Column(DateTime(timezone=False), nullable=True)

    # Engagement metrics
    open_count = Column(Integer(), default=0)
    click_count = Column(Integer(), default=0)
    bounce_reason = Column(String(256), nullable=True)

    # Polling state
    last_checked_at = Column(DateTime(timezone=False), nullable=True)
    check_count = Column(Integer(), default=0)
    last_error = Column(Text(), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships - Disabled to avoid ORM mapping issues
    # message = relationship("MessageQueue", back_populates="email_tracking")
    # events = relationship("EmailTrackingEvent", back_populates="tracking", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_email_tracking_message_recipient", "message_id", "recipient_email"),
        Index("ix_email_tracking_status", "status"),
        Index("ix_email_tracking_last_checked", "last_checked_at"),
    )


class EmailTrackingEvent(Base):
    """
    Detailed event log for each email engagement event.

    Enables complete audit trail and historical analysis of email engagement.
    """

    __tablename__ = "email_tracking_events"

    id = Column(String(256), primary_key=True, default=_new_uuid)
    tracking_id = Column(String(256), nullable=False, index=True)
    event_type = Column(String(256), nullable=False)  # sent, delivered, opened, clicked, replied, bounced, spam, deleted
    event_data = Column(JSON(), nullable=True)  # Additional event details (IP, user-agent, link clicked, etc.)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    # Relationships - Disabled to avoid ORM mapping issues
    # tracking = relationship("EmailTracking", back_populates="events")

    __table_args__ = (
        Index("ix_email_tracking_events_tracking_type", "tracking_id", "event_type"),
    )


class QueueProcessingState(Base):
    """
    Tracks processing state per queue type to prevent concurrent processing issues.
    """

    __tablename__ = "queue_processing_state"

    id = Column(String(256), primary_key=True, default=_new_uuid)
    queue_type = Column(String(256), nullable=False, unique=True, index=True)
    last_processed_message_id = Column(String(256), nullable=True)
    last_processed_at = Column(DateTime(timezone=False), nullable=True)
    is_processing = Column(Boolean(), default=False)
    process_count_total = Column(Integer(), default=0)
    error_count_total = Column(Integer(), default=0)
    last_error = Column(Text(), nullable=True)
    last_error_at = Column(DateTime(timezone=False), nullable=True)
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)


class MessageLog(Base):
    """
    Audit trail for message processing.

    Records every status change and processing attempt for audit and debugging.
    """

    __tablename__ = "message_log"

    id = Column(String(256), primary_key=True, default=_new_uuid)
    message_id = Column(String(256), nullable=False, index=True)  # FK to message_queue.id
    status = Column(String(256), nullable=False)  # Status at this point in time
    error = Column(Text(), nullable=True)  # Error (if any)
    processing_time_ms = Column(Integer, nullable=True)  # How long it took to process
    timestamp = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
