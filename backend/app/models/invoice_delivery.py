from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.models.base import Base

INVOICE_DELIVERY_STATUSES = ("QUEUED", "DRAFTED", "SENT")


class InvoiceDelivery(Base):
    """How an invoice reached the client: one row per invoice. The invoice
    becomes SENT only once this email has actually gone out (or Finance
    records that it was submitted another way, e.g. a client portal)."""
    __tablename__ = "invoice_deliveries"

    invoice_id = Column(String(512), ForeignKey("invoices.id"), primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    channel = Column(String(16), nullable=False, default="EMAIL")  # EMAIL / EXTERNAL
    to_address = Column(String(300), nullable=True)
    status = Column(String(16), nullable=False, default="QUEUED")
    request_count = Column(Integer, nullable=False, default=1)
    mailbox = Column(String(300), nullable=True)
    graph_message_id = Column(String(512), nullable=True)
    requested_by = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    requested_at = Column(DateTime, server_default=func.now())
    sent_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)
