from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_
from sqlalchemy.orm import Session

import app.schemas as schema
from app.core.database import SessionLocal, engine, check_candidate, check_user, get_db
from app.core.security import (
    verify_password,
    create_access_token,
    get_password_hash,
)
from app.core.dependencies import get_current_hr_or_admin
from app.models import Users, Candidate, CandidateAssignment, Interview, InterviewPanel, InterviewFeedback, PanelMember
from app.schemas.user import (
    AllUsersResponse, UserResponse, 
    CandidateAssignmentCreate, CandidateAssignmentResponse, 
    InterviewCreate, InterviewResponse, InterviewUpdateRequest, 
    InterviewFeedbackCreate, InterviewFeedbackResponse, 
    AssignedCandidateResponse, AssignedInterviewResponse, 
    PanelMemberCreate, PanelMemberResponse, DeleteResponse
)
from app.utils.uniq_id_generator import candidate_id_generator, generate_password, user_id_generator

router = APIRouter(prefix="/hr", tags=["hr"])


@router.get("/users/all", response_model=AllUsersResponse)
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
        users_data.append(UserResponse(
            user_id=u.UserID,
            user_name=u.UserName or "",
            user_email=u.UserEmail,
            user_role=u.UserRole,
            created_at=u.CreatedAt
        ))
    
    return AllUsersResponse(
        total_users=len(users_data),
        users=users_data
    )


@router.post("/assignments/create", response_model=CandidateAssignmentResponse, status_code=201)
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


@router.post("/interviews/create", response_model=InterviewResponse, status_code=201)
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


@router.post("/panel-members/assign", response_model=PanelMemberResponse, status_code=201)
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


@router.post("/interviews/feedback", response_model=InterviewFeedbackResponse, status_code=201)
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


@router.get("/assignments/candidates", response_model=list[AssignedCandidateResponse])
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


@router.get("/interviews/assigned", response_model=list[AssignedInterviewResponse])
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



@router.put("/update_interview/{interview_id}", response_model=InterviewResponse)
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


@router.delete("/delete_interview/{interview_id}", response_model=DeleteResponse)
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
