"""
import logging
S-061/HRMS-0461 -- AI Activity Feed, read-state tracking.

No new `thunder_activity_feed` denormalized table -- see
app.services.activity_feed_service's module docstring for why: this
codebase's `ConversationEvent` log (immutable, append-only, already
populated by every real Thunder action -- confirmed by this story's own
"Before You Start" note) IS the real activity feed, transformed into
human-readable summaries at read time. The one genuinely new piece of
state this story needs that `ConversationEvent` doesn't have is
per-item "read" tracking (BR-01) -- this sparse table holds ONLY that:
one row per conversation_event actually marked read. No row = unread
(the default), avoiding a wasteful is_read=False row for every one of
the thousands of events this codebase already logs.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.models.base import Base

logger = logging.getLogger(__name__)

class ActivityFeedReadState(Base):
    __tablename__ = "activity_feed_read_state"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    conversation_event_id = Column(Integer, ForeignKey("conversation_events.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    read_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")

    __table_args__ = (
        UniqueConstraint("conversation_event_id", name="uq_activity_feed_read_state_event"),
    )
