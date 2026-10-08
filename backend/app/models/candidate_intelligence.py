from sqlalchemy import JSON, Column, Date, DateTime, Float, Integer, String, Text, UniqueConstraint, func

from app.models.base import Base


class CandidateIntelligenceProfile(Base):
    """Autonomous enrichment state for one LinkedIn pipeline item.

    Kept out of LinkedInPipelineStatus on purpose: that is a native Postgres
    enum and create_all never alters an existing type.
    """
    __tablename__ = "candidate_intelligence_profiles"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_id = Column(String(64), nullable=False, unique=True, index=True)
    candidate_id = Column(String(512), nullable=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    linkedin_slug = Column(String(200), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="PENDING", index=True)
    profile_json = Column(JSON, nullable=True)  # {field: {value, source, confidence}}
    identity_score = Column(Float, nullable=True)
    passive_score = Column(Float, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class EnrichmentSourceUsage(Base):
    """Per-source daily call counter, so free-tier quotas are never exceeded."""
    __tablename__ = "enrichment_source_usage"
    __table_args__ = (UniqueConstraint("source", "usage_date", name="uq_enrichment_source_day"),)

    id = Column(Integer, primary_key=True)
    source = Column(String(64), nullable=False)
    usage_date = Column(Date, nullable=False)
    count = Column(Integer, nullable=False, default=0)
