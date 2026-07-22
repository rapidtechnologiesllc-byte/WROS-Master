"""
HRMS-0910 -- AI Time Entry Anomaly Detection (S-229).

BR-0910-01: flags are advisory only and never block anything -- this
module is deliberately never called from
app.services.timesheet_service.submit_timesheet()/approve_timesheet();
it's meant to run at whatever point an approval-screen endpoint (not
built yet, no REST layer exists for this domain) chooses to call it,
per the doc's own "flags surface inline on the approval screen before
manager approval" framing. A failure in detection must never affect
submission, which naturally falls out of that decoupling.

BR-0910-02: weekend flagging respects `Project.allow_weekend_billing`.
The remaining two checks (>12h/day, COMPLETED-status project) and the
duplicate check have no numbered BR in the source doc (an acknowledged
gap in S-229 itself, not an omission here) -- implemented per the
story's plain-language description with no additional invented rules.
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.employee_allocation import EmployeeAllocation
from app.models.project import Project
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.timesheet_anomaly import TimesheetAnomalyFlag

OVER_12H_THRESHOLD = 12


def _is_duplicate_entry(db: Session, timesheet: Timesheet, entry: TimesheetEntry, project: Project) -> bool:
    """Same employee + project + date, in a DIFFERENT timesheet --
    TimesheetEntry's own UNIQUE constraint already forbids two entries
    for the same date within one timesheet, so only a cross-timesheet
    collision (e.g. two allocations to the same project) counts here."""
    other = db.query(TimesheetEntry).join(
        Timesheet, TimesheetEntry.timesheet_id == Timesheet.id
    ).join(
        EmployeeAllocation, Timesheet.allocation_id == EmployeeAllocation.id
    ).filter(
        Timesheet.employee_id == timesheet.employee_id,
        EmployeeAllocation.project_id == project.id,
        TimesheetEntry.entry_date == entry.entry_date,
        TimesheetEntry.id != entry.id,
    ).first()
    return other is not None


def scan_timesheet_anomalies(db: Session, timesheet: Timesheet) -> List[TimesheetAnomalyFlag]:
    """Idempotent: re-scanning an already-flagged entry returns the
    existing flag rather than creating a duplicate row."""
    allocation = db.query(EmployeeAllocation).filter(EmployeeAllocation.id == timesheet.allocation_id).first()
    project = None
    if allocation and allocation.project_id:
        project = db.query(Project).filter(Project.id == allocation.project_id).first()

    entries = db.query(TimesheetEntry).filter(TimesheetEntry.timesheet_id == timesheet.id).all()

    flags: List[TimesheetAnomalyFlag] = []
    for entry in entries:
        anomaly_types = set()

        if entry.entry_date.weekday() >= 5 and not (project and project.allow_weekend_billing):
            anomaly_types.add("WEEKEND")
        if float(entry.hours) > OVER_12H_THRESHOLD:
            anomaly_types.add("OVER_12H")
        if project and project.status == "COMPLETED":
            anomaly_types.add("COMPLETED_PROJECT")
        if project and _is_duplicate_entry(db, timesheet, entry, project):
            anomaly_types.add("DUPLICATE")

        for anomaly_type in anomaly_types:
            existing = db.query(TimesheetAnomalyFlag).filter(
                TimesheetAnomalyFlag.timesheet_entry_id == entry.id,
                TimesheetAnomalyFlag.anomaly_type == anomaly_type,
            ).first()
            if existing:
                flags.append(existing)
                continue
            flag = TimesheetAnomalyFlag(
                tenant_id=timesheet.tenant_id, timesheet_entry_id=entry.id,
                employee_id=timesheet.employee_id, project_id=project.id if project else None,
                anomaly_type=anomaly_type,
            )
            db.add(flag)
            flags.append(flag)

    return flags


def get_anomaly_flags_for_timesheet(db: Session, timesheet: Timesheet) -> List[TimesheetAnomalyFlag]:
    entry_ids = [row[0] for row in db.query(TimesheetEntry.id).filter(TimesheetEntry.timesheet_id == timesheet.id).all()]
    if not entry_ids:
        return []
    return db.query(TimesheetAnomalyFlag).filter(TimesheetAnomalyFlag.timesheet_entry_id.in_(entry_ids)).all()
