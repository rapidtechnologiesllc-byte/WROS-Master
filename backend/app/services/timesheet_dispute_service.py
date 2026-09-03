"""
import logging
HRMS-0904 -- Timesheet Dispute Resolution.

BR-01: the original approved Timesheet/TimesheetEntry rows are never
mutated by a dispute, even when resolved as ADJUSTED -- the adjustment
lives entirely on the TimesheetDispute record itself. has_open_dispute()
is the hook point for HRMS-0904's BR-02 ("an open dispute blocks period
close for invoicing") -- not wired to an actual invoice-period-close gate
since invoicing doesn't exist in this codebase yet, same posture as
every other not-yet-reachable dependency this session.
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.timesheet import Timesheet
from app.models.timesheet_dispute import OPEN_DISPUTE_STATUSES, TimesheetDispute
from app.core.logging import logger

MIN_REASON_LENGTH = 50

logger = logging.getLogger(__name__)

class DisputeValidationError(Exception):
    pass


class InvalidDisputeTransition(Exception):
    pass


def raise_dispute(
    db: Session,
    timesheet: Timesheet,
    *,
    raised_by: str,
    reason: str,
    raised_by_user_id: Optional[str] = None,
    disputed_date=None,
    disputed_hours=None,
    tenant_id: Optional[int] = None,
) -> TimesheetDispute:
    if timesheet.status != "APPROVED":
        raise DisputeValidationError(
            f"Cannot dispute a timesheet in status '{timesheet.status}' -- only APPROVED timesheets can be disputed."
        )
    if len(reason or "") < MIN_REASON_LENGTH:
        raise DisputeValidationError(f"Dispute reason must be at least {MIN_REASON_LENGTH} characters.")

    dispute = TimesheetDispute(
        tenant_id=tenant_id, timesheet_id=timesheet.id,
        raised_by=raised_by, raised_by_user_id=raised_by_user_id,
        disputed_date=disputed_date, disputed_hours=disputed_hours,
        original_hours=timesheet.total_hours, reason=reason,
    )
    db.add(dispute)
    return dispute


def resolve_dispute(
    db: Session,
    dispute: TimesheetDispute,
    *,
    resolution: str,
    resolved_by: Optional[str] = None,
    resolution_notes: str,
    adjusted_hours=None,
) -> TimesheetDispute:
    """
    BR-01: never touches the original Timesheet/TimesheetEntry rows,
    regardless of resolution -- the adjustment is captured here only.
    """
    if dispute.status not in OPEN_DISPUTE_STATUSES:
        raise InvalidDisputeTransition(f"Cannot resolve a dispute in status '{dispute.status}'.")

    if resolution == "ADJUSTED":
        if adjusted_hours is None:
            raise DisputeValidationError("adjusted_hours is required when resolution='ADJUSTED'.")
        dispute.status = "RESOLVED_ADJUSTED"
        dispute.adjusted_hours = adjusted_hours
    elif resolution == "CONFIRMED":
        dispute.status = "RESOLVED_CONFIRMED"
    else:
        raise ValueError(f"resolution must be 'ADJUSTED' or 'CONFIRMED', got '{resolution}'.")

    dispute.resolved_by = resolved_by
    dispute.resolved_at = datetime.utcnow()
    dispute.resolution_notes = resolution_notes
    db.add(dispute)
    return dispute


def has_open_dispute(db: Session, timesheet: Timesheet) -> bool:
    """BR-02 hook: a future invoice-period-close gate should call this
    and block the period if it returns True for any timesheet in it."""
    return db.query(TimesheetDispute).filter(
        TimesheetDispute.timesheet_id == timesheet.id,
        TimesheetDispute.status.in_(OPEN_DISPUTE_STATUSES),
    ).first() is not None
