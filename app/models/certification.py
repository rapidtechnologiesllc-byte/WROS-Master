"""Certification and skill tracking for employees."""
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Enum, func
from sqlalchemy.orm import relationship
from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


CERTIFICATION_LEVELS = ("Foundation", "Intermediate", "Advanced", "Expert")
CERT_STATUS = ("Active", "Expired", "Pending", "Revoked")


class Certification(Base):
    """Certification template (e.g., "Guidewire Core", "Java Advanced")."""
    __tablename__ = "certifications"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    cert_name = Column(String(200), nullable=False)  # e.g., "Guidewire Core Certification"
    cert_code = Column(String(50), unique=True, nullable=False)  # e.g., "GW-CORE"
    description = Column(String(500), nullable=True)
    level = Column(Enum(*CERTIFICATION_LEVELS, name="cert_level", native_enum=False), default="Foundation")

    # Validity period (in months)
    validity_months = Column(Integer, default=24)

    # Whether this is required for core certifications tracking
    is_core_certification = Column(Boolean, default=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    employee_certs = relationship("EmployeeCertification", back_populates="certification", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Certification {self.cert_code}: {self.cert_name}>"


class EmployeeCertification(Base):
    """Track certifications earned by employees."""
    __tablename__ = "employee_certifications"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)
    certification_id = Column(String(36), ForeignKey("certifications.id"), nullable=False, index=True)
    bu_context_id = Column(Integer, ForeignKey("business_unit_context.id"), nullable=True, index=True)

    # Status tracking
    status = Column(Enum(*CERT_STATUS, name="emp_cert_status", native_enum=False), default="Active")

    # Date achieved
    earned_date = Column(DateTime, nullable=False)

    # Expiry tracking
    expires_date = Column(DateTime, nullable=True)

    # Certification details
    cert_number = Column(String(100), nullable=True)  # Certificate ID from issuer
    issuer = Column(String(200), nullable=True)  # e.g., "Guidewire University"

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    certification = relationship("Certification", back_populates="employee_certs")

    def __repr__(self) -> str:
        return f"<EmployeeCertification emp={self.employee_id} cert={self.certification_id}>"
