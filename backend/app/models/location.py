"""Location (Delivery Center) model for workforce management."""
import logging
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4
from app.models.base import Base

logger = logging.getLogger(__name__)

DEFAULT_TENANT_ID = 1
DEFAULT_LOCATION_STATUS = "active"
MAX_STRING_COLUMN_LENGTH = 512


class Location(Base):
    """Delivery Centers / Work Locations"""
    __tablename__ = "locations"

    id = Column(String(MAX_STRING_COLUMN_LENGTH), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, server_default=str(DEFAULT_TENANT_ID), default=DEFAULT_TENANT_ID, index=True)
    name = Column(String(MAX_STRING_COLUMN_LENGTH), nullable=False, index=True)
    city = Column(String(MAX_STRING_COLUMN_LENGTH), nullable=True)
    state = Column(String(MAX_STRING_COLUMN_LENGTH), nullable=True)
    country = Column(String(MAX_STRING_COLUMN_LENGTH), nullable=True)
    location_type = Column(String(MAX_STRING_COLUMN_LENGTH), nullable=True)  # HQ = parent company, Delivery = subsidiary
    # A subsidiary (e.g. BX-IN) belongs to a parent company (e.g. BX-US)
    parent_company_id = Column(String(MAX_STRING_COLUMN_LENGTH), ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True, index=True)
    headcount = Column(Integer, default=0)
    status = Column(String(MAX_STRING_COLUMN_LENGTH), default=DEFAULT_LOCATION_STATUS)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Location(id={self.id}, name={self.name}, city={self.city})>"
