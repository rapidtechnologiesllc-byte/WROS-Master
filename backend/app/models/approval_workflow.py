"""Approval Workflow Model - Track approval requests and their status"""
from sqlalchemy import Column, String, DateTime, Boolean, Text, JSON
from datetime import datetime, timedelta
import uuid

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class ApprovalWorkflow(Base):
    """Track approval workflow requests and their status"""

    __tablename__ = "approval_workflow"

    id = Column(String(36), primary_key=True, default=_new_uuid)

    # What is being approved
    workflow_type = Column(String(100), nullable=False, index=True)  # offer, expense, promotion, etc.
    entity_id = Column(String(100), nullable=False, index=True)  # offer_id, expense_id, etc.
    entity_type = Column(String(100), nullable=False)  # Offer, ExpenseReport, PromotionRequest, etc.

    # Who is approving
    approver_id = Column(String(100), nullable=False, index=True)  # user_id
    approver_email = Column(String(255), nullable=False)

    # Status tracking
    status = Column(
        String(50),
        nullable=False,
        default="PENDING",
        index=True,
        comment="PENDING, APPROVED, REJECTED, EXPIRED"
    )

    # Timeline
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=7), nullable=False)
    approved_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)

    # Content
    approval_data = Column(JSON(), nullable=True)  # Request details for approval
    approval_comment = Column(Text(), nullable=True)  # Approver's comment
    rejection_reason = Column(Text(), nullable=True)  # Why it was rejected

    # Notifications
    notification_sent = Column(Boolean, default=False)
    reminder_sent = Column(Boolean, default=False)

    def __repr__(self):
        return f"<ApprovalWorkflow {self.workflow_type}:{self.entity_id} status={self.status}>"
