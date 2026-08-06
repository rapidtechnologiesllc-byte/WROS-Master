"""
S-434 -- Org-wide Task Dashboard. No canonical-sheet Story ID actually
resolves to "S-434" (verified against WROS_Canonical_Backlog_S001-401.xlsx
-- HRMS-0434 is S-034's own WROS ID, referenced only as a "Depends On"
value elsewhere; there is no real S-434 row). Built as new, greenfield
scope per Avinash's direct spec (2026-08-04 session), not retrofitted
onto an existing story.

Deliberately NOT tenant-partitioned the way the candidate-engagement
tables are (where "tenant_id" resolves to a single HR user's own
UserID, per S-011's real per-tenant-owner convention) -- Avinash's own
requirement is a SINGLE org-wide Task ID space ("Task #4127 means the
same thing to anyone who hears it"), so Task follows the same
genuinely-global convention Department/BusinessUnit already use, not
the AI-agent tables' per-owner convention. tenant_id is kept as a
nullable column for future multi-org support but is never used to
partition numbering, visibility, or round-robin scope.

Org-wide Task # is just the autoincrement primary key itself -- no
separate counter table needed; a single Integer IDENTITY/autoincrement
column is already a real, atomic, monotonic, org-wide sequence in both
SQLite and SQL Server.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Enum, ForeignKey, Integer,
    String, Text, func,
)
from sqlalchemy.orm import relationship

from app.models.base import Base

TASK_PRIORITIES = ("URGENT", "HIGH", "MEDIUM", "LOW")
TASK_STATUSES = ("NEW", "IN_PROGRESS", "ON_HOLD", "COMPLETED", "CANCELLED")
TASK_VISIBILITY_SCOPES = ("ASSIGNEE_MANAGER_DEPARTMENT", "ORG_WIDE")
# TICKET reuses this same Task table as one more Task type, per
# Avinash's explicit "ticketing is a Task type, not a parallel object"
# direction. Deliberately ONE generic TICKET value, not a fixed
# TICKET_HR/TICKET_IT/... enum -- Avinash's 2026-08-04 direction was
# explicit that ticketing must cover every department/function, not
# just HR/IT, so the real category routing lives in the dynamic
# TicketCategoryRoute table (keyed to the real, admin-configurable
# Department list) instead of a hardcoded type list. See
# app.services.ticket_service.
TASK_TYPES = ("GENERAL", "TICKET")

# BR: automatic overdue priority bump never reaches URGENT -- Urgent
# stays a deliberate, human-declared (and Thunder-challenged) choice.
PRIORITY_BUMP_CEILING = "HIGH"
PRIORITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "URGENT": 3}


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Task(Base):
    __tablename__ = "tasks"

    # This IS the org-wide "Task #" -- exposed directly, no separate
    # numbering column/table.
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(
        Enum(*TASK_TYPES, name="task_type", native_enum=False, create_constraint=True),
        nullable=False, default="GENERAL",
    )
    # Reserved for the ticketing story -- unused by GENERAL tasks.
    category = Column(String(100), nullable=True)
    subcategory = Column(String(100), nullable=True)

    priority = Column(
        Enum(*TASK_PRIORITIES, name="task_priority", native_enum=False, create_constraint=True),
        nullable=False, default="MEDIUM",
    )
    # Set when priority=URGENT was created and Thunder's plausibility
    # check didn't clearly agree -- surfaced to the creator, never
    # silently downgraded.
    priority_challenged = Column(Boolean, nullable=False, default=False)
    priority_challenge_note = Column(Text, nullable=True)

    status = Column(
        Enum(*TASK_STATUSES, name="task_status", native_enum=False, create_constraint=True),
        nullable=False, default="NEW",
    )

    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    assigned_to_user_id = Column(String(50), ForeignKey("users.UserID"), nullable=True, index=True)
    created_by_user_id = Column(String(50), ForeignKey("users.UserID"), nullable=True, index=True)
    # Parent-child pattern (Freshdesk/Zendesk precedent) -- one cross-
    # functional request can fan out into per-department child Tasks
    # (e.g. "new hire needs a laptop + badge + desk" -> separate IT/
    # Security/Facilities children), each still routed through this
    # same Department + round-robin mechanism. Not yet exposed via a
    # dedicated "split into child tasks" endpoint this pass -- schema
    # is ready, the fan-out UX is follow-up work.
    parent_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True, index=True)

    # 2026-08-05 -- document review linkage. Avinash's direct rule: a
    # rejected candidate document must reopen (or create) a real Task
    # so it shows as pending work, not just a status flag nobody's
    # tracking; approving the document closes that same Task. Both
    # nullable -- every non-document-review Task leaves these null,
    # same "polymorphic-lite, not a forced generic link table" posture
    # as parent_task_id above.
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID"), nullable=True, index=True)
    document_id = Column(Integer, ForeignKey("candidate_documents.id"), nullable=True, index=True)
    # 2026-08-05 -- interview feedback/HM-decision linkage (backlog item:
    # distinguish "interviewer hasn't submitted feedback yet" from
    # "hiring manager hasn't decided yet" Tasks without clubbing across a
    # candidate's other rounds/jobs). Nullable, same posture as
    # document_id above -- most Tasks are still unrelated to any
    # interview.
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=True, index=True)
    # 2026-08-05 -- expense approval linkage: once an expense is
    # approved, a real Task assigned to Finance tracks "mark it paid
    # once paid" (Avinash's explicit rule). Completing this Task is
    # what flips the expense to REIMBURSED -- same polymorphic-lite
    # nullable-link posture as document_id/interview_id above.
    expense_id = Column(String(36), ForeignKey("expense_records.id"), nullable=True, index=True)

    due_date = Column(DateTime, nullable=True, index=True)
    is_external = Column(Boolean, nullable=False, default=False)
    visibility_scope = Column(
        Enum(*TASK_VISIBILITY_SCOPES, name="task_visibility_scope", native_enum=False, create_constraint=True),
        nullable=False, default="ASSIGNEE_MANAGER_DEPARTMENT",
    )

    # Real escalation signal (not just display styling) -- set the
    # moment an open task crosses its due_date. Drives both the red
    # due-date rendering and the one-time manager notification.
    is_escalated = Column(Boolean, nullable=False, default=False)
    escalated_at = Column(DateTime, nullable=True)

    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    department = relationship("Department", foreign_keys=[department_id])
    assigned_to = relationship("Users", foreign_keys=[assigned_to_user_id])
    created_by = relationship("Users", foreign_keys=[created_by_user_id])
    parent_task = relationship("Task", remote_side=[id], foreign_keys=[parent_task_id])
    candidate = relationship("Candidate", foreign_keys=[candidate_id])
    document = relationship("CandidateDocument", foreign_keys=[document_id])
    interview = relationship("Interview", foreign_keys=[interview_id])

    __table_args__ = (
        CheckConstraint(
            "priority NOT IN ('URGENT') OR priority_challenge_note IS NOT NULL OR priority_challenged = 0",
            name="ck_task_urgent_has_validation_attempt",
        ),
    )


class TaskReassignmentRequest(Base):
    """A manager-approval-gated reassignment, raised when an assignee is
    unavailable (e.g. taking time off) and has tasks due today. Never
    auto-applies -- see task_assignment_service.request_reassignment()/
    approve_reassignment()."""
    __tablename__ = "task_reassignment_requests"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)

    from_user_id = Column(String(50), ForeignKey("users.UserID"), nullable=False)
    suggested_to_user_id = Column(String(50), ForeignKey("users.UserID"), nullable=True)
    reason = Column(String(200), nullable=False, default="ASSIGNEE_UNAVAILABLE")

    status = Column(
        Enum("PENDING", "APPROVED", "REJECTED", name="task_reassignment_status", native_enum=False, create_constraint=True),
        nullable=False, default="PENDING",
    )
    approved_by_user_id = Column(String(50), ForeignKey("users.UserID"), nullable=True)
    final_to_user_id = Column(String(50), ForeignKey("users.UserID"), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime, nullable=True)

    task = relationship("Task")


class TaskCapacityAlert(Base):
    """Advisory-only signal raised when a user's open-task load looks
    unsustainable -- round-robin skips them going forward, and their
    manager gets a real notification with a suggestion (talk to them,
    or a hiring-gap signal), never an automatic reassignment of
    existing work."""
    __tablename__ = "task_capacity_alerts"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    user_id = Column(String(50), ForeignKey("users.UserID"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)

    open_task_count = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)

    is_resolved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime, nullable=True)
