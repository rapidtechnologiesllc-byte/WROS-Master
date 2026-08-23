"""Partner Model - Organizations that partner with BlitzenX"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.models.base import Base


class Partner(Base):
    """
    Partner - External organization/vendor
    Examples: Accenture, TCS, Infosys, etc.
    """
    __tablename__ = "partners"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # Basic info
    name = Column(String(200), nullable=False, index=True)
    code = Column(String(50), nullable=True, unique=True)  # e.g., "ACCENTURE", "TCS"
    description = Column(Text, nullable=True)
    website = Column(String(255), nullable=True)

    # Contact
    contact_email = Column(String(150), nullable=True)
    contact_phone = Column(String(20), nullable=True)

    # Status
    active = Column(Boolean, nullable=False, default=True)

    # Audit
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
