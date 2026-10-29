"""Employee performance (CEO 2026-10-24): scheduled reviews by the reporting chain, peer praise and
feedback, and internal notes. Who sees what is decided in app.services.performance_service.

- PerformanceReview: one per employee, reviewer level and period. Reporting manager every
  PERF_REVIEW_MANAGER_DAYS (bi-weekly), BU head every calendar month, partner every calendar
  quarter. Each has a task for the reviewer, a Teams meeting on both calendars and the recording;
  the reviewer writes it up and chooses who sees it: the employee and their chain, or the chain only.
- PeerFeedback: praise (everyone sees it) or feedback (the employee, their chain and HR), named or
  anonymous; an anonymous author is visible to HR only.
- PerformanceNote: internal notes, the reporting chain and HR only.
"""
import uuid

from sqlalchemy import (Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer, String, Text,
                        UniqueConstraint, func)

from app.models.base import Base

REVIEW_LEVELS = ("MANAGER", "BU_HEAD", "PARTNER")
REVIEW_STATUSES = ("PENDING", "SCHEDULED", "COMPLETED", "MISSED", "CANCELLED")
REVIEW_VISIBILITIES = ("EMPLOYEE_AND_CHAIN", "CHAIN_ONLY")
RECORDING_SOURCES = ("TEAMS", "UPLOAD", "LINK")
FEEDBACK_KINDS = ("PRAISE", "FEEDBACK")


def _uuid() -> str:
    return str(uuid.uuid4())


class PerformanceReview(Base):
    __tablename__ = "performance_reviews"
    __table_args__ = (UniqueConstraint("employee_id", "level", "period_start", name="uq_performance_review_period"),)

    id = Column(String(64), primary_key=True, default=_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)
    level = Column(Enum(*REVIEW_LEVELS, name="performance_review_level", native_enum=False, create_constraint=True),
                   nullable=False)
    reviewer_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=False, index=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    status = Column(Enum(*REVIEW_STATUSES, name="performance_review_status", native_enum=False,
                         create_constraint=True), nullable=False, default="PENDING")
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    # the Teams meeting (organized by the service mailbox)
    meeting_start = Column(DateTime, nullable=True)
    meeting_end = Column(DateTime, nullable=True)
    meeting_event_id = Column(Text, nullable=True)
    meeting_join_url = Column(Text, nullable=True)
    meeting_note = Column(Text, nullable=True)  # why no meeting was booked, when one was not
    # the recording: fetched from Teams, uploaded, or linked
    recording_source = Column(Enum(*RECORDING_SOURCES, name="performance_recording_source", native_enum=False,
                                   create_constraint=True), nullable=True)
    recording_path = Column(Text, nullable=True)  # a stored file (UPLOAD_DIR) for TEAMS / UPLOAD
    recording_url = Column(Text, nullable=True)  # an external link for LINK
    recording_fetch_error = Column(Text, nullable=True)
    # the write-up
    rating = Column(Integer, nullable=True)  # 1..PERF_REVIEW_RATING_MAX
    summary = Column(Text, nullable=True)
    strengths = Column(Text, nullable=True)
    improvements = Column(Text, nullable=True)
    goals = Column(Text, nullable=True)
    visibility = Column(Enum(*REVIEW_VISIBILITIES, name="performance_review_visibility", native_enum=False,
                             create_constraint=True), nullable=False, default="CHAIN_ONLY")
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class PeerFeedback(Base):
    __tablename__ = "peer_feedback"

    id = Column(String(64), primary_key=True, default=_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)
    author_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=False)
    kind = Column(Enum(*FEEDBACK_KINDS, name="peer_feedback_kind", native_enum=False, create_constraint=True),
                  nullable=False)
    body = Column(Text, nullable=False)
    anonymous = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class PerformanceNote(Base):
    __tablename__ = "performance_notes"

    id = Column(String(64), primary_key=True, default=_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)
    author_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
