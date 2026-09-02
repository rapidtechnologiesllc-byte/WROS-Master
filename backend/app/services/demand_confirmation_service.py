"""
import logging
S-372/HRMS-0528 -- Confirmed vs Potential Demand Workflow.

Built from `Requirements/S-372_HRMS-0528.docx` directly.
"""
from datetime import date, datetime
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.models.demand import Demand
from app.models.demand_confirmation import DemandAlignmentCall
from app.models.employee import Employee
from app.models.user import Users
from app.services.notification_service import send_notification

PARTICIPANTS = ("EMPLOYEE", "BU_HEAD")

logger = logging.getLogger(__name__)

class SOWReferenceRequired(Exception):
    """AC-6: SOW reference must be recorded before confirmation_status can flip to CONFIRMED."""


class InvalidParticipant(Exception):
    pass


class FitConfirmationAlreadyRecorded(Exception):
    """BR: an already-recorded confirmation (especially the employee's) is
    never silently overwritten -- a new alignment call is a new decision,
    not a mutation of a past one."""


class SpecialtyClientReleaseNotAllowed(Exception):
    """BR: Specialty client release cannot be triggered until
    confirmation_status=CONFIRMED and both fit confirmations are True --
    no exceptions, no partial sequence."""


def confirm_demand_with_sow(
    db: Session, demand: Demand, *, sow_reference: str, sow_received_date: Optional[date] = None,
) -> Demand:
    """AC-6: SOW reference recorded on the demand before confirmation_status
    is ever set to CONFIRMED -- both the CONFIRMED-from-the-start path and
    the POTENTIAL-path-that-just-got-its-SOW converge here."""
    if not sow_reference or not sow_reference.strip():
        raise SOWReferenceRequired(
            "sow_reference is required before a demand's confirmation_status can be set to CONFIRMED."
        )
    demand.sow_reference = sow_reference.strip()
    demand.sow_received_date = sow_received_date or date.today()
    demand.confirmation_status = "CONFIRMED"
    db.add(demand)
    return demand


def schedule_alignment_call(
    db: Session,
    demand: Demand,
    employee: Employee,
    *,
    curtis_user_id: Optional[str] = None,
    bu_head_user_id: Optional[str] = None,
    scheduler: Optional[Callable[[Optional[str], Optional[str], str], datetime]] = None,
) -> DemandAlignmentCall:
    """
    Step 4: SchedulerService.book3WayAlignment() -- no calendar
    integration (HRMS-1306) exists in this codebase; `scheduler` is an
    injectable callable(curtis_user_id, bu_head_user_id, employee_id) ->
    datetime, same "real function signature, real transport deferred"
    posture as every other unprovisioned integration here (WhatsApp,
    virus scan). Defaults to "right now" -- correct for the CONFIRMED
    path's own same-day BR; real multi-participant slot-finding for the
    POTENTIAL path is the deferred piece.

    Idempotent per demand+employee -- a second call returns the existing
    DemandAlignmentCall rather than re-booking.
    """
    existing = (
        db.query(DemandAlignmentCall)
        .filter(DemandAlignmentCall.demand_id == demand.id, DemandAlignmentCall.employee_id == employee.id)
        .first()
    )
    if existing:
        return existing

    book = scheduler or (lambda curtis_id, bu_head_id, emp_id: datetime.utcnow())
    scheduled_at = book(curtis_user_id, bu_head_user_id, employee.id)

    call = DemandAlignmentCall(
        tenant_id=demand.tenant_id, demand_id=demand.id, employee_id=employee.id,
        curtis_user_id=curtis_user_id, bu_head_user_id=bu_head_user_id, scheduled_at=scheduled_at,
    )
    db.add(call)
    db.flush()
    return call


def confirm_fit(
    db: Session, call: DemandAlignmentCall, *, participant: str, confirmed: bool, notes: Optional[str] = None,
) -> DemandAlignmentCall:
    """
    AC-4/AC-5 + BR (employee confirmation is mandatory and final): no
    parameter here lets one participant set the other's confirmation, and
    an already-recorded confirmation is never silently overwritten --
    especially the employee's; an employee who says no is not penalised
    and the BU Head cannot override that without a formal HR process this
    codebase doesn't implement.
    """
    if participant not in PARTICIPANTS:
        raise InvalidParticipant(f"participant must be one of {PARTICIPANTS}, got '{participant}'.")

    if participant == "EMPLOYEE":
        if call.employee_fit_confirmed is not None:
            raise FitConfirmationAlreadyRecorded(
                f"Employee fit confirmation for alignment call {call.id} was already recorded."
            )
        call.employee_fit_confirmed = confirmed
        call.employee_fit_confirmed_at = datetime.utcnow()
        call.employee_fit_notes = notes
    else:
        if call.bu_head_fit_confirmed is not None:
            raise FitConfirmationAlreadyRecorded(
                f"BU Head fit confirmation for alignment call {call.id} was already recorded."
            )
        call.bu_head_fit_confirmed = confirmed
        call.bu_head_fit_confirmed_at = datetime.utcnow()
        call.bu_head_fit_notes = notes

    db.add(call)
    return call


def trigger_specialty_client_release(
    db: Session,
    call: DemandAlignmentCall,
    demand: Demand,
    *,
    speciality_rm: Optional[Users] = None,
    tenant_id: Optional[int] = None,
) -> DemandAlignmentCall:
    """
    HRMS-0534 Specialty Client Release -- the hard sequence gate itself is
    built for real: confirmation_status=CONFIRMED AND both fit
    confirmations are True, no partial sequence, no exceptions. WROS does
    not notify Specialty clients directly (same posture already
    established for Core-Pull in S-353's own BR) -- this notifies the
    Speciality RM (caller-supplied, same roster-resolution-deferred
    posture as everywhere else in this codebase), who coordinates the
    actual client communication.
    """
    if demand.confirmation_status != "CONFIRMED":
        raise SpecialtyClientReleaseNotAllowed(
            f"Demand {demand.id} confirmation_status is '{demand.confirmation_status}', not CONFIRMED."
        )
    if call.employee_fit_confirmed is not True or call.bu_head_fit_confirmed is not True:
        raise SpecialtyClientReleaseNotAllowed(
            f"Both employee and BU Head fit confirmations must be True before Specialty client release "
            f"(employee={call.employee_fit_confirmed}, bu_head={call.bu_head_fit_confirmed})."
        )

    call.specialty_client_release_triggered_at = datetime.utcnow()
    db.add(call)

    if speciality_rm is not None:
        try:
            send_notification(
                db, calling_context_tenant_id=tenant_id, recipient=speciality_rm, priority_tier="P0",
                message=(
                    f"Specialty client release: demand {demand.id} confirmed, both parties have signed off. "
                    f"Please coordinate the handover communication with the client."
                ),
            )
        except Exception:
            pass

    return call
