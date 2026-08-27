"""Message Queue model - Core message queue for all system operations"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, func, Index
from sqlalchemy.orm import relationship

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class MessageQueue(Base):
    """
    Central message queue for all system operations.

    Every operation that creates/modifies data creates a message:
    - Candidate added → message
    - Thunder email sent → message
    - Flash action executed → message
    - Interview scheduled → message

    Message flow: PENDING → PROCESSING → COMPLETED/RETRYING/FAILED
    Retries: Max 5 retries, 30-minute delay between retries
    """

    __tablename__ = "message_queue"

    # Primary key and identifiers
    id = Column(String(36), primary_key=True, default=_new_uuid)
    type = Column(String(100), nullable=False, index=True)  # e.g., 'candidate_added'
    status = Column(String(50), nullable=False, index=True)  # PENDING, PROCESSING, COMPLETED, RETRYING, FAILED

    # Message content
    payload = Column(JSON(), nullable=False)  # Serialized message data
    resource_id = Column(String(36), nullable=True, index=True)  # FK to resource (candidate_id, etc.)

    # Tracking and audit
    created_by = Column(String(50), nullable=False)  # User or system that created message
    retry_count = Column(Integer, nullable=False, default=0)  # Number of retry attempts
    error = Column(Text(), nullable=True)  # Error message if failed

    # Retry scheduling
    next_retry_at = Column(DateTime(timezone=False), nullable=True, index=True)  # When to retry

    # Timestamps
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Composite indexes for common queries
    __table_args__ = (
        Index("ix_message_queue_status_retry", "status", "next_retry_at"),
        Index("ix_message_queue_type_resource", "type", "resource_id"),
        Index("ix_message_queue_created_at", "created_at"),
    )


class MessageLog(Base):
    """
    Audit trail for message processing.

    Records every status change and processing attempt for audit and debugging.
    """

    __tablename__ = "message_log"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    message_id = Column(String(36), nullable=False, index=True)  # FK to message_queue.id
    status = Column(String(50), nullable=False)  # Status at this point in time
    error = Column(Text(), nullable=True)  # Error (if any)
    processing_time_ms = Column(Integer, nullable=True)  # How long it took to process
    timestamp = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
