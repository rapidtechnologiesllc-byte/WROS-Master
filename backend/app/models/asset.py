"""Asset ledger (CEO 2026-11-10): every device the organisation holds or is responsible for, one row per
item, owned by the IT Admin function.

- Asset: the item, who owns it (one of our companies, a client, a lessor, the employee) and who holds it
  now. A live item is in exactly one of two places (CEO 2026-11-23): in the office (IN_STOCK) or with an
  employee (ASSIGNED). On a courier or at a repair shop is a flag on top of that, never a third place.
  An item leaves the ledger once: lost, retired, or back with its owner (a client's or leased item).
- AssetEvent: the item's whole record from procurement to retirement, one row per thing that happened
  to it (never edited).
- AssetCheckout: the check-out / check-in register. One row per spell with an employee: who, from when,
  how it went out (in person, courier), and when it came back, in what condition (or that it was lost).
  An ASSIGNED item has exactly one open row; an item in the office has none.
- AssetShipment: every courier movement out or back, with carrier and tracking number.
- AssetIssue: a defect on one item, from report to fix (or retirement).
- AssetReturn: an item an employee has to hand back (project end, exit, recall), until IT Admin signs
  the return off.
- AssetClearance: one per leaver. Full and final settlement waits until IT Admin signs it off, which is
  refused while any item is still out with the employee (same rule in every country).
- ProjectAssetRequirement: the kit a project needs each person on it to hold.

Times are naive UTC, set by the application (never the database clock, which follows the server's zone);
the API sends them marked as UTC.
"""
import logging
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)

from app.models.base import Base

logger = logging.getLogger(__name__)

ASSET_CATEGORIES = ("LAPTOP", "DESKTOP", "MONITOR", "PHONE", "TABLET", "SECURITY_TOKEN", "ACCESS_CARD",
                    "HEADSET", "ACCESSORY", "OTHER")
# Who owns the item: one of our companies, a client, a leasing company, or the employee (their own device
# used for work, tracked so client access on it can be removed)
OWNER_TYPES = ("COMPANY", "CLIENT", "LEASED", "PERSONAL")
# Live: IN_STOCK (in the office) or ASSIGNED (with an employee). Closed: the item left the ledger.
ASSET_STATUSES = ("IN_STOCK", "ASSIGNED", "LOST", "RETIRED", "RETURNED_TO_OWNER")
HELD_STATUSES = ("ASSIGNED",)
CLOSED_STATUSES = ("LOST", "RETIRED", "RETURNED_TO_OWNER")
CHECKOUT_METHODS = ("HAND", "COURIER", "OWN_DEVICE")
CHECKIN_OUTCOMES = ("RETURNED", "LOST", "RELEASED")  # RELEASED: an employee's own device leaves with them
ASSET_CONDITIONS = ("NEW", "GOOD", "FAIR", "DAMAGED")

EVENT_TYPES = ("PROCURED", "UPDATED", "CHECKED_OUT", "SHIPPED", "RECEIVED", "RETURN_REQUESTED", "RETURN_SHIPPED",
               "CHECKED_IN", "DEFECT_REPORTED", "REPAIR_STARTED", "DEFECT_CLOSED", "LOST", "RETIRED",
               "RETURNED_TO_OWNER", "ESCALATED")

SHIPMENT_DIRECTIONS = ("TO_EMPLOYEE", "FROM_EMPLOYEE", "TO_OWNER")
SHIPMENT_STATUSES = ("IN_TRANSIT", "DELIVERED", "LOST")
HANDOVER_METHODS = ("COURIER", "HAND")

ISSUE_SEVERITIES = ("LOW", "MEDIUM", "HIGH")
ISSUE_STATUSES = ("OPEN", "IN_REPAIR", "FIXED", "NO_FAULT", "RETIRED")
OPEN_ISSUE_STATUSES = ("OPEN", "IN_REPAIR")

RETURN_REASONS = ("PROJECT_END", "EXIT", "RECALL")
RETURN_STATUSES = ("OPEN", "RETURNED", "LOST", "CANCELLED")

CLEARANCE_STATUSES = ("PENDING", "CLEARED")

# Task categories (tasks.category): each is the IT Admin function's work, opened and closed by the system
TASK_RETURN = "ASSET_RETURN"
TASK_CLEARANCE = "ASSET_CLEARANCE"
TASK_KIT = "ASSET_KIT"
TASK_ISSUE = "ASSET_ISSUE"
TASK_TRANSIT = "ASSET_TRANSIT"
TASK_ESCALATION = "ASSET_ESCALATION"


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("tenant_id", "asset_tag", name="uq_asset_tag_per_tenant"),
                      Index("ix_assets_tenant_serial", "tenant_id", "serial_number"))

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    asset_tag = Column(String(64), nullable=False)
    category = Column(Enum(*ASSET_CATEGORIES, name="asset_category", native_enum=False, create_constraint=True),
                      nullable=False)
    make = Column(String(200), nullable=True)
    model = Column(String(200), nullable=True)
    serial_number = Column(String(200), nullable=True)

    owner_type = Column(Enum(*OWNER_TYPES, name="asset_owner_type", native_enum=False, create_constraint=True),
                        nullable=False)
    # COMPANY: which of our companies (locations.id); CLIENT: which client; LEASED: the lessor's name
    owner_company_id = Column(String(512), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_client_id = Column(String(512), ForeignKey("clients.id"), nullable=True, index=True)
    owner_name = Column(String(300), nullable=True)

    status = Column(Enum(*ASSET_STATUSES, name="asset_status", native_enum=False, create_constraint=True),
                    nullable=False, default="IN_STOCK", index=True)
    condition = Column(Enum(*ASSET_CONDITIONS, name="asset_condition", native_enum=False, create_constraint=True),
                       nullable=False, default="GOOD")
    holder_employee_id = Column(String(512), ForeignKey("employees.id"), nullable=True, index=True)
    # The project the item was issued for, and whether it comes back when that project ends
    project_id = Column(String(512), ForeignKey("projects.id"), nullable=True, index=True)
    return_at_project_end = Column(Boolean, nullable=False, default=False)
    assigned_at = Column(DateTime, nullable=True)

    # Procurement: when, from whom, on which invoice, for how much
    purchase_date = Column(Date, nullable=True)
    supplier = Column(String(300), nullable=True)
    invoice_number = Column(String(200), nullable=True)
    purchase_cost_cents = Column(Integer, nullable=True)
    currency = Column(String(3), nullable=True)
    warranty_until = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)

    created_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AssetEvent(Base):
    __tablename__ = "asset_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    asset_id = Column(String(512), ForeignKey("assets.id"), nullable=False, index=True)
    event_type = Column(Enum(*EVENT_TYPES, name="asset_event_type", native_enum=False, create_constraint=True),
                        nullable=False)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=True, index=True)
    project_id = Column(String(512), ForeignKey("projects.id"), nullable=True)
    note = Column(Text, nullable=True)
    actor_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AssetCheckout(Base):
    __tablename__ = "asset_checkouts"
    __table_args__ = (Index("ix_asset_checkouts_open", "asset_id", "checked_in_at"),)

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    asset_id = Column(String(512), ForeignKey("assets.id"), nullable=False, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)
    project_id = Column(String(512), ForeignKey("projects.id"), nullable=True)

    checked_out_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    checked_out_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    method = Column(Enum(*CHECKOUT_METHODS, name="asset_checkout_method", native_enum=False, create_constraint=True),
                    nullable=False)
    condition_out = Column(String(20), nullable=True)
    # A courier delivery: when the employee (or IT Admin) confirmed it arrived
    received_on = Column(Date, nullable=True)

    checked_in_at = Column(DateTime, nullable=True)
    checked_in_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    outcome = Column(Enum(*CHECKIN_OUTCOMES, name="asset_checkin_outcome", native_enum=False, create_constraint=True),
                     nullable=True)
    condition_in = Column(String(20), nullable=True)
    note = Column(Text, nullable=True)


class AssetShipment(Base):
    __tablename__ = "asset_shipments"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    asset_id = Column(String(512), ForeignKey("assets.id"), nullable=False, index=True)
    direction = Column(Enum(*SHIPMENT_DIRECTIONS, name="asset_shipment_direction", native_enum=False,
                            create_constraint=True), nullable=False)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=True, index=True)
    carrier = Column(String(200), nullable=False)
    tracking_number = Column(String(200), nullable=False)
    shipped_on = Column(Date, nullable=False)
    expected_on = Column(Date, nullable=True)
    received_on = Column(Date, nullable=True)
    status = Column(Enum(*SHIPMENT_STATUSES, name="asset_shipment_status", native_enum=False, create_constraint=True),
                    nullable=False, default="IN_TRANSIT", index=True)
    # The "chase the courier" task raised when it has been in transit too long (once per shipment)
    chase_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    created_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    received_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AssetIssue(Base):
    __tablename__ = "asset_issues"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    asset_id = Column(String(512), ForeignKey("assets.id"), nullable=False, index=True)
    description = Column(Text, nullable=False)
    severity = Column(Enum(*ISSUE_SEVERITIES, name="asset_issue_severity", native_enum=False, create_constraint=True),
                      nullable=False, default="MEDIUM")
    status = Column(Enum(*ISSUE_STATUSES, name="asset_issue_status", native_enum=False, create_constraint=True),
                    nullable=False, default="OPEN", index=True)
    repair_vendor = Column(String(300), nullable=True)
    resolution = Column(Text, nullable=True)
    fix_cost_cents = Column(Integer, nullable=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    reported_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    reported_at = Column(DateTime, default=datetime.utcnow)
    resolved_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)


class AssetReturn(Base):
    __tablename__ = "asset_returns"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    asset_id = Column(String(512), ForeignKey("assets.id"), nullable=False, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)
    reason = Column(Enum(*RETURN_REASONS, name="asset_return_reason", native_enum=False, create_constraint=True),
                    nullable=False)
    project_id = Column(String(512), ForeignKey("projects.id"), nullable=True)
    due_date = Column(Date, nullable=False)
    status = Column(Enum(*RETURN_STATUSES, name="asset_return_status", native_enum=False, create_constraint=True),
                    nullable=False, default="OPEN", index=True)
    # 0 = not overdue; 1 = the holder was reminded; 2 = their reporting manager; 3 = their BU head
    escalation_level = Column(Integer, nullable=False, default=0)
    last_escalated_at = Column(DateTime, nullable=True)
    signed_off_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    signed_off_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AssetClearance(Base):
    __tablename__ = "asset_clearances"
    __table_args__ = (UniqueConstraint("employee_id", name="uq_asset_clearance_employee"),)

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)
    status = Column(Enum(*CLEARANCE_STATUSES, name="asset_clearance_status", native_enum=False,
                         create_constraint=True), nullable=False, default="PENDING", index=True)
    due_date = Column(Date, nullable=True)  # the last working day
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    signed_off_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    signed_off_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ProjectAssetRequirement(Base):
    __tablename__ = "project_asset_requirements"
    __table_args__ = (UniqueConstraint("project_id", "category", "provided_by", name="uq_project_asset_requirement"),)

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    project_id = Column(String(512), ForeignKey("projects.id"), nullable=False, index=True)
    category = Column(Enum(*ASSET_CATEGORIES, name="project_asset_category", native_enum=False,
                           create_constraint=True), nullable=False)
    # COMPANY: from our stock (ours or leased); CLIENT: the client sends its own device
    provided_by = Column(Enum("COMPANY", "CLIENT", name="project_asset_provided_by", native_enum=False,
                              create_constraint=True), nullable=False, default="COMPANY")
    quantity = Column(Integer, nullable=False, default=1)
    note = Column(Text, nullable=True)
    created_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
