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
    CandidatePanForm,
    EducationRecord,
    ExperienceRecord
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
    
    # Hash and update the new password; also store plain text for credential emails
    user.candidatePassword = get_password_hash(request.new_password)
    user.candidateTempPassword = request.new_password
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
            formID=edu.formID,
            education_institute=edu.education_institute,
            degree=edu.degree,
            field_of_study=edu.field_of_study,
            starting_year=edu.starting_year,
            year_of_passing=edu.year_of_passing,
            percentage=edu.percentage,
            document_is_submitted=edu.document_is_submitted,
            document_id=edu.document_id
        )
        for edu in education_records
    ]
    
    # Get experience records
    experience_records = db.query(CandidateExperienceModel).filter(
        CandidateExperienceModel.candidateID == user.candidateID
    ).all()
    
    experience = [
        CandidateExperienceResponse(
            formID=exp.formID,
            company_name=exp.company_name,
            job_title=exp.job_title,
            start_date=exp.start_date,
            end_date=exp.end_date,
            year_of_experience=exp.year_of_experience,
            document_is_submitted=exp.document_is_submitted,
            document_id=exp.document_id
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
            formID=aadhar_form.formID,
            aadhar=aadhar_form.aadhar,
            name_in_aadhar=aadhar_form.name_in_aadhar,
            enrollment_number=aadhar_form.enrollment_number,
            aadhar_is_submitted=aadhar_form.aadhar_is_submitted,
            is_verified=aadhar_form.is_verified,
            document_id=aadhar_form.document_id
        )
    
    # Get PAN details
    pan_form = db.query(CandidatePanModel).filter(
        CandidatePanModel.candidateID == user.candidateID
    ).first()
    
    pan = None
    if pan_form:
        pan = CandidatePanResponse(
            formID=pan_form.formID,
            pan=pan_form.pan,
            name_in_pan=pan_form.name_in_pan,
            father_name_in_pan=pan_form.father_name_in_pan,
            pan_is_submitted=pan_form.pan_is_submitted,
            is_verified=pan_form.is_verified,
            document_id=pan_form.document_id
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
        candidate_gender=candidate.candidateGender,
        candidate_date_of_birth=candidate.candidateDateOfBirth,
        candidate_source=candidate.candidateSource,
        candidate_experience=candidate.candidateExperience,
        candidate_skills=candidate.candidateSkills,
        candidate_joining_date=candidate.candidateJoiningDate,
        candidate_current_location=candidate.candidateCurrentLocation,
        candidate_current_salary=candidate.candidateCurrentSalary,
        candidate_expected_salary=candidate.candidateExpectedSalary,
        job_id=candidate.job_id,
        personal_info=CandidateInfoResponse(
            position=personal_info_form.position if personal_info_form else None,
            department=personal_info_form.department if personal_info_form else None,
            dob=personal_info_form.dob if personal_info_form else None,
            gender=personal_info_form.gender if personal_info_form else None,
            marital_status=personal_info_form.marital_status if personal_info_form else None,
            nationality=personal_info_form.nationality if personal_info_form else None,
            current_address=personal_info_form.current_address if personal_info_form else None,
            permanent_address=personal_info_form.permanent_address if personal_info_form else None,
            submitted_at=personal_info_form.submittedAt if personal_info_form else None,
        ) if personal_info_form else None,
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
            document_is_submitted=edu_record.document_is_submitted,
            document_id=edu_record.document_id,
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
            document_is_submitted=exp_record.document_is_submitted,
            document_id=exp_record.document_id,
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
        existing_form.document_id = request.document_id
        
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
            is_verified=request.is_verified,
            document_id=request.document_id,
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
        existing_form.document_id = request.document_id
        
        db.commit()
        db.refresh(existing_form)
        
        return candidateFormResponse(
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
            is_verified=request.is_verified,
            document_id=request.document_id,
        )
        
        db.add(new_form)
        db.commit()
        db.refresh(new_form)
        
        return candidateFormResponse(
            status="Success",
            message="PAN form submitted successfully"
        )


# ============================================
# Enhanced CRUD Operations
# ============================================

# Individual Education Record Management
@router.post("/education/add", response_model=candidateFormResponse)
def add_education_record(
    request: EducationRecord,
    db: Session = Depends(get_db),
    user = Depends(get_current_candidate)
):
    """
    Add a single education record for the authenticated candidate.
    
    Args:
        request: EducationRecord containing education details
        db: Database session
        user: Authenticated candidate
        
    Returns:
        candidateFormResponse with success message
    """
    new_education = CandidateEducationModel(
        candidateID=user.candidateID,
        education_institute=request.education_institute,
        degree=request.degree,
        field_of_study=request.field_of_study,
        starting_year=request.starting_year,
        year_of_passing=request.year_of_passing,
        percentage=request.percentage,
        submittedAt=request.submitted_at,
        document_is_submitted=request.document_is_submitted,
        document_id=request.document_id,
    )
    
    db.add(new_education)
    db.commit()
    db.refresh(new_education)
    
    return candidateFormResponse(
        status="Success",
        message=f"Education record added successfully with ID {new_education.formID}"
    )


@router.put("/education/{education_id}", response_model=candidateFormResponse)
def update_education_record(
    education_id: int,
    request: EducationRecord,
    db: Session = Depends(get_db),
    user = Depends(get_current_candidate)
):
    """
    Update a specific education record by ID.
    
    Args:
        education_id: ID of the education record to update
        request: EducationRecord with updated details
        db: Database session
        user: Authenticated candidate
        
    Returns:
        candidateFormResponse with success message
        
    Raises:
        HTTPException: If record not found or doesn't belong to candidate
    """
    education_record = db.query(CandidateEducationModel).filter(
        CandidateEducationModel.formID == education_id,
        CandidateEducationModel.candidateID == user.candidateID
    ).first()
    
    if not education_record:
        raise HTTPException(
            status_code=404,
            detail=f"Education record with ID {education_id} not found"
        )
    
    # Update fields
    education_record.education_institute = request.education_institute
    education_record.degree = request.degree
    education_record.field_of_study = request.field_of_study
    education_record.starting_year = request.starting_year
    education_record.year_of_passing = request.year_of_passing
    education_record.percentage = request.percentage
    education_record.submittedAt = request.submitted_at
    education_record.document_is_submitted = request.document_is_submitted
    education_record.document_id = request.document_id
    
    db.commit()
    db.refresh(education_record)
    
    return candidateFormResponse(
        status="Success",
        message=f"Education record {education_id} updated successfully"
    )


@router.delete("/education/{education_id}", response_model=candidateFormResponse)
def delete_education_record(
    education_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_candidate)
):
    """
    Delete a specific education record by ID.
    
    Args:
        education_id: ID of the education record to delete
        db: Database session
        user: Authenticated candidate
        
    Returns:
        candidateFormResponse with success message
        
    Raises:
        HTTPException: If record not found or doesn't belong to candidate
    """
    education_record = db.query(CandidateEducationModel).filter(
        CandidateEducationModel.formID == education_id,
        CandidateEducationModel.candidateID == user.candidateID
    ).first()
    
    if not education_record:
        raise HTTPException(
            status_code=404,
            detail=f"Education record with ID {education_id} not found"
        )
    
    db.delete(education_record)
    db.commit()
    
    return candidateFormResponse(
        status="Success",
        message=f"Education record {education_id} deleted successfully"
    )


@router.get("/education/list")
def list_education_records(
    db: Session = Depends(get_db),
    user = Depends(get_current_candidate)
):
    """
    Get all education records for the authenticated candidate with IDs.
    
    Returns:
        List of education records with formID included
    """
    education_records = db.query(CandidateEducationModel).filter(
        CandidateEducationModel.candidateID == user.candidateID
    ).all()
    
    return {
        "status": "Success",
        "count": len(education_records),
        "records": [
            {
                "formID": edu.formID,
                "education_institute": edu.education_institute,
                "degree": edu.degree,
                "field_of_study": edu.field_of_study,
                "starting_year": edu.starting_year,
                "year_of_passing": edu.year_of_passing,
                "percentage": edu.percentage,
                "document_is_submitted": edu.document_is_submitted,
                "document_id": edu.document_id,
                "submitted_at": edu.submittedAt
            }
            for edu in education_records
        ]
    }


# Individual Experience Record Management
@router.post("/experience/add", response_model=candidateFormResponse)
def add_experience_record(
    request: ExperienceRecord,
    db: Session = Depends(get_db),
    user = Depends(get_current_candidate)
):
    """
    Add a single experience record for the authenticated candidate.
    
    Args:
        request: ExperienceRecord containing experience details
        db: Database session
        user: Authenticated candidate
        
    Returns:
        candidateFormResponse with success message
    """
    new_experience = CandidateExperienceModel(
        candidateID=user.candidateID,
        company_name=request.company_name,
        job_title=request.job_title,
        start_date=request.start_date,
        end_date=request.end_date,
        year_of_experience=request.year_of_experience,
        submittedAt=request.submitted_at,
        document_is_submitted=request.document_is_submitted,
        document_id=request.document_id,
    )
    
    db.add(new_experience)
    db.commit()
    db.refresh(new_experience)
    
    return candidateFormResponse(
        status="Success",
        message=f"Experience record added successfully with ID {new_experience.formID}"
    )


@router.put("/experience/{experience_id}", response_model=candidateFormResponse)
def update_experience_record(
    experience_id: int,
    request: ExperienceRecord,
    db: Session = Depends(get_db),
    user = Depends(get_current_candidate)
):
    """
    Update a specific experience record by ID.
    
    Args:
        experience_id: ID of the experience record to update
        request: ExperienceRecord with updated details
        db: Database session
        user: Authenticated candidate
        
    Returns:
        candidateFormResponse with success message
        
    Raises:
        HTTPException: If record not found or doesn't belong to candidate
    """
    experience_record = db.query(CandidateExperienceModel).filter(
        CandidateExperienceModel.formID == experience_id,
        CandidateExperienceModel.candidateID == user.candidateID
    ).first()
    
    if not experience_record:
        raise HTTPException(
            status_code=404,
            detail=f"Experience record with ID {experience_id} not found"
        )
    
    # Update fields
    experience_record.company_name = request.company_name
    experience_record.job_title = request.job_title
    experience_record.start_date = request.start_date
    experience_record.end_date = request.end_date
    experience_record.year_of_experience = request.year_of_experience
    experience_record.submittedAt = request.submitted_at
    experience_record.document_is_submitted = request.document_is_submitted
    experience_record.document_id = request.document_id
    
    db.commit()
    db.refresh(experience_record)
    
    return candidateFormResponse(
        status="Success",
        message=f"Experience record {experience_id} updated successfully"
    )


@router.delete("/experience/{experience_id}", response_model=candidateFormResponse)
def delete_experience_record(
    experience_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_candidate)
):
    """
    Delete a specific experience record by ID.
    
    Args:
        experience_id: ID of the experience record to delete
        db: Database session
        user: Authenticated candidate
        
    Returns:
        candidateFormResponse with success message
        
    Raises:
        HTTPException: If record not found or doesn't belong to candidate
    """
    experience_record = db.query(CandidateExperienceModel).filter(
        CandidateExperienceModel.formID == experience_id,
        CandidateExperienceModel.candidateID == user.candidateID
    ).first()
    
    if not experience_record:
        raise HTTPException(
            status_code=404,
            detail=f"Experience record with ID {experience_id} not found"
        )
    
    db.delete(experience_record)
    db.commit()
    
    return candidateFormResponse(
        status="Success",
        message=f"Experience record {experience_id} deleted successfully"
    )


@router.get("/experience/list")
def list_experience_records(
    db: Session = Depends(get_db),
    user = Depends(get_current_candidate)
):
    """
    Get all experience records for the authenticated candidate with IDs.
    
    Returns:
        List of experience records with formID included
    """
    experience_records = db.query(CandidateExperienceModel).filter(
        CandidateExperienceModel.candidateID == user.candidateID
    ).all()
    
    return {
        "status": "Success",
        "count": len(experience_records),
        "records": [
            {
                "formID": exp.formID,
                "company_name": exp.company_name,
                "job_title": exp.job_title,
                "start_date": exp.start_date,
                "end_date": exp.end_date,
                "year_of_experience": exp.year_of_experience,
                "document_is_submitted": exp.document_is_submitted,
                "document_id": exp.document_id,
                "submitted_at": exp.submittedAt
            }
            for exp in experience_records
        ]
    }


# Individual Form Retrieval
@router.get("/personal-info", response_model=CandidateInfoResponse)
def get_personal_info(
    db: Session = Depends(get_db),
    user = Depends(get_current_candidate)
):
    """
    Get only the personal info form for the authenticated candidate.
    
    Returns:
        CandidateInfoResponse with personal information
        
    Raises:
        HTTPException: If personal info not found
    """
    personal_info = db.query(CandidateInfoModel).filter(
        CandidateInfoModel.candidateID == user.candidateID
    ).first()
    
    if not personal_info:
        raise HTTPException(
            status_code=404,
            detail="Personal information not found"
        )
    
    return CandidateInfoResponse(
        position=personal_info.position,
        department=personal_info.department,
        dob=personal_info.dob,
        gender=personal_info.gender,
        marital_status=personal_info.marital_status,
        nationality=personal_info.nationality,
        current_address=personal_info.current_address,
        permanent_address=personal_info.permanent_address
    )


@router.get("/aadhar", response_model=CandidateAadharResponse)
def get_aadhar_info(
    db: Session = Depends(get_db),
    user = Depends(get_current_candidate)
):
    """
    Get only the Aadhar form for the authenticated candidate.
    
    Returns:
        CandidateAadharResponse with Aadhar information
        
    Raises:
        HTTPException: If Aadhar info not found
    """
    aadhar_info = db.query(CandidateAadharModel).filter(
        CandidateAadharModel.candidateID == user.candidateID
    ).first()
    
    if not aadhar_info:
        raise HTTPException(
            status_code=404,
            detail="Aadhar information not found"
        )
    
    return CandidateAadharResponse(
        aadhar=aadhar_info.aadhar,
        name_in_aadhar=aadhar_info.name_in_aadhar,
        enrollment_number=aadhar_info.enrollment_number,
        aadhar_is_submitted=aadhar_info.aadhar_is_submitted,
        is_verified=aadhar_info.is_verified
    )


@router.get("/pan", response_model=CandidatePanResponse)
def get_pan_info(
    db: Session = Depends(get_db),
    user = Depends(get_current_candidate)
):
    """
    Get only the PAN form for the authenticated candidate.
    
    Returns:
        CandidatePanResponse with PAN information
        
    Raises:
        HTTPException: If PAN info not found
    """
    pan_info = db.query(CandidatePanModel).filter(
        CandidatePanModel.candidateID == user.candidateID
    ).first()
    
    if not pan_info:
        raise HTTPException(
            status_code=404,
            detail="PAN information not found"
        )
    
    return CandidatePanResponse(
        pan=pan_info.pan,
        name_in_pan=pan_info.name_in_pan,
        father_name_in_pan=pan_info.father_name_in_pan,
        pan_is_submitted=pan_info.pan_is_submitted,
        is_verified=pan_info.is_verified
    )


# Onboarding Status Tracking
@router.get("/onboarding-status")
def get_onboarding_status(
    db: Session = Depends(get_db),
    user = Depends(get_current_candidate)
):
    """
    Get onboarding completion status for the authenticated candidate.
    
    Returns:
        Detailed status including completion percentage and form-wise status
    """
    # Check each form
    personal_info = db.query(CandidateInfoModel).filter(
        CandidateInfoModel.candidateID == user.candidateID
    ).first()
    
    education_count = db.query(CandidateEducationModel).filter(
        CandidateEducationModel.candidateID == user.candidateID
    ).count()
    
    experience_count = db.query(CandidateExperienceModel).filter(
        CandidateExperienceModel.candidateID == user.candidateID
    ).count()
    
    aadhar_form = db.query(CandidateAadharModel).filter(
        CandidateAadharModel.candidateID == user.candidateID
    ).first()
    
    pan_form = db.query(CandidatePanModel).filter(
        CandidatePanModel.candidateID == user.candidateID
    ).first()
    
    # Calculate completion (experience is optional, so total is 4 required forms)
    forms_completed = 0
    total_required_forms = 4
    
    if personal_info:
        forms_completed += 1
    if education_count > 0:
        forms_completed += 1
    if aadhar_form:
        forms_completed += 1
    if pan_form:
        forms_completed += 1
    
    overall_completion = (forms_completed / total_required_forms) * 100
    
    return {
        "status": "Success",
        "candidate_id": user.candidateID,
        "overall_completion": round(overall_completion, 2),
        "forms_status": {
            "personal_info": {
                "completed": personal_info is not None,
                "required": True
            },
            "education": {
                "completed": education_count > 0,
                "count": education_count,
                "required": True
            },
            "experience": {
                "completed": experience_count > 0,
                "count": experience_count,
                "required": False
            },
            "aadhar": {
                "completed": aadhar_form is not None,
                "verified": aadhar_form.is_verified if aadhar_form else False,
                "required": True
            },
            "pan": {
                "completed": pan_form is not None,
                "verified": pan_form.is_verified if pan_form else False,
                "required": True
            }
        }
    }


# Opt-out Management - CRITICAL: Included in every email/WhatsApp message
@router.post("/opt-out/{candidate_id}")
def opt_out_candidate(candidate_id: str, db: Session = Depends(get_db)):
    """
    Public opt-out endpoint (no auth required).
    IMPORTANT: This link MUST be included in every email and WhatsApp message.

    Candidates can click this link to opt out of Thunder engagement.
    Sets do_not_contact = True to stop all outreach.

    Args:
        candidate_id: The candidate's ID from the email/WhatsApp link

    Returns:
        Confirmation that candidate has been opted out
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidate.do_not_contact = True
    db.commit()

    return {
        "status": "success",
        "message": f"You have been opted out of BlitzenX communications",
        "candidate_id": candidate_id,
        "do_not_contact": True
    }


@router.get("/opt-out/status/{candidate_id}")
def check_opt_out_status(candidate_id: str, db: Session = Depends(get_db)):
    """
    Check if a candidate has opted out.
    Used in message templates to skip sending if opted out.
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return {
        "candidate_id": candidate_id,
        "do_not_contact": candidate.do_not_contact,
        "can_contact": not candidate.do_not_contact
    }


@router.post("/preferences")
def update_candidate_preferences(
    db: Session = Depends(get_db),
    user = Depends(get_current_candidate)
):
    """
    Authenticated endpoint for candidates to manage their preferences.
    Allows candidates to opt-out from their dashboard.
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == user.candidateID).first()

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Toggle do_not_contact
    candidate.do_not_contact = not candidate.do_not_contact
    db.commit()

    return {
        "status": "success",
        "candidate_id": candidate.candidateID,
        "do_not_contact": candidate.do_not_contact,
        "message": "opted out" if candidate.do_not_contact else "opted in to communications"
    }

