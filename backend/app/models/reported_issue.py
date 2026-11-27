"""Issues people report from the app (Ask Flash -> Report an Issue). CEO 2026-11-27: every reported issue is tracked
and tackled, visible under Admin -> System -> Reported issues; until then reports went to a text file on the server
that nobody saw. Status moves OPEN -> IN_PROGRESS -> FIXED / WONT_FIX / DUPLICATE, with the fix and who closed it."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.models.base import Base

ISSUE_STATUSES = ("OPEN", "IN_PROGRESS", "FIXED", "WONT_FIX", "DUPLICATE")
CLOSED_STATUSES = ("FIXED", "WONT_FIX", "DUPLICATE")
ISSUE_SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
ISSUE_TYPES = ("BUG", "IMPROVEMENT", "QUESTION")


class ReportedIssue(Base):
    __tablename__ = "reported_issues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # the reference the reporter was given (DEFECT-<utc timestamp>), also for reports imported from the old file
    reference = Column(String(64), nullable=False, unique=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    reported_by_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True, index=True)
    reporter_name = Column(String(512), nullable=True)
    screen = Column(String(255), nullable=False)
    # a Jira-style log: one-line summary (the description's first line unless given), type and assignee
    summary = Column(String(255), nullable=False)
    issue_type = Column(String(16), nullable=False, default="BUG", server_default="BUG")
    description = Column(Text, nullable=False)
    assignee_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True, index=True)
    severity = Column(String(16), nullable=False, index=True)
    blocking = Column(Boolean, nullable=False, default=False)
    status = Column(String(16), nullable=False, default="OPEN", server_default="OPEN", index=True)
    resolution = Column(Text, nullable=True)  # what was done (or why not), and where: PR / commit
    resolved_by_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ReportedIssueComment(Base):
    """A comment on a reported issue: the reporter adding detail, whoever works on it saying what they found."""
    __tablename__ = "reported_issue_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(Integer, ForeignKey("reported_issues.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    author_name = Column(String(512), nullable=True)
    body = Column(Text, nullable=False)
    # a status change is recorded in the thread too, so the history reads top to bottom
    kind = Column(String(16), nullable=False, default="COMMENT", server_default="COMMENT")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
