"""
S-029/HRMS-0429 -- Skill Extraction & Tagging from Resume.

candidate_skill_tags: genuinely new table (like S-028's resume-parsed
table) -- a many-rows-per-candidate tagging structure with its own
dedupe/unique semantics doesn't fit any existing structure. Integer-PK
+ String(50) UserID-as-tenant_id convention, matching every other new
table this round.
"""
from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, func

from app.models.base import Base

SKILL_TAG_SOURCES = ("RESUME", "CONVERSATION", "MANUAL")


class CandidateSkillTag(Base):
    __tablename__ = "candidate_skill_tags"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(256), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(256), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)

    skill_canonical = Column(String(256), nullable=False)
    skill_raw = Column(String(256), nullable=True)
    source = Column(String(20), nullable=False, server_default="RESUME")
    confidence = Column(Float, nullable=False, server_default="1.0")

    added_at = Column(DateTime(timezone=False), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "candidate_id", "skill_canonical", name="uq_candidate_skill_tag"),
        Index("ix_candidate_skill_tags_lookup", "tenant_id", "candidate_id", "skill_canonical"),
    )
