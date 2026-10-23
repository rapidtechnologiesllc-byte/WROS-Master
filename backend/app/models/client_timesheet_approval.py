"""One request for the client to approve one timesheet week (CEO 2026-10-23), for clients with
Client.requires_client_timesheet_approval.

Either the client approver decides from an emailed link (method LINK: single-use, expiring token;
only its SHA-256 is stored, the plaintext exists only inside the email) or an internal approver
uploads the client's VMS-approved timesheet as evidence (method EVIDENCE: who, when, which file).
A new request (resend, or a resubmission after a rejection) supersedes the open one, so an older
link can never decide a newer version of the week."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.models.base import Base

CLIENT_APPROVAL_DECISIONS = ("PENDING", "APPROVED", "REJECTED", "SUPERSEDED")
CLIENT_APPROVAL_METHODS = ("LINK", "EVIDENCE")


class ClientTimesheetApproval(Base):
    __tablename__ = "client_timesheet_approvals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    timesheet_id = Column(String(512), ForeignKey("timesheets.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(String(512), ForeignKey("clients.id"), nullable=False, index=True)
    approver_email = Column(String(300), nullable=True)

    # emailed link: set when the email is drafted (the handler issues the token)
    token_hash = Column(String(64), nullable=True, unique=True, index=True)
    expires_at = Column(DateTime, nullable=True)
    used_at = Column(DateTime, nullable=True)
    email_graph_id = Column(String(512), nullable=True)  # draft id: a retry re-sends the same draft
    emailed_at = Column(DateTime, nullable=True)

    decision = Column(String(20), nullable=False, default="PENDING")
    method = Column(String(20), nullable=True)
    reason = Column(Text, nullable=True)  # the client's rejection reason, or the evidence note
    decided_at = Column(DateTime, nullable=True)
    decided_ip = Column(String(64), nullable=True)

    # evidence upload (method EVIDENCE)
    recorded_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    evidence_path = Column(String(1024), nullable=True)
    evidence_filename = Column(String(512), nullable=True)
    evidence_content_type = Column(String(100), nullable=True)

    # the internal task raised when nobody can be emailed (no approver email on the placement)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    requested_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
