"""One row per person and occasion: what makes a re-run of the occasion emails harmless."""
import uuid

from sqlalchemy import Column, Date, DateTime, Index, String, func

from app.models.base import Base


class OccasionEmail(Base):
    __tablename__ = "occasion_emails"
    __table_args__ = (Index("uq_occasion_email", "person_id", "kind", "occasion_key", unique=True),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id = Column(String(512), nullable=False)
    kind = Column(String(64), nullable=False)
    occasion_key = Column(String(64), nullable=False)
    occasion_date = Column(Date, nullable=False)
    sent_from = Column(String(320), nullable=True)
    sent_at = Column(DateTime, server_default=func.now())
