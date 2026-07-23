"""
S-076/HRMS-0476 -- Conversation Audit Log.

A compliance-grade, insert-only record of significant AI/HR actions on a
candidate conversation -- distinct from ConversationEvent (candidate_ai.py),
which is the operational event log everything else in EPIC-04 reads/writes
freely. This table exists specifically so a compliance question ("who
changed ownership of this conversation, and when") has one authoritative
answer that nothing else is allowed to rewrite.

Scope for this round, per the doc's own "Depends On: all EPIC-04 stories"
note -- wired only to the two conversation-level actions genuinely in this
epic's own surface: ownership changes (take-over/hand-back) and manual
message sends (see app/api/v1/endpoints/ai_agent.py). The doc also lists
offer releases (HRMS-0454/0456), override approvals (HRMS-P604), and
state-machine transitions (HRMS-0418) as audit points -- those belong to
other epics/stories not yet built and are deliberately not wired here;
wiring them means touching that epic's own code, which is out of scope
for an EPIC-04 round.

DB-level INSERT-only enforcement (the doc's BR-01, via a restricted DB
role) isn't practical to add generically across this codebase's SQLite
test / SQL Server prod split -- enforced at the application level only:
no update/delete function exists anywhere in audit_log_service.py.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, func, Index

from app.models.base import Base

AUDIT_ACTOR_TYPES = ("AI", "RECRUITER", "HR", "SYSTEM", "CANDIDATE")


class ConversationAuditLog(Base):
    __tablename__ = "conversation_audit_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(
        String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True,
    )
    candidate_id = Column(
        String(50), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True,
    )
    # NO ACTION, not SET NULL -- SQL Server rejects SET NULL here because
    # candidates->candidate_conversations->conversation_id and
    # candidates->candidate_id (CASCADE, direct) are two cascade paths
    # reaching this table from the same root, which it refuses to order
    # deterministically ("may cause cycles or multiple cascade paths").
    conversation_id = Column(
        Integer, ForeignKey("candidate_conversations.id", ondelete="NO ACTION"), nullable=True, index=True,
    )

    audit_event_type = Column(String(100), nullable=False)
    audit_event_description = Column(Text, nullable=False)

    actor_type = Column(String(20), nullable=False)
    actor_id = Column(String(100), nullable=False)

    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=False), server_default=func.now())

    __table_args__ = (
        Index("ix_conversation_audit_log_tenant_candidate_created", "tenant_id", "candidate_id", "created_at"),
    )
