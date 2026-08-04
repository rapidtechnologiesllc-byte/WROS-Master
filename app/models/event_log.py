"""
S-078/HRMS-0478 -- Event Emission Layer for AI Actions.

Real architecture adaptation (per Avinash's explicit direction,
2026-08-04): "lightweight version" -- a real, queryable event_log
table + EventEmitter.emit(), with no actual message bus/pub-sub layer.
This codebase has no internal event bus and no message broker (Redis/
RabbitMQ/Kafka) anywhere -- there is nothing for "publish to internal
message bus / subscribers" to mean today, and no EPIC-11 agent or
webhook engine (HRMS-1310) exists yet to actually subscribe. Building
a retry queue against zero real subscribers would mean protecting
against a failure mode that cannot occur -- event_retry_queue/RetryJob
are NOT built here; when a real subscriber exists in the future, retry
semantics can be added against that real integration, not invented now.

Integer autoincrement PK + String(50) UserID-as-tenant_id convention,
matching every other new table this round, not the spec's UUID
assumption.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class EventLog(Base):
    __tablename__ = "event_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    event_version = Column(String(10), nullable=False, server_default="v1")
    payload = Column(JSON, nullable=True)
    emitted_at = Column(DateTime(timezone=False), server_default=func.now(), index=True)

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
