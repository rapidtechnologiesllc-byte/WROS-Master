from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

import app.schemas as schema
from app.core.database import check_candidate, get_db
from app.core.security import get_password_hash
from app.models.candidate import (
    Candidate,
    CandidateInfoForm,
    CandidateEducationForm,
    CandidateExperienceForm,
    CandidateAadharForm,
    CandidatePanForm
)
from app.models.user import Users, Interview, CandidateAssignment

from app.core.dependencies import get_current_hr_or_admin, get_current_candidate, require_permission

from app.schemas.candidate import (CandidateCreateRequest,
CandidateCreateResponse, CandidateCompleteResponse,
CandidateEducationResponse, CandidateExperienceResponse,
CandidateInfoResponse, CandidatePanResponse,
CandidateAadharResponse, DeleteResponse,
AllCandidatesResponse)
from app.schemas.user import CandidateUpdateRequest

from app.utils.uniq_id_generator import candidate_id_generator, generate_password

router = APIRouter(prefix="/onboarding", tags=["onboarding"])



@router.post(
    "/hr/create_candidate",
    response_model=CandidateCreateResponse,
    dependencies=[Depends(require_permission("candidate.create"))],
)
def create_candidate(request: CandidateCreateRequest, db: Session = Depends(get_db), user = Depends(get_current_hr_or_admin)):
    """
    Create a new candidate account with comprehensive information.
    
    Args:
        request: CandidateCreateRequest containing candidate details including:
                - Required: email, role
                - Optional: name fields, contact info, professional details, salary info, location
        db: Database session
        
    Returns:
        CandidateCreateResponse with candidate_id, is_first_time flag, and generated password
        
    Raises:
        HTTPException: If candidate with email already exists
    """
    # Check if candidate already exists
    existing = check_candidate(db, request.candidate_email)
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"Account already exists with email {request.candidate_email}"
        )
    
    # Generate unique ID and password
    candidate_id = candidate_id_generator()
    password = generate_password()
    
    # Hash the password before storing
    hashed_password = get_password_hash(password)
    
    # Create new candidate with all available fields
    candidate = Candidate(
        candidateID=candidate_id,
        candidateRole=request.candidate_role,
        candidateFirstName=request.candidate_first_name,
        candidateMiddleName=request.candidate_middle_name,
        candidateLastName=request.candidate_last_name,
        candidateEmail=request.candidate_email,
        candidateMobile=request.candidate_mobile,
        candidateGender=request.candidate_gender,
        candidateDateOfBirth=request.candidate_date_of_birth,
        candidateSource=request.candidate_source,
        candidateExperience=request.candidate_experience,
        candidateSkills=request.candidate_skills,
        candidateJoiningDate=request.candidate_joining_date,
        candidateExpectedSalary=request.candidate_expected_salary,
        candidateCurrentSalary=request.candidate_current_salary,
        candidateCurrentLocation=request.candidate_current_location,
        candidatePassword=hashed_password,  # Store hashed password
        candidateIsVerified=False,
        candidateCreatedAt=datetime.now()
    )
    
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    
    # Return plain password so it can be sent to the candidate
    return CandidateCreateResponse(
        candidate_id=candidate_id, 
        candidate_is_first_time=True, 
        candidate_password=password  # Return plain password
    )

@router.get(
    "/hr/get_all_candidates",
    response_model=AllCandidatesResponse,
    dependencies=[Depends(require_permission("candidate.view"))],
)
def get_all_candidates(db: Session = Depends(get_db), user = Depends(get_current_hr_or_admin)):
    """
    Get all candidates with their complete information for HR/Admin.
    
    Returns:
        AllCandidatesResponse with list of all candidates and their forms
    """
    # Get all candidates
    candidates = db.query(Candidate).all()
    
    candidates_data = []
    for candidate in candidates:
        # Construct candidate name
        name_parts = [
            candidate.candidateFirstName or "",
            candidate.candidateMiddleName or "",
            candidate.candidateLastName or ""
        ]
        candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"
        
        # Get personal info form
        personal_info = db.query(CandidateInfoForm).filter(
            CandidateInfoForm.candidateID == candidate.candidateID
        ).first()
        
        # Get all education records
        education_records = db.query(CandidateEducationForm).filter(
            CandidateEducationForm.candidateID == candidate.candidateID
        ).all()
        
        # Get all experience records
        experience_records = db.query(CandidateExperienceForm).filter(
            CandidateExperienceForm.candidateID == candidate.candidateID
        ).all()
        
        # Get Aadhar form
        aadhar_form = db.query(CandidateAadharForm).filter(
            CandidateAadharForm.candidateID == candidate.candidateID
        ).first()
        
        # Get PAN form
        pan_form = db.query(CandidatePanForm).filter(
            CandidatePanForm.candidateID == candidate.candidateID
        ).first()
        
        # Build response object
        candidate_response = CandidateCompleteResponse(
            candidate_id=candidate.candidateID,
            candidate_name=candidate_name,
            candidate_email=candidate.candidateEmail,
            candidate_mobile=candidate.candidateMobile,
            candidate_role=candidate.candidateRole,
            candidate_is_verified=candidate.candidateIsVerified,
            candidate_created_at=candidate.candidateCreatedAt,
            personal_info=CandidateInfoResponse(
                position=personal_info.position if personal_info else None,
                department=personal_info.department if personal_info else None,
                dob=personal_info.dob if personal_info else None,
                gender=personal_info.gender if personal_info else None,
                marital_status=personal_info.marital_status if personal_info else None,
                nationality=personal_info.nationality if personal_info else None,
                current_address=personal_info.current_address if personal_info else None,
                permanent_address=personal_info.permanent_address if personal_info else None
            ) if personal_info else None,
            education=[
                CandidateEducationResponse(
                    education_institute=edu.education_institute,
                    degree=edu.degree,
                    field_of_study=edu.field_of_study,
                    starting_year=edu.starting_year,
                    year_of_passing=edu.year_of_passing,
                    percentage=edu.percentage,
                    document_is_submitted=edu.document_is_submitted
                ) for edu in education_records
            ],
            experience=[
                CandidateExperienceResponse(
                    company_name=exp.company_name,
                    job_title=exp.job_title,
                    start_date=exp.start_date,
                    end_date=exp.end_date,
                    year_of_experience=exp.year_of_experience,
                    document_is_submitted=exp.document_is_submitted
                ) for exp in experience_records
            ],
            aadhar=CandidateAadharResponse(
                aadhar=aadhar_form.aadhar if aadhar_form else None,
                name_in_aadhar=aadhar_form.name_in_aadhar if aadhar_form else None,
                enrollment_number=aadhar_form.enrollment_number if aadhar_form else None,
                aadhar_is_submitted=aadhar_form.aadhar_is_submitted if aadhar_form else None,
                is_verified=aadhar_form.is_verified if aadhar_form else None
            ) if aadhar_form else None,
            pan=CandidatePanResponse(
                pan=pan_form.pan if pan_form else None,
                name_in_pan=pan_form.name_in_pan if pan_form else None,
                father_name_in_pan=pan_form.father_name_in_pan if pan_form else None,
                pan_is_submitted=pan_form.pan_is_submitted if pan_form else None,
                is_verified=pan_form.is_verified if pan_form else None
            ) if pan_form else None
        )
        
        candidates_data.append(candidate_response)
    
    return AllCandidatesResponse(
        total_candidates=len(candidates_data),
        candidates=candidates_data
    )

@router.put(
    "/hr/update_candidate/{candidate_id}",
    response_model=CandidateCreateResponse,
    dependencies=[Depends(require_permission("candidate.edit"))],
)
def update_candidate(candidate_id: str, request: CandidateUpdateRequest, db: Session = Depends(get_db), user = Depends(get_current_hr_or_admin)):
    """
    Update an existing candidate.
    
    Args:
        candidate_id: ID of the candidate to update
        request: CandidateUpdateRequest containing fields to update
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        CandidateCreateResponse with updated candidate details
        
    Raises:
        HTTPException: If candidate not found
    """
    # Find the candidate
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {candidate_id} not found"
        )
    
    # Update only provided fields
    if request.candidate_first_name is not None:
        candidate.candidateFirstName = request.candidate_first_name
    if request.candidate_middle_name is not None:
        candidate.candidateMiddleName = request.candidate_middle_name
    if request.candidate_last_name is not None:
        candidate.candidateLastName = request.candidate_last_name
    if request.candidate_mobile is not None:
        candidate.candidateMobile = request.candidate_mobile
    if request.candidate_gender is not None:
        candidate.candidateGender = request.candidate_gender
    if request.candidate_date_of_birth is not None:
        candidate.candidateDateOfBirth = request.candidate_date_of_birth
    if request.candidate_source is not None:
        candidate.candidateSource = request.candidate_source
    if request.candidate_experience is not None:
        candidate.candidateExperience = request.candidate_experience
    if request.candidate_skills is not None:
        candidate.candidateSkills = request.candidate_skills
    if request.candidate_joining_date is not None:
        candidate.candidateJoiningDate = request.candidate_joining_date
    if request.candidate_expected_salary is not None:
        candidate.candidateExpectedSalary = request.candidate_expected_salary
    if request.candidate_current_salary is not None:
        candidate.candidateCurrentSalary = request.candidate_current_salary
    if request.candidate_current_location is not None:
        candidate.candidateCurrentLocation = request.candidate_current_location
    if request.assigned_hr_manager_id is not None:
        candidate.assignedHRManagerID = request.assigned_hr_manager_id
    if request.assigned_report_manager_id is not None:
        candidate.assignedReportManagerID = request.assigned_report_manager_id
    
    db.commit()
    db.refresh(candidate)
    
    return CandidateCreateResponse(
        candidate_id=candidate.candidateID,
        candidate_is_first_time=candidate.candidateIsFirstTime,
        candidate_password=candidate.candidatePassword
    )


@router.delete(
    "/hr/delete_candidate/{candidate_id}",
    response_model=DeleteResponse,
    dependencies=[Depends(require_permission("candidate.delete"))],
)
def delete_candidate(candidate_id: str, db: Session = Depends(get_db), user = Depends(get_current_hr_or_admin)):
    """
    Delete a candidate and all associated records.
    
    Args:
        candidate_id: ID of the candidate to delete
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        DeleteResponse with success message
        
    Raises:
        HTTPException: If candidate not found
    """
    # Find the candidate
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {candidate_id} not found"
        )
    
    # Delete all associated records
    db.query(CandidateInfoForm).filter(CandidateInfoForm.candidateID == candidate_id).delete()
    db.query(CandidateEducationForm).filter(CandidateEducationForm.candidateID == candidate_id).delete()
    db.query(CandidateExperienceForm).filter(CandidateExperienceForm.candidateID == candidate_id).delete()
    db.query(CandidateAadharForm).filter(CandidateAadharForm.candidateID == candidate_id).delete()
    db.query(CandidatePanForm).filter(CandidatePanForm.candidateID == candidate_id).delete()
    db.query(CandidateAssignment).filter(CandidateAssignment.candidate_id == candidate_id).delete()
    db.query(Interview).filter(Interview.candidate_id == candidate_id).delete()
    
    # Delete the candidate
    db.delete(candidate)
    db.commit()
    
    return DeleteResponse(
        status="Success",
        message=f"Candidate with ID {candidate_id} and all associated records deleted successfully"
    )





