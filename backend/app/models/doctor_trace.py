"""
Doctor Agent Trace Model

Tracks every attempt the Doctor makes to heal a failed message or operation.
Used for debugging and audit trail.

Schema: doctor_traces
- id (UUID): Unique identifier
- message_id (str): FK to source message/operation
- attempt_number (int): 1-3 (escalates at attempt 3)
- strategy_name (str): "SMS", "DATA_CORRECT", "RETRY", "ESCALATE"
- success (bool): Did this attempt fix the problem?
- error_message (text): If failed, what was the error?
- fix_applied (text): What action did we take? (for audit)
- timestamp (datetime): When did this attempt occur?

Indexes:
- (message_id, attempt_number) - Find all attempts for a message
- (timestamp DESC) - Recent traces first
- (success=false) - Find failed attempts needing escalation
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, Index, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class DoctorTrace(Base):
    """
    Audit trail for Doctor Agent self-healing attempts.
    One row per fix attempt on a failed message.
    """
    __tablename__ = "doctor_traces"

    # Primary Key
    id = Column(String(36), primary_key=True, index=True)

    # Foreign Key (message_id is a string identifier, not a FK to another table)
    # Allows flexibility for different message types (email, SMS, API call, etc.)
    message_id = Column(String(100), nullable=False, index=True)

    # Attempt metadata
    attempt_number = Column(Integer, nullable=False)  # 1, 2, or 3
    strategy_name = Column(String(50), nullable=False)  # "SMS", "DATA_CORRECT", "RETRY", "ESCALATE"

    # Outcome
    success = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)  # If failed, what was the error?
    fix_applied = Column(Text, nullable=True)  # What action was taken? (audit trail)

    # Timestamps
    timestamp = Column(DateTime(timezone=False), server_default=func.now(), nullable=False, index=True)

    # Optional: Link to created WROS ticket if escalation happened
    ticket_id = Column(Integer, nullable=True)  # FK to tasks.id (tickets are tasks)

    # Indexes for common queries
    __table_args__ = (
        Index("ix_doctor_traces_message_id", "message_id"),
        Index("ix_doctor_traces_timestamp", "timestamp"),
        Index("ix_doctor_traces_message_attempt", "message_id", "attempt_number"),
        Index("ix_doctor_traces_failed", "success", "timestamp"),
    )

    def __repr__(self):
        return (
            f"<DoctorTrace(message_id={self.message_id}, "
            f"attempt={self.attempt_number}, "
            f"strategy={self.strategy_name}, "
            f"success={self.success})>"
        )
