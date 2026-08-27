"""Revenue Recognition Model - Tracks when revenue is recognized from invoices"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.models.base import Base

def _new_uuid() -> str:
    return str(uuid.uuid4())

RECOGNITION_TYPES = ("FULL", "PARTIAL", "DEFERRED")
RECOGNITION_STATUS = ("RECOGNIZED", "PENDING", "REVERSED")

class RevenueRecognition(Base):
    """Track revenue recognition events from invoices"""
    __tablename__ = "revenue_recognitions"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Link to invoice
    invoice_id = Column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)

    # Revenue details
    amount = Column(Float, nullable=False)  # Amount recognized
    currency = Column(String(3), default="USD")
    recognition_type = Column(
        Enum(*RECOGNITION_TYPES, name="revenue_recognition_type", native_enum=False),
        default="FULL"
    )
    status = Column(
        Enum(*RECOGNITION_STATUS, name="revenue_recognition_status", native_enum=False),
        default="RECOGNIZED"
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    recognized_at = Column(DateTime, nullable=True)
    recognized_by = Column(String(255), nullable=True)

    # Relationships
    invoice = relationship("Invoice", foreign_keys=[invoice_id])

    def __repr__(self):
        return f"<RevenueRecognition {self.id}: {self.amount} {self.currency} ({self.status})>"
