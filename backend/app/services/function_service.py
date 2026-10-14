"""Functions (CEO 2026-10-13): ONE managed list -- Recruitment, HR, Finance, Sales ... -- replacing
the separate "department" and "function" ideas. A person belongs to a function
(users.department_id), tasks and approvals route to it, and a function add-on template is for it
(RoleTemplate.specialization = the function's name). Admins add, rename and retire functions on
Organizational Hierarchy > Manage Functions. Stored in the departments table (no data moved).
"""
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.org_structure import Department

GENERAL = "General"


def active_functions(db: Session, tenant_id: int) -> List[Department]:
    return (db.query(Department).filter(Department.tenant_id == tenant_id, Department.active.is_(True))
            .order_by(Department.name).all())


def function_names(db: Session, tenant_id: int) -> List[str]:
    return [GENERAL] + [d.name for d in active_functions(db, tenant_id)]


def canonical_name(db: Session, tenant_id: int, value: Optional[str]) -> str:
    """General, or the stored name of one of the tenant's active functions (case-insensitive).
    Raises ValueError otherwise."""
    value = (value or GENERAL).strip()
    if value.lower() == GENERAL.lower():
        return GENERAL
    match = db.query(Department).filter(Department.tenant_id == tenant_id, Department.active.is_(True),
                                        func.lower(Department.name) == value.lower()).first()
    if match is None:
        raise ValueError(f"{value!r} is not an active function - add it under Manage Functions first")
    return match.name


def active_function_or_error(db: Session, tenant_id: int, function_id: Optional[str]) -> Optional[Department]:
    """The tenant's active function with this id (None for none). Raises ValueError otherwise."""
    if not function_id:
        return None
    match = db.query(Department).filter(Department.id == function_id, Department.tenant_id == tenant_id).first()
    if match is None:
        raise ValueError("Function not found")
    if not match.active:
        raise ValueError(f"The {match.name} function is retired - pick an active one")
    return match
