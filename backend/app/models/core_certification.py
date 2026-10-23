"""Core certification requests (CEO 2026-10-14). An employee is Core-certified once their BU Head
approves: Buddy Program graduated, CORE_CERT_BILLABLE_DAYS approved billable days on Staff Aug
with no escalation raised since. The daily sweep raises a request and an approval task; a
rejection is discussed with Flash and turns into follow-up tasks (follow_up_plan)."""
import uuid

from sqlalchemy import JSON, Column, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text, func, text

from app.models.base import Base

REQUEST_STATUSES = ("PENDING", "APPROVED", "REJECTED", "CLOSED")


class CoreCertificationRequest(Base):
    __tablename__ = "core_certification_requests"

    id = Column(String(512), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)
    bu_head_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    status = Column(Enum(*REQUEST_STATUSES, name="core_certification_status", native_enum=False,
                         create_constraint=True), nullable=False, default="PENDING")
    # audit: the count when the request was raised and the day after the escalation it counts from
    billable_days = Column(Integer, nullable=False)
    counted_from = Column(Date, nullable=True)
    decided_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    # [{"criterion", "days", "owner_user_id", "task_id"}]
    follow_up_plan = Column(JSON, nullable=True)
    # the Flash rejection conversation in progress, kept server-side (owners and dates are trusted)
    chat_state = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        # one open request per employee: two sweeps the same day cannot both raise one
        Index("uq_core_cert_one_pending", "employee_id", unique=True,
              postgresql_where=text("status = 'PENDING'")),
    )
