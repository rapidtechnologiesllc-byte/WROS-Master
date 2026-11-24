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

BU attribution is derived from the person's business unit at creation time (their login's, else
their employee record's), never a caller-supplied field -- same attribution-locking discipline as
app.services.client_service.create_client().

On behalf (2026-11-24): Accounts uploads receipts for employees. logged_by_user_id is then the
employee the expense is FOR -- its approvals, emails, history and P&L follow them -- and
uploaded_by_user_id is who uploaded it (audit). Neither may approve it.

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
    # Accounts uploading it for the employee above; empty when they logged it themselves
    uploaded_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True, index=True)

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
    # The visit or trip this line belongs to (CEO 2026-11-14): one receipt, one line, grouped by visit
    visit_id = Column(String(512), ForeignKey("expense_visits.id", ondelete="SET NULL"), nullable=True, index=True)

    amount_usd_cents = Column(Integer, nullable=False)
    location = Column(String(512), nullable=True)
    description = Column(Text, nullable=True)
    receipt_ref = Column(String(300), nullable=False)  # PRIORITY-3: Receipt is mandatory
    expense_date = Column(Date, nullable=False)  # the first day; the P&L counts the expense on this date
    expense_end_date = Column(Date, nullable=True)  # the last day, when it covers several (a client visit)
    # The automatic check over all its receipts (app.services.expense_receipt_service); the file
    # columns point at the first receipt, every receipt is an ExpenseReceipt:
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
    manager_review_note = Column(Text, nullable=True)  # why it was rejected, for the person who logged it

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
    logged_by = relationship("Users", foreign_keys=[logged_by_user_id])
    uploaded_by = relationship("Users", foreign_keys=[uploaded_by_user_id])
    receipts = relationship("ExpenseReceipt", cascade="all, delete-orphan",
                            order_by="ExpenseReceipt.created_at, ExpenseReceipt.id")
    edits = relationship("ExpenseEdit", cascade="all, delete-orphan", order_by="ExpenseEdit.id")
    visit = relationship("ExpenseVisit", foreign_keys=[visit_id])

    @property
    def visit_name(self):
        return self.visit.name if self.visit else None

    @property
    def logged_by_name(self):
        return (self.logged_by.UserName or self.logged_by.UserEmail) if self.logged_by else None

    @property
    def client_name(self):
        return self.client.company_name if self.client else None

    @property
    def uploaded_by_name(self):
        return (self.uploaded_by.UserName or self.uploaded_by.UserEmail) if self.uploaded_by else None


class ExpenseReceipt(Base):
    """One receipt of an expense (CEO 2026-11-06: a transaction can have several). `reading` is what
    the file says (JSON, app.services.expense_receipt_reader); `read_error` why it couldn't be read."""
    __tablename__ = "expense_receipts"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    expense_id = Column(String(512), ForeignKey("expense_records.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(300), nullable=True)
    file_path = Column(String(1024), nullable=False)
    content_type = Column(String(100), nullable=True)
    reading = Column(Text, nullable=True)
    read_error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class ExpenseEdit(Base):
    """What changed on an expense after it was logged, and who changed it: the reviewer sees this."""
    __tablename__ = "expense_edits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    expense_id = Column(String(512), ForeignKey("expense_records.id", ondelete="CASCADE"), nullable=False, index=True)
    changed_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    summary = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    changed_by = relationship("Users", foreign_keys=[changed_by_user_id])

    @property
    def changed_by_name(self):
        return (self.changed_by.UserName or self.changed_by.UserEmail) if self.changed_by else None


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


class ExpenseVisit(Base):
    """One visit, trip or event someone spent on (CEO 2026-11-14: "everything related to that visit should be
    grouped and individual itemized rows should be created for each receipt"). It holds what every line of the
    visit shares: why it was spent and who carries it. Each receipt becomes its own expense line (ExpenseRecord
    with visit_id), first waiting as an ExpenseVisitDraft until its person describes it. Client splits are
    shares in percent, so each line splits the same way whatever its amount."""
    __tablename__ = "expense_visits"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    owner_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=False, index=True)
    name = Column(String(512), nullable=False)
    purpose = Column(Enum(*EXPENSE_PURPOSES, name="expense_visit_purpose", native_enum=False, create_constraint=True),
                     nullable=False)
    spend_for = Column(String(20), nullable=False)  # SPEND_FOR
    client_id = Column(String(512), ForeignKey("clients.id"), nullable=True)
    client_splits = Column(Text, nullable=True)  # JSON [{"client_id", "percent"}] when spend_for is SPLIT
    event_id = Column(String(512), ForeignKey("expense_events.id", ondelete="SET NULL"), nullable=True)
    investment_label = Column(String(512), nullable=True)
    location = Column(String(512), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    client = relationship("Client", foreign_keys=[client_id])
    event = relationship("ExpenseEvent", foreign_keys=[event_id])
    lines = relationship("ExpenseRecord", foreign_keys="ExpenseRecord.visit_id",
                         order_by="ExpenseRecord.expense_date, ExpenseRecord.created_at", viewonly=True)
    drafts = relationship("ExpenseVisitDraft", cascade="all, delete-orphan",
                          order_by="ExpenseVisitDraft.created_at, ExpenseVisitDraft.id")


class ExpenseVisitDraft(Base):
    """A receipt added to a visit that is not yet a line: its person still says what it was for. Not in the P&L,
    not with any manager. `reading` is what the receipt says (JSON), to fill in the amount and date."""
    __tablename__ = "expense_visit_drafts"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    visit_id = Column(String(512), ForeignKey("expense_visits.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(300), nullable=True)
    file_path = Column(String(1024), nullable=False)
    content_type = Column(String(100), nullable=False)
    reading = Column(Text, nullable=True)
    read_error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


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
