from sqlalchemy import JSON, Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func

from app.models.base import Base


class InvoiceAutomationDecision(Base):
    """What auto-invoicing decided for one project and billing period: SENT (generated,
    auto-approved, emailed to the client's accounts contact), HELD (generated but an
    anomaly needs finance), or SKIPPED (already invoiced by hand). The audit trail for
    every invoice no person approved."""
    __tablename__ = "invoice_automation_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    project_id = Column(String(512), ForeignKey("projects.id"), nullable=False, index=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    invoice_id = Column(String(512), ForeignKey("invoices.id"), nullable=True)
    decision = Column(String(16), nullable=False)
    reasons = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("project_id", "period_start", name="uq_invoice_automation_period"),)
