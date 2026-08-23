"""
Executive Signal & Culture Agent -- the redesigned "Agent Avinash"
(2026-08-04 session, [[wros_ceo_agent_backlog]]). Advisory-only by
design, same posture as every other agent in this codebase: watches,
drafts, surfaces -- never autonomously acts on a real person's job,
comp, or standing.

Real correction made while building this: the original design assumed
"aggregating the health scores we've already built" for Client Health
and Project Health -- neither exists in this codebase (confirmed via
grep before writing a line here; HRMS-1107 Project Health Monitoring
is explicitly noted as NOT built in app.models.project's own module
docstring, and no client-health score exists anywhere). The org-health
view (app.services.org_health_service) aggregates what's REALLY
there instead -- employee performance, revenue leakage, SLA breaches,
bench aging, recruiting risk/intervention queue, Task system health --
not fabricated scores.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base

FEEDBACK_CYCLE_STATUSES = ("OPEN", "CLOSED")
RECOGNITION_STATUSES = ("DRAFT", "APPROVED", "SENT", "REJECTED")
RECOGNITION_OCCASIONS = ("BIRTHDAY", "WORK_ANNIVERSARY", "RECOGNITION")
CONCERN_CATEGORIES = ("RESOLVED", "ESCALATED")


def _new_uuid() -> str:
    return str(uuid.uuid4())


class EmployeeFeedbackCycle(Base):
    __tablename__ = "employee_feedback_cycles"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    quarter_label = Column(String(20), nullable=False)  # e.g. "2026-Q3"
    status = Column(String(10), nullable=False, default="OPEN")
    started_at = Column(DateTime, server_default=func.now())
    closed_at = Column(DateTime, nullable=True)


class EmployeeFeedbackResponse(Base):
    __tablename__ = "employee_feedback_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cycle_id = Column(String(36), ForeignKey("employee_feedback_cycles.id"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)
    response_text = Column(Text, nullable=False)
    # Simple heuristic flag (not an LLM verdict) -- see
    # culture_agent_service._flag_response() for the real, honest logic.
    is_flagged = Column(Boolean, nullable=False, default=False)
    submitted_at = Column(DateTime, server_default=func.now())


class RecognitionMessageDraft(Base):
    """Draft-and-approve, never auto-sent -- see [[wros_ceo_agent_backlog]]'s
    design reconciliation: a message staged as personally-written by
    Avinash when it wasn't is deceptive, not warm. Sent only once
    approved, and always attributable (signed as his, genuinely his by
    the time it goes out)."""
    __tablename__ = "recognition_message_drafts"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)
    occasion = Column(String(30), nullable=False)
    draft_text = Column(Text, nullable=False)
    status = Column(String(10), nullable=False, default="DRAFT")
    approved_by = Column(String(50), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    sent_at = Column(DateTime, nullable=True)

    employee = relationship("Employee", foreign_keys=[employee_id])


class EmployeeConcernIntake(Base):
    """Dissatisfaction triage: resolve genuinely simple stuff (FAQ-
    style, category=RESOLVED), otherwise offer to book real time with
    Avinash rather than pretend to be him -- category=ESCALATED creates
    a real Task (S-434), never a fake resolution."""
    __tablename__ = "employee_concern_intakes"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)
    message_text = Column(Text, nullable=False)
    category = Column(String(15), nullable=True)  # null until triaged
    resolution_text = Column(Text, nullable=True)
    created_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
