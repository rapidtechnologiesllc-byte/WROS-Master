"""Margin guard at placement (CEO 2026-10-23, gap 4): the rate card and who may approve a
placement priced below it.

margin % = (bill rate - loaded hourly cost) / bill rate, with the loaded hourly cost from the
CostBook (revenue_chain_service: salary + statutory + overhead for the employee's BU and country
on that day, divided by STANDARD_MONTHLY_HOURS). The floor is the most specific active
MarginPolicy for the placement's delivery engine, the employee's delivery country and the role.

Outcomes (EmployeeAllocation.margin_check / AllocationChange.margin_check):
  OK                   at or above min_margin_pct
  BELOW_MIN            below min_margin_pct          -> a BU Head approves
  BELOW_HARD_FLOOR     below hard_floor_pct          -> a Partner approves
  NO_COST_DATA         floor set, cost unknown       -> a BU Head approves (fails closed: the
  NO_BILL_RATE         floor set, no bill rate          margin cannot be shown to clear it)
  NO_FLOOR_CONFIGURED  no rate-card row applies      -> allowed, flagged on the response and UI
  NOT_BILLABLE         internal (non-billable) time  -> no margin to guard

Approval authority comes from the role template level only (settings.BU_LEADER_MIN_LEVEL,
settings.PARTNER_MIN_LEVEL via app.core.authority), for the business unit that owns the revenue
(the client's BU, else the job's, else the employee's): the approver leads that BU (heads or
partners it) or sees every BU (org-level template). Nobody approves their own placement.
"""
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core import authority
from app.core.config import settings
from app.models.margin_policy import MarginPolicy
from app.models.user import Users

logger = logging.getLogger(__name__)

OK = "OK"
BELOW_MIN = "BELOW_MIN"
BELOW_HARD_FLOOR = "BELOW_HARD_FLOOR"
NO_COST_DATA = "NO_COST_DATA"
NO_BILL_RATE = "NO_BILL_RATE"
NO_FLOOR_CONFIGURED = "NO_FLOOR_CONFIGURED"
NOT_BILLABLE = "NOT_BILLABLE"

BU_HEAD = "BU_HEAD"
PARTNER = "PARTNER"
APPROVAL_FOR = {BELOW_MIN: BU_HEAD, NO_COST_DATA: BU_HEAD, NO_BILL_RATE: BU_HEAD, BELOW_HARD_FLOOR: PARTNER}
LEVEL_LABELS = {BU_HEAD: "a BU Head", PARTNER: "a Partner"}


def required_level(approval_level: str) -> int:
    return settings.PARTNER_MIN_LEVEL if approval_level == PARTNER else settings.BU_LEADER_MIN_LEVEL


@dataclass
class MarginResult:
    check: str
    margin_pct: Optional[float] = None
    loaded_hourly_cost_usd_cents: Optional[int] = None
    policy: Optional[MarginPolicy] = None
    delivery_engine: Optional[str] = None
    country: Optional[str] = None
    flags: List[str] = field(default_factory=list)

    @property
    def approval_level(self) -> Optional[str]:
        return APPROVAL_FOR.get(self.check)

    @property
    def message(self) -> str:
        return describe(self.check, self.margin_pct,
                        float(self.policy.min_margin_pct) if self.policy else None,
                        float(self.policy.hard_floor_pct) if self.policy else None)

    def as_dict(self) -> dict:
        return {
            "margin_check": self.check,
            "margin_pct": round(self.margin_pct, 2) if self.margin_pct is not None else None,
            "loaded_hourly_cost_usd_cents": self.loaded_hourly_cost_usd_cents,
            "min_margin_pct": float(self.policy.min_margin_pct) if self.policy else None,
            "hard_floor_pct": float(self.policy.hard_floor_pct) if self.policy else None,
            "margin_policy_id": self.policy.id if self.policy else None,
            "delivery_engine": self.delivery_engine, "country": self.country,
            "approval_level": self.approval_level, "message": self.message, "flags": list(self.flags),
        }


def describe(check: Optional[str], margin_pct: Optional[float], min_margin_pct: Optional[float],
             hard_floor_pct: Optional[float]) -> str:
    """The sentence the form, the API and the approval task show for a margin check."""
    pct = f"{float(margin_pct):.1f}%" if margin_pct is not None else "unknown"
    if check is None:
        return "Placed before the margin guard: not checked."
    if check == NOT_BILLABLE:
        return "Non-billable time: no margin floor applies."
    if check == NO_FLOOR_CONFIGURED:
        return f"Margin {pct}. No margin floor configured for this placement."
    if check == NO_COST_DATA:
        return ("The employee's loaded cost is unknown (salary or cost rate missing), so the margin floor "
                "cannot be checked: a BU Head must approve.")
    if check == NO_BILL_RATE:
        return "No bill rate, so the margin floor cannot be checked: a BU Head must approve."
    if check == BELOW_HARD_FLOOR:
        return f"Margin {pct} is below the hard floor of {hard_floor_pct:.1f}%: a Partner must approve."
    if check == BELOW_MIN:
        return f"Margin {pct} is below the minimum of {min_margin_pct:.1f}%: a BU Head must approve."
    return f"Margin {pct} meets the floor of {min_margin_pct:.1f}%."


def policy_for(db: Session, tenant_id: Optional[int], engine: Optional[str], country: Optional[str],
               role: Optional[str]) -> Optional[MarginPolicy]:
    """The most specific active row: role + country, then country, then role, then the engine-wide row."""
    if engine is None or tenant_id is None:
        return None
    rows = db.query(MarginPolicy).filter(MarginPolicy.tenant_id == tenant_id, MarginPolicy.delivery_engine == engine,
                                         MarginPolicy.active.is_(True)).all()
    role_key = (role or "").strip().lower()
    best, best_score = None, -1
    for row in rows:
        if row.country is not None and row.country != country:
            continue
        if row.role is not None and row.role.strip().lower() != role_key:
            continue
        score = (2 if row.country is not None else 0) + (1 if row.role is not None else 0)
        if score > best_score:
            best, best_score = row, score
    return best


def evaluate(db: Session, *, tenant_id: Optional[int], employee, project_id: Optional[str],
             client_id: Optional[str], role: Optional[str], bill_rate_usd_cents: Optional[int],
             billable: bool, on: Optional[date] = None) -> MarginResult:
    """The margin check of a placement (or of an edit's proposed values) on day `on`."""
    from app.services.deployment_readiness_service import delivery_line
    from app.services.revenue_chain_service import CostBook

    on = on or date.today()
    if not billable:
        return MarginResult(check=NOT_BILLABLE)
    costs = CostBook(db)
    engine = delivery_line(db, project_id=project_id, client_id=client_id)
    country = costs.object_on(employee, on)[2]
    hourly = costs.hourly(employee, on)
    margin = None
    if bill_rate_usd_cents and hourly is not None:
        margin = (bill_rate_usd_cents - hourly) / bill_rate_usd_cents * 100
    result = MarginResult(check=OK, margin_pct=margin, delivery_engine=engine, country=country,
                          loaded_hourly_cost_usd_cents=round(hourly) if hourly is not None else None)
    result.policy = policy_for(db, tenant_id, engine, country, role)
    if engine is None:
        result.flags.append("NO_DELIVERY_ENGINE")
    if hourly is None:
        result.flags.append("NO_COST_DATA")
    if result.policy is None:
        result.check = NO_FLOOR_CONFIGURED
        result.flags.append("NO_MARGIN_FLOOR_CONFIGURED")
    elif not bill_rate_usd_cents:
        result.check = NO_BILL_RATE
    elif hourly is None:
        result.check = NO_COST_DATA
    elif margin < float(result.policy.hard_floor_pct):
        result.check = BELOW_HARD_FLOOR
    elif margin < float(result.policy.min_margin_pct):
        result.check = BELOW_MIN
    return result


def revenue_business_unit(db: Session, *, client_id: Optional[str], demand=None, employee=None) -> Optional[int]:
    """The BU that owns the placement's revenue: the client's, else the job's, else the employee's."""
    from app.models.client import Client

    client = db.query(Client).filter(Client.id == client_id).first() if client_id else None
    if client is not None and client.business_unit_id:
        return client.business_unit_id
    if demand is not None and getattr(demand, "assigned_bu_id", None):
        return demand.assigned_bu_id
    return getattr(employee, "bu_id", None)


def route_approver(db: Session, approval_level: str, *, bu_id: Optional[int], client_id: Optional[str],
                   employee=None, exclude_user_id: Optional[str] = None) -> Optional[str]:
    """Who gets the approval task: the BU's head (in the client's contracting company, else the
    employee's company) for a BU Head-level approval, else the BU's partner -- the first one whose
    role level reaches the required level and who is not the requester. None when nobody does."""
    from app.models.business_unit import BusinessUnit
    from app.services.bu_leadership import head_for_client, head_user_id

    if bu_id is None:
        return None
    candidates = []
    if approval_level == BU_HEAD:
        candidates.append(head_for_client(db, bu_id, client_id)
                          or head_user_id(db, bu_id, getattr(employee, "company_id", None)))
    unit = db.query(BusinessUnit).filter(BusinessUnit.id == bu_id).first()
    candidates.append(unit.partner_user_id if unit is not None else None)
    needed = required_level(approval_level)
    for user_id in candidates:
        if not user_id or user_id == exclude_user_id:
            continue
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if user is not None and authority.level(db, user) >= needed:
            return user_id
    return None


def may_decide(db: Session, user: Optional[Users], *, approval_level: str, bu_id: Optional[int],
               requested_by: Optional[str]) -> Optional[str]:
    """None when the user may decide; otherwise why not."""
    if user is None:
        return "Sign in to decide."
    if requested_by and user.UserID == requested_by:
        return "You requested this change; someone else with the authority must approve it."
    if authority.level(db, user) < required_level(approval_level):
        return f"Only {LEVEL_LABELS[approval_level]} (role level {required_level(approval_level)} or above) can decide."
    if authority.is_org_level(db, user):
        return None
    from app.services.bu_leadership import led_business_units

    if bu_id is not None and bu_id in led_business_units(db, user):
        return None
    return f"Only {LEVEL_LABELS[approval_level]} of this placement's business unit can decide."
