"""
HRMS-0314 -- Complete Timesheet Management (Phase 3)
Timesheet creation, submission, approval, and integration with invoicing.
"""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.allocation import EmployeeAllocation
from app.models.project import Project
from app.models.employee import Employee


class TimesheetCompleteService:
    """Manages complete timesheet lifecycle."""

    def create_timesheet(
        self,
        db: Session,
        employee_id: str,
        allocation_id: str,
        tenant_id: int,
        week_start_date: datetime,
        approver_id: str = None
    ) -> dict:
        """Create new timesheet for employee allocation."""
        allocation = db.query(EmployeeAllocation).filter(
            EmployeeAllocation.id == allocation_id,
            EmployeeAllocation.tenant_id == tenant_id
        ).first()

        if not allocation:
            return {"status": "error", "message": "Allocation not found"}

        timesheet = Timesheet(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            employee_id=employee_id,
            allocation_id=allocation_id,
            week_start_date=week_start_date,
            week_end_date=week_start_date + timedelta(days=6),
            status="DRAFT",
            total_hours=0,
            approver_id=approver_id,
            created_at=datetime.utcnow()
        )

        db.add(timesheet)
        db.commit()

        return {
            "status": "success",
            "timesheet_id": timesheet.id,
            "employee_id": employee_id,
            "week_start": week_start_date.isoformat(),
            "week_end": timesheet.week_end_date.isoformat()
        }

    def add_timesheet_entry(
        self,
        db: Session,
        timesheet_id: str,
        tenant_id: int,
        date: datetime,
        hours: Decimal,
        task_description: str,
        project_code: str = None
    ) -> dict:
        """Add daily entry to timesheet."""
        timesheet = db.query(Timesheet).filter(
            Timesheet.id == timesheet_id,
            Timesheet.tenant_id == tenant_id
        ).first()

        if not timesheet:
            return {"status": "error", "message": "Timesheet not found"}

        if timesheet.status != "DRAFT":
            return {"status": "error", "message": "Can only add entries to draft timesheets"}

        entry = TimesheetEntry(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            timesheet_id=timesheet_id,
            date=date,
            hours=hours,
            task_description=task_description,
            project_code=project_code,
            created_at=datetime.utcnow()
        )

        db.add(entry)

        # Update total hours
        timesheet.total_hours += hours
        db.commit()

        return {
            "status": "success",
            "entry_id": entry.id,
            "hours": float(hours),
            "updated_total_hours": float(timesheet.total_hours)
        }

    def submit_timesheet(
        self,
        db: Session,
        timesheet_id: str,
        tenant_id: int
    ) -> dict:
        """Submit timesheet for approval."""
        timesheet = db.query(Timesheet).filter(
            Timesheet.id == timesheet_id,
            Timesheet.tenant_id == tenant_id
        ).first()

        if not timesheet:
            return {"status": "error", "message": "Timesheet not found"}

        if timesheet.status != "DRAFT":
            return {"status": "error", "message": "Only draft timesheets can be submitted"}

        if timesheet.total_hours == 0:
            return {"status": "error", "message": "Timesheet has no entries"}

        timesheet.status = "SUBMITTED"
        timesheet.submitted_at = datetime.utcnow()
        db.commit()

        return {
            "status": "success",
            "timesheet_id": timesheet_id,
            "submitted_at": timesheet.submitted_at.isoformat(),
            "total_hours": float(timesheet.total_hours)
        }

    def approve_timesheet(
        self,
        db: Session,
        timesheet_id: str,
        tenant_id: int,
        approver_id: str,
        approval_notes: str = None
    ) -> dict:
        """Approve submitted timesheet."""
        timesheet = db.query(Timesheet).filter(
            Timesheet.id == timesheet_id,
            Timesheet.tenant_id == tenant_id
        ).first()

        if not timesheet:
            return {"status": "error", "message": "Timesheet not found"}

        if timesheet.status != "SUBMITTED":
            return {"status": "error", "message": "Only submitted timesheets can be approved"}

        timesheet.status = "APPROVED"
        timesheet.approved_by = approver_id
        timesheet.approved_at = datetime.utcnow()
        timesheet.approval_notes = approval_notes
        db.commit()

        return {
            "status": "success",
            "timesheet_id": timesheet_id,
            "approved_at": timesheet.approved_at.isoformat(),
            "approved_by": approver_id,
            "total_hours": float(timesheet.total_hours),
            "ready_for_invoicing": True
        }

    def reject_timesheet(
        self,
        db: Session,
        timesheet_id: str,
        tenant_id: int,
        rejected_by: str,
        rejection_reason: str
    ) -> dict:
        """Reject timesheet and return to employee."""
        timesheet = db.query(Timesheet).filter(
            Timesheet.id == timesheet_id,
            Timesheet.tenant_id == tenant_id
        ).first()

        if not timesheet:
            return {"status": "error", "message": "Timesheet not found"}

        timesheet.status = "REJECTED"
        timesheet.rejected_by = rejected_by
        timesheet.rejected_at = datetime.utcnow()
        timesheet.rejection_reason = rejection_reason
        db.commit()

        return {
            "status": "success",
            "timesheet_id": timesheet_id,
            "rejected_at": timesheet.rejected_at.isoformat(),
            "rejected_by": rejected_by,
            "reason": rejection_reason
        }

    def get_timesheet_summary(
        self,
        db: Session,
        timesheet_id: str,
        tenant_id: int
    ) -> dict:
        """Get complete timesheet details."""
        timesheet = db.query(Timesheet).filter(
            Timesheet.id == timesheet_id,
            Timesheet.tenant_id == tenant_id
        ).first()

        if not timesheet:
            return None

        entries = db.query(TimesheetEntry).filter(
            TimesheetEntry.timesheet_id == timesheet_id,
            TimesheetEntry.tenant_id == tenant_id
        ).all()

        return {
            "timesheet_id": timesheet_id,
            "employee_id": timesheet.employee_id,
            "allocation_id": timesheet.allocation_id,
            "week_start": timesheet.week_start_date.isoformat(),
            "week_end": timesheet.week_end_date.isoformat(),
            "status": timesheet.status,
            "total_hours": float(timesheet.total_hours),
            "entries": [
                {
                    "date": e.date.isoformat(),
                    "hours": float(e.hours),
                    "task": e.task_description
                }
                for e in entries
            ],
            "submitted_at": timesheet.submitted_at.isoformat() if timesheet.submitted_at else None,
            "approved_at": timesheet.approved_at.isoformat() if timesheet.approved_at else None,
            "approved_by": timesheet.approved_by
        }
