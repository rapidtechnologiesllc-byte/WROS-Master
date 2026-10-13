from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.models.base import Base


class PipelineEmail(Base):
    """One email the hiring pipeline sends a candidate (onboarding started, documents
    outstanding, BGV consent...). The body is built at send time (it carries a portal link,
    which is never stored); the Graph draft id makes a retry re-send the same draft."""
    __tablename__ = "pipeline_emails"

    id = Column(String(255), primary_key=True)  # the queue task id: one row per intended email
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False, index=True)
    kind = Column(String(32), nullable=False)
    ref = Column(String(255), nullable=True)
    graph_id = Column(String(512), nullable=True)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
