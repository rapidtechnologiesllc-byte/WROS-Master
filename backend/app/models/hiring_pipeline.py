from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, func, text

from app.models.base import Base

# The CEO-mandated hiring order. A candidate is in the furthest stage whose entry facts hold.
STAGES = ("SCREEN", "L1", "L2", "OFFER", "ACCEPTED", "ONBOARDING", "BGV", "BENCH",
          "SUBMITTED", "CLIENT_SELECTED", "CLIENT_ONBOARDING", "ALLOCATED")
CLOSED_STAGES = ("REJECTED", "WITHDRAWN")


class HiringPipeline(Base):
    """One candidate's journey from screening to client allocation. Its stage is derived
    from facts (interview verdicts, offer, documents, BGV, employee, submission, client
    onboarding), never set by hand, so re-evaluating is always safe."""
    __tablename__ = "hiring_pipelines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False, index=True)
    job_id = Column(String(512), ForeignKey("jobs.jobID"), nullable=True)
    stage = Column(String(24), nullable=False, default="SCREEN", index=True)
    stage_entered_at = Column(DateTime, server_default=func.now())
    screen_required = Column(Boolean, nullable=False, default=True)
    screen_decision = Column(String(8), nullable=True)  # PASS / SKIP / FAIL
    screen_decided_by = Column(String(512), nullable=True)  # UserID or "system"
    offer_letter_id = Column(Integer, ForeignKey("offer_letters.id"), nullable=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=True)
    submission_id = Column(String(512), ForeignKey("submissions.id"), nullable=True)
    blockers = Column(JSON, nullable=True)
    grandfathered = Column(Boolean, nullable=False, default=False)
    backfilled = Column(Boolean, nullable=False, default=False)
    last_evaluated_at = Column(DateTime, nullable=True, index=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_one_open_pipeline_per_candidate", "candidate_id", unique=True,
              postgresql_where=text("closed_at IS NULL")),
    )


class HiringPipelineEvent(Base):
    __tablename__ = "hiring_pipeline_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_id = Column(Integer, ForeignKey("hiring_pipelines.id", ondelete="CASCADE"), nullable=False, index=True)
    from_stage = Column(String(24), nullable=True)
    to_stage = Column(String(24), nullable=False)
    trigger = Column(String(64), nullable=True)
    ref = Column(String(512), nullable=True)
    actor = Column(String(512), nullable=False, default="system")
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
