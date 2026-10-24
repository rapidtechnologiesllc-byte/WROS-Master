"""Where an employee stands, on two axes (CEO 2026-10-24):

- employment: JOINING (pre-joining), EMPLOYED, ON_LEAVE, SERVING_NOTICE, TERMINATED (exited)
- deployment, for people on the payroll: HTD (in Hire-Train-Deploy training), BUDDY (in the Buddy
  Program, not yet deployable),
  PROJECT (on an active allocation), PROJECT_ENDING (every active allocation is ending: inside the
  renewal-alert window without an agreed extension, or rolling off), BENCH (no active allocation).

Derived, never stored: employment from Employee.status, deployment from the active allocations,
HTD, the Buddy Program status and the bench pool. One definition for the employee list, the drawer and
any dashboard.
"""
from datetime import date
from typing import Optional

from app.services.allocation_renewal_service import alert_thresholds

EMPLOYMENT_BY_STATUS = {
    "PRE_JOINING": "JOINING",
    "ON_LEAVE": "ON_LEAVE",
    "NOTICE_PERIOD": "SERVING_NOTICE",
    "EXITED": "TERMINATED",
}
ON_PAYROLL = {"EMPLOYED", "ON_LEAVE", "SERVING_NOTICE"}
BUDDY_RUNNING = {"IN_PROGRESS", "EXTENDED"}
HTD_DONE = {"COMPLETED", "EXITED"}


def in_htd(htd_track: bool, htd_phase: Optional[str]) -> bool:
    """On the Hire-Train-Deploy track and not yet through it (or out of it)."""
    return bool(htd_track) and htd_phase not in HTD_DONE


def ending_soon(end_date: Optional[date], renewal_status: Optional[str], today: date) -> bool:
    """An active allocation is ending when it is marked rolling off, or ends inside the renewal-alert
    window (the largest of settings.RENEWAL_ALERT_DAYS) and no extension has been agreed."""
    if end_date is None:
        return False
    if renewal_status == "ROLLING_OFF":
        return True
    return renewal_status != "EXTENDED" and (end_date - today).days <= alert_thresholds()[0]


def employment_status(employee_status: str) -> str:
    return EMPLOYMENT_BY_STATUS.get(employee_status, "EMPLOYED")


def employment_actions(employee_status: str) -> list:
    """The employment changes (app.services.employment_change_service) this status allows now."""
    from app.models.employee import ALLOWED_STATUS_TRANSITIONS

    allowed = ALLOWED_STATUS_TRANSITIONS.get(employee_status, set())
    actions = []
    if "NOTICE_PERIOD" in allowed:
        actions.append("START_NOTICE")
    if "NOTICE_PERIOD" in allowed or employee_status == "NOTICE_PERIOD":
        actions.append("RECORD_EXIT")
    if "ON_LEAVE" in allowed:
        actions.append("START_LEAVE")
    if employee_status == "ON_LEAVE":
        actions.append("END_LEAVE")
    return actions


def deployment_status(employee_status: str, buddy_program_status: Optional[str], allocations: list,
                      bench_days: Optional[int], today: date, htd_active: bool = False) -> dict:
    """{"status", "until", "days"}: until = the date the last active allocation ends (PROJECT /
    PROJECT_ENDING), days = days left on it, or days on bench. status None when not on payroll.
    allocations are the employee's ACTIVE allocation summaries (end_date ISO or None,
    renewal_status)."""
    if employment_status(employee_status) not in ON_PAYROLL:
        return {"status": None, "until": None, "days": None}
    if allocations:
        if any(a.get("end_date") is None for a in allocations):
            return {"status": "PROJECT", "until": None, "days": None}
        ends = [(date.fromisoformat(a["end_date"]), a.get("renewal_status")) for a in allocations]
        until = max(end for end, _ in ends)
        ending = all(ending_soon(end, renewal, today) for end, renewal in ends)
        return {"status": "PROJECT_ENDING" if ending else "PROJECT", "until": until.isoformat(),
                "days": (until - today).days}
    if htd_active:
        return {"status": "HTD", "until": None, "days": None}
    if buddy_program_status in BUDDY_RUNNING:
        return {"status": "BUDDY", "until": None, "days": None}
    return {"status": "BENCH", "until": None, "days": bench_days}
