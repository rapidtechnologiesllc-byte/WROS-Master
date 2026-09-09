"""
QueueDoctor State Tracking - Queue Processing Health & Diagnostics

Tracks queue processing metrics, stalled messages, and health indicators
for each message processed by the queue worker.
"""
import logging
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, Index, func
from sqlalchemy.orm import relationship

from app.models.base import Base

logger = logging.getLogger(__name__)


class QueueDoctorState(Base):
    """Queue processing health and diagnostics per message."""
    __tablename__ = "queue_doctor_state"
    __table_args__ = (
        Index('idx_message_id', 'message_id'),
        Index('idx_candidate_id', 'candidate_id'),
        Index('idx_message_type', 'message_type'),
        Index('idx_status', 'status'),
        Index('idx_queued_at', 'queued_at'),
    )

    id = Column(String(512), primary_key=True, index=True)
    message_id = Column(String(512), nullable=False, unique=True, index=True)
    message_type = Column(String(100), nullable=False, index=True)

    # Timing diagnostics
    queued_at = Column(DateTime, nullable=False, server_default=func.now())
    started_at = Column(DateTime, nullable=True)  # When processing began
    completed_at = Column(DateTime, nullable=True)  # When processing ended
    processing_time_ms = Column(Integer, nullable=True)  # (completed - started)

    # Health metrics
    attempt_count = Column(Integer, default=1)
    max_attempts = Column(Integer, default=5)
    is_stalled = Column(Boolean, default=False, index=True)  # True if queued > 30min without progress

    # Status tracking
    status = Column(String(50), nullable=False, index=True)  # PENDING, PROCESSING, COMPLETED, FAILED, STALLED
    error_message = Column(Text, nullable=True)

    # Correlation & context
    candidate_id = Column(String(512), nullable=True, index=True)
    workflow_id = Column(String(512), nullable=True, index=True)  # Group related messages

    # Healing/Recovery
    healing_attempted = Column(Boolean, default=False)
    healing_succeeded = Column(Boolean, nullable=True)
    healing_strategy = Column(String(100), nullable=True)  # ALTERNATIVE_CONTACT, DATA_CORRECTION, SERVICE_RETRY, ESCALATE

    # Audit
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<QueueDoctorState message_id={self.message_id} status={self.status} type={self.message_type}>"
