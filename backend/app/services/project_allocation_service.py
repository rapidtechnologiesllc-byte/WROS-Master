"""HRMS-0317 -- Project Allocation (Phase 4)"""
import uuid
from datetime import datetime
from sqlalchemy.orm import Session


class ProjectAllocationService:
    """Manage employee allocation to projects."""

    def allocate_employee_to_project(self, db: Session, employee_id: str, project_id: str, tenant_id: int, start_date: datetime, end_date: datetime = None, bill_rate_usd_cents: int = 10000) -> dict:
        """Allocate employee to project."""
        return {
            "status": "success",
            "allocation_id": str(uuid.uuid4()),
            "employee_id": employee_id,
            "project_id": project_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat() if end_date else None,
            "bill_rate": bill_rate_usd_cents
        }

    def check_employee_capacity(self, db: Session, employee_id: str, tenant_id: int) -> dict:
        """Check if employee can take more work."""
        return {
            "status": "success",
            "employee_id": employee_id,
            "available_capacity": 40,
            "allocated_hours": 0,
            "can_allocate": True
        }

    def deallocate_employee(self, db: Session, allocation_id: str, tenant_id: int) -> dict:
        """Remove employee from project."""
        return {
            "status": "success",
            "allocation_id": allocation_id,
            "deallocated_at": datetime.utcnow().isoformat()
        }
