from datetime import datetime
import logging
from typing import Optional, Union
from functools import wraps

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

import app.schemas as schema
from app.core.database import SessionLocal, engine, check_candidate, check_user, get_db
from fastapi import Request
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

from app.core.dependencies import get_current_user, get_current_candidate, require_resource_permission
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
from app.services.linkedin_import_service import (
    import_linkedin_candidate,
    InvalidLinkedInURL,
    ApolloCandidateNotFound,
    CandidateNotOpenToWork,
    DuplicateCandidateExists
)
from app.services.apollo_integration import search_apollo_by_linkedin_url

router = APIRouter(prefix="/candidates", tags=["candidates"])


# ============================================================================
# Database Error Handling Decorator
# ============================================================================

def handle_db_errors(func):
    """
    Decorator to wrap endpoint functions and handle database errors.

    Catches any database exceptions, rolls back the session, and returns
    proper HTTP error responses with logging.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        db = None
        try:
            # Extract db from kwargs if present (for dependency injection)
            db = kwargs.get('db')
            return func(*args, **kwargs)
        except Exception as e:
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
            logger.error(f"Database error in {func.__name__}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e
    return wrapper


# ============================================================================
# Create Candidate Request/Response Models (Async via Message Queue)
# ============================================================================

class CreateCandidateRequest(BaseModel):
    """Request to create a new candidate (queued for async processing)"""
    # Accept both prefixed and unprefixed field names for compatibility
    email: Optional[str] = None
    candidate_email: Optional[str] = None
    first_name: Optional[str] = None
    candidate_first_name: Optional[str] = None
    last_name: Optional[str] = None
    candidate_last_name: Optional[str] = None
    mobile: Optional[str] = None
    candidate_mobile: Optional[str] = None
    gender: Optional[str] = None
    candidate_gender: Optional[str] = None
    current_location: Optional[str] = None
    candidate_current_location: Optional[str] = None
    source: Optional[str] = "form_submission"
    candidate_source: Optional[str] = None
    resume_data: Optional[dict] = None
    education: Optional[list] = None
    experience: Optional[list] = None
    certifications: Optional[list] = None

    class Config:
        populate_by_name = True  # Allow both field names to be used

    def get_email(self):
        return self.email or self.candidate_email

    def get_first_name(self):
        return self.first_name or self.candidate_first_name

    def get_last_name(self):
        return self.last_name or self.candidate_last_name

    def get_mobile(self):
        return self.mobile or self.candidate_mobile

    def get_gender(self):
        return self.gender or self.candidate_gender

    def get_current_location(self):
        return self.current_location or self.candidate_current_location

    def get_source(self):
        return self.candidate_source or self.source or "form_submission"


class CreateCandidateResponse(BaseModel):
    """Response for candidate creation request (returns queue info for polling)"""
    status: str
    message_id: str
    polling_endpoint: str


# ============================================================================
# Create Candidate Endpoint - CONSOLIDATED in candidates/create_queue_first.py
# ============================================================================
# NOTE: This endpoint is handled by app/api/v1/endpoints/candidates/create_queue_first.py
# which is registered FIRST in routes.py to take precedence.
# See routes.py line: router.include_router(router=create_queue_first_router)  # Must come BEFORE candidates_router


# ============================================================================
# LinkedIn Import Request/Response Models
# ============================================================================

class LinkedInImportRequest(BaseModel):
    """Import candidate from LinkedIn profile URL"""
    linkedin_url: str

class LinkedInImportResponse(BaseModel):
    """Response after LinkedIn candidate import"""
    status: str
    candidate_id: str
    email: str
    phone: str
    full_name: str
    open_to_work: bool
    linkedin_url: str
    message: str

# ============================================================================
# Get All Candidates Endpoint
# ============================================================================

@router.get(
    "",
    response_model=dict,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
)
def list_candidates(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """List all candidates (API endpoint for UI)"""
    try:
        candidates = db.query(Candidate).filter(
            Candidate.tenant_id == (getattr(current_user, 'tenant_id', 1) or 1)
        ).all()

        result = []
        for c in candidates:
            result.append({
                'id': c.candidateID,
                'candidate_email': c.candidateEmail,
                'candidate_name': f"{c.candidateFirstName} {c.candidateLastName}".strip(),
                'candidate_role': c.candidateRole,
                'candidate_source': c.candidateSource,
                'created_at': c.candidateCreatedAt.isoformat() if c.candidateCreatedAt else None,
            })
        return {"data": result, "count": len(result)}
    except Exception as e:
        logger.error(f"Error fetching candidates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Update Candidate Endpoint (PUT)
# ============================================================================

@router.put(
    "/{candidate_id}",
    response_model=dict,
    dependencies=[Depends(require_resource_permission("candidates", "can_edit"))],
)
def update_candidate_endpoint(
    candidate_id: str,
    request: schema.CandidateUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Update existing candidate with field-level audit logging.

    Args:
        candidate_id: ID of candidate to update
        request: CandidateUpdateRequest with fields to update (only non-null values processed)
        db: Database session
        current_user: Authenticated user making changes

    Returns:
        {
            'status': 'success' | 'error',
            'candidate_id': str,
            'fields_updated': List[str],
            'audit_trail': List[Dict],
            'message': str
        }
    """
    try:
        from app.services.candidate_update_service import update_candidate_safe

        # Extract fields from request (convert to dict, filter None values)
        update_fields = {
            'candidate_first_name': request.candidate_first_name,
            'candidate_last_name': request.candidate_last_name,
            'candidate_mobile': request.candidate_mobile,
            'candidate_current_location': request.candidate_current_location,
            'candidate_source': request.candidate_source,
            'candidate_experience': request.candidate_experience,
            'candidate_skills': request.candidate_skills,
            'candidate_job_title': request.candidate_job_title,
            'candidate_gender': request.candidate_gender,
            'candidate_date_of_birth': request.candidate_date_of_birth,
            'candidate_email': request.candidate_email,
        }

        # Remove None values
        update_fields = {k: v for k, v in update_fields.items() if v is not None}

        # Call update service
        result = update_candidate_safe(
            db=db,
            candidate_id=candidate_id,
            updated_by_user_id=getattr(current_user, 'UserID', None),
            updated_by_name=getattr(current_user, 'UserName', 'System'),
            **update_fields
        )

        if result['status'] == 'error':
            raise HTTPException(status_code=400, detail=result.get('error', 'Update failed'))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating candidate {candidate_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update candidate: {str(e)}")


# ============================================================================
# LinkedIn Import Endpoint
# ============================================================================

@router.post(
    "/import/linkedin",
    response_model=dict,
    dependencies=[Depends(require_resource_permission("candidate", "create"))],
)
async def import_linkedin_candidate_endpoint(
    request: LinkedInImportRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Queue LinkedIn candidate import for async processing.

    IMPORTANT: This endpoint does NOT import synchronously.
    It queues the import request and returns a polling endpoint.

    This architecture enables:
    1. Fast HTTP response (no blocking on API calls)
    2. Proper async processing via Celery
    3. Automatic retry with exponential backoff
    4. Audit trail via ChannelQueueItem
    5. Thunder integration after candidate creation

    Workflow:
    1. Validate LinkedIn URL format
    2. Queue 'import_linkedin_candidate' task
    3. Return message_id for polling

    Backend async task (import_linkedin_candidate_task) will:
    1. Parse LinkedIn URL to extract profile slug
    2. Call Apollo.io to enrich: email, phone, company, title, open_to_work status
    3. GATE: Only proceed if candidate is marked "Open to Work"
    4. Check for duplicates (email OR phone)
    5. Create real Candidate record
    6. Queue to Thunder for autonomous processing

    Args:
        request: LinkedInImportRequest with linkedin_url

    Returns:
        dict with:
        - status: 'queued'
        - message_id: UUID for polling task status
        - polling_endpoint: URL to poll for result
        - polling_interval_seconds: Recommended poll interval

    Raises:
        HTTPException 400: Invalid LinkedIn URL format
        HTTPException 500: Failed to queue task
    """
    from app.services.message_queue_service import MessageQueueService

    try:
        # Validate LinkedIn URL format first
        if not request.linkedin_url:
            raise HTTPException(
                status_code=400,
                detail="LinkedIn URL is required"
            )

        linkedin_url_lower = request.linkedin_url.lower()
        if not ('linkedin.com' in linkedin_url_lower or 'lnkd.in' in linkedin_url_lower):
            raise HTTPException(
                status_code=400,
                detail="Invalid LinkedIn URL format. Must be linkedin.com or lnkd.in"
            )

        logger.info(f"[LINKEDIN_ENDPOINT] Queueing LinkedIn import: {request.linkedin_url}")

        # Extract tenant_id from authenticated user (LinkedIn import requires auth)
        tenant_id = 1  # Default fallback
        if current_user:
            if isinstance(current_user, dict):
                tenant_id = current_user.get('tenant_id', 1)
            elif hasattr(current_user, 'tenant_id'):
                tenant_id = getattr(current_user, 'tenant_id', 1)

        # Queue the LinkedIn import as async task
        # This allows:
        # 1. Quick HTTP response (no blocking on API calls or DB operations)
        # 2. Proper async processing via Celery
        # 3. Automatic retry with exponential backoff (60s, 120s, 240s)
        # 4. Audit trail via ChannelQueueItem
        # 5. Thunder integration after candidate creation
        result = MessageQueueService.enqueue(
            task_name='import_linkedin_candidate',
            data={
                'linkedin_url': request.linkedin_url,
                'tenant_id': tenant_id  # ✅ From authenticated user
            }
        )

        if not result or result.get('status') != 'queued':
            logger.error(f"[LINKEDIN_ENDPOINT] Failed to queue: {result}")
            raise HTTPException(
                status_code=500,
                detail="Failed to queue LinkedIn import"
            )

        message_id = result.get('message_id')
        logger.info(f"[LINKEDIN_ENDPOINT] Queued successfully: {message_id}")

        return {
            "status": "queued",
            "message_id": message_id,
            "linkedin_url": request.linkedin_url,
            "polling_endpoint": f"/api/v1/tasks/{message_id}/status",
            "polling_interval_seconds": 5,
            "message": "LinkedIn import queued. Check polling_endpoint for result."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LINKEDIN_ENDPOINT] Failed to queue: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue LinkedIn import. Please try again."
        )

@router.post("/change_password", response_model=ChangePasswordResponse, dependencies=[Depends(require_resource_permission("change_password", "create"))])
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
    try:
        user.candidatePassword = get_password_hash(request.new_password)
        user.candidateTempPassword = request.new_password
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to change candidate password: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to change password: {str(e)}"
        ) from e
    
    return ChangePasswordResponse(
        status="Success",
        message="Password changed successfully"
    )

@router.get("/my-info", response_model=CandidateCompleteResponse, dependencies=[Depends(require_resource_permission("my-info", "view"))])
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

@router.post("/candidate-form/", response_model=candidateFormResponse, dependencies=[Depends(require_resource_permission("candidate-form", "create"))])
def candidate_info(request: candidateFormRequest, db: Session = Depends(get_db)):
    """Queue candidate creation (async via message queue)."""
    from app.services.message_queue_service import MessageQueueService
    from app.utils.uniq_id_generator import candidate_id_generator

    if not request.candidate_email:
        raise HTTPException(status_code=400, detail="Email is required")
    if not request.candidate_first_name:
        raise HTTPException(status_code=400, detail="First name is required")
    if not request.candidate_last_name:
        raise HTTPException(status_code=400, detail="Last name is required")
    if not request.candidate_mobile:
        raise HTTPException(status_code=400, detail="Mobile is required")

    candidate_id = candidate_id_generator()
    try:
        message_id = MessageQueueService.enqueue(
            task_name='candidate_form_submission',
            data={
                'candidate_id': candidate_id,
                'email': request.candidate_email,
                'first_name': request.candidate_first_name,
                'last_name': request.candidate_last_name,
                'mobile': request.candidate_mobile,
                'source': request.candidate_source,
                'location': request.candidate_current_location,
            }
        )
        logger.info(f"[CandidateForm] Queued submission: candidate_id={candidate_id}, message_id={message_id}")
        return candidateFormResponse(
            status="queued",
            message="Candidate submission queued for processing",
            message_id=message_id.get('message_id') if isinstance(message_id, dict) else message_id
        )
    except Exception as e:
        logger.error(f"[CandidateForm] Failed to queue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to queue candidate: {str(e)}")

@router.post("/education-form/", response_model=candidateFormResponse, dependencies=[Depends(require_resource_permission("education-form", "create"))])
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

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save education records: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

    return candidateFormResponse(
        status="Success",
        message=f"{records_created} education record(s) submitted successfully"
    )

@router.post("/experience-form/", response_model=candidateFormResponse, dependencies=[Depends(require_resource_permission("experience-form", "create"))])
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

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save experience records: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

    return candidateFormResponse(
        status="Success",
        message=f"{records_created} experience record(s) submitted successfully"
    )

@router.post("/aadhar-form/", response_model=candidateFormResponse, dependencies=[Depends(require_resource_permission("aadhar-form", "create"))])
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

        try:
            db.commit()
            db.refresh(existing_form)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update aadhar form: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e

        return candidateFormResponse(
            status="Success",
            message="Aadhar form updated successfully"
        )
    else:
        # Create new form (formID is auto-generated by database)
        try:
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
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create aadhar form: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e

        return candidateFormResponse(
            status="Success",
            message="Aadhar form submitted successfully"
        )

@router.post("/pan-form/", response_model=candidateFormResponse, dependencies=[Depends(require_resource_permission("pan-form", "create"))])
@handle_db_errors
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
@router.post("/education/add", response_model=candidateFormResponse, dependencies=[Depends(require_resource_permission("education", "create"))])
@handle_db_errors
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

@router.put("/education/{education_id}", response_model=candidateFormResponse, dependencies=[Depends(require_resource_permission("education", "update"))])
@handle_db_errors
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

@router.delete("/education/{education_id}", response_model=candidateFormResponse, dependencies=[Depends(require_resource_permission("education", "delete"))])
@handle_db_errors
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

@router.get("/education/list", dependencies=[Depends(require_resource_permission("education", "view"))])
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
@router.post("/experience/add", response_model=candidateFormResponse, dependencies=[Depends(require_resource_permission("experience", "create"))])
@handle_db_errors
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

@router.put("/experience/{experience_id}", response_model=candidateFormResponse, dependencies=[Depends(require_resource_permission("experience", "update"))])
@handle_db_errors
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

@router.delete("/experience/{experience_id}", response_model=candidateFormResponse, dependencies=[Depends(require_resource_permission("experience", "delete"))])
@handle_db_errors
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

@router.get("/experience/list", dependencies=[Depends(require_resource_permission("experience", "view"))])
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
@router.get("/personal-info", response_model=CandidateInfoResponse, dependencies=[Depends(require_resource_permission("personal-info", "view"))])
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

@router.get("/aadhar", response_model=CandidateAadharResponse, dependencies=[Depends(require_resource_permission("aadhar", "view"))])
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

@router.get("/pan", response_model=CandidatePanResponse, dependencies=[Depends(require_resource_permission("pan", "view"))])
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
@router.get("/onboarding-status", dependencies=[Depends(require_resource_permission("onboarding-statu", "view"))])
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


# ============================================================================
# RECRUITER ASSIGNMENT - Enable recruiter ownership tracking for authorization
# ============================================================================

class AssignRecruiterRequest(BaseModel):
    """Request to assign a recruiter to a candidate"""
    recruiter_id: str = Field(..., description="User ID of recruiter to assign")


@router.post(
    "/{candidate_id}/assign-recruiter",
    dependencies=[Depends(require_resource_permission("candidate.recruiter_assignment", "create"))]
)
def assign_recruiter_to_candidate(
    candidate_id: str,
    request: AssignRecruiterRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    """
    RECRUITER AUTHORIZATION: Assign a recruiter to a candidate.

    Authorization: Only managers or admins can assign (not recruiters themselves).
    This enables ownership-based authorization for escalations and bulk operations.

    Effects:
    - Sets candidate.assigned_recruiter_id
    - Only assigned recruiter (or manager/admin) can escalate Flash/SLM conflicts
    - Prevents recruiters from stealing each other's candidates
    """
    try:
        tenant_id = getattr(current_user, 'tenant_id', 1) or 1

        # Verify recruiter authorization
        from app.core.dependencies import PermissionHelper, require_resource_permission

        can_assign = (
            PermissionHelper.has_permission(
                current_user.UserID, "recruiter.management", db, tenant_id
            ) or
            PermissionHelper.is_super_admin(current_user.UserID, db, tenant_id)
        )

        if not can_assign:
            logger.warning(
                f"[RecruiterAssignment] SECURITY: {current_user.UserID} attempted unauthorized recruiter assignment"
            )
            raise HTTPException(status_code=403, detail="Only managers can assign recruiters")

        # Verify candidate exists and belongs to tenant
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id,
            Candidate.tenant_id == tenant_id
        ).first()

        if not candidate:
            raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")

        # Verify recruiter exists and belongs to tenant
        from app.models.user import Users
        recruiter = db.query(Users).filter(
            Users.UserID == request.recruiter_id,
            Users.tenant_id == tenant_id
        ).first()

        if not recruiter:
            raise HTTPException(status_code=404, detail="Recruiter not found")

        # BU ISOLATION FIX: Verify recruiter's BU matches candidate's BU
        recruiter_bu = getattr(recruiter, 'business_unit_id', None)
        candidate_bu = getattr(candidate, 'associated_bu_id', None)

        if candidate_bu and recruiter_bu and candidate_bu != recruiter_bu:
            logger.warning(
                f"[RecruiterAssignment] SECURITY: Recruiter {recruiter.UserID} from BU {recruiter_bu} "
                f"attempted to assign candidate from BU {candidate_bu}"
            )
            raise HTTPException(status_code=403, detail="Recruiter cannot assign candidate from different BU")

        # SECURITY: Prevent recruiters from self-assigning (prevent candidate stealing)
        if recruiter.UserID == current_user.UserID:
            raise HTTPException(status_code=400, detail="Cannot assign to yourself")

        # Log the assignment change for audit trail
        old_recruiter = candidate.assigned_recruiter_id
        candidate.assigned_recruiter_id = recruiter.UserID
        candidate.assigned_recruiter_changed_at = datetime.utcnow()
        candidate.assigned_recruiter_changed_by = current_user.UserID

        db.add(candidate)
        db.commit()

        logger.info(
            f"[RecruiterAssignment] ✅ Assigned {candidate_id} from {old_recruiter} to {recruiter.UserID} "
            f"by {current_user.UserID}"
        )

        return {
            "candidate_id": candidate_id,
            "assigned_recruiter_id": recruiter.UserID,
            "assigned_recruiter_name": f"{recruiter.FirstName} {recruiter.LastName}",
            "previous_recruiter_id": old_recruiter,
            "assigned_at": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[RecruiterAssignment] Failed to assign recruiter: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to assign recruiter: {str(e)}")

