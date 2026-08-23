"""
Data Scoping Helper - RBAC Permission Enforcement
Ensures users only see data they have permission to access based on:
1. Role (CEO, Partner, BU Head, Manager, etc.)
2. Business Unit (BU scoping)
3. Reporting hierarchy (team members only)
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.user import Users
from app.models.employee import Employee


def get_reporting_tree_ids(db: Session, employee_id: str) -> list:
    """
    Get all employee IDs in the reporting tree below this employee.
    Includes: self + all direct and indirect subordinates.
    """
    if not employee_id:
        return []

    # Get self
    result_ids = [employee_id]

    # Get all direct reports
    def get_subordinates(emp_id: str):
        subordinates = db.query(Employee).filter(
            Employee.manager_id == emp_id
        ).all()
        for sub in subordinates:
            result_ids.append(sub.id)
            get_subordinates(sub.id)  # Recursive: get their reports too

    get_subordinates(employee_id)
    return result_ids


def enforce_data_scope(query, user: Users, resource_type, db: Session):
    """
    Apply data scoping filters based on user's role and hierarchy.

    Rules:
    - CEO: No filter (all data)
    - Partner/BU Head: BU filter + reporting tree filter
    - BU Manager/HR: BU filter only
    - Recruiter: Created_by filter (own candidates)
    - Everyone else: 403 (no access to financial data)

    Usage:
        query = db.query(Invoice)
        query = enforce_data_scope(query, current_user, Invoice, db)
    """
    from app.models.employee import Employee
    from app.models.candidate import Candidate
    from app.models.user import Users as UserModel

    # Get user's role template permissions
    user_role = user.UserRole or ""
    user_role_upper = user_role.upper()

    # CEO: No filtering
    if user_role_upper == "CEO" or user_role_upper == "SUPER_USER":
        return query

    # Partner/BU Head: Filter by BU + reporting hierarchy
    if user_role_upper in ["PARTNER", "BU_HEAD", "BU HEAD"]:
        # Must be in user's BU
        if hasattr(resource_type, 'business_unit_id'):
            query = query.filter(resource_type.business_unit_id == user.business_unit_id)

        # For employees: also filter by reporting tree
        if resource_type.__name__ == 'Employee':
            user_employee = db.query(Employee).filter(
                Employee.user_id == user.UserID
            ).first()
            if user_employee:
                team_ids = get_reporting_tree_ids(db, user_employee.id)
                query = query.filter(resource_type.id.in_(team_ids))

        return query

    # HR Manager: BU filter only (no hierarchy filter)
    if user_role_upper in ["HR_MANAGER", "HR MANAGER", "HR"]:
        if hasattr(resource_type, 'business_unit_id'):
            query = query.filter(resource_type.business_unit_id == user.business_unit_id)
        return query

    # Recruiter: Only own candidates (created_by filter)
    if user_role_upper in ["RECRUITER", "RECRUITMENT_MANAGER", "RECRUITMENT MANAGER"]:
        if resource_type.__name__ == 'Candidate':
            query = query.filter(resource_type.created_by == user.UserID)
        return query

    # Resource Manager: No filter (full financial access)
    if user_role_upper in ["RESOURCE_MANAGER", "RESOURCE MANAGER"]:
        return query

    # Everyone else: No access (will return empty)
    return query.filter(False)


def get_user_financial_access(user: Users) -> bool:
    """
    Check if user has any financial data access.
    Returns True only for: CEO, Partner, BU Head, Resource Manager
    """
    role = (user.UserRole or "").upper()
    return role in ["CEO", "SUPER_USER", "PARTNER", "BU_HEAD", "BU HEAD", "RESOURCE_MANAGER", "RESOURCE MANAGER"]


def get_user_bu_ids(db: Session, user: Users) -> list:
    """
    Get list of BU IDs user has access to.
    CEO: all BUs
    Partner/BU Head: their own BU only
    Others: their assigned BU only
    """
    role = (user.UserRole or "").upper()

    if role in ["CEO", "SUPER_USER"]:
        # Return None to indicate "all BUs"
        return None

    # Return user's assigned BU
    if user.business_unit_id:
        return [user.business_unit_id]

    return []
