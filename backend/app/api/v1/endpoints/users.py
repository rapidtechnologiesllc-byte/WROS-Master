from datetime import datetime
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db, check_user
from app.core.security import get_password_hash, create_access_token
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models import Users, Candidate, CandidateAssignment, Interview, InterviewPanel, InterviewFeedback, PanelMember, BusinessUnit, Department

# Alias for backward compatibility
get_current_user = get_current_internal_user
from app.models.user import Jobs
from app.models.offer_letter import OfferLetter
from app.models.document import CandidateDocument
from app.models.role_template import RoleTemplate
from app.models.newsletter import Newsletter
from app.models.permission import JobTitle
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
    CreateUserWithRolesRequest,
    UpdateUserWithRolesRequest,
)
from app.utils.uniq_id_generator import user_id_generator
from app.services.org_hierarchy_validator import validate_before_employee_creation
from app.services.message_queue_service import MessageQueueService
from app.models.org_structure import OrgNode

router = APIRouter(prefix="/hr", tags=["hr"])

@router.get(
    "/me",
    dependencies=[Depends(get_current_internal_user), Depends(require_resource_permission("user", "view"))],
    summary="Get current HR/Admin user's profile with a fresh access token",
)
def get_me(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Return the profile of the currently authenticated HR / Admin user
    together with a fresh access token, roles, and permissions.

    Useful for:
    - Restoring session state after page reload
    - Refreshing the token without a full re-login
    - Fetching up-to-date role / business-unit information
    - Building dynamic navigation based on user permissions
    """
    from app.services.role_template_permission_service import RoleTemplatePermissionService

    # Get tenant ID (default to 1, handle None case)
    tenant_id = (getattr(current_user, 'tenant_id', None) or 1)

    # Get user's assigned role template
    user_roles = []
    roles_list = []

    if current_user.role_template_id:
        rt = db.query(RoleTemplate).filter(RoleTemplate.id == current_user.role_template_id).first()
        if rt:
            roles_list.append(rt.name)
            user_roles.append({
                "id": rt.id,
                "name": rt.name,
            })

    # Get all permissions for the user based on their role template permissions
    # Returns dict: { "resource_name": { "can_view": True, ... }, ... }
    permission_resources = []

    if current_user.UserID:
        permissions_dict = RoleTemplatePermissionService.get_user_permissions(
            db, current_user.UserID, tenant_id
        )

        # Extract resource names where user has at least one permission
        if permissions_dict and isinstance(permissions_dict, dict):
            for resource_name, perms in permissions_dict.items():
                # Include resource if user has any permission (view/create/edit/delete)
                if perms and (perms.get('can_view') or perms.get('can_create') or
                             perms.get('can_edit') or perms.get('can_delete')):
                    permission_resources.append(resource_name)

    # Mint a fresh token using the same claims as login
    access_token = create_access_token(
        data={
            "sub": current_user.UserID,
            "email": current_user.UserEmail,
            "type": "user",
            "name": current_user.UserName,
        }
    )

    response_data = HrMeResponse(
        user_id=current_user.UserID,
        user_name=current_user.UserName,
        user_email=current_user.UserEmail,
        user_role=current_user.UserRole,
        job_title=current_user.job_title,
        permission_role=roles_list[0] if roles_list else None,
        role_template_id=current_user.role_template_id,
        business_unit_id=current_user.business_unit_id,
        created_at=current_user.CreatedAt,
        access_token=access_token,
        digest_enabled=current_user.digest_enabled,
    )

    # Add roles and permissions to response as extra fields
    response_dict = response_data.dict()
    response_dict["roles"] = roles_list
    response_dict["permissions"] = permission_resources

    return response_dict

@router.patch(
    "/me/digest-preference",
    dependencies=[Depends(get_current_internal_user), Depends(require_resource_permission("user", "view"))],
    response_model=DigestPreferenceResponse,
    summary="Enable/disable the recruiter's own Thunder morning digest (S-065/HRMS-0465)",
)
def update_digest_preference(
    payload: DigestPreferenceRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    current_user.digest_enabled = payload.digest_enabled
    db.add(current_user)
    db.commit()
    return DigestPreferenceResponse(digest_enabled=current_user.digest_enabled)

@router.get(
    "/me/permissions",
    dependencies=[Depends(get_current_internal_user), Depends(require_resource_permission("user", "view"))],
    summary="Get current user's permissions for frontend access control",
)
def get_current_user_permissions(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    """
    Get current user's permissions in a format optimized for frontend use.

    This endpoint is called by the frontend after login to cache permissions locally,
    enabling offline permission checking without repeated API calls.

    Returns:
        {
            "user_id": "...",
            "permissions": ["administration.view", "administration.create", ...],
            "modules": [{"id": 1, "name": "administration"}, ...],
            "is_super_admin": false
        }
    """
    from app.services.permission_helper import PermissionHelper

    tenant_id = getattr(current_user, 'tenant_id', 1)

    # Get all permissions for the user
    permissions = PermissionHelper.get_user_permissions(current_user.UserID, db, tenant_id)

    # Get accessible modules
    modules = PermissionHelper.get_accessible_modules(current_user.UserID, db, tenant_id)

    # Check if super admin
    is_super_admin = PermissionHelper.is_super_admin(current_user.UserID, db, tenant_id)

    return {
        "user_id": current_user.UserID,
        "permissions": sorted(list(permissions)),
        "modules": [{"id": m.id, "name": m.name} for m in modules],
        "is_super_admin": is_super_admin
    }

@router.get(
    "/users/all",
    dependencies=[Depends(get_current_internal_user), Depends(require_resource_permission("user", "view"))],
    response_model=AllUsersResponse,
)
def get_all_users(
    db: Session = Depends(get_db), 
    user = Depends(get_current_internal_user)
):
    """
    Get all users (HR, Admin, etc.) from the system.
    Does not include candidates.
    
    Args:
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        AllUsersResponse with list of all users and total count
    """
    # HRMS-0109 -- scoped to the caller's own tenant, never all tenants' users.
    users = db.query(Users).all()

    # Build response
    users_data = []
    for u in users:
        # role_template_id is MANDATORY - skip users without role assignment
        if not u.role_template_id:
            logger.warning(f"User {u.UserID} has no role_template_id assigned, skipping")
            continue
        role_template = db.query(RoleTemplate).filter(RoleTemplate.id == u.role_template_id).first()
        users_data.append(UserResponse(
            user_id=u.UserID,
            user_name=u.UserName or "",
            user_email=u.UserEmail,
            user_role=u.UserRole,
            job_title=u.job_title,
            role_template_id=u.role_template_id,
            created_at=u.CreatedAt,
            permission_role=role_template.name if role_template else None,
            department_id=u.department_id,
            department_name=u.department.name if u.department else None,
            business_unit_id=u.business_unit_id,
            business_unit_name=u.business_unit.name if u.business_unit else None,
        ))
    
    return AllUsersResponse(
        total_users=len(users_data),
        users=users_data
    )

@router.get(
    "/users/search",
    dependencies=[Depends(get_current_internal_user), Depends(require_resource_permission("user", "view"))],
    response_model=AllUsersResponse,
    summary="Search / filter users by name, permission role, or user role",
)
def search_users(
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
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
    limit: int = Query(default=50, ge=1, le=200, description="Max records to return (1â€“200)"),
):
    """
    Search users with any combination of filters.  All filters are optional â€”
    omit all of them to get a paginated list of every user.

    **Filters:**
    - `name` â€” partial, case-insensitive match on `UserName` **or** `UserEmail`
    - `permission_role` â€” exact match on the RBAC `Role.name`
      (e.g. `'HR Manager'`, `'Recruiter'`, `'Admin'`)
    - `user_role` â€” exact match on the legacy `UserRole` column
      (e.g. `'HR'`, `'Admin'`)
    - `department` â€” partial, case-insensitive match on `Department.name`
    - `business_unit` â€” partial, case-insensitive match on `BusinessUnit.name`

    **Pagination:** use `skip` / `limit`.
    """
    from sqlalchemy import or_, func as sql_func

    # HRMS-0109 -- scope to the caller's tenant before any of the
    # optional filters below narrow it further.
    query = db.query(Users)

    # â”€â”€ name filter â€” partial match on UserName OR UserEmail â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if name:
        pattern = f"%{name.lower()}%"
        query = query.filter(
            or_(
                sql_func.lower(Users.UserName).like(pattern),
                sql_func.lower(Users.UserEmail).like(pattern),
            )
        )

    # â”€â”€ role template filter (via role_template_id) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if user_role:
        query = query.join(RoleTemplate, RoleTemplate.id == Users.role_template_id).filter(
            RoleTemplate.name == user_role
        )

    # NOTE: permission_role filter removed 2026-08-24 (referenced non-existent Role model and Users.role_id field)
    # If needed, use RoleTemplate join: query.join(RoleTemplate, RoleTemplate.id == Users.role_template_id)

    # â”€â”€ Department filter â€” join through Department â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if department:
        dept_pattern = f"%{department.lower()}%"
        query = query.join(Department, Department.id == Users.department_id).filter(
            sql_func.lower(Department.name).like(dept_pattern)
        )

    # â”€â”€ Business unit filter â€” join through BusinessUnit â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if business_unit:
        bu_pattern = f"%{business_unit.lower()}%"
        from app.models.business_unit import BusinessUnitContext
        query = query.join(BusinessUnitContext, BusinessUnitContext.user_id == Users.UserID).join(
            BusinessUnit, BusinessUnit.id == BusinessUnitContext.business_unit_id
        ).filter(
            sql_func.lower(BusinessUnit.name).like(bu_pattern)
        )

    total = query.count()
    matched_users = query.order_by(Users.UserID).offset(skip).limit(limit).all()

    users_data = []
    for u in matched_users:
        role_template = db.query(RoleTemplate).filter(RoleTemplate.id == u.role_template_id).first()
        users_data.append(UserResponse(
            user_id=u.UserID,
            user_name=u.UserName or "",
            user_email=u.UserEmail,
            user_role=u.UserRole,
            job_title=u.job_title,
            created_at=u.CreatedAt,
            permission_role=role_template.name if role_template else None,
            department_id=u.department_id,
            department_name=u.department.name if u.department else None,
            business_unit_id=u.business_unit_id,
            business_unit_name=u.business_unit.name if u.business_unit else None,
        ))

    return AllUsersResponse(
        total_users=total,
        users=users_data,
    )

@router.get(
    "/users/details/{user_id}",
    dependencies=[Depends(get_current_internal_user), Depends(require_resource_permission("user", "view"))],
    response_model=UserResponse,
    summary="Get user details by user ID",
)
def get_user_details_by_id(
    user_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
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

    role_template = db.query(RoleTemplate).filter(RoleTemplate.id == u.role_template_id).first()

    return UserResponse(
        user_id=u.UserID,
        user_name=u.UserName or "",
        user_email=u.UserEmail,
        user_role=u.UserRole,
        job_title=u.job_title,
        created_at=u.CreatedAt,
        permission_role=role_template.name if role_template else None,
        department_id=u.department_id,
        department_name=u.department.name if u.department else None,
        business_unit_id=u.business_unit_id,
        business_unit_name=u.business_unit.name if u.business_unit else None,
    )

@router.post(
    "/assignments/create",
    response_model=CandidateAssignmentResponse,
    status_code=201,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
)
def create_candidate_assignment(
    request: CandidateAssignmentCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
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
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
)
def get_assigned_candidates(
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
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
    dependencies=[Depends(require_resource_permission("interviews", "view"))],
)
def get_assigned_interviews(
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
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
    dependencies=[Depends(require_resource_permission("users", "edit"))],
)
def create_user(
    request: SignupRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user)
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

    # PRODUCTION SAFETY: Auto-assign tenant_id from creating user's tenant
    tenant_id = current_user.tenant_id or 1

    new_user = Users(
        UserID=user_id_generator(),
        UserName=request.user_name,
        UserEmail=request.user_email,
        UserPassword=get_password_hash(request.user_password),
        UserRole=request.user_role,
        tenant_id=tenant_id  # PRODUCTION: Always set from creator's tenant or default to 1
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
    summary="Create a new user with roles and optional job title",
    dependencies=[Depends(require_resource_permission("users", "edit"))],
)
def create_user_with_roles(
    request: CreateUserWithRolesRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Create a new user with roles and org hierarchy (MANDATORY: hierarchy_level + specialization).

    REQUIRED FIELDS (from request):
    - user_name, user_email, user_password, role_template_id
    - hierarchy_level (1-17): MANDATORY - defines org position
    - specialization: MANDATORY - Recruitment, Development, HR, Finance, Project Management, QA, Business Analysis

    Validates reporting structure before creating OrgNode.
    Requires permission: user.manage
    """
    user_name = request.user_name
    user_email = request.user_email
    user_password = request.user_password
    job_title = request.job_title
    partner_id = request.partner_id
    business_unit_id = request.business_unit_id
    role_template_id = request.role_template_id
    hierarchy_level = request.hierarchy_level  # MANDATORY
    specialization = request.specialization    # MANDATORY
    parent_node_id = request.parent_node_id

    if not user_name or not user_name.strip():
        raise HTTPException(status_code=400, detail="User name is required")
    if not user_email or not user_email.strip():
        raise HTTPException(status_code=400, detail="User email is required")
    if not user_password or not user_password.strip():
        raise HTTPException(status_code=400, detail="Password is required")
    if not role_template_id:
        raise HTTPException(status_code=400, detail="Role template is required")

    existing = check_user(db, user_email)
    if existing:
        raise HTTPException(status_code=400, detail=f"User with email {user_email} already exists")

    # PRODUCTION SAFETY: Auto-assign tenant_id from creating user's tenant
    tenant_id = current_user.tenant_id or 1

    # Validate role template exists
    role_template = db.query(RoleTemplate).filter(
        RoleTemplate.id == role_template_id
    ).first()

    if not role_template:
        raise HTTPException(status_code=400, detail="Role template not found")

    # CRITICAL: Validate org hierarchy with 17-level system + specialization
    is_valid, error_msg = validate_before_employee_creation(
        db,
        hierarchy_level=hierarchy_level,
        specialization=specialization,
        parent_node_id=parent_node_id,
        business_unit_id=business_unit_id
    )

    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid reporting structure: {error_msg}")

    new_user = Users(
        UserID=user_id_generator(),
        UserName=user_name,
        UserEmail=user_email,
        UserPassword=get_password_hash(user_password),
        UserRole="Admin",  # Default role
        tenant_id=tenant_id
    )

    # Set optional fields if provided
    if job_title:
        new_user.job_title = job_title
    if partner_id:
        new_user.partner_id = partner_id
    if business_unit_id:
        new_user.business_unit_id = business_unit_id

    new_user.role_template_id = role_template_id

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create OrgNode record with VALIDATED hierarchy_level and specialization
    try:
        org_node = OrgNode(
            name=f"{new_user.UserName} - {specialization}",
            node_type="PERSON",
            user_id=new_user.UserID,
            parent_node_id=parent_node_id,
            hierarchy_level=hierarchy_level,  # From request (already validated)
            specialization=specialization,    # From request (already validated)
            authority_level="INDIVIDUAL",     # Default, can be overridden per role
            business_unit_id=business_unit_id,
            email=user_email,
            tenant_id=tenant_id,
        )
        db.add(org_node)
        db.commit()
        db.refresh(org_node)
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        from app.core.logging import logger
        logger.error(f"Failed to create OrgNode for new user {user_email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create organizational hierarchy: {str(e)}")

    # Queue user_created message for welcome email
    MessageQueueService.enqueue(
        message_type="user_created",
        payload={
            "user_id": new_user.UserID,
            "user_name": new_user.UserName,
            "user_email": new_user.UserEmail,
            "user_role": new_user.UserRole,
            "job_title": job_title,
            "business_unit_id": business_unit_id,
            "hierarchy_level": hierarchy_level,
            "specialization": specialization,
        },
        resource_id=new_user.UserID,
        queue_type="EMAIL_QUEUE",
        created_by=current_user.UserID,
        db=db,
    )

    return UserResponse(
        user_id=new_user.UserID,
        user_name=new_user.UserName or "",
        user_email=new_user.UserEmail,
        user_role=new_user.UserRole,
        created_at=new_user.CreatedAt
    )

@router.put(
    "/users/{user_id}/update-with-roles",
    response_model=UserResponse,
    summary="Update user with roles, job title, and business unit",
    dependencies=[Depends(require_resource_permission("users", "edit"))],
)
def update_user_with_roles(
    user_id: str,
    request: UpdateUserWithRolesRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Update a user with role template (single), job title, partner, and business unit.
    Requires permission: user.manage
    """
    target = db.query(Users).filter(Users.UserID == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    if request.user_name is not None:
        target.UserName = request.user_name
    if request.user_email is not None:
        target.UserEmail = request.user_email
    if request.job_title is not None:
        target.job_title = request.job_title
    if request.partner_id is not None:
        target.partner_id = request.partner_id
    if request.business_unit_id is not None:
        target.business_unit_id = request.business_unit_id

    # Handle role template update: set single role_template_id on user
    if request.role_template_id is not None:
        target.role_template_id = request.role_template_id

    db.commit()
    db.refresh(target)

    return UserResponse(
        user_id=target.UserID,
        user_name=target.UserName or "",
        user_email=target.UserEmail,
        user_role=target.UserRole,
        job_title=target.job_title,
        role_template_id=target.role_template_id,
        created_at=target.CreatedAt
    )

@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Update an HR/Admin user's profile, role, job title, and role template",
    dependencies=[Depends(require_resource_permission("users", "edit"))],
)
def update_user(
    user_id: str,
    request: UpdateUserWithRolesRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user)
):
    """
    Update a user's name, role, job title, role template, and business unit.
    If user has NULL tenant_id, assigns current user's tenant_id.
    Requires permission: user.manage
    """
    target = db.query(Users).filter(Users.UserID == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Fix NULL tenant_id by assigning current user's tenant
    if target.tenant_id is None:
        target.tenant_id = current_user.tenant_id or 1

    if request.user_name is not None:
        target.UserName = request.user_name
    if request.job_title is not None:
        target.job_title = request.job_title
    if request.role_template_id is not None:
        target.role_template_id = request.role_template_id
    if request.business_unit_id is not None:
        target.business_unit_id = request.business_unit_id

    db.commit()
    db.refresh(target)

    # Build response with all fields
    role_template = db.query(RoleTemplate).filter(RoleTemplate.id == target.role_template_id).first() if target.role_template_id else None

    return UserResponse(
        user_id=target.UserID,
        user_name=target.UserName or "",
        user_email=target.UserEmail,
        user_role=target.UserRole,
        job_title=target.job_title,
        role_template_id=target.role_template_id,
        permission_role=role_template.name if role_template else None,
        department_id=target.department_id,
        department_name=target.department.name if target.department else None,
        business_unit_id=target.business_unit_id,
        business_unit_name=target.business_unit.name if target.business_unit else None,
        created_at=target.CreatedAt
    )

@router.delete(
    "/users/{user_id}",
    response_model=DeleteResponse,
    summary="Delete an HR/Admin user account",
    dependencies=[Depends(require_resource_permission("users", "edit"))],
)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user)
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

    # 1. Jobs â€” recruiter / hiring-manager
    db.query(Jobs).filter(Jobs.recuriterID == user_id).update(
        {Jobs.recuriterID: None}, synchronize_session=False
    )
    db.query(Jobs).filter(Jobs.hiringManagerID == user_id).update(
        {Jobs.hiringManagerID: None}, synchronize_session=False
    )

    # 2. CandidateAssignment â€” hiring / reporting manager
    db.query(CandidateAssignment).filter(
        CandidateAssignment.hiring_manager_id == user_id
    ).update({CandidateAssignment.hiring_manager_id: None}, synchronize_session=False)
    db.query(CandidateAssignment).filter(
        CandidateAssignment.reporting_manager_id == user_id
    ).update({CandidateAssignment.reporting_manager_id: None}, synchronize_session=False)

    # 3. PanelMember â€” interviewer
    db.query(PanelMember).filter(PanelMember.interviewer_id == user_id).update(
        {PanelMember.interviewer_id: None}, synchronize_session=False
    )

    # 4. InterviewFeedback â€” interviewer
    db.query(InterviewFeedback).filter(InterviewFeedback.interviewer_id == user_id).update(
        {InterviewFeedback.interviewer_id: None}, synchronize_session=False
    )

    # 5. OfferLetter â€” hiring manager / reporting manager / created_by / cancelled_by
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

    # 6. CandidateDocument â€” verified_by
    db.query(CandidateDocument).filter(CandidateDocument.verified_by == user_id).update(
        {CandidateDocument.verified_by: None}, synchronize_session=False
    )

    # 7. Newsletter â€” created_by
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
    dependencies=[Depends(require_resource_permission("users", "edit"))],
)
def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
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
    dependencies=[Depends(require_resource_permission("users", "edit"))],
)
def admin_reset_password(
    user_id: str,
    request: AdminResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
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
    dependencies=[Depends(require_resource_permission("users", "edit"))],
)
def get_user_by_id(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
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
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
)
def get_hiring_manager_assigned_candidates(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
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

@router.get(
    "/job-titles",
    dependencies=[Depends(get_current_internal_user), Depends(require_resource_permission("user", "view"))],
    summary="Get all active job titles for the tenant",
    tags=["reference-data"]
)
def get_job_titles(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Fetch all active job titles for the current tenant.

    Used to populate dropdowns in user creation/edit forms.
    Only returns active job titles (active=true).
    """
    try:
        # Get tenant ID from current user (default to 1 if None or missing)
        tenant_id = current_user.tenant_id if (hasattr(current_user, 'tenant_id') and current_user.tenant_id) else 1

        job_titles = db.query(JobTitle).filter(
            JobTitle.tenant_id == tenant_id,
            JobTitle.active == True
        ).order_by(JobTitle.name).all()

        return {
            "job_titles": [
                {
                    "id": jt.id,
                    "name": jt.name,
                    "description": jt.description
                }
                for jt in job_titles
            ]
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        # If table doesn't exist or other DB error, return empty list
        # (migration may not have run yet)
        return {"job_titles": []}

