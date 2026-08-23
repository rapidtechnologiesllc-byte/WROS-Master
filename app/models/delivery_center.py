"""Delivery Center Model - Physical or virtual centers where work is delivered"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.models.base import Base


class DeliveryCenter(Base):
    """
    Delivery Center - Physical or virtual location where work is delivered
    Examples: Bangalore, Delhi, Chennai, Remote, etc.
    """
    __tablename__ = "delivery_centers"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # Basic info
    name = Column(String(150), nullable=False, index=True)
    code = Column(String(50), nullable=True, unique=True)  # e.g., "BNG", "DEL", "CHN", "REMOTE"
    description = Column(Text, nullable=True)
    location = Column(String(200), nullable=True)  # City or location description

    # Contact
    contact_email = Column(String(150), nullable=True)
    contact_phone = Column(String(20), nullable=True)

    # Status
    active = Column(Boolean, nullable=False, default=True)

    # Audit
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
