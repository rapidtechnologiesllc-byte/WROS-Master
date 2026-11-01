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

Who the spend is on (CEO 2026-10-31): every expense says whether it is internal (just the
person -- BD overhead of their BU), on one client, or split across several clients
(`spend_for`). Client spend is stored as ExpenseClientShare rows -- one row at 100% for a
single client -- and the P&L reads the shares, so each client (and its BU and contracting
company) carries its own part. Conference spend points at one shared ExpenseEvent so every
teammate's expenses for the same conference roll up to one event.
"""
import logging
import uuid

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.models.base import Base

def _new_uuid() -> str:
    return str(uuid.uuid4())

EXPENSE_PURPOSES = ("CLIENT_CURRENT", "CLIENT_PROSPECT", "CONFERENCE", "INVESTMENT", "OTHER")
EXPENSE_CATEGORIES = ("TRAVEL", "MEALS", "LODGING", "ENTERTAINMENT", "OTHER")
TRAVEL_TYPES = ("AIRFARE", "GROUND_TRANSPORT", "HOTEL", "MEALS", "OTHER")
EXPENSE_PAYMENT_STATUSES = ("PENDING", "APPROVED", "REIMBURSED")
MANAGER_APPROVAL_STATUSES = ("PENDING", "APPROVED", "REJECTED")
# Who the spend is on: INTERNAL (the person / their BU), CLIENT (one client), SPLIT (several)
SPEND_FOR = ("INTERNAL", "CLIENT", "SPLIT")
FULL_SHARE_BPS = 10000  # 100.00%

# Purposes that require a client_id -- the real fork between "spend on
# a client relationship" (current or prospect) vs. everything else.
CLIENT_DIRECTED_PURPOSES = {"CLIENT_CURRENT", "CLIENT_PROSPECT"}

logger = logging.getLogger(__name__)

class ExpenseRecord(Base):
    __tablename__ = "expense_records"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Derived from the logger's own BU at creation time -- never a
    # freely-editable field, same rule as Client.business_unit_id.
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)
    logged_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=False, index=True)

    purpose = Column(Enum(*EXPENSE_PURPOSES, name="expense_purpose", native_enum=False, create_constraint=True), nullable=False)
    client_id = Column(String(512), ForeignKey("clients.id"), nullable=True, index=True)
    conference_name = Column(String(512), nullable=True)  # the event's name, kept for display
    event_id = Column(String(512), ForeignKey("expense_events.id", ondelete="SET NULL"), nullable=True, index=True)
    spend_for = Column(String(20), nullable=True)  # SPEND_FOR; NULL only on rows not yet backfilled
    investment_label = Column(String(512), nullable=True)

    expense_category = Column(Enum(*EXPENSE_CATEGORIES, name="expense_category", native_enum=False, create_constraint=True), nullable=False)
    travel_type = Column(Enum(*TRAVEL_TYPES, name="expense_travel_type", native_enum=False, create_constraint=True), nullable=True)

    # Groups multiple line items from one door-to-door trip (a flight +
    # hotel + Uber + meals) without a separate trip table -- matches the
    # real ledger's flat, one-row-per-line-item shape.
    trip_label = Column(String(512), nullable=True)

    amount_usd_cents = Column(Integer, nullable=False)
    location = Column(String(512), nullable=True)
    description = Column(Text, nullable=True)
    receipt_ref = Column(String(300), nullable=False)  # PRIORITY-3: Receipt is mandatory
    expense_date = Column(Date, nullable=False)
    # Attached receipt and its automatic check (app.services.expense_receipt_service):
    # NOT_ATTACHED -> MATCHED (manager step auto-approved) | MISMATCH | UNREADABLE (manager reviews)
    receipt_file_path = Column(String(1024), nullable=True)
    receipt_content_type = Column(String(100), nullable=True)
    receipt_check_status = Column(String(20), nullable=False, default="NOT_ATTACHED", server_default="NOT_ATTACHED")
    receipt_check_detail = Column(Text, nullable=True)  # JSON: what the receipt says + why it matched or not

    # PRIORITY-3: Manager approval step (Employee → Manager → Finance)
    manager_approval_status = Column(
        Enum(*MANAGER_APPROVAL_STATUSES, name="expense_manager_approval_status", native_enum=False, create_constraint=True),
        nullable=False, default="PENDING",
    )
    manager_approved_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    manager_approved_at = Column(DateTime, nullable=True)

    # Finance approval (after manager approval)
    payment_status = Column(
        Enum(*EXPENSE_PAYMENT_STATUSES, name="expense_payment_status", native_enum=False, create_constraint=True),
        nullable=False, default="PENDING",
    )
    approved_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    client = relationship("Client", foreign_keys=[client_id])
    event = relationship("ExpenseEvent", foreign_keys=[event_id])
    client_shares = relationship("ExpenseClientShare", cascade="all, delete-orphan",
                                 order_by="ExpenseClientShare.id")

    @property
    def client_name(self):
        return self.client.company_name if self.client else None


class ExpenseEvent(Base):
    """One conference or event the whole team shares (CEO 2026-10-31): "NAMIC 2026" and
    "Namic-2026" are the same event. `name_key` is the name lower-cased with punctuation,
    spaces and the year removed; (tenant, name_key, year) is unique. A merged event points
    at the event it was merged into and is no longer offered."""
    __tablename__ = "expense_events"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(300), nullable=False)
    name_key = Column(String(300), nullable=False)
    year = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    location = Column(String(300), nullable=True)
    merged_into_id = Column(String(512), ForeignKey("expense_events.id", ondelete="SET NULL"), nullable=True)
    created_by_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("tenant_id", "name_key", "year", name="uq_expense_event_key_per_tenant"),)


class ExpenseClientShare(Base):
    """The part of an expense carried by one client: 100% for a single client, or one line of
    a split. The shares of an expense add up to 100% and to its full amount."""
    __tablename__ = "expense_client_shares"

    id = Column(Integer, primary_key=True, autoincrement=True)
    expense_id = Column(String(512), ForeignKey("expense_records.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(String(512), ForeignKey("clients.id"), nullable=False, index=True)
    share_bps = Column(Integer, nullable=False)  # basis points; 10000 = 100%
    amount_usd_cents = Column(Integer, nullable=False)

    client = relationship("Client", foreign_keys=[client_id])

    @property
    def company_name(self):
        return self.client.company_name if self.client else None

    __table_args__ = (UniqueConstraint("expense_id", "client_id", name="uq_expense_client_share"),)
