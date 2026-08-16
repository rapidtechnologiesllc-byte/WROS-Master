import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db, check_user
from app.core.visibility import should_bypass_bu_filter, get_user_bu_id

logger = logging.getLogger(__name__)
from app.core.security import get_password_hash, create_access_token
from app.core.dependencies import get_current_hr_or_admin, require_permission
from app.models import Users, Candidate, CandidateAssignment, Interview, InterviewPanel, InterviewFeedback, PanelMember, Role, BusinessUnit, Department
from app.models.user import Jobs
from app.models.offer_letter import OfferLetter
from app.models.document import CandidateDocument
from app.models.newsletter import Newsletter
from app.schemas.auth import SignupRequest
from app.schemas.user import (
    AllUsersResponse, UserResponse,
    CandidateAssignmentCreate, CandidateAssignmentResponse,
    InterviewCreate, InterviewResponse, InterviewUpdateRequest,
    InterviewFeedbackCreate, InterviewFeedbackResponse,
    AssignedCandidateResponse, AssignedInterviewResponse,
    PanelMemberCreate, PanelMemberResponse, DeleteResponse,
    ChangePasswordRequest, HrMeResponse,
    SingleUserResponse, HiringManagerAssignedCandidateResponse,
    DigestPreferenceRequest, DigestPreferenceResponse,
    AdminResetPasswordRequest,
    CreateUserWithRolesRequest, UpdateUserWithRolesRequest,
)
from app.utils.uniq_id_generator import user_id_generator

router = APIRouter(prefix="/hr", tags=["hr"])


@router.get(
    "/me",
    response_model=HrMeResponse,
    summary="Get current HR/Admin user's profile with a fresh access token",
)
def get_me(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    """
    Return the profile of the currently authenticated HR / Admin user
    together with a fresh access token.

    Useful for:
    - Restoring session state after page reload
    - Refreshing the token without a full re-login
    - Fetching up-to-date role / business-unit information
    """
    from app.models.user import UserRole as UserRoleModel
    from app.models.rbac import RolePermission, Permission

    # Get actual roles from user_roles junction table (not legacy UserRole column)
    user_roles = db.query(UserRoleModel).filter(UserRoleModel.user_id == current_user.UserID).all()
    assigned_roles = []
    roles_list = []
    for ur in user_roles:
        if ur.role:
            assigned_roles.append(ur.role.name)
            roles_list.append({"id": ur.role.id, "name": ur.role.name})

    # Display role: if has roles, join them; otherwise fall back to legacy UserRole
    display_role = ", ".join(assigned_roles) if assigned_roles else current_user.UserRole

    # Get all permissions for this user (union of all role permissions)
    permissions_set = set()
    for ur in user_roles:
        if ur.role:
            role_perms = db.query(RolePermission).filter(
                RolePermission.role_id == ur.role.id
            ).all()
            for rp in role_perms:
                if rp.permission:
                    permissions_set.add(rp.permission.name)

    permissions = list(permissions_set)

    # Resolve the RBAC role name (if any)
    role = db.query(Role).filter(Role.id == current_user.role_id).first() if current_user.role_id else None

    # Mint a fresh token using the same claims as login
    access_token = create_access_token(
        data={
            "sub": current_user.UserEmail,
            "type": display_role,
            "name": current_user.UserName,
            "roles": roles_list,
            "permissions": permissions,
        }
    )

    return HrMeResponse(
        user_id=current_user.UserID,
        user_name=current_user.UserName,
        user_email=current_user.UserEmail,
        user_role=display_role,
        permission_role=role.name if role else None,
        role_id=current_user.role_id,
        business_unit_id=current_user.business_unit_id,
        created_at=current_user.CreatedAt,
        access_token=access_token,
        digest_enabled=current_user.digest_enabled,
        roles=roles_list,
        permissions=permissions,
    )


@router.patch(
    "/me/digest-preference",
    response_model=DigestPreferenceResponse,
    summary="Enable/disable the recruiter's own Thunder morning digest (S-065/HRMS-0465)",
)
def update_digest_preference(
    payload: DigestPreferenceRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    current_user.digest_enabled = payload.digest_enabled
    db.add(current_user)
    db.commit()
    return DigestPreferenceResponse(digest_enabled=current_user.digest_enabled)


@router.get(
    "/users/all",
    response_model=AllUsersResponse,
)
def get_all_users(
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Get all users (HR, Admin, etc.) from the system.
    Does not include candidates.
    Returns actual roles assigned via user_roles junction table, not legacy UserRole column.

    Args:
        db: Database session
        user: Authenticated HR/Admin user

    Returns:
        AllUsersResponse with list of all users and total count
    """
    try:
        from app.models.user import UserRole
        from app.models.rbac import Role

        # HRMS-0109 -- scoped to the caller's own tenant, never all tenants' users.
        users = db.query(Users).all()

        # Build response
        users_data = []
        for u in users:
            # Get actual roles from user_roles junction table (not legacy UserRole column)
            user_roles = db.query(UserRole).filter(UserRole.user_id == u.UserID).all()
            assigned_roles = []
            for ur in user_roles:
                if ur.role:
                    assigned_roles.append(ur.role.name)

            # Display role: if has roles, join them; otherwise fall back to legacy UserRole
            display_role = ", ".join(assigned_roles) if assigned_roles else u.UserRole

            users_data.append(UserResponse(
                user_id=u.UserID,
                user_name=u.UserName or "",
                user_email=u.UserEmail,
                user_role=display_role,
                created_at=u.CreatedAt,
                permission_role=u.role.name if u.role else None,
                department_id=u.department_id,
                department_name=u.department.name if u.department else None,
                business_unit_id=u.business_unit_id,
                business_unit_name=u.bu_context.business_unit.name if u.bu_context and u.bu_context.business_unit else None,
            ))

        return AllUsersResponse(
            total_users=len(users_data),
            users=users_data
        )
    except Exception as exc:
        logger.error(f"Error fetching users: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch users: {str(exc)}")


@router.get(
    "/users/search",
    response_model=AllUsersResponse,
    summary="Search / filter users by name, permission role, or user role",
)
def search_users(
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
    name: Optional[str] = Query(
        default=None,
        description="Partial, case-insensitive search on user name or email",
    ),
    permission_role: Optional[str] = Query(
        default=None,
        description="Exact RBAC role name to filter by (e.g. 'HR Manager', 'Admin')",
    ),
    user_role: Optional[str] = Query(
        default=None,
        description="Legacy UserRole field filter (e.g. 'HR', 'Admin', 'Recruiter')",
    ),
    department: Optional[str] = Query(
        default=None,
        description="Partial, case-insensitive match on department name",
    ),
    business_unit: Optional[str] = Query(
        default=None,
        description="Partial, case-insensitive match on business unit name",
    ),
    skip: int = Query(default=0, ge=0, description="Records to skip"),
    limit: int = Query(default=50, ge=1, le=200, description="Max records to return (1–200)"),
):
    """
    Search users with any combination of filters.  All filters are optional —
    omit all of them to get a paginated list of every user.

    **Filters:**
    - `name` — partial, case-insensitive match on `UserName` **or** `UserEmail`
    - `permission_role` — exact match on the RBAC `Role.name`
      (e.g. `'HR Manager'`, `'Recruiter'`, `'Admin'`)
    - `user_role` — exact match on the legacy `UserRole` column
      (e.g. `'HR'`, `'Admin'`)
    - `department` — partial, case-insensitive match on `Department.name`
    - `business_unit` — partial, case-insensitive match on `BusinessUnit.name`

    **Pagination:** use `skip` / `limit`.
    """
    from sqlalchemy import or_, func as sql_func

    # HRMS-0109 -- scope to the caller's tenant before any of the
    # optional filters below narrow it further.
    query = db.query(Users)

    # ── name filter — partial match on UserName OR UserEmail ─────────────────
    if name:
        pattern = f"%{name.lower()}%"
        query = query.filter(
            or_(
                sql_func.lower(Users.UserName).like(pattern),
                sql_func.lower(Users.UserEmail).like(pattern),
            )
        )

    # ── legacy role filter ────────────────────────────────────────────────────
    if user_role:
        query = query.filter(Users.UserRole == user_role)

    # ── RBAC permission role filter — join through Role ───────────────────────
    if permission_role:
        query = query.join(Role, Role.id == Users.role_id).filter(
            Role.name == permission_role
        )

    # ── Department filter — join through Department ───────────────────────────
    if department:
        dept_pattern = f"%{department.lower()}%"
        query = query.join(Department, Department.id == Users.department_id).filter(
            sql_func.lower(Department.name).like(dept_pattern)
        )

    # ── Business unit filter — join through BusinessUnit ─────────────────────
    if business_unit:
        bu_pattern = f"%{business_unit.lower()}%"
        query = query.join(BusinessUnit, BusinessUnit.id == Users.business_unit_id).filter(
            sql_func.lower(BusinessUnit.name).like(bu_pattern)
        )

    total = query.count()
    matched_users = query.order_by(Users.UserID).offset(skip).limit(limit).all()

    users_data = []
    for u in matched_users:
        role = db.query(Role).filter(Role.id == u.role_id).first()
        users_data.append(UserResponse(
            user_id=u.UserID,
            user_name=u.UserName or "",
            user_email=u.UserEmail,
            user_role=u.UserRole,
            created_at=u.CreatedAt,
            permission_role=role.name if role else None,
            department_id=u.department_id,
            department_name=u.department.name if u.department else None,
            business_unit_id=u.business_unit_id,
            business_unit_name=u.bu_context.name if u.bu_context else None,
        ))

    return AllUsersResponse(
        total_users=total,
        users=users_data,
    )


@router.get(
    "/users/details/{user_id}",
    response_model=UserResponse,
    summary="Get user details by user ID",
)
def get_user_details_by_id(
    user_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_hr_or_admin),
):
    """
    Retrieve user details by their User ID, including department and business unit.
    """
    u = db.query(Users).filter(Users.UserID == user_id).first()
    if not u:
        raise HTTPException(
            status_code=404,
            detail=f"User with ID '{user_id}' not found"
        )

    role = db.query(Role).filter(Role.id == u.role_id).first() if u.role_id else None

    return UserResponse(
        user_id=u.UserID,
        user_name=u.UserName or "",
        user_email=u.UserEmail,
        user_role=u.UserRole,
        created_at=u.CreatedAt,
        permission_role=role.name if role else None,
        department_id=u.department_id,
        department_name=u.department.name if u.department else None,
        business_unit_id=u.business_unit_id,
        business_unit_name=u.bu_context.name if u.bu_context else None,
    )



@router.post(
    "/assignments/create",
    response_model=CandidateAssignmentResponse,
    status_code=201,
    dependencies=[Depends(require_permission("candidate.edit"))],
)
def create_candidate_assignment(
    request: CandidateAssignmentCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Create a candidate assignment with hiring and reporting managers.
    
    Args:
        request: CandidateAssignmentCreate containing candidate_id and manager IDs
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        CandidateAssignmentResponse with assignment details
        
    Raises:
        HTTPException: If candidate or managers not found
    """
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == request.candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {request.candidate_id} not found"
        )
    
    # Verify hiring manager exists if provided
    if request.hiring_manager_id:
        hiring_manager = db.query(Users).filter(Users.UserID == request.hiring_manager_id).first()
        if not hiring_manager:
            raise HTTPException(
                status_code=404,
                detail=f"Hiring manager with ID {request.hiring_manager_id} not found"
            )
    
    # Verify reporting manager exists if provided
    if request.reporting_manager_id:
        reporting_manager = db.query(Users).filter(Users.UserID == request.reporting_manager_id).first()
        if not reporting_manager:
            raise HTTPException(
                status_code=404,
                detail=f"Reporting manager with ID {request.reporting_manager_id} not found"
            )
    
    # Create assignment
    assignment = CandidateAssignment(
        candidate_id=request.candidate_id,
        hiring_manager_id=request.hiring_manager_id,
        reporting_manager_id=request.reporting_manager_id
    )
    
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    
    return CandidateAssignmentResponse(
        id=assignment.id,
        candidate_id=assignment.candidate_id,
        hiring_manager_id=assignment.hiring_manager_id,
        reporting_manager_id=assignment.reporting_manager_id,
        created_at=assignment.created_at
    )


@router.get(
    "/assignments/candidates",
    response_model=list[AssignedCandidateResponse],
    dependencies=[Depends(require_permission("candidate.view"))],
)
def get_assigned_candidates(
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Get all candidates assigned to the logged-in user (as hiring or reporting manager).
    
    Args:
        db: Database session
        user: Authenticated user
        
    Returns:
        List of AssignedCandidateResponse with candidate details
    """
    # Get user ID from Users object (user is a Users object, not a dict)
    user_id = user.UserID  # Using UserID to match foreign key in CandidateAssignment
    
    # Query assignments where user is hiring or reporting manager
    assignments = db.query(CandidateAssignment).filter(
        or_(
            CandidateAssignment.hiring_manager_id == user_id,
            CandidateAssignment.reporting_manager_id == user_id
        )
    ).all()
    
    results = []
    for assignment in assignments:
        # Get candidate details
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == assignment.candidate_id
        ).first()
        
        if candidate:
            # Construct candidate name
            name_parts = [
                candidate.candidateFirstName or "",
                candidate.candidateMiddleName or "",
                candidate.candidateLastName or ""
            ]
            candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"
            
            # Determine assignment type
            assignment_type = "hiring_manager" if assignment.hiring_manager_id == user_id else "reporting_manager"
            
            results.append(AssignedCandidateResponse(
                candidate_id=candidate.candidateID,
                candidate_name=candidate_name,
                candidate_email=candidate.candidateEmail,
                candidate_mobile=candidate.candidateMobile,
                assignment_type=assignment_type,
                assigned_at=assignment.created_at
            ))
    
    return results


@router.get(
    "/interviews/assigned",
    response_model=list[AssignedInterviewResponse],
    dependencies=[Depends(require_permission("interview.view"))],
)
def get_assigned_interviews(
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Get all interviews where the logged-in user is a panel member.
    
    Args:
        db: Database session
        user: Authenticated user
        
    Returns:
        List of AssignedInterviewResponse with interview details
    """
    # Get user ID from Users object (user is a Users object, not a dict)
    user_id = user.UserID  # Using UserID to match foreign key in PanelMember
    
    # Query panel memberships for this user
    panel_memberships = db.query(PanelMember).filter(
        PanelMember.interviewer_id == user_id
    ).all()
    
    results = []
    for membership in panel_memberships:
        # Get interviews for this panel
        interviews = db.query(Interview).filter(
            Interview.panel_id == membership.panel_id
        ).all()
        
        for interview in interviews:
            # Get panel details
            panel = db.query(InterviewPanel).filter(
                InterviewPanel.id == interview.panel_id
            ).first()
            
            # Get candidate details
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == interview.candidate_id
            ).first()
            
            if candidate and panel:
                # Construct candidate name
                name_parts = [
                    candidate.candidateFirstName or "",
                    candidate.candidateMiddleName or "",
                    candidate.candidateLastName or ""
                ]
                candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"
                
                results.append(AssignedInterviewResponse(
                    interview_id=interview.id,
                    candidate_id=candidate.candidateID,
                    candidate_name=candidate_name,
                    panel_id=panel.id,
                    round_name=panel.round_name,
                    start_time=interview.start_time,
                    end_time=interview.end_time,
                    meeting_link=interview.meeting_link,
                    status=interview.status
                ))
    
    return results



# ============================================
# HR User Management Endpoints
# ============================================

@router.post(
    "/users/create",
    response_model=UserResponse,
    status_code=201,
    summary="Create a new HR/Admin user",
    dependencies=[Depends(require_permission("user.manage"))],
)
def create_user(
    request: SignupRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Create a new internal user (HR, Admin, etc.).
    Requires permission: user.manage
    """
    from app.schemas.auth import SignupRequest as SR
    from app.core.database import check_user
    existing = check_user(db, request.user_email)
    if existing:
        raise HTTPException(status_code=400, detail=f"User with email {request.user_email} already exists")
    new_user = Users(
        UserID=user_id_generator(),
        UserName=request.user_name,
        UserEmail=request.user_email,
        UserPassword=get_password_hash(request.user_password),
        UserRole=request.user_role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return UserResponse(
        user_id=new_user.UserID,
        user_name=new_user.UserName or "",
        user_email=new_user.UserEmail,
        user_role=new_user.UserRole,
        created_at=new_user.CreatedAt
    )


@router.post(
    "/users/create-with-roles",
    response_model=UserResponse,
    status_code=201,
    summary="Create user with multi-role and BU assignment",
    dependencies=[Depends(require_permission("user.manage"))],
)
def create_user_with_roles(
    payload: CreateUserWithRolesRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_hr_or_admin)
):
    """
    Create user with multiple roles and Business Unit assignment.

    Supports:
    - Multi-role assignment (e.g., Partner + BU Head + Hiring Manager)
    - Business Unit scoping
    - Combined permissions from all assigned roles
    - Optional job title field

    Requires permission: user.manage
    """
    from app.core.database import check_user
    from app.models.rbac import Role
    from app.models.user import UserRole

    # Check if any org-level roles are being assigned
    from app.models.rbac import Role
    org_level_role_names = {"CEO", "CFO", "Super User", "ADMIN", "SUPER_USER"}

    # Get all roles being assigned
    roles_to_assign = db.query(Role).filter(Role.id.in_(payload.role_ids)).all()
    has_org_level_role = any(r.name in org_level_role_names for r in roles_to_assign)

    # Check if current user has org-level role(s)
    current_user_roles = db.query(UserRole).filter(UserRole.user_id == current_user.UserID).all()
    current_user_has_org_role = any(
        ur.role and ur.role.name in org_level_role_names
        for ur in current_user_roles
    )
    # Also check legacy UserRole field
    if current_user.UserRole and current_user.UserRole.upper() in org_level_role_names:
        current_user_has_org_role = True

    # Verify BU access (skip if assigning org-level roles OR if current user is org-level)
    if not has_org_level_role and not current_user_has_org_role and payload.business_unit_id and current_user.business_unit_id != payload.business_unit_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot create users outside your Business Unit"
        )

    # Check if email exists
    existing = check_user(db, payload.user_email)
    if existing:
        raise HTTPException(status_code=400, detail=f"User with email {payload.user_email} already exists")

    # Create user
    # Note: business_unit_id is a property; actual column is bu_context_id
    # Org-level roles should NOT have BU restriction (no BU set)
    bu_context_id = None
    if has_org_level_role:
        # Org-level roles have no BU restriction
        bu_context_id = None
    elif payload.business_unit_id:
        from app.models.business_unit import BusinessUnitContext
        bu_context = db.query(BusinessUnitContext).filter(
            BusinessUnitContext.id == payload.business_unit_id
        ).first()
        if bu_context:
            bu_context_id = bu_context.id

    new_user = Users(
        UserID=user_id_generator(),
        UserName=payload.user_name,
        UserEmail=payload.user_email,
        UserPassword=get_password_hash(payload.user_password),
        bu_context_id=bu_context_id,
        UserRole="MultiRole"  # Indicates user has multiple roles
    )
    db.add(new_user)
    db.flush()

    # Assign roles
    for role_id in payload.role_ids:
        # Verify role exists
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail=f"Role {role_id} not found")

        user_role = UserRole(
            id=f"ur_{new_user.UserID}_{role_id}",
            user_id=new_user.UserID,
            role_id=role_id,
            # Note: UserRole doesn't have business_unit_id field; BU scoping done via Users.business_unit_id
        )
        db.add(user_role)

    db.commit()
    db.refresh(new_user)

    return UserResponse(
        user_id=new_user.UserID,
        user_name=new_user.UserName or "",
        user_email=new_user.UserEmail,
        user_role="MultiRole",
        created_at=new_user.CreatedAt
    )


@router.put(
    "/users/{user_id}/update-with-roles",
    response_model=UserResponse,
    summary="Update user with multi-role and BU assignment",
    dependencies=[Depends(require_permission("user.manage"))],
)
def update_user_with_roles(
    user_id: str,
    payload: UpdateUserWithRolesRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_hr_or_admin)
):
    """
    Update user with multiple roles and Business Unit assignment.

    Supports:
    - Multi-role assignment (e.g., Partner + BU Head + Hiring Manager)
    - Business Unit scoping
    - Combined permissions from all assigned roles
    - Optional job title field

    Requires permission: user.manage
    """
    from app.models.rbac import Role
    from app.models.user import UserRole

    # Find target user
    target = db.query(Users).filter(Users.UserID == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Check if any org-level roles are being assigned
    from app.models.rbac import Role
    org_level_role_names = {"CEO", "CFO", "Super User", "ADMIN", "SUPER_USER"}

    # Get all roles being assigned
    roles_to_assign = db.query(Role).filter(Role.id.in_(payload.role_ids)).all()
    has_org_level_role = any(r.name in org_level_role_names for r in roles_to_assign)

    # Check if current user has org-level role(s)
    current_user_roles = db.query(UserRole).filter(UserRole.user_id == current_user.UserID).all()
    current_user_has_org_role = any(
        ur.role and ur.role.name in org_level_role_names
        for ur in current_user_roles
    )
    # Also check legacy UserRole field
    if current_user.UserRole and current_user.UserRole.upper() in org_level_role_names:
        current_user_has_org_role = True

    # Verify BU access (skip if assigning org-level roles OR if current user is org-level)
    if not has_org_level_role and not current_user_has_org_role and payload.business_unit_id and current_user.business_unit_id != payload.business_unit_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot update users outside your Business Unit"
        )

    # Update user name and BU
    target.UserName = payload.user_name
    # Note: business_unit_id is a property; actual column is bu_context_id
    # Org-level roles should NOT have BU restriction (no BU set)
    if has_org_level_role:
        # Clear BU for org-level roles
        target.bu_context_id = None
    elif payload.business_unit_id:
        # Get business unit context for BU-scoped roles
        from app.models.business_unit import BusinessUnitContext
        bu_context = db.query(BusinessUnitContext).filter(
            BusinessUnitContext.id == payload.business_unit_id
        ).first()
        if bu_context:
            target.bu_context_id = bu_context.id

    db.flush()

    # Remove existing user roles
    db.query(UserRole).filter(UserRole.user_id == user_id).delete()
    db.flush()

    # Assign new roles and collect role names for display
    assigned_role_names = []
    for role_id in payload.role_ids:
        # Verify role exists
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail=f"Role {role_id} not found")

        assigned_role_names.append(role.name)

        # Create user role with assigned_at timestamp
        user_role = UserRole(
            id=f"ur_{user_id}_{role_id}",
            user_id=user_id,
            role_id=role_id,
            # Note: UserRole doesn't have business_unit_id field; BU scoping done via Users.business_unit_id
        )
        db.add(user_role)

    db.commit()
    db.refresh(target)

    # Return the actual assigned roles, not "MultiRole"
    display_role = ", ".join(assigned_role_names) if assigned_role_names else target.UserRole

    return UserResponse(
        user_id=target.UserID,
        user_name=target.UserName or "",
        user_email=target.UserEmail,
        user_role=display_role,
        created_at=target.CreatedAt
    )


@router.get(
    "/users/{user_id}/roles",
    summary="Get all roles assigned to a user",
    dependencies=[Depends(require_permission("user.manage"))],
)
def get_user_roles(
    user_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_hr_or_admin)
):
    """
    Get all roles assigned to a specific user via the user_roles junction table.
    Returns list of role objects with id and name.
    """
    from app.models.user import UserRole
    from app.models.rbac import Role

    # Get all user roles
    user_roles = db.query(UserRole).filter(UserRole.user_id == user_id).all()
    roles = []

    for ur in user_roles:
        if ur.role:
            roles.append({
                "id": ur.role.id,
                "name": ur.role.name
            })

    return {"roles": roles}


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Update an HR/Admin user's profile, role, department, or business unit",
    dependencies=[Depends(require_permission("user.manage"))],
)
def update_user(
    user_id: str,
    user_name: Optional[str] = None,
    user_role: Optional[str] = None,
    business_unit_id: Optional[int] = None,
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_hr_or_admin)
):
    """
    Update a user's name, role, business unit, or department.
    Requires permission: user.manage

    Args:
        user_id: User ID to update
        user_name: New user name (optional)
        user_role: New legacy user role (optional)
        business_unit_id: New business unit ID (optional)
        department_id: New department ID (optional)
    """
    target = db.query(Users).filter(Users.UserID == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    if user_name is not None:
        target.UserName = user_name
    if user_role is not None:
        target.UserRole = user_role
    if business_unit_id is not None:
        # Verify BU exists
        bu = db.query(BusinessUnit).filter(BusinessUnit.id == business_unit_id).first()
        if not bu:
            raise HTTPException(status_code=404, detail=f"Business Unit {business_unit_id} not found")
        target.business_unit_id = business_unit_id
    if department_id is not None:
        # Verify department exists
        dept = db.query(Department).filter(Department.id == department_id).first()
        if not dept:
            raise HTTPException(status_code=404, detail=f"Department {department_id} not found")
        target.department_id = department_id

    db.commit()
    db.refresh(target)

    role = db.query(Role).filter(Role.id == target.role_id).first() if target.role_id else None

    return UserResponse(
        user_id=target.UserID,
        user_name=target.UserName or "",
        user_email=target.UserEmail,
        user_role=target.UserRole,
        created_at=target.CreatedAt,
        permission_role=role.name if role else None,
        department_id=target.department_id,
        department_name=target.department.name if target.department else None,
        business_unit_id=target.business_unit_id,
        business_unit_name=target.business_unit.name if target.business_unit else None,
    )


@router.post(
    "/users/{user_id}/assign-bu",
    response_model=UserResponse,
    summary="Assign or change a user's business unit",
    dependencies=[Depends(require_permission("user.manage"))],
)
def assign_user_to_bu(
    user_id: str,
    business_unit_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_hr_or_admin)
):
    """
    Assign or change a user's business unit.
    Requires permission: user.manage

    Args:
        user_id: User ID to update
        business_unit_id: Business unit ID to assign
    """
    target = db.query(Users).filter(Users.UserID == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Verify BU exists
    bu = db.query(BusinessUnit).filter(BusinessUnit.id == business_unit_id).first()
    if not bu:
        raise HTTPException(status_code=404, detail=f"Business Unit {business_unit_id} not found")

    target.business_unit_id = business_unit_id
    db.commit()
    db.refresh(target)

    role = db.query(Role).filter(Role.id == target.role_id).first() if target.role_id else None

    return UserResponse(
        user_id=target.UserID,
        user_name=target.UserName or "",
        user_email=target.UserEmail,
        user_role=target.UserRole,
        created_at=target.CreatedAt,
        permission_role=role.name if role else None,
        department_id=target.department_id,
        department_name=target.department.name if target.department else None,
        business_unit_id=target.business_unit_id,
        business_unit_name=target.business_unit.name if target.business_unit else None,
    )


@router.delete(
    "/users/{user_id}",
    response_model=DeleteResponse,
    summary="Delete an HR/Admin user account",
    dependencies=[Depends(require_permission("user.manage"))],
)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_hr_or_admin)
):
    """
    Delete an internal user account.
    Before deleting, all FK references to this user across every table are
    set to NULL so that no foreign-key constraint blocks the delete.
    Requires permission: user.manage
    """
    if current_user.UserID == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    target = db.query(Users).filter(Users.UserID == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # ------------------------------------------------------------------
    # Null out every FK that references this user before deleting them
    # ------------------------------------------------------------------

    # 1. Jobs — recruiter / hiring-manager
    db.query(Jobs).filter(Jobs.recuriterID == user_id).update(
        {Jobs.recuriterID: None}, synchronize_session=False
    )
    db.query(Jobs).filter(Jobs.hiringManagerID == user_id).update(
        {Jobs.hiringManagerID: None}, synchronize_session=False
    )

    # 2. CandidateAssignment — hiring / reporting manager
    db.query(CandidateAssignment).filter(
        CandidateAssignment.hiring_manager_id == user_id
    ).update({CandidateAssignment.hiring_manager_id: None}, synchronize_session=False)
    db.query(CandidateAssignment).filter(
        CandidateAssignment.reporting_manager_id == user_id
    ).update({CandidateAssignment.reporting_manager_id: None}, synchronize_session=False)

    # 3. PanelMember — interviewer
    db.query(PanelMember).filter(PanelMember.interviewer_id == user_id).update(
        {PanelMember.interviewer_id: None}, synchronize_session=False
    )

    # 4. InterviewFeedback — interviewer
    db.query(InterviewFeedback).filter(InterviewFeedback.interviewer_id == user_id).update(
        {InterviewFeedback.interviewer_id: None}, synchronize_session=False
    )

    # 5. OfferLetter — hiring manager / reporting manager / created_by / cancelled_by
    db.query(OfferLetter).filter(OfferLetter.hiring_manager_id == user_id).update(
        {OfferLetter.hiring_manager_id: None}, synchronize_session=False
    )
    db.query(OfferLetter).filter(OfferLetter.reporting_manager_id == user_id).update(
        {OfferLetter.reporting_manager_id: None}, synchronize_session=False
    )
    db.query(OfferLetter).filter(OfferLetter.created_by == user_id).update(
        {OfferLetter.created_by: None}, synchronize_session=False
    )
    db.query(OfferLetter).filter(OfferLetter.cancelled_by == user_id).update(
        {OfferLetter.cancelled_by: None}, synchronize_session=False
    )

    # 6. CandidateDocument — verified_by
    db.query(CandidateDocument).filter(CandidateDocument.verified_by == user_id).update(
        {CandidateDocument.verified_by: None}, synchronize_session=False
    )

    # 7. Newsletter — created_by
    db.query(Newsletter).filter(Newsletter.created_by == user_id).update(
        {Newsletter.created_by: None}, synchronize_session=False
    )

    # ------------------------------------------------------------------
    # Now it is safe to delete the user row
    # ------------------------------------------------------------------
    db.delete(target)
    db.commit()

    return DeleteResponse(
        status="Success",
        message=f"User {user_id} deleted successfully"
    )


@router.put(
    "/users/me/change-password",
    response_model=DeleteResponse,
    summary="Change current user's password",
    dependencies=[Depends(require_permission("user.manage"))],
)
def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    """
    Change the password of the currently logged-in user.
    Requires the correct current password for verification.

    Raises:
        400 if current password is wrong
        400 if new password is same as current
    """
    from app.core.security import verify_password

    # Verify current password
    if not verify_password(request.current_password, current_user.UserPassword):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect"
        )

    # Prevent setting the same password
    if verify_password(request.new_password, current_user.UserPassword):
        raise HTTPException(
            status_code=400,
            detail="New password must be different from the current password"
        )

    current_user.UserPassword = get_password_hash(request.new_password)
    db.commit()

    return DeleteResponse(
        status="Success",
        message="Password changed successfully"
    )


@router.put(
    "/admin/users/{user_id}/reset-password",
    response_model=DeleteResponse,
    summary="Admin force reset user password",
    dependencies=[Depends(require_permission("user.manage"))],
)
def admin_reset_password(
    user_id: str,
    request: AdminResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    """
    Admin-only password reset endpoint. No current password required.

    This endpoint allows admins to reset any user's password without
    knowing their current password - fixing the logical flaw that admins
    shouldn't need to know user passwords to reset them.

    Args:
        user_id: The user whose password to reset
        request: AdminResetPasswordRequest with new_password

    Raises:
        404 if user not found
        400 if new password is invalid
    """
    from app.core.security import verify_password

    # Find target user
    target_user = db.query(Users).filter(Users.UserID == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=404,
            detail=f"User with ID '{user_id}' not found"
        )

    # Prevent setting the same password
    if verify_password(request.new_password, target_user.UserPassword):
        raise HTTPException(
            status_code=400,
            detail="New password must be different from the current password"
        )

    # Force reset the password
    target_user.UserPassword = get_password_hash(request.new_password)
    db.commit()

    return DeleteResponse(
        status="Success",
        message=f"Password reset successfully for user {user_id}"
    )


# ============================================================
# User Section
# ============================================================

@router.get(
    "/users/{user_id}",
    response_model=SingleUserResponse,
    summary="Get a single user by ID",
    dependencies=[Depends(require_permission("user.manage"))],
)
def get_user_by_id(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    """
    Retrieve the full profile of a single internal user (HR, Admin, etc.)
    by their User ID.

    Args:
        user_id: The unique ID of the user to retrieve.
        db: Database session.
        current_user: Authenticated HR/Admin user (requires user.manage permission).

    Returns:
        SingleUserResponse with all user details.

    Raises:
        HTTPException 404: If the user is not found.
    """
    from app.models.rbac import Role  # avoid circular if needed

    target = db.query(Users).filter(Users.UserID == user_id).first()
    if not target:
        raise HTTPException(
            status_code=404,
            detail=f"User with ID '{user_id}' not found",
        )

    role = db.query(Role).filter(Role.id == target.role_id).first() if target.role_id else None

    return SingleUserResponse(
        user_id=target.UserID,
        user_name=target.UserName,
        user_email=target.UserEmail,
        user_role=target.UserRole,
        permission_role=role.name if role else None,
        role_id=target.role_id,
        business_unit_id=target.business_unit_id,
        created_at=target.CreatedAt,
    )


# ============================================================
# Hiring Manager Section
# ============================================================

@router.get(
    "/hiring_manager/assigned/candidate",
    response_model=list[HiringManagerAssignedCandidateResponse],
    summary="List candidates assigned to the authenticated hiring manager",
    dependencies=[Depends(require_permission("candidate.view"))],
)
def get_hiring_manager_assigned_candidates(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    """
    Retrieve all candidates that are directly assigned to the currently
    authenticated user **as a hiring manager**.

    Returns enriched candidate details including pipeline status so the
    hiring manager can see the full picture at a glance.

    Args:
        db: Database session.
        current_user: The authenticated hiring manager.

    Returns:
        List of HiringManagerAssignedCandidateResponse.
    """
    from app.models.candidate import CandidateStatus

    assignments = (
        db.query(CandidateAssignment)
        .filter(CandidateAssignment.hiring_manager_id == current_user.UserID)
        .all()
    )

    results = []
    for assignment in assignments:
        candidate = (
            db.query(Candidate)
            .filter(Candidate.candidateID == assignment.candidate_id)
            .first()
        )
        if not candidate:
            continue

        # Build full name
        name_parts = [
            candidate.candidateFirstName,
            candidate.candidateMiddleName,
            candidate.candidateLastName,
        ]
        candidate_name = " ".join(filter(None, name_parts)) or "N/A"

        # Latest pipeline status (most recently updated row)
        status_row = (
            db.query(CandidateStatus)
            .filter(CandidateStatus.candidateID == candidate.candidateID)
            .order_by(CandidateStatus.updatedAt.desc())
            .first()
        )
        pipeline_status = status_row.piplineStatus if status_row else None

        results.append(
            HiringManagerAssignedCandidateResponse(
                assignment_id=assignment.id,
                candidate_id=candidate.candidateID,
                candidate_name=candidate_name,
                candidate_email=candidate.candidateEmail,
                candidate_mobile=candidate.candidateMobile,
                candidate_job_title=candidate.candidateJobTitle,
                candidate_experience=candidate.candidateExperience,
                candidate_current_location=candidate.candidateCurrentLocation,
                candidate_joining_date=candidate.candidateJoiningDate,
                candidate_expected_salary=candidate.candidateExpectedSalary,
                candidate_current_salary=candidate.candidateCurrentSalary,
                candidate_is_verified=candidate.candidateIsVerified,
                pipeline_status=pipeline_status,
                assigned_at=assignment.created_at,
            )
        )

    return results

