"""Location (Delivery Center) model for workforce management."""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class Location(Base):
    """Delivery Centers / Work Locations"""
    __tablename__ = "locations"

    id = Column(String(36), primary_key=True, default=lambda: str(__import__('uuid').uuid4()))
    tenant_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    city = Column(String(255), nullable=True)
    country = Column(String(255), nullable=True)
    location_type = Column(String(100), nullable=True)
    headcount = Column(Integer, default=0)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Location(id={self.id}, name={self.name}, city={self.city})>"
