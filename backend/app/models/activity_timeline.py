"""
S-216/HRMS-0118 -- Shared Activity Timeline & File Attachment Framework.

Polymorphic (entity_type, entity_id) history table -- BR-0118-01's
sanctioned pattern: any story needing a "what happened" feed writes
here instead of building its own history table.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.models.base import Base

ACTOR_TYPES = ("USER", "SYSTEM", "AI_AGENT")


class ActivityTimeline(Base):
    __tablename__ = "activity_timeline"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # HRMS-0109 -- nullable-first, same reason as every other tenant_id
    # column added this round (safe-upgrade for existing/system rows).
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    entity_type = Column(String(512), nullable=False, index=True)
    entity_id = Column(String(512), nullable=False, index=True)

    actor_type = Column(String(20), nullable=False, default="USER", server_default="USER")
    # Nullable -- a SYSTEM/AI_AGENT-authored entry has no real Users row.
    actor_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=True)

    action = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=False), server_default=func.now(), index=True)
