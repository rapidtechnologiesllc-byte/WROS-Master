"""Resume-parsing feedback and SLM model versions (app.services.slm_feedback_engine).

Declared here, in app.models, so that importing app.models registers the tables with
Base.metadata and every Base.metadata.create_all creates them (they used to live in the service
module, registered only by an explicit import in db_contract)."""
from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, func

from app.models.base import Base


class SLMFeedback(Base):
    """Database table for collecting parsing corrections"""
    __tablename__ = "slm_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feedback_session_id = Column(String(100), nullable=False, index=True, unique=True)
    field_name = Column(String(100), nullable=False, index=True)  # skills, title, employer, etc.
    parsed_value = Column(String(1000), nullable=True)
    corrected_value = Column(String(1000), nullable=True)
    confidence_score = Column(Float, nullable=True)  # 0.0-1.0
    parsed_at = Column(DateTime, default=func.now(), index=True)
    corrected_at = Column(DateTime, default=func.now(), index=True)
    is_useful = Column(Integer, default=1)  # 1=useful, 0=noisy
    feedback_type = Column(String(50), default="correction")  # correction, validation, edge_case

class SLMModelVersion(Base):
    """Track SLM model versions and performance"""
    __tablename__ = "slm_model_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50), unique=True, index=True)  # e.g., "1.0", "1.1", "2.0"
    training_examples = Column(Integer)  # How many labeled examples used
    accuracy_overall = Column(Float)  # 0-100%
    accuracy_by_field = Column(JSON)  # {"skills": 85, "title": 92, ...}
    created_at = Column(DateTime, default=func.now())
    is_active = Column(Integer, default=0)  # 1 = currently in production
    deployment_date = Column(DateTime, nullable=True)
    rollback_available = Column(Integer, default=1)  # Can we roll back?
