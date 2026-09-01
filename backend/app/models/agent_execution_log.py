"""
S-066/HRMS-0466 -- Supervisor Agent, agent_execution_log.

Real architecture adaptation (per Avinash's explicit direction,
2026-08-04): batch process, no Redis. This codebase's scheduler
(app.core.scheduler) runs as a single in-process AsyncIOScheduler --
there is exactly one process ever running SUPERVISOR_AGENT_JOB, so the
race the spec's Redis distributed-locking step protects against
(two concurrent cycles acting on the same candidate) cannot occur by
construction. See supervisor_agent_service's own module docstring for
the full reasoning and what this story builds instead: a real
observability/coordination rollup over the ~18 already-independent,
already-correctly-gated scheduled jobs this codebase runs (each one
already re-evaluates fresh DB state every cycle -- the "log and retry
till complete" mechanism Avinash asked for is exactly what those jobs
already do), not a second dispatch layer that reimplements their logic.

Integer autoincrement PK + String(50) UserID-as-tenant_id convention,
matching every other new table this round, not the spec's UUID
assumption.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class AgentExecutionLog(Base):
    __tablename__ = "agent_execution_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=True, index=True)
    agent_name = Column(String(512), nullable=False)
    action_taken = Column(String(512), nullable=False)
    action_data = Column(JSON, nullable=True)
    execution_at = Column(DateTime(timezone=False), server_default=func.now(), index=True)
    duration_ms = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=False, server_default="1")
    error_message = Column(Text, nullable=True)

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
