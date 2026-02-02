from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin
from app.models import (
    Users, Candidate, Interview, InterviewPanel, 
    InterviewFeedback, PanelMember
)
from app.schemas.interview import (
    # Panel schemas
    InterviewPanelCreate, InterviewPanelResponse, InterviewPanelWithDetails,
    # Panel member schemas
    PanelMemberCreate, PanelMemberResponse, PanelMemberWithDetails,
    # Interview schemas
    InterviewCreate, InterviewUpdate, InterviewResponse, InterviewDetailedResponse,
    # Feedback schemas
    InterviewFeedbackCreate, InterviewFeedbackUpdate, 
    InterviewFeedbackResponse, InterviewFeedbackWithDetails,
    # Statistics and history
    InterviewStatistics, CandidateInterviewHistory, InterviewerWorkload,
    # Common responses
    DeleteResponse, BulkDeleteResponse
)

router = APIRouter(prefix="/interviews", tags=["interviews"])


# ============================================
# Interview Panel Endpoints
# ============================================

@router.post("/panels/create", response_model=InterviewPanelResponse, status_code=201)
def create_interview_panel(
    request: InterviewPanelCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Create a new interview panel for a candidate.
    
    Args:
        request: InterviewPanelCreate with candidate_id and round_name
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewPanelResponse with panel details
        
    Raises:
        HTTPException: If candidate not found
    """
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == request.candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {request.candidate_id} not found"
        )
    
    # Create panel
    panel = InterviewPanel(
        candidate_id=request.candidate_id,
        round_name=request.round_name
    )
    
    db.add(panel)
    db.commit()
    db.refresh(panel)
    
    return InterviewPanelResponse(
        id=panel.id,
        candidate_id=panel.candidate_id,
        round_name=panel.round_name,
        created_at=panel.created_at
    )


@router.get("/panels/{panel_id}", response_model=InterviewPanelWithDetails)
def get_interview_panel(
    panel_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Get details of a specific interview panel.
    
    Args:
        panel_id: ID of the panel
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewPanelWithDetails including member and interview counts
        
    Raises:
        HTTPException: If panel not found
    """
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == panel_id).first()
    if not panel:
        raise HTTPException(
            status_code=404,
            detail=f"Interview panel with ID {panel_id} not found"
        )
    
    # Get candidate details
    candidate = db.query(Candidate).filter(Candidate.candidateID == panel.candidate_id).first()
    candidate_name = "N/A"
    if candidate:
        name_parts = [
            candidate.candidateFirstName or "",
            candidate.candidateMiddleName or "",
            candidate.candidateLastName or ""
        ]
        candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"
    
    # Count members and interviews
    member_count = db.query(PanelMember).filter(PanelMember.panel_id == panel_id).count()
    interview_count = db.query(Interview).filter(Interview.panel_id == panel_id).count()
    
    return InterviewPanelWithDetails(
        id=panel.id,
        candidate_id=panel.candidate_id,
        candidate_name=candidate_name,
        round_name=panel.round_name,
        created_at=panel.created_at,
        member_count=member_count,
        interview_count=interview_count
    )


@router.get("/panels", response_model=List[InterviewPanelWithDetails])
def get_all_interview_panels(
    candidate_id: Optional[str] = Query(None, description="Filter by candidate ID"),
    round_name: Optional[str] = Query(None, description="Filter by round name"),
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Get all interview panels with optional filtering.
    
    Args:
        candidate_id: Optional filter by candidate ID
        round_name: Optional filter by round name
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        List of InterviewPanelWithDetails
    """
    query = db.query(InterviewPanel)
    
    if candidate_id:
        query = query.filter(InterviewPanel.candidate_id == candidate_id)
    if round_name:
        query = query.filter(InterviewPanel.round_name == round_name)
    
    panels = query.all()
    
    results = []
    for panel in panels:
        # Get candidate details
        candidate = db.query(Candidate).filter(Candidate.candidateID == panel.candidate_id).first()
        candidate_name = "N/A"
        if candidate:
            name_parts = [
                candidate.candidateFirstName or "",
                candidate.candidateMiddleName or "",
                candidate.candidateLastName or ""
            ]
            candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"
        
        # Count members and interviews
        member_count = db.query(PanelMember).filter(PanelMember.panel_id == panel.id).count()
        interview_count = db.query(Interview).filter(Interview.panel_id == panel.id).count()
        
        results.append(InterviewPanelWithDetails(
            id=panel.id,
            candidate_id=panel.candidate_id,
            candidate_name=candidate_name,
            round_name=panel.round_name,
            created_at=panel.created_at,
            member_count=member_count,
            interview_count=interview_count
        ))
    
    return results


@router.delete("/panels/{panel_id}", response_model=DeleteResponse)
def delete_interview_panel(
    panel_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Delete an interview panel and all associated data.
    
    Args:
        panel_id: ID of the panel to delete
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        DeleteResponse with success message
        
    Raises:
        HTTPException: If panel not found
    """
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == panel_id).first()
    if not panel:
        raise HTTPException(
            status_code=404,
            detail=f"Interview panel with ID {panel_id} not found"
        )
    
    # Delete associated interviews and their feedback
    interviews = db.query(Interview).filter(Interview.panel_id == panel_id).all()
    for interview in interviews:
        db.query(InterviewFeedback).filter(InterviewFeedback.interview_id == interview.id).delete()
    
    # Delete interviews
    db.query(Interview).filter(Interview.panel_id == panel_id).delete()
    
    # Delete panel members
    db.query(PanelMember).filter(PanelMember.panel_id == panel_id).delete()
    
    # Delete panel
    db.delete(panel)
    db.commit()
    
    return DeleteResponse(
        status="Success",
        message=f"Interview panel {panel_id} and all associated data deleted successfully"
    )


# ============================================
# Panel Member Endpoints
# ============================================

@router.post("/panel-members/assign", response_model=PanelMemberResponse, status_code=201)
def assign_panel_member(
    request: PanelMemberCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Assign an interviewer to an interview panel.
    
    Args:
        request: PanelMemberCreate with panel_id and interviewer_id
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        PanelMemberResponse with assignment details
        
    Raises:
        HTTPException: If panel or interviewer not found, or already assigned
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


@router.get("/panel-members/{panel_id}", response_model=List[PanelMemberWithDetails])
def get_panel_members(
    panel_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Get all members of a specific panel.
    
    Args:
        panel_id: ID of the panel
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        List of PanelMemberWithDetails
        
    Raises:
        HTTPException: If panel not found
    """
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == panel_id).first()
    if not panel:
        raise HTTPException(
            status_code=404,
            detail=f"Interview panel with ID {panel_id} not found"
        )
    
    members = db.query(PanelMember).filter(PanelMember.panel_id == panel_id).all()
    
    results = []
    for member in members:
        interviewer = db.query(Users).filter(Users.UserID == member.interviewer_id).first()
        if interviewer:
            results.append(PanelMemberWithDetails(
                id=member.id,
                panel_id=member.panel_id,
                interviewer_id=member.interviewer_id,
                interviewer_name=interviewer.UserName or "N/A",
                interviewer_email=interviewer.UserEmail
            ))
    
    return results


@router.delete("/panel-members/{member_id}", response_model=DeleteResponse)
def remove_panel_member(
    member_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Remove an interviewer from a panel.
    
    Args:
        member_id: ID of the panel member to remove
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        DeleteResponse with success message
        
    Raises:
        HTTPException: If panel member not found
    """
    member = db.query(PanelMember).filter(PanelMember.id == member_id).first()
    if not member:
        raise HTTPException(
            status_code=404,
            detail=f"Panel member with ID {member_id} not found"
        )
    
    db.delete(member)
    db.commit()
    
    return DeleteResponse(
        status="Success",
        message=f"Panel member {member_id} removed successfully"
    )


# ============================================
# Interview Endpoints
# ============================================

@router.post("/create", response_model=InterviewResponse, status_code=201)
def create_interview(
    request: InterviewCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Create a new interview.
    
    Args:
        request: InterviewCreate with interview details
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewResponse with interview details
        
    Raises:
        HTTPException: If panel or candidate not found, or time validation fails
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
    
    # Validate time
    if request.end_time <= request.start_time:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time"
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


@router.get("/{interview_id}", response_model=InterviewDetailedResponse)
def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Get details of a specific interview.
    
    Args:
        interview_id: ID of the interview
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewDetailedResponse with complete interview details
        
    Raises:
        HTTPException: If interview not found
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=404,
            detail=f"Interview with ID {interview_id} not found"
        )
    
    # Get panel details
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
    panel_round_name = panel.round_name if panel else "N/A"
    
    # Get candidate details
    candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
    candidate_name = "N/A"
    candidate_email = "N/A"
    if candidate:
        name_parts = [
            candidate.candidateFirstName or "",
            candidate.candidateMiddleName or "",
            candidate.candidateLastName or ""
        ]
        candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"
        candidate_email = candidate.candidateEmail
    
    # Count feedback
    feedback_count = db.query(InterviewFeedback).filter(
        InterviewFeedback.interview_id == interview_id
    ).count()
    
    return InterviewDetailedResponse(
        id=interview.id,
        panel_id=interview.panel_id,
        panel_round_name=panel_round_name,
        candidate_id=interview.candidate_id,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        start_time=interview.start_time,
        end_time=interview.end_time,
        meeting_link=interview.meeting_link,
        outlook_event_id=interview.outlook_event_id,
        status=interview.status,
        feedback_count=feedback_count
    )


@router.get("", response_model=List[InterviewDetailedResponse])
def get_all_interviews(
    candidate_id: Optional[str] = Query(None, description="Filter by candidate ID"),
    panel_id: Optional[int] = Query(None, description="Filter by panel ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Get all interviews with optional filtering.
    
    Args:
        candidate_id: Optional filter by candidate ID
        panel_id: Optional filter by panel ID
        status: Optional filter by status
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        List of InterviewDetailedResponse
    """
    query = db.query(Interview)
    
    if candidate_id:
        query = query.filter(Interview.candidate_id == candidate_id)
    if panel_id:
        query = query.filter(Interview.panel_id == panel_id)
    if status:
        query = query.filter(Interview.status == status)
    
    interviews = query.all()
    
    results = []
    for interview in interviews:
        # Get panel details
        panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
        panel_round_name = panel.round_name if panel else "N/A"
        
        # Get candidate details
        candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
        candidate_name = "N/A"
        candidate_email = "N/A"
        if candidate:
            name_parts = [
                candidate.candidateFirstName or "",
                candidate.candidateMiddleName or "",
                candidate.candidateLastName or ""
            ]
            candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"
            candidate_email = candidate.candidateEmail
        
        # Count feedback
        feedback_count = db.query(InterviewFeedback).filter(
            InterviewFeedback.interview_id == interview.id
        ).count()
        
        results.append(InterviewDetailedResponse(
            id=interview.id,
            panel_id=interview.panel_id,
            panel_round_name=panel_round_name,
            candidate_id=interview.candidate_id,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            start_time=interview.start_time,
            end_time=interview.end_time,
            meeting_link=interview.meeting_link,
            outlook_event_id=interview.outlook_event_id,
            status=interview.status,
            feedback_count=feedback_count
        ))
    
    return results


@router.put("/{interview_id}", response_model=InterviewResponse)
def update_interview(
    interview_id: int,
    request: InterviewUpdate,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Update an existing interview.
    
    Args:
        interview_id: ID of the interview to update
        request: InterviewUpdate with fields to update
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewResponse with updated interview details
        
    Raises:
        HTTPException: If interview not found or validation fails
    """
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
    
    # Validate time if both are set
    if interview.end_time <= interview.start_time:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time"
        )
    
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


@router.delete("/{interview_id}", response_model=DeleteResponse)
def delete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
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
        message=f"Interview {interview_id} and all associated feedback deleted successfully"
    )


# ============================================
# Interview Feedback Endpoints
# ============================================

@router.post("/feedback/submit", response_model=InterviewFeedbackResponse, status_code=201)
def submit_interview_feedback(
    request: InterviewFeedbackCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Submit interview feedback.
    
    Args:
        request: InterviewFeedbackCreate with feedback details
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewFeedbackResponse with feedback details
        
    Raises:
        HTTPException: If interview or interviewer not found, or validation fails
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


@router.get("/feedback/interview/{interview_id}", response_model=List[InterviewFeedbackWithDetails])
def get_feedback_by_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Get all feedback for a specific interview.
    
    Args:
        interview_id: ID of the interview
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        List of InterviewFeedbackWithDetails
        
    Raises:
        HTTPException: If interview not found
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=404,
            detail=f"Interview with ID {interview_id} not found"
        )
    
    feedbacks = db.query(InterviewFeedback).filter(
        InterviewFeedback.interview_id == interview_id
    ).all()
    
    results = []
    for feedback in feedbacks:
        interviewer = db.query(Users).filter(Users.UserID == feedback.interviewer_id).first()
        
        # Calculate average score
        avg_score = (
            feedback.technical_score +
            feedback.communication_score +
            feedback.problem_solving_score +
            feedback.culture_fit_score
        ) / 4.0
        
        results.append(InterviewFeedbackWithDetails(
            id=feedback.id,
            interview_id=feedback.interview_id,
            interviewer_id=feedback.interviewer_id,
            interviewer_name=interviewer.UserName if interviewer else "N/A",
            interviewer_email=interviewer.UserEmail if interviewer else "N/A",
            technical_score=feedback.technical_score,
            communication_score=feedback.communication_score,
            problem_solving_score=feedback.problem_solving_score,
            culture_fit_score=feedback.culture_fit_score,
            average_score=round(avg_score, 2),
            comments=feedback.comments,
            recommendation=feedback.recommendation,
            submitted_at=feedback.submitted_at
        ))
    
    return results


@router.get("/feedback/{feedback_id}", response_model=InterviewFeedbackWithDetails)
def get_feedback_by_id(
    feedback_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Get specific feedback details.
    
    Args:
        feedback_id: ID of the feedback
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewFeedbackWithDetails
        
    Raises:
        HTTPException: If feedback not found
    """
    feedback = db.query(InterviewFeedback).filter(InterviewFeedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(
            status_code=404,
            detail=f"Feedback with ID {feedback_id} not found"
        )
    
    interviewer = db.query(Users).filter(Users.UserID == feedback.interviewer_id).first()
    
    # Calculate average score
    avg_score = (
        feedback.technical_score +
        feedback.communication_score +
        feedback.problem_solving_score +
        feedback.culture_fit_score
    ) / 4.0
    
    return InterviewFeedbackWithDetails(
        id=feedback.id,
        interview_id=feedback.interview_id,
        interviewer_id=feedback.interviewer_id,
        interviewer_name=interviewer.UserName if interviewer else "N/A",
        interviewer_email=interviewer.UserEmail if interviewer else "N/A",
        technical_score=feedback.technical_score,
        communication_score=feedback.communication_score,
        problem_solving_score=feedback.problem_solving_score,
        culture_fit_score=feedback.culture_fit_score,
        average_score=round(avg_score, 2),
        comments=feedback.comments,
        recommendation=feedback.recommendation,
        submitted_at=feedback.submitted_at
    )


@router.put("/feedback/{feedback_id}", response_model=InterviewFeedbackResponse)
def update_interview_feedback(
    feedback_id: int,
    request: InterviewFeedbackUpdate,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Update existing interview feedback.
    
    Args:
        feedback_id: ID of the feedback to update
        request: InterviewFeedbackUpdate with fields to update
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewFeedbackResponse with updated feedback
        
    Raises:
        HTTPException: If feedback not found or validation fails
    """
    feedback = db.query(InterviewFeedback).filter(InterviewFeedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(
            status_code=404,
            detail=f"Feedback with ID {feedback_id} not found"
        )
    
    # Update only provided fields
    if request.technical_score is not None:
        feedback.technical_score = request.technical_score
    if request.communication_score is not None:
        feedback.communication_score = request.communication_score
    if request.problem_solving_score is not None:
        feedback.problem_solving_score = request.problem_solving_score
    if request.culture_fit_score is not None:
        feedback.culture_fit_score = request.culture_fit_score
    if request.comments is not None:
        feedback.comments = request.comments
    if request.recommendation is not None:
        # Validate recommendation
        valid_recommendations = ["Hire", "Hold", "Reject"]
        if request.recommendation not in valid_recommendations:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid recommendation. Must be one of: {', '.join(valid_recommendations)}"
            )
        feedback.recommendation = request.recommendation
    
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


@router.delete("/feedback/{feedback_id}", response_model=DeleteResponse)
def delete_interview_feedback(
    feedback_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Delete interview feedback.
    
    Args:
        feedback_id: ID of the feedback to delete
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        DeleteResponse with success message
        
    Raises:
        HTTPException: If feedback not found
    """
    feedback = db.query(InterviewFeedback).filter(InterviewFeedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(
            status_code=404,
            detail=f"Feedback with ID {feedback_id} not found"
        )
    
    db.delete(feedback)
    db.commit()
    
    return DeleteResponse(
        status="Success",
        message=f"Feedback {feedback_id} deleted successfully"
    )


# ============================================
# Statistics and Analytics Endpoints
# ============================================

@router.get("/statistics", response_model=InterviewStatistics)
def get_interview_statistics(
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Get overall interview statistics.
    
    Args:
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewStatistics with counts and averages
    """
    total_interviews = db.query(Interview).count()
    scheduled = db.query(Interview).filter(Interview.status == "Scheduled").count()
    completed = db.query(Interview).filter(Interview.status == "Completed").count()
    cancelled = db.query(Interview).filter(Interview.status == "Cancelled").count()
    total_panels = db.query(InterviewPanel).count()
    total_feedback = db.query(InterviewFeedback).count()
    
    # Calculate average feedback score
    avg_score = None
    if total_feedback > 0:
        feedbacks = db.query(InterviewFeedback).all()
        total_score = sum(
            (f.technical_score + f.communication_score + 
             f.problem_solving_score + f.culture_fit_score) / 4.0
            for f in feedbacks
        )
        avg_score = round(total_score / total_feedback, 2)
    
    return InterviewStatistics(
        total_interviews=total_interviews,
        scheduled=scheduled,
        completed=completed,
        cancelled=cancelled,
        total_panels=total_panels,
        total_feedback=total_feedback,
        average_feedback_score=avg_score
    )


@router.get("/candidate-history/{candidate_id}", response_model=CandidateInterviewHistory)
def get_candidate_interview_history(
    candidate_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Get complete interview history for a candidate.
    
    Args:
        candidate_id: ID of the candidate
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        CandidateInterviewHistory with all interview details
        
    Raises:
        HTTPException: If candidate not found
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {candidate_id} not found"
        )
    
    # Get candidate name
    name_parts = [
        candidate.candidateFirstName or "",
        candidate.candidateMiddleName or "",
        candidate.candidateLastName or ""
    ]
    candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"
    
    # Get all interviews
    interviews = db.query(Interview).filter(Interview.candidate_id == candidate_id).all()
    
    total_interviews = len(interviews)
    scheduled_interviews = sum(1 for i in interviews if i.status == "Scheduled")
    completed_interviews = sum(1 for i in interviews if i.status == "Completed")
    cancelled_interviews = sum(1 for i in interviews if i.status == "Cancelled")
    
    # Build detailed interview list
    interview_details = []
    for interview in interviews:
        panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
        panel_round_name = panel.round_name if panel else "N/A"
        
        feedback_count = db.query(InterviewFeedback).filter(
            InterviewFeedback.interview_id == interview.id
        ).count()
        
        interview_details.append(InterviewDetailedResponse(
            id=interview.id,
            panel_id=interview.panel_id,
            panel_round_name=panel_round_name,
            candidate_id=interview.candidate_id,
            candidate_name=candidate_name,
            candidate_email=candidate.candidateEmail,
            start_time=interview.start_time,
            end_time=interview.end_time,
            meeting_link=interview.meeting_link,
            outlook_event_id=interview.outlook_event_id,
            status=interview.status,
            feedback_count=feedback_count
        ))
    
    return CandidateInterviewHistory(
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        candidate_email=candidate.candidateEmail,
        total_interviews=total_interviews,
        scheduled_interviews=scheduled_interviews,
        completed_interviews=completed_interviews,
        cancelled_interviews=cancelled_interviews,
        interviews=interview_details
    )


@router.get("/interviewer-workload/{interviewer_id}", response_model=InterviewerWorkload)
def get_interviewer_workload(
    interviewer_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Get workload statistics for an interviewer.
    
    Args:
        interviewer_id: ID of the interviewer
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewerWorkload with statistics and upcoming interviews
        
    Raises:
        HTTPException: If interviewer not found
    """
    interviewer = db.query(Users).filter(Users.UserID == interviewer_id).first()
    if not interviewer:
        raise HTTPException(
            status_code=404,
            detail=f"Interviewer with ID {interviewer_id} not found"
        )
    
    # Get panel memberships
    panel_memberships = db.query(PanelMember).filter(
        PanelMember.interviewer_id == interviewer_id
    ).all()
    
    total_panels = len(panel_memberships)
    panel_ids = [m.panel_id for m in panel_memberships]
    
    # Get all interviews for these panels
    interviews = db.query(Interview).filter(Interview.panel_id.in_(panel_ids)).all() if panel_ids else []
    
    total_interviews = len(interviews)
    scheduled_interviews = sum(1 for i in interviews if i.status == "Scheduled")
    completed_interviews = sum(1 for i in interviews if i.status == "Completed")
    
    # Get feedback submitted by this interviewer
    feedback_submitted = db.query(InterviewFeedback).filter(
        InterviewFeedback.interviewer_id == interviewer_id
    ).count()
    
    # Get upcoming interviews (scheduled, future)
    now = datetime.utcnow()
    upcoming = [i for i in interviews if i.status == "Scheduled" and i.start_time > now]
    
    upcoming_details = []
    for interview in upcoming[:10]:  # Limit to 10 upcoming
        panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
        panel_round_name = panel.round_name if panel else "N/A"
        
        candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
        candidate_name = "N/A"
        candidate_email = "N/A"
        if candidate:
            name_parts = [
                candidate.candidateFirstName or "",
                candidate.candidateMiddleName or "",
                candidate.candidateLastName or ""
            ]
            candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"
            candidate_email = candidate.candidateEmail
        
        feedback_count = db.query(InterviewFeedback).filter(
            InterviewFeedback.interview_id == interview.id
        ).count()
        
        upcoming_details.append(InterviewDetailedResponse(
            id=interview.id,
            panel_id=interview.panel_id,
            panel_round_name=panel_round_name,
            candidate_id=interview.candidate_id,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            start_time=interview.start_time,
            end_time=interview.end_time,
            meeting_link=interview.meeting_link,
            outlook_event_id=interview.outlook_event_id,
            status=interview.status,
            feedback_count=feedback_count
        ))
    
    return InterviewerWorkload(
        interviewer_id=interviewer_id,
        interviewer_name=interviewer.UserName or "N/A",
        interviewer_email=interviewer.UserEmail,
        total_panels=total_panels,
        total_interviews=total_interviews,
        scheduled_interviews=scheduled_interviews,
        completed_interviews=completed_interviews,
        feedback_submitted=feedback_submitted,
        upcoming_interviews=upcoming_details
    )
