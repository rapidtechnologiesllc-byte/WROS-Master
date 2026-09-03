"""
import logging
S-055/HRMS-0455 -- Offer FAQ Bot.

offer_faq_entries: genuinely new table -- the real, honest substitute
for the spec's fictional `system_configuration` table (no such table
exists anywhere in this codebase; the identical gap has already been
flagged by every prior story that assumed one, e.g. S-020/S-041's
threshold constants). One row per (tenant, topic); admin-editability
is explicitly out of scope this round ("What NOT to build: no
recruiter FAQ management UI") so there is no endpoint to write these
yet -- `offer_faq_service.py`'s own `DEFAULT_FAQ_CONTENT` constant is
the real fallback when no row exists for a tenant+topic, same "no
system_configuration table, module-constant fallback with a
documented gap" convention S-020/S-041 already established.

Real, honest content-approval gap: the seeded/default English copy for
each topic is placeholder wording, not text a Lead BA has actually
signed off on (no Lead BA was available to review it live in this
session) -- same posture S-029's synonym library took for an identical
"no BA available" situation. Flag for real content review before
launch.
"""
import logging
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.models.base import Base

FAQ_TOPICS = (
    "BENEFITS", "JOINING_PROCESS", "FIRST_DAY", "BACKGROUND_CHECK",
    "PROBATION_PERIOD", "LEAVE_POLICY", "REMOTE_WORK_POLICY", "EQUIPMENT_PROVIDED",
)

logger = logging.getLogger(__name__)

class OfferFAQEntry(Base):
    __tablename__ = "offer_faq_entries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    topic = Column(String(512), nullable=False)
    answer_text = Column(Text, nullable=False)

    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")

    __table_args__ = (
        UniqueConstraint("tenant_id", "topic", name="uq_offer_faq_entry"),
    )
