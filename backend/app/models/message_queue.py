"""Message Queue Models - Database models for message queue system."""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    JSON,
    ForeignKey,
    Text,
    Index,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class MessageQueue(Base):
    """Message queue table for tracking all system operations."""

    __tablename__ = "message_queue"

    id = Column(String(36), primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    type = Column(String(100), nullable=False)  # e.g., candidate_added, thunder_email, flash_agent_action
    payload = Column(JSON, nullable=False)  # Message payload
    status = Column(
        String(50), nullable=False, default="PENDING"
    )  # PENDING, PROCESSING, COMPLETED, FAILED, RETRYING
    resource_id = Column(String(100), nullable=True)  # ID of related resource
    created_by = Column(String(36), nullable=True)  # User who triggered the message
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    next_retry_at = Column(DateTime, nullable=True)  # When to retry if failed
    retry_count = Column(Integer, nullable=False, default=0)  # Number of retry attempts
    error_message = Column(Text, nullable=True)  # Error description if failed
    completed_at = Column(DateTime, nullable=True)  # When the message was completed
    processing_started_at = Column(DateTime, nullable=True)  # When processing started

    # Relationships
    logs = relationship(
        "MessageQueueLog",
        back_populates="message",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # Indexes
    __table_args__ = (
        Index("ix_message_queue_status_retry", "status", "next_retry_at"),
        Index("ix_message_queue_created_at", "created_at"),
        Index("ix_message_queue_type_resource", "type", "resource_id"),
        Index("ix_message_queue_tenant_status", "tenant_id", "status"),
        Index("ix_message_queue_created_by", "created_by"),
    )

    def __repr__(self):
        return f"<MessageQueue(id={self.id}, type={self.type}, status={self.status}, retry_count={self.retry_count})>"


class MessageQueueLog(Base):
    """Message queue audit log - tracks each processing attempt."""

    __tablename__ = "message_queue_log"

    id = Column(String(36), primary_key=True)
    message_id = Column(String(36), ForeignKey("message_queue.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), nullable=False)  # PROCESSING, COMPLETED, FAILED, RETRYING
    error = Column(Text, nullable=True)  # Error message if applicable
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    duration_ms = Column(Integer, nullable=True)  # How long processing took
    retry_attempt = Column(Integer, nullable=True)  # Which retry attempt this was

    # Relationships
    message = relationship("MessageQueue", back_populates="logs")

    # Indexes
    __table_args__ = (
        Index("ix_message_queue_log_message_id", "message_id"),
        Index("ix_message_queue_log_timestamp", "timestamp"),
        Index("ix_message_queue_log_status", "status"),
    )

    def __repr__(self):
        return f"<MessageQueueLog(id={self.id}, message_id={self.message_id}, status={self.status}, timestamp={self.timestamp})>"
