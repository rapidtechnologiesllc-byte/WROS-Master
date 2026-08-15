"""
Partner/BU spend tracking -- Avinash's 2026-08-05 direction: expense
tracking is manual entry, shaped like the real FY26-27 finance
workbook's Expense Ledger (Month/Year/Expense Category/Subcategory/
Employee-Partner/Location/Client/Home BU/Amount/Description/Receipt
Ref/Approved By/Date/Payment Status -- structure only, no real figures
recorded anywhere in this codebase per the standing no-real-data rule).

Refined the same day with the real gap Avinash flagged: "who spent it
and which BU" isn't enough to answer "was this worth it" -- every
expense needs a `purpose` (what it was FOR) and, for client-directed
spend, a `client_id` (which client, even while still a PROSPECT --
Client.status/ClientHistory already track the prospect-to-active
timeline, this reuses it rather than duplicating it).

BU attribution is derived from the logged-by user's own business_unit_id
at creation time, never a caller-supplied field -- same
attribution-locking discipline as app.services.client_service.create_client().
"""
import uuid

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


EXPENSE_PURPOSES = ("CLIENT_CURRENT", "CLIENT_PROSPECT", "CONFERENCE", "INVESTMENT", "OTHER")
EXPENSE_CATEGORIES = ("TRAVEL", "MEALS", "LODGING", "ENTERTAINMENT", "OTHER")
TRAVEL_TYPES = ("AIRFARE", "GROUND_TRANSPORT", "HOTEL", "MEALS", "OTHER")
EXPENSE_PAYMENT_STATUSES = ("PENDING", "APPROVED", "REIMBURSED")
MANAGER_APPROVAL_STATUSES = ("PENDING", "APPROVED", "REJECTED")

# Purposes that require a client_id -- the real fork between "spend on
# a client relationship" (current or prospect) vs. everything else.
CLIENT_DIRECTED_PURPOSES = {"CLIENT_CURRENT", "CLIENT_PROSPECT"}


class ExpenseRecord(Base):
    __tablename__ = "expense_records"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Derived from the logger's own BU at creation time -- never a
    # freely-editable field, same rule as Client.business_unit_id.
    bu_context_id = Column(Integer, ForeignKey("business_unit_context.id"), nullable=True, index=True)
    logged_by_user_id = Column(String(50), ForeignKey("users.UserID"), nullable=False, index=True)

    purpose = Column(Enum(*EXPENSE_PURPOSES, name="expense_purpose", native_enum=False, create_constraint=True), nullable=False)
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=True, index=True)
    conference_name = Column(String(200), nullable=True)
    investment_label = Column(String(200), nullable=True)

    expense_category = Column(Enum(*EXPENSE_CATEGORIES, name="expense_category", native_enum=False, create_constraint=True), nullable=False)
    travel_type = Column(Enum(*TRAVEL_TYPES, name="expense_travel_type", native_enum=False, create_constraint=True), nullable=True)

    # Groups multiple line items from one door-to-door trip (a flight +
    # hotel + Uber + meals) without a separate trip table -- matches the
    # real ledger's flat, one-row-per-line-item shape.
    trip_label = Column(String(200), nullable=True)

    amount_usd_cents = Column(Integer, nullable=False)
    location = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    receipt_ref = Column(String(300), nullable=False)  # PRIORITY-3: Receipt is mandatory
    expense_date = Column(Date, nullable=False)

    # PRIORITY-3: Manager approval step (Employee → Manager → Finance)
    manager_approval_status = Column(
        Enum(*MANAGER_APPROVAL_STATUSES, name="expense_manager_approval_status", native_enum=False, create_constraint=True),
        nullable=False, default="PENDING",
    )
    manager_approved_by = Column(String(50), ForeignKey("users.UserID"), nullable=True)
    manager_approved_at = Column(DateTime, nullable=True)

    # Finance approval (after manager approval)
    payment_status = Column(
        Enum(*EXPENSE_PAYMENT_STATUSES, name="expense_payment_status", native_enum=False, create_constraint=True),
        nullable=False, default="PENDING",
    )
    approved_by = Column(String(50), ForeignKey("users.UserID"), nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    client = relationship("Client", foreign_keys=[client_id])
