import logging
"""Business Unit Model"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.models.base import Base

logger = logging.getLogger(__name__)

class BusinessUnit(Base):
    """
    Business Unit (BU) - Geographic or organizational division
    Examples: NA (North America), EU (Europe), APAC (Asia-Pacific)
    """
    __tablename__ = "business_units"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    # PRODUCTION SAFETY: tenant_id MUST be set, never allow None. Default to 1
    # All new business units get tenant_id from creator's tenant (fallback to 1)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, server_default="1", default=1, index=True)

    # Basic info
    name = Column(String(512), nullable=False, index=True)
    display_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    bu_code = Column(String(20), nullable=True, unique=True)  # e.g., "NA", "EU", "APAC"

    # Leadership
    manager_id = Column(String(512), ForeignKey("users.UserID"), nullable=True)

    # Status
    active = Column(Boolean, nullable=False, default=True)

    # Audit
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    manager = relationship("Users", foreign_keys=[manager_id], lazy="select")
