"""Employee KPI management with certification targets and scoring."""
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Float, func, Text
from sqlalchemy.orm import relationship
from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class EmployeeKPITarget(Base):
    """Target certifications and goals for an employee."""
    __tablename__ = "employee_kpi_targets"

    id = Column(String(256), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    employee_id = Column(String(256), ForeignKey("employees.id"), nullable=False, index=True)
    certification_id = Column(String(256), ForeignKey("certifications.id"), nullable=False, index=True)
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)

    # Target deadline for certification
    target_date = Column(DateTime, nullable=False)

    # Weight for KPI calculation (e.g., 0.1 = 10% of total KPI)
    weight = Column(Float, default=0.1)

    # Is this certification achieved
    is_achieved = Column(Boolean, default=False)

    # Achievement date (when certified)
    achieved_date = Column(DateTime, nullable=True)

    # Status: PENDING, ACHIEVED, OVERDUE, WAIVED
    status = Column(String(20), default="PENDING")

    # Notes (e.g., why waived)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    certification = relationship("Certification")

    def __repr__(self) -> str:
        return f"<EmployeeKPITarget emp={self.employee_id} cert={self.certification_id} status={self.status}>"


class EmployeeKPIScore(Base):
    """Aggregated KPI scores for employees."""
    __tablename__ = "employee_kpi_scores"

    id = Column(String(256), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    employee_id = Column(String(256), ForeignKey("employees.id"), nullable=False, index=True, unique=True)
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)

    # Overall KPI score (0-100)
    overall_score = Column(Float, default=0.0)

    # Certification KPI component (0-100)
    certification_score = Column(Float, default=0.0)

    # Performance component (0-100)
    performance_score = Column(Float, default=0.0)

    # Utilization component (0-100)
    utilization_score = Column(Float, default=0.0)

    # Last calculated
    last_calculated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])

    def __repr__(self) -> str:
        return f"<EmployeeKPIScore emp={self.employee_id} overall={self.overall_score}>"
