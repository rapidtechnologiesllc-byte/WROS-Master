from datetime import datetime
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db, check_user
from app.core.security import get_password_hash, create_access_token
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.services.permission_helper import PermissionHelper
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hr", tags=["hr"])

@router.get(
    "/me",
    dependencies=[Depends(get_current_internal_user)],
    summary="Get current HR/Admin user's profile with a fresh access token",
)
async def get_me(
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
    try:
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

        # Get all permissions for the user
        permissions_dict = {}

        # Only check role_template if user has one assigned
        if current_user.UserID and current_user.role_template_id:
            # Regular users: fetch permissions from role_template
            try:
                perms_result = RoleTemplatePermissionService.get_user_permissions(
                    db, current_user.UserID, tenant_id
                )
                permissions_dict = perms_result or {}
                logger.debug(f"get_user_permissions returned type={type(permissions_dict)}, len={len(permissions_dict)}")
            except Exception as e:
                logger.warning(f"Failed to get permissions for user {current_user.UserID}: {e}")
                permissions_dict = {}

        # Mint a fresh token using the same claims as login
        access_token = create_access_token(
            data={
                "sub": current_user.UserID,
                "email": current_user.UserEmail,
                "type": "user",
                "name": current_user.UserName,
                "tenant_id": tenant_id,
                "role_template_id": current_user.role_template_id,
            }
        )

        # Return response matching the login endpoint format
        return {
            "user_id": current_user.UserID,
            "user_name": current_user.UserName,
            "user_email": current_user.UserEmail,
            "user_role": current_user.UserRole,
            "job_title": getattr(current_user, 'job_title', None),
            "permission_role": roles_list[0] if roles_list else None,
            "role_template_id": current_user.role_template_id,
            "business_unit_id": getattr(current_user, 'business_unit_id', None),
            "whatsapp_number": getattr(current_user, 'whatsapp_number', None),
            "permissions": permissions_dict,
            "created_at": current_user.CreatedAt,
            "access_token": access_token,
            "token_type": "bearer",
            "digest_enabled": getattr(current_user, 'digest_enabled', True),
            "roles": roles_list,
        }
    except Exception as e:
        logger.error(f"[get_me] Error getting user profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve user profile: {str(e)}")

@router.patch(
    "/me/digest-preference",
    dependencies=[Depends(get_current_internal_user), Depends(require_resource_permission("users-access-control", "view"))],
    response_model=DigestPreferenceResponse,
    summary="Enable/disable the recruiter's own Thunder morning digest (S-065/HRMS-0465)",
)
def update_digest_preference(
    payload: DigestPreferenceRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if payload.digest_enabled is None:
        raise ValueError("digest_enabled value is required")

    try:
        current_user.digest_enabled = payload.digest_enabled
    except Exception as update_error:
        logger.error(f"Failed to set digest_enabled on user {current_user.UserID}: {update_error}", exc_info=True)
        raise

    try:
        db.add(current_user)
    except Exception as add_error:
        logger.error(f"Failed to add user to session: {add_error}", exc_info=True)
        raise

    try:
        db.commit()
    except Exception as commit_error:
        logger.error(f"Failed to commit digest preference update: {commit_error}", exc_info=True)
        db.rollback()
        raise

    return DigestPreferenceResponse(digest_enabled=current_user.digest_enabled)

@router.get(
    "/me/permissions",
    dependencies=[Depends(get_current_internal_user), Depends(require_resource_permission("users-access-control", "view"))],
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
    dependencies=[Depends(get_current_internal_user), Depends(require_resource_permission("users-access-control", "view"))],
    response_model=AllUsersResponse,
)
def get_all_users(
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """Get all users (HR, Admin, etc.) from the system."""
    try:
        logger.info("get_all_users: Starting query")
        users = db.query(Users).all()
        logger.info(f"get_all_users: Found {len(users)} users")

        users_data = []
        for idx, u in enumerate(users):
            try:
                logger.info(f"get_all_users: Processing user {idx+1}/{len(users)} - UserID={u.UserID}")
                if not u.role_template_id:
                    logger.warning(f"User {u.UserID} has no role_template_id, skipping")
                    continue

                role_template = db.query(RoleTemplate).filter(RoleTemplate.id == u.role_template_id).first()
                logger.info(f"get_all_users: Creating UserResponse for {u.UserID}")

                users_data.append(UserResponse(
                    user_id=u.UserID,
                    user_name=u.UserName or "",
                    user_email=u.UserEmail,
                    user_role=u.UserRole,
                    job_title=u.job_title,
                    role_template_id=u.role_template_id,
                    created_at=u.CreatedAt,
                    permission_role=(role_template.name if role_template else None),
                    department_id=u.department_id,
                    department_name=(u.department.name if (u.department and hasattr(u.department, 'name')) else None),
                    business_unit_id=u.business_unit_id,
                    business_unit_name=(u.business_unit.name if (u.business_unit and hasattr(u.business_unit, 'name')) else None),
                ))
            except Exception as e:
                logger.error(f"Error processing user {u.UserID}: {str(e)}", exc_info=True)
                continue

        logger.info(f"get_all_users: Returning {len(users_data)} users")
        return AllUsersResponse(total_users=len(users_data), users=users_data)
    except Exception as e:
        logger.error(f"CRITICAL: get_all_users failed: {str(e)}", exc_info=True)
        raise

@router.get(
    "/users/search",
    dependencies=[Depends(get_current_internal_user), Depends(require_resource_permission("users-access-control", "view"))],
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
    limit: int = Query(default=50, ge=1, le=200, description="Max records to return (1-200)"),
):
    """
    Search users with any combination of filters.  All filters are optional â€"
    omit all of them to get a paginated list of every user.

    **Filters:**
    - `name` â€" partial, case-insensitive match on `UserName` **or** `UserEmail`
    - `permission_role` â€" exact match on the RBAC `Role.name`
      (e.g. `'HR Manager'`, `'Recruiter'`, `'Admin'`)
    - `user_role` â€" exact match on the legacy `UserRole` column
      (e.g. `'HR'`, `'Admin'`)
    - `department` â€" partial, case-insensitive match on `Department.name`
    - `business_unit` â€" partial, case-insensitive match on `BusinessUnit.name`

    **Pagination:** use `skip` / `limit`.
    """
    from sqlalchemy import or_, func as sql_func

    # HRMS-0109 -- scope to the caller's tenant before any of the
    # optional filters below narrow it further.
    query = db.query(Users)

    # â"€â"€ name filter â€" partial match on UserName OR UserEmail â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    if name:
        pattern = f"%{name.lower()}%"
        query = query.filter(
            or_(
                sql_func.lower(Users.UserName).like(pattern),
                sql_func.lower(Users.UserEmail).like(pattern),
            )
        )

    # â"€â"€ role template filter (via role_template_id) â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    if user_role:
        query = query.join(RoleTemplate, RoleTemplate.id == Users.role_template_id).filter(
            RoleTemplate.name == user_role
        )

    # NOTE: permission_role filter removed 2026-08-24 (referenced non-existent Role model and Users.role_id field)
    # If needed, use RoleTemplate join: query.join(RoleTemplate, RoleTemplate.id == Users.role_template_id)

    # â"€â"€ Department filter â€" join through Department â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    if department:
        dept_pattern = f"%{department.lower()}%"
        query = query.join(Department, Department.id == Users.department_id).filter(
            sql_func.lower(Department.name).like(dept_pattern)
        )

    # â"€â"€ Business unit filter â€" join through BusinessUnit â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
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
            permission_role=(role_template.name if role_template else None),
            department_id=u.department_id,
            department_name=(u.department.name if (u.department and hasattr(u.department, 'name')) else None),
            business_unit_id=u.business_unit_id,
            business_unit_name=(u.business_unit.name if (u.business_unit and hasattr(u.business_unit, 'name')) else None),
        ))

    return AllUsersResponse(
        total_users=total,
        users=users_data,
    )

@router.get(
    "/users/details/{user_id}",
    dependencies=[Depends(get_current_internal_user), Depends(require_resource_permission("users-access-control", "view"))],
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
        permission_role=(role_template.name if role_template else None),
        department_id=u.department_id,
        department_name=(u.department.name if (u.department and hasattr(u.department, 'name')) else None),
        business_unit_id=u.business_unit_id,
        business_unit_name=(u.business_unit.name if (u.business_unit and hasattr(u.business_unit, 'name')) else None),
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
    if not request.candidate_id:
        raise ValueError("candidate_id is required")

    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == request.candidate_id).first()
    except Exception as query_error:
        logger.error(f"Failed to query candidate {request.candidate_id}: {query_error}", exc_info=True)
        raise

    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {request.candidate_id} not found"
        )

    if request.hiring_manager_id:
        try:
            hiring_manager = db.query(Users).filter(Users.UserID == request.hiring_manager_id).first()
        except Exception as query_error:
            logger.error(f"Failed to query hiring manager {request.hiring_manager_id}: {query_error}", exc_info=True)
            raise

        if not hiring_manager:
            raise HTTPException(
                status_code=404,
                detail=f"Hiring manager with ID {request.hiring_manager_id} not found"
            )

    if request.reporting_manager_id:
        try:
            reporting_manager = db.query(Users).filter(Users.UserID == request.reporting_manager_id).first()
        except Exception as query_error:
            logger.error(f"Failed to query reporting manager {request.reporting_manager_id}: {query_error}", exc_info=True)
            raise

        if not reporting_manager:
            raise HTTPException(
                status_code=404,
                detail=f"Reporting manager with ID {request.reporting_manager_id} not found"
            )

    try:
        assignment = CandidateAssignment(
            candidate_id=request.candidate_id,
            hiring_manager_id=request.hiring_manager_id,
            reporting_manager_id=request.reporting_manager_id
        )
    except Exception as creation_error:
        logger.error(f"Failed to create CandidateAssignment: {creation_error}", exc_info=True)
        raise

    try:
        db.add(assignment)
    except Exception as add_error:
        logger.error(f"Failed to add assignment to session: {add_error}", exc_info=True)
        raise

    try:
        db.commit()
    except Exception as commit_error:
        logger.error(f"Failed to commit assignment: {commit_error}", exc_info=True)
        db.rollback()
        raise

    try:
        db.refresh(assignment)
    except Exception as refresh_error:
        logger.error(f"Failed to refresh assignment: {refresh_error}", exc_info=True)
        raise

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
    response_model=dict,
    status_code=202,
    summary="Queue new HR/Admin user creation",
    dependencies=[Depends(require_resource_permission("users-access-control", "edit"))],
)
def create_user(
    request: SignupRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user)
):
    """
    Queue user creation for async background processing.

    This endpoint:
    1. Validates request
    2. Queues 'create_user_with_roles' task
    3. Returns message_id for polling

    Background processing handles:
    1. User record creation
    2. Role template assignment
    3. Permission setup
    4. Welcome email notification
    5. Audit logging

    Args:
        request: SignupRequest with user_name, user_email, user_password, user_role, role_template_id

    Returns:
        dict with:
        - status: 'queued'
        - message_id: UUID for polling task status
        - polling_endpoint: URL to check status

    Raises:
        HTTPException 400: Validation error
        HTTPException 409: User email already exists
        HTTPException 500: Failed to queue
    """
    from app.services.message_queue_service import MessageQueueService

    # Validate inputs
    if not request.user_name or not request.user_name.strip():
        raise HTTPException(status_code=400, detail="User name is required")
    if not request.user_email or not request.user_email.strip():
        raise HTTPException(status_code=400, detail="User email is required")
    if not request.user_password or not request.user_password.strip():
        raise HTTPException(status_code=400, detail="Password is required")
    if not request.user_role or not request.user_role.strip():
        raise HTTPException(status_code=400, detail="User role is required")
    if not request.role_template_id:
        raise HTTPException(status_code=400, detail="Role template ID is required")

    # Check if user already exists
    from app.core.database import check_user

    try:
        existing = check_user(db, request.user_email)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"User with email {request.user_email} already exists"
            )
    except HTTPException:
        raise
    except Exception as check_error:
        logger.error(f"Failed to check existing user: {check_error}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to validate email")

    tenant_id = current_user.tenant_id or 1

    try:
        # Queue user creation for background processing
        result = MessageQueueService.enqueue(
            task_name='create_user_with_roles',
            data={
                'user_email': request.user_email,
                'user_name': request.user_name,
                'user_password': request.user_password,
                'business_unit_id': None,  # Not provided in basic create
                'role_ids': [request.role_template_id],
                'created_by_user_id': current_user.UserID,
                'tenant_id': tenant_id
            }
        )

        if not result or result.get('status') != 'queued':
            logger.error(f"Failed to queue user creation: {result}")
            raise HTTPException(status_code=500, detail="Failed to queue user creation")

        message_id = result.get('message_id')
        logger.info(f"User creation queued: {message_id} for {request.user_email}")

        return {
            "status": "queued",
            "message_id": message_id,
            "user_email": request.user_email,
            "polling_endpoint": f"/api/v1/tasks/{message_id}/status",
            "polling_interval_seconds": 3
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to queue user creation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to queue user creation")

@router.post(
    "/users/create-with-roles",
    response_model=dict,
    status_code=202,
    summary="Queue new user with roles and org hierarchy",
    dependencies=[Depends(require_resource_permission("users-access-control", "edit"))],
)
def create_user_with_roles(
    request: CreateUserWithRolesRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Queue user creation with roles and org hierarchy for async processing.

    This endpoint:
    1. Validates request and org hierarchy
    2. Queues 'create_user_with_roles' task
    3. Returns message_id for polling

    Background processing handles:
    1. User record creation
    2. OrgNode creation with hierarchy
    3. Role assignment
    4. Permission setup
    5. Welcome email and onboarding

    REQUIRED FIELDS (from request):
    - user_name, user_email, user_password, role_template_id
    - hierarchy_level (1-17): defines org position
    - specialization: Recruitment, Development, HR, Finance, etc.

    Args:
        request: CreateUserWithRolesRequest with all user details

    Returns:
        dict with:
        - status: 'queued'
        - message_id: UUID for polling task status
        - polling_endpoint: URL to check status

    Raises:
        HTTPException 400: Validation error
        HTTPException 409: User email already exists or invalid hierarchy
        HTTPException 500: Failed to queue
    """
    from app.services.message_queue_service import MessageQueueService

    # Validate all required fields
    if not request.user_name or not request.user_name.strip():
        raise HTTPException(status_code=400, detail="User name is required")
    if not request.user_email or not request.user_email.strip():
        raise HTTPException(status_code=400, detail="User email is required")
    if not request.user_password or not request.user_password.strip():
        raise HTTPException(status_code=400, detail="Password is required")
    if not request.role_template_id:
        raise HTTPException(status_code=400, detail="Role template is required")
    if not request.hierarchy_level:
        raise HTTPException(status_code=400, detail="Hierarchy level is required")
    if not request.specialization:
        raise HTTPException(status_code=400, detail="Specialization is required")

    # Check if user email already exists
    try:
        existing = check_user(db, request.user_email)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"User with email {request.user_email} already exists"
            )
    except HTTPException:
        raise
    except Exception as check_error:
        logger.error(f"Failed to check existing user: {check_error}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to validate email")

    # Validate role template exists
    try:
        role_template = db.query(RoleTemplate).filter(
            RoleTemplate.id == request.role_template_id
        ).first()

        if not role_template:
            raise HTTPException(status_code=400, detail="Role template not found")
    except HTTPException:
        raise
    except Exception as role_error:
        logger.error(f"Failed to check role template: {role_error}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to validate role template")

    # Validate org hierarchy with 17-level system + specialization
    try:
        is_valid, error_msg = validate_before_employee_creation(
            db,
            hierarchy_level=request.hierarchy_level,
            specialization=request.specialization,
            parent_node_id=request.parent_node_id,
            business_unit_id=request.business_unit_id
        )

        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid reporting structure: {error_msg}"
            )
    except HTTPException:
        raise
    except Exception as hierarchy_error:
        logger.error(f"Failed to validate org hierarchy: {hierarchy_error}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to validate hierarchy")

    tenant_id = current_user.tenant_id or 1

    try:
        # Queue user creation for background processing
        result = MessageQueueService.enqueue(
            task_name='create_user_with_roles',
            data={
                'user_email': request.user_email,
                'user_name': request.user_name,
                'user_password': request.user_password,
                'business_unit_id': request.business_unit_id,
                'role_ids': [request.role_template_id],
                'job_title': request.job_title,
                'partner_id': request.partner_id,
                'hierarchy_level': request.hierarchy_level,
                'specialization': request.specialization,
                'parent_node_id': request.parent_node_id,
                'created_by_user_id': current_user.UserID,
                'tenant_id': tenant_id
            }
        )

        if not result or result.get('status') != 'queued':
            logger.error(f"Failed to queue user creation: {result}")
            raise HTTPException(status_code=500, detail="Failed to queue user creation")

        message_id = result.get('message_id')
        logger.info(f"User with roles queued: {message_id} for {request.user_email}")

        return {
            "status": "queued",
            "message_id": message_id,
            "user_email": request.user_email,
            "user_name": request.user_name,
            "polling_endpoint": f"/api/v1/tasks/{message_id}/status",
            "polling_interval_seconds": 3
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to queue user creation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to queue user creation")

@router.put(
    "/users/{user_id}/update-with-roles",
    response_model=UserResponse,
    summary="Update user with roles, job title, and business unit",
    dependencies=[Depends(require_resource_permission("users-access-control", "edit"))],
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
    if not user_id or not user_id.strip():
        raise ValueError("user_id is required")

    try:
        target = db.query(Users).filter(Users.UserID == user_id).first()
    except Exception as query_error:
        logger.error(f"Failed to query user {user_id}: {query_error}", exc_info=True)
        raise

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

    if request.role_template_id is not None:
        target.role_template_id = request.role_template_id

    try:
        db.commit()
    except Exception as commit_error:
        logger.error(f"Failed to commit user update for {user_id}: {commit_error}", exc_info=True)
        db.rollback()
        raise

    try:
        db.refresh(target)
    except Exception as refresh_error:
        logger.error(f"Failed to refresh user {user_id}: {refresh_error}", exc_info=True)
        raise

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
    dependencies=[Depends(require_resource_permission("users-access-control", "edit"))],
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
    if not user_id or not user_id.strip():
        raise ValueError("user_id is required")

    try:
        target = db.query(Users).filter(Users.UserID == user_id).first()
    except Exception as query_error:
        logger.error(f"Failed to query user {user_id}: {query_error}", exc_info=True)
        raise

    if not target:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

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

    try:
        db.commit()
    except Exception as commit_error:
        logger.error(f"Failed to commit user update for {user_id}: {commit_error}", exc_info=True)
        db.rollback()
        raise

    try:
        db.refresh(target)
    except Exception as refresh_error:
        logger.error(f"Failed to refresh user {user_id}: {refresh_error}", exc_info=True)
        raise

    role_template = None
    if target.role_template_id:
        try:
            role_template = db.query(RoleTemplate).filter(RoleTemplate.id == target.role_template_id).first()
        except Exception as query_error:
            logger.error(f"Failed to query role template {target.role_template_id}: {query_error}", exc_info=True)
            raise

    return UserResponse(
        user_id=target.UserID,
        user_name=target.UserName or "",
        user_email=target.UserEmail,
        user_role=target.UserRole,
        job_title=target.job_title,
        role_template_id=target.role_template_id,
        permission_role=(role_template.name if role_template else None),
        department_id=target.department_id,
        department_name=(target.department.name if (target.department and hasattr(target.department, 'name')) else None),
        business_unit_id=target.business_unit_id,
        business_unit_name=(target.business_unit.name if (target.business_unit and hasattr(target.business_unit, 'name')) else None),
        created_at=target.CreatedAt
    )

@router.delete(
    "/users/{user_id}",
    response_model=DeleteResponse,
    summary="Delete an HR/Admin user account",
    dependencies=[Depends(require_resource_permission("users-access-control", "edit"))],
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
    if not user_id or not user_id.strip():
        raise ValueError("user_id is required")
    if current_user.UserID == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    try:
        target = db.query(Users).filter(Users.UserID == user_id).first()
    except Exception as query_error:
        logger.error(f"Failed to query user {user_id}: {query_error}", exc_info=True)
        raise

    if not target:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # ------------------------------------------------------------------
    # Null out every FK that references this user before deleting them
    # ------------------------------------------------------------------

    try:
        db.query(Jobs).filter(Jobs.recuriterID == user_id).update(
            {Jobs.recuriterID: None}, synchronize_session=False
        )
    except Exception as update_error:
        logger.error(f"Failed to nullify Jobs.recuriterID for {user_id}: {update_error}", exc_info=True)
        raise

    try:
        db.query(Jobs).filter(Jobs.hiringManagerID == user_id).update(
            {Jobs.hiringManagerID: None}, synchronize_session=False
        )
    except Exception as update_error:
        logger.error(f"Failed to nullify Jobs.hiringManagerID for {user_id}: {update_error}", exc_info=True)
        raise

    try:
        db.query(CandidateAssignment).filter(
            CandidateAssignment.hiring_manager_id == user_id
        ).update({CandidateAssignment.hiring_manager_id: None}, synchronize_session=False)
    except Exception as update_error:
        logger.error(f"Failed to nullify CandidateAssignment.hiring_manager_id for {user_id}: {update_error}", exc_info=True)
        raise

    try:
        db.query(CandidateAssignment).filter(
            CandidateAssignment.reporting_manager_id == user_id
        ).update({CandidateAssignment.reporting_manager_id: None}, synchronize_session=False)
    except Exception as update_error:
        logger.error(f"Failed to nullify CandidateAssignment.reporting_manager_id for {user_id}: {update_error}", exc_info=True)
        raise

    try:
        db.query(PanelMember).filter(PanelMember.interviewer_id == user_id).update(
            {PanelMember.interviewer_id: None}, synchronize_session=False
        )
    except Exception as update_error:
        logger.error(f"Failed to nullify PanelMember.interviewer_id for {user_id}: {update_error}", exc_info=True)
        raise

    try:
        db.query(InterviewFeedback).filter(InterviewFeedback.interviewer_id == user_id).update(
            {InterviewFeedback.interviewer_id: None}, synchronize_session=False
        )
    except Exception as update_error:
        logger.error(f"Failed to nullify InterviewFeedback.interviewer_id for {user_id}: {update_error}", exc_info=True)
        raise

    try:
        db.query(OfferLetter).filter(OfferLetter.hiring_manager_id == user_id).update(
            {OfferLetter.hiring_manager_id: None}, synchronize_session=False
        )
    except Exception as update_error:
        logger.error(f"Failed to nullify OfferLetter.hiring_manager_id for {user_id}: {update_error}", exc_info=True)
        raise

    try:
        db.query(OfferLetter).filter(OfferLetter.reporting_manager_id == user_id).update(
            {OfferLetter.reporting_manager_id: None}, synchronize_session=False
        )
    except Exception as update_error:
        logger.error(f"Failed to nullify OfferLetter.reporting_manager_id for {user_id}: {update_error}", exc_info=True)
        raise

    try:
        db.query(OfferLetter).filter(OfferLetter.created_by == user_id).update(
            {OfferLetter.created_by: None}, synchronize_session=False
        )
    except Exception as update_error:
        logger.error(f"Failed to nullify OfferLetter.created_by for {user_id}: {update_error}", exc_info=True)
        raise

    try:
        db.query(OfferLetter).filter(OfferLetter.cancelled_by == user_id).update(
            {OfferLetter.cancelled_by: None}, synchronize_session=False
        )
    except Exception as update_error:
        logger.error(f"Failed to nullify OfferLetter.cancelled_by for {user_id}: {update_error}", exc_info=True)
        raise

    try:
        db.query(CandidateDocument).filter(CandidateDocument.verified_by == user_id).update(
            {CandidateDocument.verified_by: None}, synchronize_session=False
        )
    except Exception as update_error:
        logger.error(f"Failed to nullify CandidateDocument.verified_by for {user_id}: {update_error}", exc_info=True)
        raise

    try:
        db.query(Newsletter).filter(Newsletter.created_by == user_id).update(
            {Newsletter.created_by: None}, synchronize_session=False
        )
    except Exception as update_error:
        logger.error(f"Failed to nullify Newsletter.created_by for {user_id}: {update_error}", exc_info=True)
        raise

    try:
        db.delete(target)
    except Exception as delete_error:
        logger.error(f"Failed to delete user {user_id}: {delete_error}", exc_info=True)
        raise

    try:
        db.commit()
    except Exception as commit_error:
        logger.error(f"Failed to commit user deletion for {user_id}: {commit_error}", exc_info=True)
        db.rollback()
        raise

    return DeleteResponse(
        status="Success",
        message=f"User {user_id} deleted successfully"
    )

@router.put(
    "/users/me/change-password",
    response_model=DeleteResponse,
    summary="Change current user's password",
    dependencies=[Depends(require_resource_permission("users-access-control", "edit"))],
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
    "/users/me/whatsapp",
    response_model=DeleteResponse,
    summary="Update current user's WhatsApp number",
)
def update_whatsapp_number(
    request: dict,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Update the WhatsApp number for the currently logged-in user.
    Used by Thunder for candidate outreach when no shared number is available.

    Request body:
        {
            "whatsapp_number": "+1 (555) 123-4567" or null
        }
    """
    whatsapp_number = request.get("whatsapp_number")

    # Validate format if provided
    if whatsapp_number:
        # Basic validation: only allow +, digits, spaces, hyphens, parentheses
        import re
        if not re.match(r'^\+?[0-9\s\-()]+$', str(whatsapp_number)):
            raise HTTPException(
                status_code=400,
                detail="Invalid WhatsApp number format. Use format like +1 (555) 123-4567"
            )

    current_user.whatsapp_number = whatsapp_number
    db.commit()

    return DeleteResponse(
        status="Success",
        message="WhatsApp number updated successfully"
    )

@router.put(
    "/admin/users/{user_id}/reset-password",
    response_model=DeleteResponse,
    summary="Admin force reset user password",
    dependencies=[Depends(require_resource_permission("users-access-control", "edit"))],
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
    dependencies=[Depends(require_resource_permission("users-access-control", "edit"))],
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
    dependencies=[Depends(get_current_internal_user), Depends(require_resource_permission("users-access-control", "view"))],
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

