"""
S-062/HRMS-0462 -- Recruiter Intervention Queue.

recruiter_intervention_queue: genuinely new table -- one row per open
(candidate, queue_reason) combination, matching every other new table
this round (Integer-autoincrement PK, String(50) UserID-as-tenant_id,
String(50) candidate_id FK), not the spec's UUID assumption.

BR-02 (one OPEN item per candidate per reason) is enforced at the DB
level via a partial/filtered unique index (`WHERE status='OPEN'`),
same technique S-051's reschedule-chain fix already established --
resolved/in-progress historical rows are exempt so a candidate can
legitimately re-enter the same queue_reason after a prior item there
was resolved.

A real, documented overlap: OFFER_COUNTER (this story's own distinct
queue_reason) and the generic ESCALATION path can both fire for the
same countered-offer event in this codebase, since
offer_decision_service._handle_counter() already calls the generic
conversation_state_service.escalate() (S-035) as part of its existing,
already-shipped behavior. Both queue entries are added as this story's
own integrations table literally asks for both HRMS-0435 (escalation)
and HRMS-0456 (offer counter) as separate callers -- same "build what
spec asks, flag the real overlap" posture already established for the
several other overlapping "candidate went silent" mechanisms earlier
in this EPIC-04 round, not silently resolved by dropping one.
"""
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import relationship

from app.models.base import Base

QUEUE_REASONS = (
    "ESCALATION", "HIGH_DROP_RISK", "CRITICAL_DROP_RISK", "SLA_BREACH",
    "HIGH_ABANDONMENT", "NO_SHOW", "OFFER_COUNTER", "DOCUMENT_OVERDUE",
)
QUEUE_STATUSES = ("OPEN", "IN_PROGRESS", "RESOLVED")
PRIORITY_CRITICAL, PRIORITY_HIGH, PRIORITY_MEDIUM = True, 2, 3


class RecruiterInterventionQueue(Base):
    __tablename__ = "recruiter_intervention_queue"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)

    queue_reason = Column(Enum(*QUEUE_REASONS, name="intervention_queue_reason", native_enum=False, create_constraint=True), nullable=False)
    reason_detail = Column(Text, nullable=True)
    priority = Column(Integer, nullable=False)  # 1=CRITICAL, 2=HIGH, 3=MEDIUM -- see module constants
    status = Column(Enum(*QUEUE_STATUSES, name="intervention_queue_status", native_enum=False, create_constraint=True), nullable=False, default="OPEN")

    assigned_to_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=True)

    added_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=False), nullable=True)
    resolved_by = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=True)
    resolution_note = Column(Text, nullable=True)

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    assignee = relationship("Users", foreign_keys=[assigned_to_user_id], lazy="select")
    resolver = relationship("Users", foreign_keys=[resolved_by], lazy="select")

    __table_args__ = (
        Index(
            "ix_one_open_item_per_candidate_reason", "tenant_id", "candidate_id", "queue_reason", unique=True,
            sqlite_where=text("status = 'OPEN'"), mssql_where=text("status = 'OPEN'"),
        ),
    )
