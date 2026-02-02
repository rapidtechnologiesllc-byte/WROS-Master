from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import app.schemas as schema
from app.core.database import SessionLocal, engine, check_candidate, check_user, get_db
from app.core.security import (
    verify_password,
    create_access_token,
    get_password_hash,
)
from app.models.candidate import (
    Candidate,
    CandidateInfoForm as CandidateInfoModel,
    CandidateEducationForm as CandidateEducationModel,
    CandidateExperienceForm as CandidateExperienceModel,
    CandidateAadharForm as CandidateAadharModel,
    CandidatePanForm as CandidatePanModel
)

from app.core.dependencies import get_current_candidate
from app.schemas.candidate import (
    candidateFormRequest,
    candidateFormResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    CandidateCompleteResponse,
    CandidateInfoResponse,
    CandidateEducationResponse,
    CandidateExperienceResponse,
    CandidateAadharResponse,
    CandidatePanResponse,
    CandidateEducationForm,
    CandidateExperienceForm,
    CandidateAadharForm,
    CandidatePanForm
)
from app.utils.uniq_id_generator import candidate_id_generator, generate_password, user_id_generator

router = APIRouter(prefix="/candidate", tags=["candidate"])

@router.post("/change_password", response_model=ChangePasswordResponse)
def change_password(request: ChangePasswordRequest, db: Session = Depends(get_db), user = Depends(get_current_candidate)):
    """
    Change candidate password after first login.
    
    Args:
        request: ChangePasswordRequest containing candidate_id, old_password, new_password, confirm_password
        db: Database session
        
    Returns:
        ChangePasswordResponse with status and message
        
    Raises:
        HTTPException: If candidate not found, old password incorrect, or validation fails
    """
    # Validate new password and confirm password match
    if request.new_password != request.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="New password and confirm password do not match"
        )
    
    # Validate password strength (minimum 8 characters)
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail="New password must be at least 8 characters long"
        )
    
    # Hash and update the new password
    user.candidatePassword = get_password_hash(request.new_password)
    db.commit()
    db.refresh(user)
    
    return ChangePasswordResponse(
        status="Success",
        message="Password changed successfully"
    )

@router.get("/my-info", response_model=CandidateCompleteResponse)
def get_my_info(db: Session = Depends(get_db), user = Depends(get_current_candidate)):
    """
    Get complete information for the authenticated candidate.
    
    Args:
        db: Database session
        user: Authenticated candidate user
        
    Returns:
        CandidateCompleteResponse with all candidate information including:
        - Personal info (name, email, mobile, etc.)
        - Candidate info form (position, department, dob, etc.)
        - Education records
        - Experience records
        - Aadhar details
        - PAN details
        
    Raises:
        HTTPException: If candidate not found
    """
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == user.candidateID).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {user.candidateID} not found"
        )
    
    # Get candidate name (combine first, middle, last names)
    name_parts = []
    if candidate.candidateFirstName:
        name_parts.append(candidate.candidateFirstName)
    if candidate.candidateMiddleName:
        name_parts.append(candidate.candidateMiddleName)
    if candidate.candidateLastName:
        name_parts.append(candidate.candidateLastName)
    candidate_name = " ".join(name_parts) if name_parts else "N/A"
    
    # Get personal info form
    personal_info_form = db.query(CandidateInfoModel).filter(
        CandidateInfoModel.candidateID == user.candidateID
    ).first()
    
    personal_info = None
    if personal_info_form:
        personal_info = CandidateInfoResponse(
            position=personal_info_form.position,
            department=personal_info_form.department,
            dob=personal_info_form.dob,
            gender=personal_info_form.gender,
            marital_status=personal_info_form.marital_status,
            nationality=personal_info_form.nationality,
            current_address=personal_info_form.current_address,
            permanent_address=personal_info_form.permanent_address
        )
    
    # Get education records
    education_records = db.query(CandidateEducationModel).filter(
        CandidateEducationModel.candidateID == user.candidateID
    ).all()
    
    education = [
        CandidateEducationResponse(
            education_institute=edu.education_institute,
            degree=edu.degree,
            field_of_study=edu.field_of_study,
            starting_year=edu.starting_year,
            year_of_passing=edu.year_of_passing,
            percentage=edu.percentage,
            document_is_submitted=edu.document_is_submitted
        )
        for edu in education_records
    ]
    
    # Get experience records
    experience_records = db.query(CandidateExperienceModel).filter(
        CandidateExperienceModel.candidateID == user.candidateID
    ).all()
    
    experience = [
        CandidateExperienceResponse(
            company_name=exp.company_name,
            job_title=exp.job_title,
            start_date=exp.start_date,
            end_date=exp.end_date,
            year_of_experience=exp.year_of_experience,
            document_is_submitted=exp.document_is_submitted
        )
        for exp in experience_records
    ]
    
    # Get Aadhar details
    aadhar_form = db.query(CandidateAadharModel).filter(
        CandidateAadharModel.candidateID == user.candidateID
    ).first()
    
    aadhar = None
    if aadhar_form:
        aadhar = CandidateAadharResponse(
            aadhar=aadhar_form.aadhar,
            name_in_aadhar=aadhar_form.name_in_aadhar,
            enrollment_number=aadhar_form.enrollment_number,
            aadhar_is_submitted=aadhar_form.aadhar_is_submitted,
            is_verified=aadhar_form.is_verified
        )
    
    # Get PAN details
    pan_form = db.query(CandidatePanModel).filter(
        CandidatePanModel.candidateID == user.candidateID
    ).first()
    
    pan = None
    if pan_form:
        pan = CandidatePanResponse(
            pan=pan_form.pan,
            name_in_pan=pan_form.name_in_pan,
            father_name_in_pan=pan_form.father_name_in_pan,
            pan_is_submitted=pan_form.pan_is_submitted,
            is_verified=pan_form.is_verified
        )
    
    # Build and return complete response
    return CandidateCompleteResponse(
        candidate_id=candidate.candidateID,
        candidate_name=candidate_name,
        candidate_email=candidate.candidateEmail,
        candidate_mobile=candidate.candidateMobile,
        candidate_role=candidate.candidateRole,
        candidate_is_verified=candidate.candidateIsVerified,
        candidate_created_at=candidate.candidateCreatedAt,
        personal_info=personal_info,
        education=education,
        experience=experience,
        aadhar=aadhar,
        pan=pan
    )


@router.post("/candidate-form/", response_model=candidateFormResponse)
def candidate_info(request: candidateFormRequest, db: Session = Depends(get_db), user = Depends(get_current_candidate)):
    """
    Create or update candidate information form.
    
    Args:
        request: candidateFormRequest containing candidate form details
        db: Database session
        
    Returns:
        candidateFormResponse with status and message
        
    Raises:
        HTTPException: If candidate not found or validation fails
    """
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == user.candidateID).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {user.candidateID} not found"
        )
    
    # Check if form already exists for this candidate
    existing_form = db.query(CandidateInfoModel).filter(
        CandidateInfoModel.candidateID == user.candidateID
    ).first()
    
    if existing_form:
        # Update existing form
        existing_form.position = request.position
        existing_form.department = request.department
        existing_form.dob = request.dob
        existing_form.gender = request.gender
        existing_form.marital_status = request.marital_status
        existing_form.nationality = request.nationality
        existing_form.current_address = request.current_address
        existing_form.permanent_address = request.permanent_address
        existing_form.submittedAt = request.submitted_at
        
        db.commit()
        db.refresh(existing_form)
        
        return candidateFormResponse(
            status="Success",
            message="Candidate form updated successfully"
        )
    else:
        # Create new form (formID is auto-generated by database)
        new_form = CandidateInfoModel(
            candidateID=user.candidateID,
            position=request.position,
            department=request.department,
            dob=request.dob,
            gender=request.gender,
            marital_status=request.marital_status,
            nationality=request.nationality,
            current_address=request.current_address,
            permanent_address=request.permanent_address,
            submittedAt=request.submitted_at
        )
        
        db.add(new_form)
        db.commit()
        db.refresh(new_form)
        
        return candidateFormResponse(
            status="Success",
            message="Candidate form submitted successfully"
        )


@router.post("/education-form/", response_model=candidateFormResponse)
def candidate_education(request: CandidateEducationForm, db: Session = Depends(get_db), user = Depends(get_current_candidate)):
    """
    Create or update candidate education forms (supports multiple records).
    
    Args:
        request: CandidateEducationForm containing candidate_id and list of education records
        db: Database session
        
    Returns:
        candidateFormResponse with status and message
        
    Raises:
        HTTPException: If candidate not found, empty list, or validation fails
    """
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == user.candidateID).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {user.candidateID} not found"
        )
    
    # Validate that education_records is not empty
    if not request.education_records or len(request.education_records) == 0:
        raise HTTPException(
            status_code=400,
            detail="At least one education record is required"
        )
    
    # Delete existing education records for this candidate (replace all)
    db.query(CandidateEducationModel).filter(
        CandidateEducationModel.candidateID == user.candidateID
    ).delete()
    
    # Insert all new education records
    records_created = 0
    for edu_record in request.education_records:
        new_form = CandidateEducationModel(
            candidateID=user.candidateID,
            education_institute=edu_record.education_institute,
            degree=edu_record.degree,
            field_of_study=edu_record.field_of_study,
            starting_year=edu_record.starting_year,
            year_of_passing=edu_record.year_of_passing,
            percentage=edu_record.percentage,
            submittedAt=edu_record.submitted_at,
            document_is_submitted=edu_record.document_is_submitted
        )
        db.add(new_form)
        records_created += 1
    
    db.commit()
    
    return candidateFormResponse(
        status="Success",
        message=f"{records_created} education record(s) submitted successfully"
    )


@router.post("/experience-form/", response_model=candidateFormResponse)
def candidate_experience(request: CandidateExperienceForm, db: Session = Depends(get_db), user = Depends(get_current_candidate)):
    """
    Create or update candidate experience forms (supports multiple records).
    
    Args:
        request: CandidateExperienceForm containing candidate_id and list of experience records
        db: Database session
        
    Returns:
        candidateFormResponse with status and message
        
    Raises:
        HTTPException: If candidate not found, empty list, or validation fails
    """
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == user.candidateID).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {user.candidateID} not found"
        )
    
    # Validate that experience_records is not empty
    if not request.experience_records or len(request.experience_records) == 0:
        raise HTTPException(
            status_code=400,
            detail="At least one experience record is required"
        )
    
    # Delete existing experience records for this candidate (replace all)
    db.query(CandidateExperienceModel).filter(
        CandidateExperienceModel.candidateID == user.candidateID
    ).delete()
    
    # Insert all new experience records
    records_created = 0
    for exp_record in request.experience_records:
        new_form = CandidateExperienceModel(
            candidateID=user.candidateID,
            company_name=exp_record.company_name,
            job_title=exp_record.job_title,
            start_date=exp_record.start_date,
            end_date=exp_record.end_date,
            year_of_experience=exp_record.year_of_experience,
            submittedAt=exp_record.submitted_at,
            document_is_submitted=exp_record.document_is_submitted
        )
        db.add(new_form)
        records_created += 1
    
    db.commit()
    
    return candidateFormResponse(
        status="Success",
        message=f"{records_created} experience record(s) submitted successfully"
    )


@router.post("/aadhar-form/", response_model=candidateFormResponse)
def candidate_aadhar(request: CandidateAadharForm, db: Session = Depends(get_db), user = Depends(get_current_candidate)):
    """
    Create or update candidate Aadhar form.
    
    Args:
        request: CandidateAadharForm containing Aadhar details
        db: Database session
        user: Authenticated candidate user
        
    Returns:
        candidateFormResponse with status and message
        
    Raises:
        HTTPException: If candidate not found or validation fails
    """
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == user.candidateID).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {user.candidateID} not found"
        )
    
    # Check if form already exists for this candidate
    existing_form = db.query(CandidateAadharModel).filter(
        CandidateAadharModel.candidateID == user.candidateID
    ).first()
    
    if existing_form:
        # Update existing form
        existing_form.aadhar = request.aadhar
        existing_form.name_in_aadhar = request.name_in_aadhar
        existing_form.enrollment_number = request.enrollment_number
        existing_form.aadhar_is_submitted = request.aadhar_is_submitted
        existing_form.submittedAt = request.submitted_at
        existing_form.is_verified = request.is_verified
        
        db.commit()
        db.refresh(existing_form)
        
        return candidateFormResponse(
            status="Success",
            message="Aadhar form updated successfully"
        )
    else:
        # Create new form (formID is auto-generated by database)
        new_form = CandidateAadharModel(
            candidateID=user.candidateID,
            aadhar=request.aadhar,
            name_in_aadhar=request.name_in_aadhar,
            enrollment_number=request.enrollment_number,
            aadhar_is_submitted=request.aadhar_is_submitted,
            submittedAt=request.submitted_at,
            is_verified=request.is_verified
        )
        
        db.add(new_form)
        db.commit()
        db.refresh(new_form)
        
        return candidateFormResponse(
            status="Success",
            message="Aadhar form submitted successfully"
        )


@router.post("/pan-form/", response_model=candidateFormResponse)
def candidate_pan(request: CandidatePanForm, db: Session = Depends(get_db), user = Depends(get_current_candidate)):
    """
    Create or update candidate PAN form.
    
    Args:
        request: CandidatePanForm containing PAN details
        db: Database session
        user: Authenticated candidate user
        
    Returns:
        candidateFormResponse with status and message
        
    Raises:
        HTTPException: If candidate not found or validation fails
    """
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == user.candidateID).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {user.candidateID} not found"
        )
    
    # Check if form already exists for this candidate
    existing_form = db.query(CandidatePanModel).filter(
        CandidatePanModel.candidateID == user.candidateID
    ).first()
    
    if existing_form:
        # Update existing form
        existing_form.pan = request.pan
        existing_form.name_in_pan = request.name_in_pan
        existing_form.father_name_in_pan = request.father_name_in_pan
        existing_form.pan_is_submitted = request.pan_is_submitted
        existing_form.submittedAt = request.submitted_at
        existing_form.is_verified = request.is_verified
        
        db.commit()
        db.refresh(existing_form)
        
        return schema.candidateFormResponse(
            status="Success",
            message="PAN form updated successfully"
        )
    else:
        # Create new form (formID is auto-generated by database)
        new_form = CandidatePanModel(
            candidateID=user.candidateID,
            pan=request.pan,
            name_in_pan=request.name_in_pan,
            father_name_in_pan=request.father_name_in_pan,
            pan_is_submitted=request.pan_is_submitted,
            submittedAt=request.submitted_at,
            is_verified=request.is_verified
        )
        
        db.add(new_form)
        db.commit()
        db.refresh(new_form)
        
        return candidateFormResponse(
            status="Success",
            message="PAN form submitted successfully"
        )

