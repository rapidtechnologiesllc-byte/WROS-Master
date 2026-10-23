"""An escalation raised against an employee (conduct, delivery, client complaint, compliance).
While one is OPEN the employee cannot be submitted to or deployed at a client (CEO 2026-10-14);
only a Director or above resolves it, with a note."""
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text, func

from app.models.base import Base

ESCALATION_SEVERITIES = ("LOW", "MEDIUM", "HIGH")
ESCALATION_STATUSES = ("OPEN", "RESOLVED")


class EmployeeEscalation(Base):
    __tablename__ = "employee_escalations"

    id = Column(String(512), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False)
    reason = Column(Text, nullable=False)
    severity = Column(Enum(*ESCALATION_SEVERITIES, name="employee_escalation_severity", native_enum=False,
                           create_constraint=True), nullable=False, default="MEDIUM")
    status = Column(Enum(*ESCALATION_STATUSES, name="employee_escalation_status", native_enum=False,
                         create_constraint=True), nullable=False, default="OPEN")
    raised_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    raised_at = Column(DateTime, server_default=func.now(), nullable=False)
    resolved_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)

    __table_args__ = (Index("ix_employee_escalations_employee_status", "employee_id", "status"),)
