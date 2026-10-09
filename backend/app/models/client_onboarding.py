from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, func

from app.models.base import Base

CLIENT_ONBOARDING_STATUSES = ("PENDING", "START_CONFIRMED", "STARTED", "CANCELLED")


class ClientOnboarding(Base):
    """After a client selects a candidate (submission OFFER_EXTENDED): the client's own
    onboarding until they confirm a start date. The employee is placed and allocated to the
    client's project on that confirmed date, not before."""
    __tablename__ = "client_onboardings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    submission_id = Column(String(512), ForeignKey("submissions.id"), nullable=False, unique=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=True)
    demand_id = Column(String(512), ForeignKey("jobs.jobID"), nullable=True)
    client_id = Column(String(512), ForeignKey("clients.id"), nullable=True)
    status = Column(String(16), nullable=False, default="PENDING", index=True)
    proposed_start_date = Column(Date, nullable=True)
    confirmed_start_date = Column(Date, nullable=True)
    confirmed_by = Column(String(512), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    allocation_id = Column(String(512), ForeignKey("employee_allocations.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
