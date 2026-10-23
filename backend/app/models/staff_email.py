"""Emails to staff (timesheet approvals, decisions, reminders) sent from the HRMS mailbox by the
send_staff_email queue handler. One row per queued message (id = the queue task id, a
deterministic key, so the same notice is never queued twice); the Graph draft id is kept so a
retry re-sends the same draft instead of a second email."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.models.base import Base


class StaffEmail(Base):
    __tablename__ = "staff_emails"

    id = Column(String(512), primary_key=True)  # the queue task id
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    user_id = Column(String(512), ForeignKey("users.UserID"), nullable=False, index=True)
    subject = Column(String(512), nullable=False)
    graph_id = Column(String(512), nullable=True)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
