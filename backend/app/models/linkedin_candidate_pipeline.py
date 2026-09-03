"""
LinkedIn Candidate Pipeline Model

Tracks candidates queued from LinkedIn URLs for manual recruiter outreach.
Enables deduplication and workflow management.
"""
from sqlalchemy import Column, String, DateTime, UUID, Boolean, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import uuid
from datetime import datetime
import enum

from app.models.base import Base

class LinkedInPipelineStatus(str, enum.Enum):
    PENDING_CONNECTION = "PENDING_CONNECTION"
    CONNECTED = "CONNECTED"
    PHONE_COLLECTED = "PHONE_COLLECTED"
    IMPORTED_TO_THUNDER = "IMPORTED_TO_THUNDER"

class LinkedInCandidatePipeline(Base):
    __tablename__ = "linkedin_candidate_pipeline"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # LinkedIn Data
    linkedin_url = Column(String(500), nullable=False, unique=True, index=True)
    linkedin_profile_slug = Column(String(200), nullable=False)

    # Status Tracking
    status = Column(SQLEnum(LinkedInPipelineStatus), default=LinkedInPipelineStatus.PENDING_CONNECTION, index=True)

    # Assignment
    assigned_to_user_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)  # User doing manual outreach
    created_by_user_id = Column(PG_UUID(as_uuid=True), nullable=False)  # User who added to queue

    # Contact Information (collected manually)
    phone_number = Column(String(20), nullable=True)
    candidate_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)  # Links to actual candidate once imported

    # Timeline
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    connected_at = Column(DateTime, nullable=True)
    imported_at = Column(DateTime, nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Audit
    tenant_id = Column(String(36), nullable=True, index=True)
