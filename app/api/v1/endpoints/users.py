from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db, check_user
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
    # Resolve the RBAC role name (if any)
    role = db.query(Role).filter(Role.id == current_user.role_id).first() if current_user.role_id else None

    # Mint a fresh token using the same claims as login
    access_token = create_access_token(
        data={
            "sub": current_user.UserEmail,
            "type": current_user.UserRole,
            "name": current_user.UserName,
        }
    )

    return HrMeResponse(
        user_id=current_user.UserID,
        user_name=current_user.UserName,
        user_email=current_user.UserEmail,
        user_role=current_user.UserRole,
        permission_role=role.name if role else None,
        role_id=current_user.role_id,
        business_unit_id=current_user.business_unit_id,
        created_at=current_user.CreatedAt,
        access_token=access_token,
    )


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
    
    Args:
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        AllUsersResponse with list of all users and total count
    """
    # Query all users from the Users table
    users = db.query(Users).all()
    
    # Build response
    users_data = []
    for u in users:
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
            business_unit_name=u.business_unit.name if u.business_unit else None,
        ))
    
    return AllUsersResponse(
        total_users=len(users_data),
        users=users_data
    )


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
            business_unit_name=u.business_unit.name if u.business_unit else None,
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
        business_unit_name=u.business_unit.name if u.business_unit else None,
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


@router.post(
    "/interviews/create",
    response_model=InterviewResponse,
    status_code=201,
    dependencies=[Depends(require_permission("interview.create"))],
)
def create_interview(
    request: InterviewCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Create an interview with panel and candidate.
    
    Args:
        request: InterviewCreate containing interview details
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewResponse with interview details
        
    Raises:
        HTTPException: If panel or candidate not found
    """
    # Verify panel exists
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == request.panel_id).first()
    if not panel:
        raise HTTPException(
            status_code=404,
            detail=f"Interview panel with ID {request.panel_id} not found"
        )
    
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == request.candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {request.candidate_id} not found"
        )
    
    # Create interview
    interview = Interview(
        panel_id=request.panel_id,
        candidate_id=request.candidate_id,
        start_time=request.start_time,
        end_time=request.end_time,
        meeting_link=request.meeting_link,
        outlook_event_id=request.outlook_event_id,
        status=request.status
    )
    
    db.add(interview)
    db.commit()
    db.refresh(interview)
    
    return InterviewResponse(
        id=interview.id,
        panel_id=interview.panel_id,
        candidate_id=interview.candidate_id,
        start_time=interview.start_time,
        end_time=interview.end_time,
        meeting_link=interview.meeting_link,
        outlook_event_id=interview.outlook_event_id,
        status=interview.status
    )


@router.post(
    "/panel-members/assign",
    response_model=PanelMemberResponse,
    status_code=201,
    dependencies=[Depends(require_permission("interview.create"))],
)
def assign_panel_member(
    request: PanelMemberCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Assign an interviewer to an interview panel.
    
    Args:
        request: PanelMemberCreate containing panel_id and interviewer_id
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        PanelMemberResponse with panel member details
        
    Raises:
        HTTPException: If panel or interviewer not found
    """
    # Verify panel exists
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == request.panel_id).first()
    if not panel:
        raise HTTPException(
            status_code=404,
            detail=f"Interview panel with ID {request.panel_id} not found"
        )
    
    # Verify interviewer exists
    interviewer = db.query(Users).filter(Users.UserID == request.interviewer_id).first()
    if not interviewer:
        raise HTTPException(
            status_code=404,
            detail=f"Interviewer with ID {request.interviewer_id} not found"
        )
    
    # Check if already assigned
    existing = db.query(PanelMember).filter(
        PanelMember.panel_id == request.panel_id,
        PanelMember.interviewer_id == request.interviewer_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Interviewer {request.interviewer_id} is already assigned to panel {request.panel_id}"
        )
    
    # Create panel member
    panel_member = PanelMember(
        panel_id=request.panel_id,
        interviewer_id=request.interviewer_id
    )
    
    db.add(panel_member)
    db.commit()
    db.refresh(panel_member)
    
    return PanelMemberResponse(
        id=panel_member.id,
        panel_id=panel_member.panel_id,
        interviewer_id=panel_member.interviewer_id
    )


@router.post(
    "/interviews/feedback",
    response_model=InterviewFeedbackResponse,
    status_code=201,
    dependencies=[Depends(require_permission("interview.create"))],
)
def submit_interview_feedback(
    request: InterviewFeedbackCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Submit interview feedback with scores and recommendation.
    
    Args:
        request: InterviewFeedbackCreate containing feedback details
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewFeedbackResponse with feedback details
        
    Raises:
        HTTPException: If interview or interviewer not found
    """
    # Verify interview exists
    interview = db.query(Interview).filter(Interview.id == request.interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=404,
            detail=f"Interview with ID {request.interview_id} not found"
        )
    
    # Verify interviewer exists
    interviewer = db.query(Users).filter(Users.UserID == request.interviewer_id).first()
    if not interviewer:
        raise HTTPException(
            status_code=404,
            detail=f"Interviewer with ID {request.interviewer_id} not found"
        )
    
    # Validate recommendation
    valid_recommendations = ["Hire", "Hold", "Reject"]
    if request.recommendation not in valid_recommendations:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid recommendation. Must be one of: {', '.join(valid_recommendations)}"
        )
    
    # Create feedback
    feedback = InterviewFeedback(
        interview_id=request.interview_id,
        interviewer_id=request.interviewer_id,
        technical_score=request.technical_score,
        communication_score=request.communication_score,
        problem_solving_score=request.problem_solving_score,
        culture_fit_score=request.culture_fit_score,
        comments=request.comments,
        recommendation=request.recommendation
    )
    
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    
    return InterviewFeedbackResponse(
        id=feedback.id,
        interview_id=feedback.interview_id,
        interviewer_id=feedback.interviewer_id,
        technical_score=feedback.technical_score,
        communication_score=feedback.communication_score,
        problem_solving_score=feedback.problem_solving_score,
        culture_fit_score=feedback.culture_fit_score,
        comments=feedback.comments,
        recommendation=feedback.recommendation,
        submitted_at=feedback.submitted_at
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



@router.put(
    "/update_interview/{interview_id}",
    response_model=InterviewResponse,
    dependencies=[Depends(require_permission("interview.edit"))],
)
def update_interview(interview_id: int, request: InterviewUpdateRequest, db: Session = Depends(get_db), user = Depends(get_current_hr_or_admin)):
    """
    Update an existing interview.
    
    Args:
        interview_id: ID of the interview to update
        request: InterviewUpdateRequest containing fields to update
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewResponse with updated interview details
        
    Raises:
        HTTPException: If interview not found
    """
    # Find the interview
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=404,
            detail=f"Interview with ID {interview_id} not found"
        )
    
    # Update only provided fields
    if request.start_time is not None:
        interview.start_time = request.start_time
    if request.end_time is not None:
        interview.end_time = request.end_time
    if request.meeting_link is not None:
        interview.meeting_link = request.meeting_link
    if request.outlook_event_id is not None:
        interview.outlook_event_id = request.outlook_event_id
    if request.status is not None:
        interview.status = request.status
    
    db.commit()
    db.refresh(interview)
    
    return InterviewResponse(
        id=interview.id,
        panel_id=interview.panel_id,
        candidate_id=interview.candidate_id,
        start_time=interview.start_time,
        end_time=interview.end_time,
        meeting_link=interview.meeting_link,
        outlook_event_id=interview.outlook_event_id,
        status=interview.status
    )


@router.delete(
    "/delete_interview/{interview_id}",
    response_model=DeleteResponse,
    dependencies=[Depends(require_permission("interview.delete"))],
)
def delete_interview(interview_id: int, db: Session = Depends(get_db), user = Depends(get_current_hr_or_admin)):
    """
    Delete an interview and all associated feedback.
    
    Args:
        interview_id: ID of the interview to delete
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        DeleteResponse with success message
        
    Raises:
        HTTPException: If interview not found
    """
    # Find the interview
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=404,
            detail=f"Interview with ID {interview_id} not found"
        )
    
    # Delete all associated feedback
    db.query(InterviewFeedback).filter(InterviewFeedback.interview_id == interview_id).delete()
    
    # Delete the interview
    db.delete(interview)
    db.commit()
    
    return DeleteResponse(
        status="Success",
        message=f"Interview with ID {interview_id} and all associated feedback deleted successfully"
    )


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


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Update an HR/Admin user's profile or role",
    dependencies=[Depends(require_permission("user.manage"))],
)
def update_user(
    user_id: str,
    user_name: Optional[str] = None,
    user_role: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_hr_or_admin)
):
    """
    Update a user's name or role.
    Requires permission: user.manage
    """
    target = db.query(Users).filter(Users.UserID == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    if user_name is not None:
        target.UserName = user_name
    if user_role is not None:
        target.UserRole = user_role
    db.commit()
    db.refresh(target)
    return UserResponse(
        user_id=target.UserID,
        user_name=target.UserName or "",
        user_email=target.UserEmail,
        user_role=target.UserRole,
        created_at=target.CreatedAt
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

