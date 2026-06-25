"""
RBAC Admin Endpoints — manage roles, permissions, and user role assignments.
All routes require Super User or Admin access.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin, require_permission
from app.schemas.rbac import (
    RoleCreate, RoleResponse, RoleListItem,
    PermissionCreate, PermissionResponse,
    AssignRoleRequest, AssignPermissionRequest,
    UserPermissionSummary,
    SetBusinessUnitRequest, SetBusinessUnitResponse,
    BusinessUnitCreate, BusinessUnitResponse, BusinessUnitListItem,
    BusinessUnitWithDepartmentsResponse,
    DepartmentCreate, DepartmentUpdate, DepartmentResponse, DepartmentListItem,
    SetDepartmentRequest, SetDepartmentResponse,
)
from app.services.rbac_service import RBACService
from app.core.logging import logger
from app.models.rbac import BusinessUnit, Department
from app.models.user import Users, Jobs
from app.models.candidate_ownership import CandidateOwnership

router = APIRouter(prefix="/rbac", tags=["RBAC"])


# ===========================================================================
# Roles
# ===========================================================================

@router.get(
    "/roles",
    response_model=List[RoleListItem],
    summary="List all roles",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def list_roles(
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Return all defined RBAC roles (lightweight list)."""
    return RBACService.list_roles(db)


@router.post(
    "/roles",
    response_model=RoleListItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new role",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def create_role(
    data: RoleCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Create a new RBAC role. Returns 409 if the role name already exists."""
    try:
        return RBACService.create_role(db, data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error creating role: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create role")


@router.get(
    "/roles/{role_id}",
    response_model=RoleResponse,
    summary="Get a role with its attributes and permissions",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Retrieve a single role with its full attribute list and assigned permissions.
    """
    role = RBACService.get_role_or_404(db, role_id)
    # Build permissions list from role_permissions relationship
    permissions = [rp.permission for rp in role.role_permissions if rp.permission]
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        created_at=role.created_at,
        attributes=[
            {"id": a.id, "role_id": a.role_id, "attribute_name": a.attribute_name, "attribute_value": a.attribute_value}
            for a in role.attributes
        ],
        permissions=[
            {"id": p.id, "name": p.name, "description": p.description, "created_at": p.created_at}
            for p in permissions
        ],
    )


# ===========================================================================
# Permissions
# ===========================================================================

@router.get(
    "/permissions",
    response_model=List[PermissionResponse],
    summary="List all permissions",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def list_permissions(
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Return all defined RBAC permissions."""
    return RBACService.list_permissions(db)


@router.post(
    "/permissions",
    response_model=PermissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new permission",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def create_permission(
    data: PermissionCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Create a new named permission string. Returns 409 if it already exists."""
    try:
        return RBACService.create_permission(db, data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error creating permission: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create permission")


# ===========================================================================
# Role ↔ Permission Management
# ===========================================================================

@router.post(
    "/roles/{role_id}/permissions",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Assign a permission to a role",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def assign_permission_to_role(
    role_id: int,
    data: AssignPermissionRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Add a permission to a role. Idempotent — no error if already assigned."""
    try:
        RBACService.assign_permission_to_role(db, role_id, data.permission_id)
        return {"message": "Permission assigned successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error assigning permission: {exc}")
        raise HTTPException(status_code=500, detail="Failed to assign permission")


@router.delete(
    "/roles/{role_id}/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a permission from a role",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def remove_permission_from_role(
    role_id: int,
    permission_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Remove a permission from a role. Returns 404 if the mapping doesn't exist."""
    try:
        RBACService.remove_permission_from_role(db, role_id, permission_id)
        return {"message": "Permission removed successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error removing permission: {exc}")
        raise HTTPException(status_code=500, detail="Failed to remove permission")


# ===========================================================================
# User Role Assignment
# ===========================================================================

@router.post(
    "/users/{user_id}/assign-role",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Assign a role to a user",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def assign_role_to_user(
    user_id: str,
    data: AssignRoleRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Assign an RBAC role to a user by their UserID.
    Returns 404 if the user or role does not exist.
    """
    try:
        RBACService.assign_role_to_user(db, user_id, data.role_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error assigning role to user: {exc}")
        raise HTTPException(status_code=500, detail="Failed to assign role")


@router.get(
    "/users/{user_id}/permissions",
    response_model=UserPermissionSummary,
    summary="Get a user's effective permissions and attributes",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def get_user_permissions(
    user_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Inspect the full permission and attribute set for a user based on their assigned RBAC role.
    Returns an empty summary if no role is assigned.
    """
    return RBACService.get_user_permission_summary(db, user_id)


@router.post(
    "/users/set-business-unit",
    response_model=SetBusinessUnitResponse,
    summary="Assign a business unit to a user",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def set_business_unit_for_user(
    data: SetBusinessUnitRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_hr_or_admin),  # renamed to avoid shadowing
):
    """
    Assign a business unit to a user by their UserID.
    Returns 404 if the user or business unit does not exist.
    """
    target_user = db.query(Users).filter(Users.UserID == data.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        target_user.business_unit_id = data.business_unit_id
        db.commit()
        db.refresh(target_user)
        return SetBusinessUnitResponse(
            user_id=target_user.UserID,
            business_unit_id=target_user.business_unit_id,
            message="Business unit assigned successfully",
        )
    except Exception as exc:
        logger.error(f"Error setting business unit for user: {exc}")
        raise HTTPException(status_code=500, detail="Failed to set business unit")

@router.put(
    "/users/{user_id}/business-unit",
    response_model=SetBusinessUnitResponse,
    summary="Update a user's business unit",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def update_business_unit_for_user(
    user_id: str,
    data: SetBusinessUnitRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_hr_or_admin),  # renamed to avoid shadowing
):
    """
    Update a user's business unit by their UserID.
    Returns 404 if the user or business unit does not exist.
    """
    target_user = db.query(Users).filter(Users.UserID == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        target_user.business_unit_id = data.business_unit_id
        db.commit()
        db.refresh(target_user)
        return SetBusinessUnitResponse(
            user_id=target_user.UserID,
            business_unit_id=target_user.business_unit_id,
            message="Business unit updated successfully",
        )
    except Exception as exc:
        logger.error(f"Error updating business unit for user: {exc}")
        raise HTTPException(status_code=500, detail="Failed to update business unit")

@router.get(
    "/users/{user_id}/business-unit",
    response_model=BusinessUnitResponse,
    summary="Get the business unit assigned to a user",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def get_user_business_unit(
    user_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Retrieve the business unit assigned to a user by their UserID.
    Returns 404 if the user does not exist or has no business unit assigned.
    """
    target_user = db.query(Users).filter(Users.UserID == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    if not target_user.business_unit_id:
        raise HTTPException(status_code=404, detail="No business unit assigned to this user")
    bu = db.query(BusinessUnit).filter(BusinessUnit.id == target_user.business_unit_id).first()
    if not bu:
        raise HTTPException(status_code=404, detail="Assigned business unit not found")
    return bu


@router.post(
    "/business-units",
    response_model=BusinessUnitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new business unit",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def create_business_unit(
    data: BusinessUnitCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Create a new business unit.
    Returns 409 if the business unit name already exists.
    """
    if db.query(BusinessUnit).filter(BusinessUnit.name == data.name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Business unit '{data.name}' already exists")
    try:
        business_unit = BusinessUnit(
            name=data.name,
            description=data.description,
            # created_at is set by server_default — do NOT pass it manually
        )
        db.add(business_unit)
        db.commit()
        db.refresh(business_unit)
        return business_unit
    except Exception as exc:
        logger.error(f"Error creating business unit: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create business unit")

@router.get(
    "/business-units",
    response_model=List[BusinessUnitListItem],
    summary="List all business units",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def list_business_units(
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Return all defined business units."""
    try:
        BusinessUnitList = db.query(BusinessUnit).all()
        return BusinessUnitList
    except Exception as exc:
        logger.error(f"Error listing business units: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list business units")

@router.delete(
    "/business-units/{business_unit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a business unit",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def delete_business_unit(
    business_unit_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Delete a business unit by its ID. Returns 404 if not found."""
    business_unit = db.query(BusinessUnit).filter(BusinessUnit.id == business_unit_id).first()
    if not business_unit:
        raise HTTPException(status_code=404, detail="Business unit not found")
    try:
        # Nullify referencing departments, users, jobs, and candidate ownerships to avoid foreign key violations
        db.query(Department).filter(Department.business_unit_id == business_unit_id).update({Department.business_unit_id: None}, synchronize_session=False)
        db.query(Users).filter(Users.business_unit_id == business_unit_id).update({Users.business_unit_id: None}, synchronize_session=False)
        db.query(Jobs).filter(Jobs.business_unit_id == business_unit_id).update({Jobs.business_unit_id: None}, synchronize_session=False)
        db.query(CandidateOwnership).filter(CandidateOwnership.owned_by_bu_id == business_unit_id).update({CandidateOwnership.owned_by_bu_id: None}, synchronize_session=False)
        db.delete(business_unit)
        db.commit()
    except Exception as exc:
        logger.error(f"Error deleting business unit: {exc}")
        raise HTTPException(status_code=500, detail="Failed to delete business unit")


# ===========================================================================
# Missing RBAC Management Endpoints
# ===========================================================================

@router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a role",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Delete an RBAC role by ID. Returns 404 if not found."""
    role = RBACService.get_role_or_404(db, role_id)
    try:
        db.delete(role)
        db.commit()
    except Exception as exc:
        logger.error(f"Error deleting role: {exc}")
        raise HTTPException(status_code=500, detail="Failed to delete role")


@router.put(
    "/roles/{role_id}",
    response_model=RoleListItem,
    summary="Update a role name/description",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def update_role(
    role_id: int,
    data: RoleCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Update the name or description of a role. Returns 404 if not found."""
    role = RBACService.get_role_or_404(db, role_id)
    try:
        role.name = data.name
        role.description = data.description
        db.commit()
        db.refresh(role)
        return role
    except Exception as exc:
        logger.error(f"Error updating role: {exc}")
        raise HTTPException(status_code=500, detail="Failed to update role")


@router.delete(
    "/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a permission",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def delete_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Delete a permission by ID. Returns 404 if not found."""
    from app.models.rbac import Permission
    perm = db.query(Permission).filter(Permission.id == permission_id).first()
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    try:
        db.delete(perm)
        db.commit()
    except Exception as exc:
        logger.error(f"Error deleting permission: {exc}")
        raise HTTPException(status_code=500, detail="Failed to delete permission")


@router.get(
    "/users/{user_id}/role",
    response_model=RoleListItem,
    summary="Get the RBAC role assigned to a user",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def get_user_role(
    user_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Return the role currently assigned to a user. Returns 404 if no role is set."""
    target = db.query(Users).filter(Users.UserID == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if not target.role_id:
        raise HTTPException(status_code=404, detail="No role assigned to this user")
    from app.models.rbac import Role
    role = db.query(Role).filter(Role.id == target.role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Assigned role not found")
    return role


@router.delete(
    "/users/{user_id}/role",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the RBAC role from a user",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def revoke_user_role(
    user_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Remove the RBAC role assignment from a user."""
    target = db.query(Users).filter(Users.UserID == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        target.role_id = None
        db.commit()
    except Exception as exc:
        logger.error(f"Error revoking role from user: {exc}")
        raise HTTPException(status_code=500, detail="Failed to revoke role")


@router.get(
    "/business-units/{business_unit_id}",
    response_model=BusinessUnitResponse,
    summary="Get a single business unit by ID",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def get_business_unit(
    business_unit_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Retrieve a single business unit by its ID. Returns 404 if not found."""
    bu = db.query(BusinessUnit).filter(BusinessUnit.id == business_unit_id).first()
    if not bu:
        raise HTTPException(status_code=404, detail="Business unit not found")
    return bu


@router.put(
    "/business-units/{business_unit_id}",
    response_model=BusinessUnitResponse,
    summary="Update a business unit",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def update_business_unit(
    business_unit_id: int,
    data: BusinessUnitCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Update the name or description of a business unit. Returns 404 if not found."""
    bu = db.query(BusinessUnit).filter(BusinessUnit.id == business_unit_id).first()
    if not bu:
        raise HTTPException(status_code=404, detail="Business unit not found")
    try:
        bu.name = data.name
        bu.description = data.description
        db.commit()
        db.refresh(bu)
        return bu
    except Exception as exc:
        logger.error(f"Error updating business unit: {exc}")
        raise HTTPException(status_code=500, detail="Failed to update business unit")


# ===========================================================================
# Departments
# ===========================================================================

@router.post(
    "/departments",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new department",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def create_department(
    data: DepartmentCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Create a new department, optionally linking it to a Business Unit.
    Returns **409** if a department with the same name already exists.
    Returns **404** if the specified `business_unit_id` does not exist.
    """
    if data.business_unit_id is not None:
        bu = db.query(BusinessUnit).filter(BusinessUnit.id == data.business_unit_id).first()
        if not bu:
            raise HTTPException(status_code=404, detail=f"Business unit {data.business_unit_id} not found")
    try:
        dept = Department(
            name=data.name,
            description=data.description,
            business_unit_id=data.business_unit_id,
        )
        db.add(dept)
        db.commit()
        db.refresh(dept)
        return DepartmentResponse(
            id=dept.id,
            name=dept.name,
            description=dept.description,
            created_at=dept.created_at,
            business_unit_id=dept.business_unit_id,
            business_unit_name=dept.business_unit.name if dept.business_unit else None,
        )
    except Exception as exc:
        logger.error(f"Error creating department: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create department")


@router.get(
    "/departments",
    response_model=List[DepartmentListItem],
    summary="List all departments",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def list_departments(
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Return all defined departments with their linked Business Unit info."""
    try:
        depts = db.query(Department).order_by(Department.name).all()
        return [
            DepartmentListItem(
                id=d.id,
                name=d.name,
                description=d.description,
                business_unit_id=d.business_unit_id,
                business_unit_name=d.business_unit.name if d.business_unit else None,
            )
            for d in depts
        ]
    except Exception as exc:
        logger.error(f"Error listing departments: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list departments")


@router.get(
    "/departments/{department_id}",
    response_model=DepartmentResponse,
    summary="Get a single department by ID",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Retrieve a single department by its ID. Returns **404** if not found."""
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return DepartmentResponse(
        id=dept.id,
        name=dept.name,
        description=dept.description,
        created_at=dept.created_at,
        business_unit_id=dept.business_unit_id,
        business_unit_name=dept.business_unit.name if dept.business_unit else None,
    )


@router.put(
    "/departments/{department_id}",
    response_model=DepartmentResponse,
    summary="Update a department",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def update_department(
    department_id: int,
    data: DepartmentUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Update the name, description, or Business Unit of a department.
    Returns **404** if the department or specified BU is not found.
    Returns **409** if the new name already exists.
    """
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    if data.name and data.name != dept.name:
        if db.query(Department).filter(Department.name == data.name).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Department '{data.name}' already exists",
            )
    # Validate business_unit_id if it is being changed
    if data.business_unit_id is not None:
        bu = db.query(BusinessUnit).filter(BusinessUnit.id == data.business_unit_id).first()
        if not bu:
            raise HTTPException(status_code=404, detail=f"Business unit {data.business_unit_id} not found")
    try:
        if data.name is not None:
            dept.name = data.name
        if data.description is not None:
            dept.description = data.description
        # Allow explicit None to unlink from BU; only update if key was provided
        if data.business_unit_id is not None or "business_unit_id" in (data.model_fields_set or set()):
            dept.business_unit_id = data.business_unit_id
        db.commit()
        db.refresh(dept)
        return DepartmentResponse(
            id=dept.id,
            name=dept.name,
            description=dept.description,
            created_at=dept.created_at,
            business_unit_id=dept.business_unit_id,
            business_unit_name=dept.business_unit.name if dept.business_unit else None,
        )
    except Exception as exc:
        logger.error(f"Error updating department: {exc}")
        raise HTTPException(status_code=500, detail="Failed to update department")


@router.delete(
    "/departments/{department_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a department",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Delete a department by its ID. Returns **404** if not found."""
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    try:
        # Nullify referencing users and jobs to avoid foreign key violations
        db.query(Users).filter(Users.department_id == department_id).update({Users.department_id: None}, synchronize_session=False)
        db.query(Jobs).filter(Jobs.department_id == department_id).update({Jobs.department_id: None}, synchronize_session=False)
        db.delete(dept)
        db.commit()
    except Exception as exc:
        logger.error(f"Error deleting department: {exc}")
        raise HTTPException(status_code=500, detail="Failed to delete department")


@router.post(
    "/users/set-department",
    response_model=SetDepartmentResponse,
    summary="Assign a department to a user",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def set_department_for_user(
    data: SetDepartmentRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_hr_or_admin),
):
    """
    Assign a department to a user by their UserID.
    Returns **404** if the user or department does not exist.
    """
    target_user = db.query(Users).filter(Users.UserID == data.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    dept = db.query(Department).filter(Department.id == data.department_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    try:
        target_user.department_id = data.department_id
        db.commit()
        db.refresh(target_user)
        return SetDepartmentResponse(
            user_id=target_user.UserID,
            department_id=target_user.department_id,
            message="Department assigned successfully",
        )
    except Exception as exc:
        logger.error(f"Error setting department for user: {exc}")
        raise HTTPException(status_code=500, detail="Failed to set department")


@router.put(
    "/users/{user_id}/department",
    response_model=SetDepartmentResponse,
    summary="Update a user's department",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def update_department_for_user(
    user_id: str,
    data: SetDepartmentRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_hr_or_admin),
):
    """
    Change the department assigned to a user.
    Returns **404** if the user or department does not exist.
    """
    target_user = db.query(Users).filter(Users.UserID == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    dept = db.query(Department).filter(Department.id == data.department_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    try:
        target_user.department_id = data.department_id
        db.commit()
        db.refresh(target_user)
        return SetDepartmentResponse(
            user_id=target_user.UserID,
            department_id=target_user.department_id,
            message="Department updated successfully",
        )
    except Exception as exc:
        logger.error(f"Error updating department for user: {exc}")
        raise HTTPException(status_code=500, detail="Failed to update department")


@router.get(
    "/users/{user_id}/department",
    response_model=DepartmentResponse,
    summary="Get the department assigned to a user",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def get_user_department(
    user_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Retrieve the department assigned to the given user.
    Returns **404** if the user does not exist or has no department assigned.
    """
    target_user = db.query(Users).filter(Users.UserID == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    if not target_user.department_id:
        raise HTTPException(status_code=404, detail="No department assigned to this user")
    dept = db.query(Department).filter(Department.id == target_user.department_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Assigned department not found")
    return DepartmentResponse(
        id=dept.id,
        name=dept.name,
        description=dept.description,
        created_at=dept.created_at,
        business_unit_id=dept.business_unit_id,
        business_unit_name=dept.business_unit.name if dept.business_unit else None,
    )


# ===========================================================================
# BU ↔ Department cross-lookup endpoints
# ===========================================================================

@router.get(
    "/business-units/{business_unit_id}/departments",
    response_model=BusinessUnitWithDepartmentsResponse,
    summary="Get all departments that belong to a Business Unit",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def get_departments_by_business_unit(
    business_unit_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Return a Business Unit together with the full list of departments linked to it.
    Returns **404** if the Business Unit does not exist.
    """
    bu = db.query(BusinessUnit).filter(BusinessUnit.id == business_unit_id).first()
    if not bu:
        raise HTTPException(status_code=404, detail="Business unit not found")
    return BusinessUnitWithDepartmentsResponse(
        id=bu.id,
        name=bu.name,
        description=bu.description,
        created_at=bu.created_at,
        departments=bu.departments,
    )


@router.get(
    "/departments/{department_id}/business-unit",
    response_model=BusinessUnitResponse,
    summary="Get the Business Unit that a department belongs to",
    dependencies=[Depends(require_permission("rbac.manage"))],
)
def get_business_unit_by_department(
    department_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Resolve the parent Business Unit for a given department.
    Returns **404** if the department does not exist or is not linked to any BU.
    """
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    if not dept.business_unit_id:
        raise HTTPException(
            status_code=404,
            detail="This department is not linked to any Business Unit",
        )
    bu = db.query(BusinessUnit).filter(BusinessUnit.id == dept.business_unit_id).first()
    if not bu:
        raise HTTPException(status_code=404, detail="Linked Business Unit not found")
    return bu
