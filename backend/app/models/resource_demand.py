"""Resource Demand Model - Track resource needs and fulfillment"""
import uuid
from datetime import datetime, date

from sqlalchemy import Column, String, Integer, DateTime, Date, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship

from app.models.base import Base

def _new_uuid() -> str:
    return str(uuid.uuid4())

DEMAND_STATUS = ("OPEN", "PARTIALLY_FULFILLED", "FULFILLED", "CLOSED", "CANCELLED")

class ResourceDemand(Base):
    """Track resource demand across the organization"""
    __tablename__ = "resource_demands"

    id = Column(String(256), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Resource details
    resource_type = Column(String(256), nullable=False, index=True)  # DEVELOPER, QA, DESIGNER, etc.
    quantity_needed = Column(Integer, nullable=False, default=0)
    quantity_fulfilled = Column(Integer, nullable=False, default=0)

    # Timeline
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    # Organization context
    business_unit_id = Column(String(256), ForeignKey("business_units.id"), nullable=False, index=True)
    project_id = Column(String(256), ForeignKey("projects.id"), nullable=True, index=True)

    # Status tracking
    status = Column(
        Enum(*DEMAND_STATUS, name="demand_status", native_enum=False),
        default="OPEN",
        index=True
    )
    closure_reason = Column(String(256), nullable=True)

    # Audit fields
    created_by = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    adjusted_by = Column(String(256), nullable=True)
    adjusted_at = Column(DateTime, nullable=True)

    closed_by = Column(String(256), nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    business_unit = relationship("BusinessUnit", foreign_keys=[business_unit_id])

    def __repr__(self):
        return f"<ResourceDemand {self.id}: {self.resource_type} x{self.quantity_needed} ({self.status})>"
