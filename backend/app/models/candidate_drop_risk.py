"""
S-060/HRMS-0460 -- Drop Risk Prediction.

candidate_drop_risk: genuinely new table -- one row per (tenant,
candidate), UPSERTed on every recalculation. Integer-autoincrement PK +
String(50) UserID-as-tenant_id + String(50) candidate_id convention,
matching every other new table this round, not the spec's UUID
assumption.

risk_level is a real, DB-CHECK-constrained enum computed from
drop_risk_score (LOW 0-39, MEDIUM 40-59, HIGH 60-79, CRITICAL 80-100),
same native_enum=False/create_constraint=True convention used
throughout this codebase.
"""
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.models.base import Base

RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


class CandidateDropRisk(Base):
    __tablename__ = "candidate_drop_risk"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True, unique=True)

    drop_risk_score = Column(Integer, nullable=False)
    risk_level = Column(Enum(*RISK_LEVELS, name="candidate_drop_risk_level", native_enum=False, create_constraint=True), nullable=False)
    risk_signals = Column(JSON, nullable=True)
    is_flagged = Column(Boolean, nullable=False, default=False)

    calculated_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")

    __table_args__ = (
        UniqueConstraint("tenant_id", "candidate_id", name="uq_candidate_drop_risk"),
    )
