"""Organization Service - Single source of truth for organizational hierarchy.

This service provides centralized access to:
- Employee hierarchy (reporting chain)
- Business unit structure
- Location management
- Manager-subordinate relationships
- Recursive hierarchy queries

Used by Permission Helper Service and all data access logic for hierarchy filtering.
"""

from typing import List, Optional, Set
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.org_structure import OrgNode


class OrganizationService:
    """Centralized organizational hierarchy queries."""

    @staticmethod
    def get_employee(employee_id: str, db: Session, tenant_id: int = 1) -> Optional[Employee]:
        """Get employee with hierarchy info."""
        return db.query(Employee).filter(
            Employee.id == employee_id,
            Employee.tenant_id == tenant_id
        ).first()

    @staticmethod
    def get_employee_manager(employee_id: str, db: Session, tenant_id: int = 1) -> Optional[Employee]:
        """Get direct manager of employee."""
        employee = OrganizationService.get_employee(employee_id, db, tenant_id)
        if not employee or not employee.manager_id:
            return None
        return db.query(Employee).filter(
            Employee.id == employee.manager_id,
            Employee.tenant_id == tenant_id
        ).first()

    @staticmethod
    def get_direct_reports(employee_id: str, db: Session, tenant_id: int = 1) -> List[Employee]:
        """Get all direct reports of employee."""
        return db.query(Employee).filter(
            Employee.manager_id == employee_id,
            Employee.tenant_id == tenant_id
        ).order_by(Employee.name).all()

    @staticmethod
    def get_all_subordinates(employee_id: str, db: Session, tenant_id: int = 1) -> List[str]:
        """Get all subordinates recursively (reporting chain).

        Returns list of employee IDs who report directly or indirectly to this employee.
        """
        # Recursive CTE to get all subordinates
        subordinates = []
        to_process = [employee_id]
        processed = set()

        while to_process:
            current_id = to_process.pop(0)
            if current_id in processed:
                continue
            processed.add(current_id)

            direct_reports = OrganizationService.get_direct_reports(current_id, db, tenant_id)
            for report in direct_reports:
                subordinates.append(report.id)
                to_process.append(report.id)

        return subordinates

    @staticmethod
    def get_reporting_chain_to_ceo(employee_id: str, db: Session, tenant_id: int = 1) -> List[str]:
        """Get chain of command from employee to CEO.

        Returns list of employee IDs from employee up to CEO.
        """
        chain = [employee_id]
        current_employee = OrganizationService.get_employee(employee_id, db, tenant_id)

        while current_employee and current_employee.manager_id:
            manager = OrganizationService.get_employee_manager(current_employee.id, db, tenant_id)
            if manager:
                chain.append(manager.id)
                current_employee = manager
            else:
                break

        return chain

    @staticmethod
    def get_hierarchy_info(employee_id: str, db: Session, tenant_id: int = 1) -> dict:
        """Get complete hierarchy information for employee."""
        employee = OrganizationService.get_employee(employee_id, db, tenant_id)
        if not employee:
            return {}

        return {
            "employee_id": employee.id,
            "name": employee.name,
            "manager_id": employee.manager_id,
            "bu_id": employee.business_unit_id,
            "location_id": getattr(employee, 'location_id', None),
            "direct_reports": [e.id for e in OrganizationService.get_direct_reports(employee_id, db, tenant_id)],
            "all_subordinates": OrganizationService.get_all_subordinates(employee_id, db, tenant_id),
            "reporting_chain": OrganizationService.get_reporting_chain_to_ceo(employee_id, db, tenant_id),
        }

    @staticmethod
    def get_business_unit_employees(bu_id: str, db: Session, tenant_id: int = 1) -> List[Employee]:
        """Get all employees in business unit."""
        return db.query(Employee).filter(
            Employee.business_unit_id == bu_id,
            Employee.tenant_id == tenant_id
        ).order_by(Employee.name).all()

    @staticmethod
    def get_employees_in_locations(location_ids: List[str], db: Session, tenant_id: int = 1) -> List[Employee]:
        """Get all employees in specific locations."""
        if not location_ids:
            return []
        return db.query(Employee).filter(
            Employee.location_id.in_(location_ids),
            Employee.tenant_id == tenant_id
        ).all()

    @staticmethod
    def can_employee_work_across_locations(employee_id: str, db: Session, tenant_id: int = 1) -> bool:
        """Check if employee can work across locations.

        Rule: Employees cannot work across locations.
        Only Partners and BU Heads can have cross-location responsibilities.
        """
        employee = OrganizationService.get_employee(employee_id, db, tenant_id)
        if not employee:
            return False

        # Employees at certain levels can work cross-location
        cross_location_levels = [
            "Partner",
            "BU Head",
            "Senior Vice President",
            "Director"
        ]

        return any(level.lower() in str(getattr(employee, 'level', '')).lower()
                   for level in cross_location_levels)

    @staticmethod
    def get_user_accessible_locations(employee_id: str, db: Session, tenant_id: int = 1) -> List[str]:
        """Get list of locations this employee can access.

        If employee cannot work cross-location, returns only their location.
        Otherwise returns all locations.
        """
        employee = OrganizationService.get_employee(employee_id, db, tenant_id)
        if not employee:
            return []

        # Check if employee can work across locations
        if OrganizationService.can_employee_work_across_locations(employee_id, db, tenant_id):
            # Get all locations
            locations = db.query(func.distinct(Employee.location_id)).filter(
                Employee.tenant_id == tenant_id,
                Employee.location_id != None
            ).all()
            return [loc[0] for loc in locations if loc[0]]
        else:
            # Only their location
            return [employee.location_id] if employee.location_id else []

    @staticmethod
    def get_user_accessible_business_units(employee_id: str, db: Session, tenant_id: int = 1) -> List[str]:
        """Get list of business units this employee can access.

        Rules:
        - Employees see only their BU (cannot work cross-BU)
        - Partners see all BUs they manage
        - BU Heads see only their BU
        - Managers see their BU + their reports' BUs
        """
        employee = OrganizationService.get_employee(employee_id, db, tenant_id)
        if not employee:
            return []

        accessible_bus = set()

        # Add employee's own BU
        if employee.business_unit_id:
            accessible_bus.add(employee.business_unit_id)

        # Add reports' BUs if applicable
        subordinates = OrganizationService.get_all_subordinates(employee_id, db, tenant_id)
        for sub_id in subordinates:
            sub_emp = OrganizationService.get_employee(sub_id, db, tenant_id)
            if sub_emp and sub_emp.business_unit_id:
                accessible_bus.add(sub_emp.business_unit_id)

        return list(accessible_bus)

    @staticmethod
    def is_manager_of(manager_id: str, employee_id: str, db: Session, tenant_id: int = 1) -> bool:
        """Check if manager_id is a manager (direct or indirect) of employee_id."""
        if manager_id == employee_id:
            return False

        subordinates = OrganizationService.get_all_subordinates(manager_id, db, tenant_id)
        return employee_id in subordinates

    @staticmethod
    def get_org_hierarchy_tree(employee_id: str, db: Session, tenant_id: int = 1) -> dict:
        """Get complete organizational tree under employee."""
        employee = OrganizationService.get_employee(employee_id, db, tenant_id)
        if not employee:
            return {}

        def build_tree(emp_id: str) -> dict:
            emp = OrganizationService.get_employee(emp_id, db, tenant_id)
            if not emp:
                return {}

            direct_reports = OrganizationService.get_direct_reports(emp_id, db, tenant_id)

            return {
                "id": emp.id,
                "name": emp.name,
                "level": getattr(emp, 'level', None),
                "bu_id": emp.business_unit_id,
                "reports": [build_tree(report.id) for report in direct_reports]
            }

        return build_tree(employee_id)
