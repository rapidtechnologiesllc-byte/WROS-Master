"""Delivery Center Model - Physical or virtual centers where work is delivered"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Index
from sqlalchemy.orm import relationship
from app.models.base import Base


class DeliveryCenter(Base):
    """
    Delivery Center - Physical or virtual location where an employee reports from
    Examples: Bangalore, Delhi, Chennai, Hyderabad, Remote

    Employees select which delivery center they are assigned to.
    This is organizational location, separate from work_location (REMOTE/ONSITE/HYBRID).
    """
    __tablename__ = "delivery_centers"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # Basic info
    name = Column(String(150), nullable=False, index=True)  # e.g., "Bangalore", "Delhi", "Remote"
    code = Column(String(50), nullable=True, unique=True)  # e.g., "BNG", "DEL", "CHN", "HYD", "REM"
    description = Column(Text, nullable=True)
    location = Column(String(200), nullable=True)  # City or location description

    # Contact (for center management)
    contact_email = Column(String(150), nullable=True)
    contact_phone = Column(String(20), nullable=True)

    # Status
    active = Column(Boolean, nullable=False, default=True, index=True)

    # Audit
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employees = relationship("Employee", back_populates="delivery_center", foreign_keys="Employee.delivery_center_id")

    __table_args__ = (
        Index("ix_delivery_centers_tenant_id", "tenant_id"),
    )

    def __repr__(self) -> str:
        return f"<DeliveryCenter id={self.id} name={self.name!r} code={self.code!r}>"
