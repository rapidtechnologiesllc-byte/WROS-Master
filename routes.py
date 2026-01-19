from fastapi import FastAPI, Depends, HTTPException, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base, check_candidate
from typing import Optional
from fastapi import APIRouter
from security import get_current_hr_or_admin, verify_password, create_access_token, get_password_hash, get_current_candidate
from datetime import datetime
from utils.uniq_id_generator import candidate_id_generator, generate_password, user_id_generator
import schema
from schema import CandidateCreateRequest, CandidateCreateResponse
from model import Candidate
from model import Users
from database import check_user

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/v1/signup", response_model=schema.SignupResponse)
def signup(request: schema.SignupRequest, db: Session = Depends(get_db)):
    """
    Create a new user account
    
    Args:
        request: SignupRequest containing user details
        db: Database session
        
    Returns:
        SignupResponse with success message
        
    Raises:
        HTTPException: If user with email already exists
    """
    # Check if user already exists
    existing = check_user(db, request.user_email)
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"Account already exists with email {request.user_email}"
        )
    
    # Generate unique ID and hash password
    user_id = user_id_generator()
    hashed_password = get_password_hash(request.user_password)
    
    # Create new user with correct field names matching Users model
    user = Users(
        UserID=user_id,
        UserName=request.user_name,
        UserEmail=request.user_email,
        UserPassword=hashed_password,
        UserRole=request.user_role
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return schema.SignupResponse(response="User created successfully")
    



@router.post("/v1/login", response_model=schema.LoginResponse)
def login(request: schema.LoginRequest, db: Session = Depends(get_db)):
    """
    User login endpoint
    
    Args:
        request: LoginRequest containing email and password
        db: Database session
        
    Returns:
        LoginResponse with user details and access token
        
    Raises:
        HTTPException: If credentials are invalid
    """
    # Authenticate user
    from database import authenticate_user
    
    user = authenticate_user(db, request.UserEmail, request.UserPassword)
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Create access token
    access_token = create_access_token(
        data={
            "sub": user.UserID,
            "type": "user"
        }
    )
    
    # Return user info and token
    return schema.LoginResponse(
        user_role=user.UserRole,
        user_name=user.UserName or "",
        user_email=user.UserEmail,
        is_first_time=False,  # Assuming existing users are not first time
        access_token=access_token
    )

        
@router.post("/hr/create_candidate", response_model=CandidateCreateResponse)
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

@router.get("/hr/get_all_candidates", response_model=schema.AllCandidatesResponse)
def get_all_candidates(db: Session = Depends(get_db), user = Depends(get_current_hr_or_admin)):
    """
    Get all candidates with their complete information for HR/Admin.
    
    Returns:
        AllCandidatesResponse with list of all candidates and their forms
    """
    from model import (
        Candidate, CandidateInfoForm, CandidateEducationForm, 
        CandidateExperienceForm, CandidateAadharForm, CandidatePanForm
    )
    
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
        candidate_response = schema.CandidateCompleteResponse(
            candidate_id=candidate.candidateID,
            candidate_name=candidate_name,
            candidate_email=candidate.candidateEmail,
            candidate_mobile=candidate.candidateMobile,
            candidate_role=candidate.candidateRole,
            candidate_is_verified=candidate.candidateIsVerified,
            candidate_created_at=candidate.candidateCreatedAt,
            personal_info=schema.CandidateInfoResponse(
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
                schema.CandidateEducationResponse(
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
                schema.CandidateExperienceResponse(
                    company_name=exp.company_name,
                    job_title=exp.job_title,
                    start_date=exp.start_date,
                    end_date=exp.end_date,
                    year_of_experience=exp.year_of_experience,
                    document_is_submitted=exp.document_is_submitted
                ) for exp in experience_records
            ],
            aadhar=schema.CandidateAadharResponse(
                aadhar=aadhar_form.aadhar if aadhar_form else None,
                name_in_aadhar=aadhar_form.name_in_aadhar if aadhar_form else None,
                enrollment_number=aadhar_form.enrollment_number if aadhar_form else None,
                aadhar_is_submitted=aadhar_form.aadhar_is_submitted if aadhar_form else None,
                is_verified=aadhar_form.is_verified if aadhar_form else None
            ) if aadhar_form else None,
            pan=schema.CandidatePanResponse(
                pan=pan_form.pan if pan_form else None,
                name_in_pan=pan_form.name_in_pan if pan_form else None,
                father_name_in_pan=pan_form.father_name_in_pan if pan_form else None,
                pan_is_submitted=pan_form.pan_is_submitted if pan_form else None,
                is_verified=pan_form.is_verified if pan_form else None
            ) if pan_form else None
        )
        
        candidates_data.append(candidate_response)
    
    return schema.AllCandidatesResponse(
        total_candidates=len(candidates_data),
        candidates=candidates_data
    )


@router.post("/candidate/login", response_model=schema.CandidateLoginResponse)
def candidate_login(request: schema.CandidateLoginRequest, db : Session = Depends(get_db)):
    """
    Candidate login endpoint
    
    Args:
        request: CandidateLoginRequest containing email and password
        db: Database session
        
    Returns:
        CandidateLoginResponse with candidate details and access token
        
    Raises:
        HTTPException: If credentials are invalid
    """
    # Authenticate candidate
    from database import authenticate_candidate
    
    candidate = authenticate_candidate(db, request.candidate_email, request.candidate_password)
    
    if not candidate:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Create access token
    access_token = create_access_token(
        data={
            "sub": candidate.candidateID,
            "type": "candidate"
        }
    )
    
    # Construct full name from name fields
    name_parts = [
        candidate.candidateFirstName,
        candidate.candidateMiddleName,
        candidate.candidateLastName
    ]
    candidate_name = " ".join(filter(None, name_parts)) or ""
    
    # Return candidate info and token
    return schema.CandidateLoginResponse(
        candidate_id=candidate.candidateID,
        candidate_role=candidate.candidateRole or "Candidate",
        candidate_name=candidate_name,
        candidate_email=candidate.candidateEmail,
        candidate_mobile=candidate.candidateMobile,
        is_first_time=not candidate.candidateIsVerified if candidate.candidateIsVerified is not None else True,
        access_token=access_token
    )

@router.post("/candidate/candidate-form/", response_model=schema.candidateFormResponse)
def candidate_info(request: schema.candidateFormRequest, db: Session = Depends(get_db), user = Depends(get_current_candidate)):
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
    # Import model here to avoid circular import
    from model import CandidateInfoForm, Candidate
    
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == request.candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {request.candidate_id} not found"
        )
    
    # Check if form already exists for this candidate
    existing_form = db.query(CandidateInfoForm).filter(
        CandidateInfoForm.candidateID == request.candidate_id
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
        
        return schema.candidateFormResponse(
            status="Success",
            message="Candidate form updated successfully"
        )
    else:
        # Create new form (formID is auto-generated by database)
        new_form = CandidateInfoForm(
            candidateID=request.candidate_id,
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
        
        return schema.candidateFormResponse(
            status="Success",
            message="Candidate form submitted successfully"
        )


@router.post("/candidate/education-form/", response_model=schema.candidateFormResponse)
def candidate_education(request: schema.CandidateEducationForm, db: Session = Depends(get_db), user = Depends(get_current_candidate)):
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
    # Import model here to avoid circular import
    from model import CandidateEducationForm, Candidate
    
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == request.candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {request.candidate_id} not found"
        )
    
    # Validate that education_records is not empty
    if not request.education_records or len(request.education_records) == 0:
        raise HTTPException(
            status_code=400,
            detail="At least one education record is required"
        )
    
    # Delete existing education records for this candidate (replace all)
    db.query(CandidateEducationForm).filter(
        CandidateEducationForm.candidateID == request.candidate_id
    ).delete()
    
    # Insert all new education records
    records_created = 0
    for edu_record in request.education_records:
        new_form = CandidateEducationForm(
            candidateID=request.candidate_id,
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
    
    return schema.candidateFormResponse(
        status="Success",
        message=f"{records_created} education record(s) submitted successfully"
    )


@router.post("/candidate/experience-form/", response_model=schema.candidateFormResponse)
def candidate_experience(request: schema.CandidateExperienceForm, db: Session = Depends(get_db), user = Depends(get_current_candidate)):
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
    # Import model here to avoid circular import
    from model import CandidateExperienceForm, Candidate
    
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == request.candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {request.candidate_id} not found"
        )
    
    # Validate that experience_records is not empty
    if not request.experience_records or len(request.experience_records) == 0:
        raise HTTPException(
            status_code=400,
            detail="At least one experience record is required"
        )
    
    # Delete existing experience records for this candidate (replace all)
    db.query(CandidateExperienceForm).filter(
        CandidateExperienceForm.candidateID == request.candidate_id
    ).delete()
    
    # Insert all new experience records
    records_created = 0
    for exp_record in request.experience_records:
        new_form = CandidateExperienceForm(
            candidateID=request.candidate_id,
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
    
    return schema.candidateFormResponse(
        status="Success",
        message=f"{records_created} experience record(s) submitted successfully"
    )


@router.post("/candidate/aadhar-form/", response_model=schema.candidateFormResponse)
def candidate_aadhar(request: schema.CandidateAadharForm, db: Session = Depends(get_db), user = Depends(get_current_candidate)):
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
    # Import model here to avoid circular import
    from model import CandidateAadharForm, Candidate
    
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == request.candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {request.candidate_id} not found"
        )
    
    # Check if form already exists for this candidate
    existing_form = db.query(CandidateAadharForm).filter(
        CandidateAadharForm.candidateID == request.candidate_id
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
        
        return schema.candidateFormResponse(
            status="Success",
            message="Aadhar form updated successfully"
        )
    else:
        # Create new form (formID is auto-generated by database)
        new_form = CandidateAadharForm(
            candidateID=request.candidate_id,
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
        
        return schema.candidateFormResponse(
            status="Success",
            message="Aadhar form submitted successfully"
        )


@router.post("/candidate/pan-form/", response_model=schema.candidateFormResponse)
def candidate_pan(request: schema.CandidatePanForm, db: Session = Depends(get_db), user = Depends(get_current_candidate)):
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
    # Import model here to avoid circular import
    from model import CandidatePanForm, Candidate
    
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == request.candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {request.candidate_id} not found"
        )
    
    # Check if form already exists for this candidate
    existing_form = db.query(CandidatePanForm).filter(
        CandidatePanForm.candidateID == request.candidate_id
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
        new_form = CandidatePanForm(
            candidateID=request.candidate_id,
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
        
        return schema.candidateFormResponse(
            status="Success",
            message="PAN form submitted successfully"
        )



# @router.get("candidate/candidate-form/", response_model=schema.CandidateGetResponse)
# def candidate_info(request: schema.CandidateGetRequest, db: Session = Depends(get_db)):
    


# PAN verification
# PROTEAN_USER_ID = "YOUR_USER_ID"
# PROTEAN_API_URL = "https://121.240.36.237/TIN/PanInquiryAPIBackEnd" # UAT URL
# CERTIFICATE_PATH = "path/to/your/certificate.pem"

# # --- Helper Functions ---
# def generate_transaction_id(user_id: str):
#     """Recommended format <User_ID>:timestamp"""
#     now = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
#     return f"{user_id}:{now}"

# def sign_data(data: str):
#     """
#     Apply digital signature using your certificate's private key.
#     Note: You must use a library like 'cryptography' or 'pyopenssl' 
#     to sign the 'inputData' string.
#     """
#     # Implementation depends on your certificate format (.p12, .pem, etc.)
#     return "SIGNED_HASH_STRING"

# @router.post("hr/verify-pan")
# async def verify_pan(request: schema.OnboardingRequest):
#     if len(request.records) > 5:
#         raise HTTPException(status_code=400, detail="Max 5 records allowed per call")

#     # 1. Prepare Request Data
#     transaction_id = generate_transaction_id(PROTEAN_USER_ID)
#     request_time = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S") #
    
#     # Format individual input data
#     input_data = [record.model_dump() for record in request.records]
    
#     # 2. Create the Signed Request Body
#     payload = {
#         "User_ID": PROTEAN_USER_ID,
#         "Records_count": str(len(input_data)),
#         "Request_time": request_time,
#         "Transaction_ID": transaction_id,
#         "Version": "4", # Required Version 4
#         "inputData": input_data,
#         "signature": sign_data(str(input_data)) # Sign the inputData object
#     }

#     # 3. Call Protean API
#     async with httpx.AsyncClient() as client:
#         try:
#             response = await client.post(
#                 PROTEAN_API_URL, 
#                 json=payload,
#                 headers={"Content-Type": "application/json"}
#             )
#             response.raise_for_status()
#             return response.json()
#         except httpx.HTTPError as e:
#             raise HTTPException(status_code=500, detail=f"API connection failed: {str(e)}")


# ===== Interview and Assignment Management APIs =====

@router.post("/hr/assignments/create", response_model=schema.CandidateAssignmentResponse, status_code=201)
def create_candidate_assignment(
    request: schema.CandidateAssignmentCreate, 
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
    from model import CandidateAssignment, Candidate, Users
    
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
    
    return schema.CandidateAssignmentResponse(
        id=assignment.id,
        candidate_id=assignment.candidate_id,
        hiring_manager_id=assignment.hiring_manager_id,
        reporting_manager_id=assignment.reporting_manager_id,
        created_at=assignment.created_at
    )


@router.post("/hr/interviews/create", response_model=schema.InterviewResponse, status_code=201)
def create_interview(
    request: schema.InterviewCreate, 
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
    from model import Interview, InterviewPanel, Candidate
    
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
    
    return schema.InterviewResponse(
        id=interview.id,
        panel_id=interview.panel_id,
        candidate_id=interview.candidate_id,
        start_time=interview.start_time,
        end_time=interview.end_time,
        meeting_link=interview.meeting_link,
        outlook_event_id=interview.outlook_event_id,
        status=interview.status
    )


@router.post("/hr/panel-members/assign", response_model=schema.PanelMemberResponse, status_code=201)
def assign_panel_member(
    request: schema.PanelMemberCreate, 
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
    from model import PanelMember, InterviewPanel, Users
    
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
    
    return schema.PanelMemberResponse(
        id=panel_member.id,
        panel_id=panel_member.panel_id,
        interviewer_id=panel_member.interviewer_id
    )


@router.post("/hr/interviews/feedback", response_model=schema.InterviewFeedbackResponse, status_code=201)
def submit_interview_feedback(
    request: schema.InterviewFeedbackCreate, 
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
    from model import InterviewFeedback, Interview, Users
    
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
    
    return schema.InterviewFeedbackResponse(
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


@router.get("/hr/assignments/candidates", response_model=list[schema.AssignedCandidateResponse])
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
    from model import CandidateAssignment, Candidate
    from sqlalchemy import or_
    
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
            
            results.append(schema.AssignedCandidateResponse(
                candidate_id=candidate.candidateID,
                candidate_name=candidate_name,
                candidate_email=candidate.candidateEmail,
                candidate_mobile=candidate.candidateMobile,
                assignment_type=assignment_type,
                assigned_at=assignment.created_at
            ))
    
    return results


@router.get("/hr/interviews/assigned", response_model=list[schema.AssignedInterviewResponse])
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
    from model import Interview, PanelMember, InterviewPanel, Candidate
    
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
                
                results.append(schema.AssignedInterviewResponse(
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



@router.get("/hr/users/all", response_model=schema.AllUsersResponse)
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
    from model import Users
    
    # Query all users from the Users table
    users = db.query(Users).all()
    
    # Build response
    users_data = []
    for u in users:
        users_data.append(schema.UserResponse(
            user_id=u.UserID,
            user_name=u.UserName or "",
            user_email=u.UserEmail,
            user_role=u.UserRole,
            created_at=u.CreatedAt
        ))
    
    return schema.AllUsersResponse(
        total_users=len(users_data),
        users=users_data
    )
