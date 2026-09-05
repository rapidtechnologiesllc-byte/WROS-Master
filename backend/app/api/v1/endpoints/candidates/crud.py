from datetime import datetime
import logging
import uuid
from typing import Optional, List
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
import time

import app.schemas as schema
from app.core.database import get_db
from app.core.logging import logger
from app.services.message_queue_service import MessageQueueService
from app.services.ai_conversation_service import run_auto_assign_ai_agent_in_background
from app.services.candidate_service import (
    create_candidate_safe,
    DuplicateCandidateError,
    parse_experience_to_months,
)
from app.services.guidewire_candidate_service import is_guidewire_candidate
from app.core.bu_scope import apply_bu_scope_to_candidate_query, get_candidate_by_id_with_bu_scope

# ============================================
# Constants for candidate pipeline
# ============================================
CANDIDATE_STATUS_APPLIED = "Applied"
CANDIDATE_STATUS_ACTIVE = "Active"
CANDIDATE_STATUS_EMPLOYEE = "EMPLOYEE"
CANDIDATE_STATUS_OFFER = "OFFER"
CANDIDATE_PIPELINE_STATUS_EMPLOYEE = "EMPLOYEE"
CANDIDATE_PIPELINE_STATUS_OFFER = "OFFER"
from app.models.candidate import (
    Candidate,
    CandidateInfoForm,
    CandidateEducationForm,
    CandidateExperienceForm,
    CandidateAadharForm,
    CandidatePanForm,
    CandidateStatus,
)
from app.models.user import Users, Jobs, Interview, CandidateAssignment, InterviewPanel, PanelMember, InterviewFeedback
from app.models.document import CandidateDocument
from app.models.checklist import CandidateChecklist, CandidateChecklistItem
from app.models.candidate_history import CandidateHistory
from app.models.candidate_ai import CandidateConversation, CandidateAIAssignment, ConversationEvent
from app.models.offer_letter import OfferLetter
from app.models.internal_note import InternalNote
from app.models.ats import ATSScore
from app.models.hr_assignment import HRAssignment
from app.models.candidate_ownership import CandidateOwnership

from app.core.dependencies import get_current_hr_or_admin, get_current_candidate, require_resource_permission

from app.schemas.candidate import (CandidateCreateRequest,
CandidateCreateResponse, CandidateCompleteResponse,
CandidateEducationResponse, CandidateExperienceResponse,
CandidateInfoResponse, CandidatePanResponse,
CandidateAadharResponse, DeleteResponse,
AllCandidatesResponse)
from app.schemas.user import CandidateUpdateRequest

from app.utils.uniq_id_generator import generate_password

router = APIRouter(prefix="/candidates", tags=["candidates"])

# ============================================
# Validation Helpers
# ============================================

def _is_valid_email(email: str) -> bool:
    """Validate email format."""
    if not email or not isinstance(email, str):
        return False
    pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    return bool(re.match(pattern, email.strip()))

def _is_valid_phone(phone: str) -> bool:
    """Validate phone format (basic: digits, spaces, dashes, +, parentheses)."""
    if not phone or not isinstance(phone, str):
        return False
    pattern = r'^[\d\s\-\+\(\)]{7,}$'  # At least 7 characters of phone number format
    return bool(re.match(pattern, phone.strip()))

def _serialize_skills(skills) -> Optional[str]:
    """Convert skills list to comma-separated string with error handling."""
    if not skills:
        return None
    try:
        if isinstance(skills, list):
            return ", ".join(filter(None, [str(s).strip() for s in skills])) or None
        if isinstance(skills, str):
            return skills.strip() or None
        return None
    except Exception as e:
        logger.warning(f"Failed to serialize skills: {e}")
        return None

def _build_candidate_response(
    candidate,
    candidate_status=None,
    personal_info=None,
    education_records=None,
    experience_records=None,
    aadhar_form=None,
    pan_form=None,
    is_guidewire=False,
    serialize_skills=True
):
    """Helper function to build CandidateCompleteResponse (DRY pattern)."""
    name_parts = [
        candidate.candidateFirstName or "",
        candidate.candidateMiddleName or "",
        candidate.candidateLastName or ""
    ]
    candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"

    # Safely serialize skills
    skills_str = _serialize_skills(candidate.candidateSkills) if serialize_skills else candidate.candidateSkills

    return CandidateCompleteResponse(
        candidate_id=candidate.candidateID,
        candidate_name=candidate_name,
        candidate_first_name=candidate.candidateFirstName,
        candidate_middle_name=candidate.candidateMiddleName,
        candidate_last_name=candidate.candidateLastName,
        candidate_email=candidate.candidateEmail,
        candidate_mobile=candidate.candidateMobile,
        candidate_role=getattr(candidate, 'candidateRole', None),
        candidate_job_title=candidate.candidateJobTitle,
        candidate_is_verified=getattr(candidate, 'candidateIsVerified', False),
        candidate_created_at=getattr(candidate, 'candidateCreatedAt', None),
        candidate_gender=getattr(candidate, 'candidateGender', None),
        candidate_date_of_birth=getattr(candidate, 'candidateDateOfBirth', None),
        candidate_source=getattr(candidate, 'candidateSource', None),
        candidate_experience=candidate.candidateExperience,
        candidate_skills=skills_str,
        candidate_joining_date=getattr(candidate, 'candidateJoiningDate', None),
        candidate_current_location=candidate.candidateCurrentLocation,
        candidate_current_salary=getattr(candidate, 'candidateCurrentSalary', None),
        candidate_expected_salary=getattr(candidate, 'candidateExpectedSalary', None),
        candidate_employee_type=getattr(candidate, 'candidateEmployeeType', None),
        is_guidewire_candidate=is_guidewire,
        job_id=getattr(candidate, 'job_id', None),
        personal_info=CandidateInfoResponse(
            position=personal_info.position if personal_info else None,
            department=personal_info.department if personal_info else None,
            dob=personal_info.dob if personal_info else None,
            gender=personal_info.gender if personal_info else None,
            marital_status=getattr(personal_info, 'marital_status', None) if personal_info else None,
            nationality=getattr(personal_info, 'nationality', None) if personal_info else None,
            current_address=getattr(personal_info, 'current_address', None) if personal_info else None,
            permanent_address=getattr(personal_info, 'permanent_address', None) if personal_info else None,
            submitted_at=personal_info.submittedAt if personal_info else None,
        ) if personal_info else None,
        education=[
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
            ) for edu in (education_records or [])
        ],
        experience=[
            CandidateExperienceResponse(
                formID=exp.formID,
                company_name=exp.company_name,
                job_title=exp.job_title,
                start_date=exp.start_date,
                end_date=exp.end_date,
                year_of_experience=exp.year_of_experience,
                document_is_submitted=exp.document_is_submitted,
                document_id=exp.document_id
            ) for exp in (experience_records or [])
        ],
        aadhar=CandidateAadharResponse(
            formID=aadhar_form.formID if aadhar_form else None,
            aadhar=aadhar_form.aadhar if aadhar_form else None,
            name_in_aadhar=aadhar_form.name_in_aadhar if aadhar_form else None,
            enrollment_number=getattr(aadhar_form, 'enrollment_number', None) if aadhar_form else None,
            aadhar_is_submitted=aadhar_form.aadhar_is_submitted if aadhar_form else None,
            is_verified=aadhar_form.is_verified if aadhar_form else None,
            document_id=aadhar_form.document_id if aadhar_form else None
        ) if aadhar_form else None,
        pan=CandidatePanResponse(
            formID=pan_form.formID if pan_form else None,
            pan=pan_form.pan if pan_form else None,
            name_in_pan=pan_form.name_in_pan if pan_form else None,
            father_name_in_pan=getattr(pan_form, 'father_name_in_pan', None) if pan_form else None,
            pan_is_submitted=pan_form.pan_is_submitted if pan_form else None,
            is_verified=pan_form.is_verified if pan_form else None,
            document_id=pan_form.document_id if pan_form else None
        ) if pan_form else None,
        status=candidate_status.status if candidate_status else None,
        pipline_status=candidate_status.piplineStatus if candidate_status else None
    )

@router.post(
    "/create",
    response_model=CandidateCreateResponse,
    dependencies=[Depends(require_resource_permission("candidates", "create"))],
)
def create_candidate(
    request: CandidateCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin),
):
    """
    Create a new candidate account with comprehensive information.

    Args:
        request: CandidateCreateRequest containing candidate details including:
                - Required: email, location (City, State, Country format)
                - Optional: name fields, contact info, professional details, salary info
        db: Database session

    Returns:
        CandidateCreateResponse with candidate_id, is_first_time flag, and generated password

    Raises:
        HTTPException: If candidate with email already exists, or location not provided
    """
    # Validate location is provided (required for candidate search)
    if not request.candidate_current_location or not request.candidate_current_location.strip():
        raise HTTPException(
            status_code=400,
            detail="Location (City, State, Country) is mandatory for candidate creation"
        )

    # R-07: createCandidateSafe() is the only sanctioned creation path --
    # runs email/phone/LinkedIn dedup (each independently) before any insert.
    password = generate_password()
    try:
        candidate = create_candidate_safe(
            db,
            email=request.candidate_email,
            mobile=request.candidate_mobile,
            plain_password=password,
            tenant_id=user.tenant_id,
            candidateRole=request.candidate_role,
            candidateEmployeeType=request.candidate_employee_type,
            candidateJobTitle=request.candidate_job_title,
            candidateFirstName=request.candidate_first_name,
            candidateMiddleName=request.candidate_middle_name,
            candidateLastName=request.candidate_last_name,
            candidateGender=request.candidate_gender,
            candidateDateOfBirth=request.candidate_date_of_birth,
            candidateSource=request.candidate_source,
            candidateExperience=request.candidate_experience,
            # R-01 (HRMS-P601): interim substitute for HRMS-0428's
            # not-yet-built resume parsing -- see candidate_service.py.
            total_experience_months=parse_experience_to_months(request.candidate_experience),
            candidateSkills=request.candidate_skills,
            candidateJoiningDate=request.candidate_joining_date,
            candidateExpectedSalary=request.candidate_expected_salary,
            candidateCurrentSalary=request.candidate_current_salary,
            candidateCurrentLocation=request.candidate_current_location,
            candidateCreatedAt=datetime.now(),
        )
    except DuplicateCandidateError:
        raise HTTPException(
            status_code=400,
            detail=f"Account already exists with email {request.candidate_email}"
        )

    # R-01 (HRMS-P601): REMOVED as a creation-time block, 2026-07-23 --
    # direct instruction from Avinash: "we should still gather all
    # resumes not stop building our DB." A candidate below the 5-year
    # floor (or not yet experience-verified) is now created exactly like
    # any other candidate; total_experience_months above is still
    # computed and stored so the rule can be enforced for real at the
    # point it actually matters -- submission/matching to a role
    # requiring 5+ years -- via
    # app.services.submission_service.check_experience_eligibility(),
    # unaffected by this change.
    candidate_id = candidate.candidateID

    # Must commit before creating related records to ensure candidate exists
    try:
        db.commit()
        db.refresh(candidate)
    except Exception as e:
        logger.error(f"Failed to commit candidate {candidate_id}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create candidate: {str(e)}")

    # Create candidate status
    # TIER 3 FIX: Use constants instead of magic strings
    candidate_status = CandidateStatus(
        candidateID=candidate_id,
        piplineStatus=CANDIDATE_STATUS_APPLIED,
        status=CANDIDATE_STATUS_ACTIVE,
        createdAt=datetime.now(),
        updatedAt=datetime.now(),
    )
    # Ensure this is a new record (not re-running)
    existing_status = db.query(CandidateStatus).filter(CandidateStatus.candidateID == candidate_id).first()
    if existing_status:
        logger.warning(f"Candidate status already exists for {candidate_id}, updating instead")
        existing_status.status = "Active"
        existing_status.updatedAt = datetime.now()
    else:
        db.add(candidate_status)

    # Create candidate personal info form
    # TIER 1 FIX: Check if CandidateInfoForm already exists before adding
    existing_info = db.query(CandidateInfoForm).filter(CandidateInfoForm.candidateID == candidate_id).first()
    if not existing_info:
        candidate_info = CandidateInfoForm(
            candidateID=candidate_id,
            dob=request.candidate_date_of_birth,
            gender=request.candidate_gender,
            submittedAt=datetime.now().date(),
        )
        db.add(candidate_info)
    else:
        logger.warning(f"Candidate info already exists for {candidate_id}, skipping creation")

    # CRITICAL: Must commit status before queuing background tasks.
    # Background tasks run in a fresh session and need to find BOTH
    # the candidate AND its status record. Without this commit,
    # background tasks see incomplete data or 404 candidate not found.
    try:
        db.commit()
    except Exception as e:
        logger.error(f"Failed to commit candidate status {candidate_id}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create candidate status")

    # Bulk-insert education records if provided
    if request.education_records:
        for edu in request.education_records:
            try:
                # Check if this education record already exists (idempotency)
                existing_edu = db.query(CandidateEducationForm).filter(
                    CandidateEducationForm.candidateID == candidate_id,
                    CandidateEducationForm.education_institute == edu.education_institute,
                    CandidateEducationForm.degree == edu.degree,
                ).first()
                if not existing_edu:
                    # Safe to add: verified record doesn't exist above
                    edu_row = CandidateEducationForm(
                        candidateID=candidate_id,
                        education_institute=edu.education_institute,
                        degree=edu.degree,
                        field_of_study=edu.field_of_study,
                        starting_year=edu.starting_year,
                        year_of_passing=edu.year_of_passing,
                        percentage=edu.percentage,
                        submittedAt=edu.submitted_at,
                        document_is_submitted=edu.document_is_submitted,
                        document_id=edu.document_id,
                    )
                    assert not existing_edu, "Education record unexpectedly exists"
                    db.add(edu_row)
                else:
                    logger.debug(f"Education record already exists for {candidate_id}: {edu.degree}")
            except Exception as e:
                logger.error(f"Failed to add education record for {candidate_id}: {str(e)}", exc_info=True)
                raise

    # Bulk-insert experience records if provided
    if request.experience_records:
        for exp in request.experience_records:
            try:
                # Check if this experience record already exists (idempotency)
                existing_exp = db.query(CandidateExperienceForm).filter(
                    CandidateExperienceForm.candidateID == candidate_id,
                    CandidateExperienceForm.company_name == exp.company_name,
                    CandidateExperienceForm.job_title == exp.job_title,
                ).first()
                if not existing_exp:
                    exp_row = CandidateExperienceForm(
                        candidateID=candidate_id,
                        company_name=exp.company_name,
                        job_title=exp.job_title,
                        start_date=exp.start_date,
                        end_date=exp.end_date,
                        year_of_experience=exp.year_of_experience,
                        submittedAt=exp.submitted_at,
                        document_is_submitted=exp.document_is_submitted,
                        document_id=exp.document_id,
                    )
                    db.add(exp_row)
                else:
                    logger.debug(f"Experience record already exists for {candidate_id}: {exp.job_title}")
            except Exception as e:
                logger.error(f"Failed to add experience record for {candidate_id}: {str(e)}", exc_info=True)
                raise

    if request.education_records or request.experience_records:
        try:
            db.commit()
        except Exception as e:
            logger.error(f"Failed to commit education/experience for {candidate_id}: {str(e)}", exc_info=True)
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to save candidate details")

    # HRMS-0401: Thunder auto-assignment on candidate creation.
    # 2026-08-12 real bug fix -- Avinash: "when i add a candidate there
    # is no work done by flash neither any notification is showing up."
    # This used to call assign_ai_agent() inline with a hardcoded
    # tenant_id="1" that never matched what /activity-feed (and every
    # other real reader) resolves via resolve_default_tenant_id() --
    # the assignment silently succeeded but was invisible everywhere.
    # It also wrote a ConversationEvent(conversation_id=None, ...) that
    # violated a NOT NULL constraint on every single call, logged as an
    # Queue candidate for Thunder autonomous intake via Celery (async, non-blocking)
    try:
        result = MessageQueueService.enqueue(
            message_type='process_candidate',
            payload={
                'candidate_id': candidate_id,
                'candidate_email': candidate.candidateEmail,
                'tenant_id': user.tenant_id
            },
            resource_id=candidate_id,
            queue_type='THUNDER_QUEUE',
            created_by=user.UserID,
            db=db
        )

        if not result or result.get('status') != 'queued':
            logger.error(f"Failed to queue candidate {candidate_id}: {result}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to queue candidate for processing")
    except Exception as e:
        logger.error(f"Error queuing candidate {candidate_id}: {str(e)}", exc_info=True)
        # Don't fail the creation - candidate is already in DB
        # Task queue failure shouldn't block candidate creation
        # (Though in production, this should trigger an alert)

    # Return plain password so it can be sent to the candidate
    # Task has been queued; candidate will be processed asynchronously
    return CandidateCreateResponse(
        candidate_id=candidate_id,
        candidate_is_first_time=True,
        candidate_password=password  # Return plain password
    )

@router.get(
    "/all",
    response_model=AllCandidatesResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))]
)
async def get_all_candidates(db: Session = Depends(get_db), user = Depends(get_current_hr_or_admin)):
    """
    Get all candidates with their complete information for HR/Admin.

    Returns:
        AllCandidatesResponse with list of all candidates and their forms
    """
    # HRMS-0109 -- scoped to the caller's own tenant, never all tenants'
    # candidates. See app.core.tenant_context; fails closed (403) if
    # `user` has no tenant assigned rather than silently showing everyone's.
    # Backlog item, 2026-08-05: on top of tenant scoping, a bu_restricted
    # role (e.g. HR Manager) is further scoped to Org Pool candidates
    # plus their own Business Unit's -- see app.core.bu_scope's module
    # docstring for why this endpoint specifically needed the fix
    # (a correctly-scoped sibling endpoint already existed but no
    # frontend screen ever called it).
    candidates = apply_bu_scope_to_candidate_query(
        db, db.query(Candidate), current_user=user,
    ).all()

    if not candidates:
        return AllCandidatesResponse(total_candidates=0, candidates=[])

    candidate_ids = [c.candidateID for c in candidates]

    # TIER 2 FIX: Batch load all related data to prevent N+1 queries
    # Pre-load all related data in batch queries instead of per-candidate queries
    personal_infos = {
        row.candidateID: row
        for row in db.query(CandidateInfoForm).filter(
            CandidateInfoForm.candidateID.in_(candidate_ids)
        ).all()
    }

    education_records_map = {}
    for edu in db.query(CandidateEducationForm).filter(
        CandidateEducationForm.candidateID.in_(candidate_ids)
    ).all():
        if edu.candidateID not in education_records_map:
            education_records_map[edu.candidateID] = []
        education_records_map[edu.candidateID].append(edu)

    experience_records_map = {}
    for exp in db.query(CandidateExperienceForm).filter(
        CandidateExperienceForm.candidateID.in_(candidate_ids)
    ).all():
        if exp.candidateID not in experience_records_map:
            experience_records_map[exp.candidateID] = []
        experience_records_map[exp.candidateID].append(exp)

    aadhar_forms = {
        row.candidateID: row
        for row in db.query(CandidateAadharForm).filter(
            CandidateAadharForm.candidateID.in_(candidate_ids)
        ).all()
    }

    pan_forms = {
        row.candidateID: row
        for row in db.query(CandidatePanForm).filter(
            CandidatePanForm.candidateID.in_(candidate_ids)
        ).all()
    }

    candidate_statuses = {
        row.candidateID: row
        for row in db.query(CandidateStatus).filter(
            CandidateStatus.candidateID.in_(candidate_ids)
        ).all()
    }

    candidates_data = []
    for candidate in candidates:
        try:
            # TIER 2 FIX: Use pre-loaded data instead of N+1 queries
            personal_info = personal_infos.get(candidate.candidateID)
            education_records = education_records_map.get(candidate.candidateID, [])
            experience_records = experience_records_map.get(candidate.candidateID, [])
            aadhar_form = aadhar_forms.get(candidate.candidateID)
            pan_form = pan_forms.get(candidate.candidateID)
            candidate_status = candidate_statuses.get(candidate.candidateID)

            # Guidewire check: can still be called per-candidate if necessary
            # (this is acceptable as it's a specialized check, not a standard join)
            is_guidewire = is_guidewire_candidate(db, candidate)

            # Use helper function to build response (DRY pattern)
            candidate_response = _build_candidate_response(
                candidate,
                candidate_status=candidate_status,
                personal_info=personal_info,
                education_records=education_records,
                experience_records=experience_records,
                aadhar_form=aadhar_form,
                pan_form=pan_form,
                is_guidewire=is_guidewire,
                serialize_skills=True
            )

            candidates_data.append(candidate_response)
        except Exception as e:
            logger.error(f"Error building candidate response for {candidate.candidateID}: {str(e)}", exc_info=True)
            # Continue processing other candidates instead of failing entire request
            continue

    return AllCandidatesResponse(
        total_candidates=len(candidates_data),
        candidates=candidates_data
    )

@router.get(
    "/{candidate_id}",
    response_model=CandidateCompleteResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
)
def get_candidate_by_id(
    candidate_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Get full details of a single candidate by candidate ID.

    Returns all profile data including personal info form, education,
    experience, Aadhar, and PAN records.

    BU scoping only applies AFTER a candidate is submitted to a job
    (gains a CandidateOwnership record). Newly created candidates are
    in the Org Pool by default and visible to all HR users. A
    bu_restricted role (HR Manager) can only reach BU-owned candidates
    AFTER they've been submitted to a job in that BU.

    Raises:
        HTTPException 404: If no candidate with the given ID exists, or
        the candidate has been submitted to a job outside the caller's
        Business Unit and the caller is bu_restricted.
    """
    # Safely fetch candidate with proper BU scoping logic:
    # - Org Pool (no job submission yet): visible to all HR users
    # - Job-submitted: respect BU ownership if user is bu_restricted
    candidate = get_candidate_by_id_with_bu_scope(db, candidate_id, user)
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID '{candidate_id}' not found"
        )

    # Construct display name
    name_parts = [
        candidate.candidateFirstName or "",
        candidate.candidateMiddleName or "",
        candidate.candidateLastName or "",
    ]
    candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"

    personal_info = db.query(CandidateInfoForm).filter(
        CandidateInfoForm.candidateID == candidate_id
    ).first()

    education_records = db.query(CandidateEducationForm).filter(
        CandidateEducationForm.candidateID == candidate_id
    ).all()

    experience_records = db.query(CandidateExperienceForm).filter(
        CandidateExperienceForm.candidateID == candidate_id
    ).all()

    aadhar_form = db.query(CandidateAadharForm).filter(
        CandidateAadharForm.candidateID == candidate_id
    ).first()

    pan_form = db.query(CandidatePanForm).filter(
        CandidatePanForm.candidateID == candidate_id
    ).first()

    # Get candidate status
    candidate_status = db.query(CandidateStatus).filter(
        CandidateStatus.candidateID == candidate_id
    ).first()

    # TIER 2 FIX: Use helper function to eliminate code duplication
    is_guidewire = is_guidewire_candidate(db, candidate)

    return _build_candidate_response(
        candidate,
        candidate_status=candidate_status,
        personal_info=personal_info,
        education_records=education_records,
        experience_records=experience_records,
        aadhar_form=aadhar_form,
        pan_form=pan_form,
        is_guidewire=is_guidewire,
        serialize_skills=True
    )

@router.get(
    "/hr/my-bu/candidates",
    response_model=AllCandidatesResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get all candidates owned by the calling user's Business Unit",
)
def get_candidates_by_my_bu(
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
    include_org_pool: bool = Query(
        default=False,
        description="If true, also include Org Pool candidates (not BU-owned) in the result",
    ),
    pipeline_status: Optional[str] = Query(
        default=None,
        description="Filter by pipeline status (e.g. 'Applied', 'Interview', 'Offered')",
    ),
):
    """
    Returns all candidates that are currently **owned by the calling user's
    Business Unit** (pool_status = 'BU Owned').

    - The BU is determined automatically from the logged-in user's
      `business_unit_id` --" no parameter needed.
    - Use `include_org_pool=true` to also fetch unassigned Org Pool candidates
      (useful for BU managers who want to pick new candidates).
    - Optionally filter by `pipeline_status`.

    **Requires:** `candidate.view` permission.
    """
    from app.models.candidate_ownership import CandidateOwnership, POOL_BU, POOL_ORG

    # â"€â"€ Resolve the calling user's BU â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    calling_user = db.query(Users).filter(Users.UserID == user.UserID).first()
    bu_id = calling_user.business_unit_id if calling_user else None

    if not bu_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Your account is not assigned to any Business Unit. "
                "Ask an Admin to set your BU before using this endpoint."
            ),
        )

    # â"€â"€ Find candidate IDs that belong to this BU â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    ownership_query = db.query(CandidateOwnership).filter(
        CandidateOwnership.owned_by_bu_id == bu_id,
        CandidateOwnership.pool_status == POOL_BU,
    )
    bu_candidate_ids = {row.candidateID for row in ownership_query.all()}

    # â"€â"€ Optionally include Org Pool candidates â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    if include_org_pool:
        owned_ids = {row.candidateID for row in db.query(CandidateOwnership).all()}
        all_candidate_ids = db.query(Candidate.candidateID).all()
        org_pool_ids = {row.candidateID for row in all_candidate_ids} - owned_ids
        # also include candidates whose ownership row says "Org Pool"
        org_pool_rows = db.query(CandidateOwnership).filter(
            CandidateOwnership.pool_status == POOL_ORG
        ).all()
        org_pool_ids.update(row.candidateID for row in org_pool_rows)
        bu_candidate_ids.update(org_pool_ids)

    if not bu_candidate_ids:
        return AllCandidatesResponse(total_candidates=0, candidates=[])

    # â"€â"€ Fetch candidate rows â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    candidate_query = db.query(Candidate).filter(
        Candidate.candidateID.in_(bu_candidate_ids)
    )

    # Optional pipeline_status filter (via CandidateStatus join)
    if pipeline_status:
        candidate_query = candidate_query.join(
            CandidateStatus,
            CandidateStatus.candidateID == Candidate.candidateID,
            isouter=True,
        ).filter(CandidateStatus.piplineStatus == pipeline_status)

    candidates = candidate_query.all()

    # â"€â"€ Build full response (reusing exact same pattern as get_all_candidates) â"€
    candidates_data = []
    for candidate in candidates:
        name_parts = [
            candidate.candidateFirstName or "",
            candidate.candidateMiddleName or "",
            candidate.candidateLastName or "",
        ]
        candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"

        personal_info = db.query(CandidateInfoForm).filter(
            CandidateInfoForm.candidateID == candidate.candidateID
        ).first()
        education_records = db.query(CandidateEducationForm).filter(
            CandidateEducationForm.candidateID == candidate.candidateID
        ).all()
        experience_records = db.query(CandidateExperienceForm).filter(
            CandidateExperienceForm.candidateID == candidate.candidateID
        ).all()
        aadhar_form = db.query(CandidateAadharForm).filter(
            CandidateAadharForm.candidateID == candidate.candidateID
        ).first()
        pan_form = db.query(CandidatePanForm).filter(
            CandidatePanForm.candidateID == candidate.candidateID
        ).first()
        candidate_status = db.query(CandidateStatus).filter(
            CandidateStatus.candidateID == candidate.candidateID
        ).first()

        candidates_data.append(CandidateCompleteResponse(
            candidate_id=candidate.candidateID,
            candidate_name=candidate_name,
            candidate_first_name=candidate.candidateFirstName,
            candidate_middle_name=candidate.candidateMiddleName,
            candidate_last_name=candidate.candidateLastName,
            candidate_email=candidate.candidateEmail,
            candidate_mobile=candidate.candidateMobile,
            candidate_role=candidate.candidateRole,
            candidate_job_title=candidate.candidateJobTitle,
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
            candidate_employee_type=candidate.candidateEmployeeType,
            is_guidewire_candidate=is_guidewire_candidate(db, candidate),
            job_id=candidate.job_id,
            personal_info=CandidateInfoResponse(
                position=personal_info.position if personal_info else None,
                department=personal_info.department if personal_info else None,
                dob=personal_info.dob if personal_info else None,
                gender=personal_info.gender if personal_info else None,
                marital_status=personal_info.marital_status if personal_info else None,
                nationality=personal_info.nationality if personal_info else None,
                current_address=personal_info.current_address if personal_info else None,
                permanent_address=personal_info.permanent_address if personal_info else None,
                submitted_at=personal_info.submittedAt if personal_info else None,
            ) if personal_info else None,
            education=[
                CandidateEducationResponse(
                    formID=edu.formID,
                    education_institute=edu.education_institute,
                    degree=edu.degree,
                    field_of_study=edu.field_of_study,
                    starting_year=edu.starting_year,
                    year_of_passing=edu.year_of_passing,
                    percentage=edu.percentage,
                    document_is_submitted=edu.document_is_submitted,
                    document_id=edu.document_id,
                ) for edu in education_records
            ],
            experience=[
                CandidateExperienceResponse(
                    formID=exp.formID,
                    company_name=exp.company_name,
                    job_title=exp.job_title,
                    start_date=exp.start_date,
                    end_date=exp.end_date,
                    year_of_experience=exp.year_of_experience,
                    document_is_submitted=exp.document_is_submitted,
                    document_id=exp.document_id,
                ) for exp in experience_records
            ],
            aadhar=CandidateAadharResponse(
                formID=aadhar_form.formID if aadhar_form else None,
                aadhar=aadhar_form.aadhar if aadhar_form else None,
                name_in_aadhar=aadhar_form.name_in_aadhar if aadhar_form else None,
                enrollment_number=aadhar_form.enrollment_number if aadhar_form else None,
                aadhar_is_submitted=aadhar_form.aadhar_is_submitted if aadhar_form else None,
                is_verified=aadhar_form.is_verified if aadhar_form else None,
                document_id=aadhar_form.document_id if aadhar_form else None,
            ) if aadhar_form else None,
            pan=CandidatePanResponse(
                formID=pan_form.formID if pan_form else None,
                pan=pan_form.pan if pan_form else None,
                name_in_pan=pan_form.name_in_pan if pan_form else None,
                father_name_in_pan=pan_form.father_name_in_pan if pan_form else None,
                pan_is_submitted=pan_form.pan_is_submitted if pan_form else None,
                is_verified=pan_form.is_verified if pan_form else None,
                document_id=pan_form.document_id if pan_form else None,
            ) if pan_form else None,
            status=candidate_status.status if candidate_status else None,
            pipline_status=candidate_status.piplineStatus if candidate_status else None,
        ))

    return AllCandidatesResponse(
        total_candidates=len(candidates_data),
        candidates=candidates_data,
    )

@router.put(
    "/hr/update_candidate/{candidate_id}",
    response_model=CandidateCompleteResponse,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
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
        HTTPException: If candidate not found or user lacks permission to update
    """
    # Use safe candidate fetch with proper BU scoping
    candidate = get_candidate_by_id_with_bu_scope(db, candidate_id, user)
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {candidate_id} not found"
        )
    
    # Store original values for SLM correction tracking
    corrections = {}

    # Update only provided fields and track corrections
    if request.candidate_first_name is not None:
        old_val = candidate.candidateFirstName
        candidate.candidateFirstName = request.candidate_first_name
        if old_val != request.candidate_first_name:
            corrections['candidate_first_name'] = (old_val, request.candidate_first_name)

    if request.candidate_middle_name is not None:
        old_val = candidate.candidateMiddleName
        candidate.candidateMiddleName = request.candidate_middle_name
        if old_val != request.candidate_middle_name:
            corrections['candidate_middle_name'] = (old_val, request.candidate_middle_name)

    if request.candidate_last_name is not None:
        old_val = candidate.candidateLastName
        candidate.candidateLastName = request.candidate_last_name
        if old_val != request.candidate_last_name:
            corrections['candidate_last_name'] = (old_val, request.candidate_last_name)

    if request.candidate_mobile is not None:
        old_val = candidate.candidateMobile
        candidate.candidateMobile = request.candidate_mobile
        if old_val != request.candidate_mobile:
            corrections['candidate_mobile'] = (old_val, request.candidate_mobile)

    if request.candidate_gender is not None:
        old_val = candidate.candidateGender
        candidate.candidateGender = request.candidate_gender
        if old_val != request.candidate_gender:
            corrections['candidate_gender'] = (old_val, request.candidate_gender)

    if request.candidate_date_of_birth is not None:
        old_val = candidate.candidateDateOfBirth
        candidate.candidateDateOfBirth = request.candidate_date_of_birth
        if old_val != request.candidate_date_of_birth:
            corrections['candidate_date_of_birth'] = (old_val, request.candidate_date_of_birth)

    if request.candidate_source is not None:
        old_val = candidate.candidateSource
        candidate.candidateSource = request.candidate_source
        if old_val != request.candidate_source:
            corrections['candidate_source'] = (old_val, request.candidate_source)

    if request.candidate_experience is not None:
        old_val = candidate.candidateExperience
        candidate.candidateExperience = request.candidate_experience
        if old_val != request.candidate_experience:
            corrections['candidate_experience'] = (old_val, request.candidate_experience)

    if request.candidate_skills is not None:
        old_val = candidate.candidateSkills
        candidate.candidateSkills = request.candidate_skills
        if old_val != request.candidate_skills:
            corrections['candidate_skills'] = (old_val, request.candidate_skills)

    if request.candidate_joining_date is not None:
        old_val = candidate.candidateJoiningDate
        candidate.candidateJoiningDate = request.candidate_joining_date
        if old_val != request.candidate_joining_date:
            corrections['candidate_joining_date'] = (old_val, request.candidate_joining_date)

    if request.candidate_expected_salary is not None:
        old_val = candidate.candidateExpectedSalary
        candidate.candidateExpectedSalary = request.candidate_expected_salary
        if old_val != request.candidate_expected_salary:
            corrections['candidate_expected_salary'] = (old_val, request.candidate_expected_salary)

    if request.candidate_current_salary is not None:
        old_val = candidate.candidateCurrentSalary
        candidate.candidateCurrentSalary = request.candidate_current_salary
        if old_val != request.candidate_current_salary:
            corrections['candidate_current_salary'] = (old_val, request.candidate_current_salary)

    if request.candidate_current_location is not None:
        old_val = candidate.candidateCurrentLocation
        candidate.candidateCurrentLocation = request.candidate_current_location
        if old_val != request.candidate_current_location:
            corrections['candidate_current_location'] = (old_val, request.candidate_current_location)

    if request.candidate_job_title is not None:
        old_val = candidate.candidateJobTitle
        candidate.candidateJobTitle = request.candidate_job_title
        if old_val != request.candidate_job_title:
            corrections['candidate_job_title'] = (old_val, request.candidate_job_title)

    if request.candidate_employee_type is not None:
        old_val = candidate.candidateEmployeeType
        candidate.candidateEmployeeType = request.candidate_employee_type
        if old_val != request.candidate_employee_type:
            corrections['candidate_employee_type'] = (old_val, request.candidate_employee_type)

    # Update CandidateInfoForm when personal info fields are updated
    personal_info = db.query(CandidateInfoForm).filter(CandidateInfoForm.candidateID == candidate_id).first()
    if personal_info:
        if request.candidate_gender is not None:
            personal_info.gender = request.candidate_gender
        if request.candidate_date_of_birth is not None:
            dob_value = request.candidate_date_of_birth
            if hasattr(dob_value, 'date'):
                dob_value = dob_value.date()
            personal_info.dob = dob_value
        if request.candidate_current_location is not None:
            personal_info.current_address = request.candidate_current_location

    # CRITICAL: Must commit changes immediately
    try:
        db.commit()
        db.refresh(candidate)
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update candidate: {str(e)}"
        )

    # Wire SLM: Record corrections for learning
    if corrections:
        try:
            from app.services.slm_feedback_engine import SLMFeedbackEngine
            for field_name, (parsed_value, corrected_value) in corrections.items():
                SLMFeedbackEngine.record_correction(
                    db=db,
                    candidate_id=candidate_id,
                    field_name=field_name,
                    parsed_value=str(parsed_value) if parsed_value is not None else "",
                    corrected_value=str(corrected_value) if corrected_value is not None else "",
                    confidence_score=0.5  # Recruiter correction
                )
            logger.info(f"[SLM] Recorded {len(corrections)} corrections for candidate: {candidate_id}")
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"[SLM] Failed to record candidate corrections: {e}", exc_info=True)
            # Continue - SLM failure shouldn't block updates

    # Return full candidate object so frontend doesn't need separate refresh GET
    # Convert skills list to comma-separated string if it's a list
    skills_str = candidate.candidateSkills
    if isinstance(skills_str, list):
        skills_str = ", ".join(filter(None, skills_str)) if skills_str else None

    return CandidateCompleteResponse(
        candidate_id=candidate.candidateID,
        candidate_name=f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''}".strip(),
        candidate_first_name=candidate.candidateFirstName,
        candidate_middle_name=candidate.candidateMiddleName,
        candidate_last_name=candidate.candidateLastName,
        candidate_email=candidate.candidateEmail,
        candidate_mobile=candidate.candidateMobile,
        candidate_gender=candidate.candidateGender,
        candidate_date_of_birth=candidate.candidateDateOfBirth,
        candidate_job_title=candidate.candidateJobTitle,
        candidate_experience=candidate.candidateExperience,
        candidate_skills=skills_str,
        candidate_current_location=candidate.candidateCurrentLocation,
        candidate_joining_date=candidate.candidateJoiningDate,
        candidate_expected_salary=candidate.candidateExpectedSalary,
        candidate_expected_salary_type=getattr(candidate, 'candidateExpectedSalaryType', None),
        candidate_current_salary=candidate.candidateCurrentSalary,
        candidate_current_salary_type=getattr(candidate, 'candidateCurrentSalaryType', None),
        candidate_source=candidate.candidateSource,
    )

@router.delete(
    "/hr/delete_candidate/{candidate_id}",
    response_model=DeleteResponse,
    dependencies=[Depends(require_resource_permission("candidates", "delete"))],
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
        HTTPException: If candidate not found or user lacks BU permission
    """
    # TIER 2 FIX: Add BU scoping to delete_candidate
    # User can only delete candidates they have access to
    candidate = get_candidate_by_id_with_bu_scope(db, candidate_id, user)
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {candidate_id} not found or not accessible"
        )
    
    # ---------------------------------------------------------------
    # Delete child records in FK-safe order (deepest children first)
    # ---------------------------------------------------------------

    # 1. InterviewFeedback â†' references interviews.id
    feedback_ids = [
        row.id for row in
        db.query(Interview.id).filter(Interview.candidate_id == candidate_id).all()
    ]
    if feedback_ids:
        db.query(InterviewFeedback).filter(InterviewFeedback.interview_id.in_(feedback_ids)).delete(synchronize_session=False)

    # 2. PanelMember â†' references interview_panels.id
    panel_ids = [
        row.id for row in
        db.query(InterviewPanel.id).filter(InterviewPanel.candidate_id == candidate_id).all()
    ]
    if panel_ids:
        db.query(PanelMember).filter(PanelMember.panel_id.in_(panel_ids)).delete(synchronize_session=False)

    # 3. Interviews â†' references interview_panels.id + candidates.candidateID
    db.query(Interview).filter(Interview.candidate_id == candidate_id).delete(synchronize_session=False)

    # 4. InterviewPanel â†' references candidates.candidateID
    db.query(InterviewPanel).filter(InterviewPanel.candidate_id == candidate_id).delete(synchronize_session=False)

    # 5. CandidateAssignment â†' references candidates.candidateID
    db.query(CandidateAssignment).filter(CandidateAssignment.candidate_id == candidate_id).delete(synchronize_session=False)

    # 6. CandidateDocument (SharePoint file metadata) â†' references candidates.candidateID
    db.query(CandidateDocument).filter(CandidateDocument.candidate_id == candidate_id).delete(synchronize_session=False)

    # 7. Candidate form tables
    db.query(CandidateInfoForm).filter(CandidateInfoForm.candidateID == candidate_id).delete(synchronize_session=False)
    db.query(CandidateEducationForm).filter(CandidateEducationForm.candidateID == candidate_id).delete(synchronize_session=False)
    db.query(CandidateExperienceForm).filter(CandidateExperienceForm.candidateID == candidate_id).delete(synchronize_session=False)
    db.query(CandidateAadharForm).filter(CandidateAadharForm.candidateID == candidate_id).delete(synchronize_session=False)
    db.query(CandidatePanForm).filter(CandidatePanForm.candidateID == candidate_id).delete(synchronize_session=False)
    db.query(CandidateStatus).filter(CandidateStatus.candidateID == candidate_id).delete(synchronize_session=False)

    # 8. Checklist items then checklists
    checklist_ids = [
        row.id for row in
        db.query(CandidateChecklist.id).filter(CandidateChecklist.candidate_id == candidate_id).all()
    ]
    if checklist_ids:
        db.query(CandidateChecklistItem).filter(
            CandidateChecklistItem.checklist_id.in_(checklist_ids)
        ).delete(synchronize_session=False)
    db.query(CandidateChecklist).filter(
        CandidateChecklist.candidate_id == candidate_id
    ).delete(synchronize_session=False)

    # 9. CandidateHistory --" has backref="history" which makes SQLAlchemy try to
    #    SET candidateID=NULL before the parent delete; column is NOT NULL so we
    #    must delete these rows explicitly first.
    db.query(CandidateHistory).filter(
        CandidateHistory.candidateID == candidate_id
    ).delete(synchronize_session=False)

    # 10. OfferLetter --" no ondelete="CASCADE" on FK; must be deleted manually.
    db.query(OfferLetter).filter(
        OfferLetter.candidate_id == candidate_id
    ).delete(synchronize_session=False)

    # 11. InternalNote --" has backref="internal_notes"; same NULL risk as CandidateHistory.
    db.query(InternalNote).filter(
        InternalNote.candidate_id == candidate_id
    ).delete(synchronize_session=False)

    # 12. ATSScore --" has ondelete="CASCADE" but ORM may still interfere; explicit is safer.
    db.query(ATSScore).filter(
        ATSScore.candidate_id == candidate_id
    ).delete(synchronize_session=False)

    # 13. HRAssignment --" has ondelete="CASCADE" but explicit delete ensures no ORM conflict.
    db.query(HRAssignment).filter(
        HRAssignment.candidate_id == candidate_id
    ).delete(synchronize_session=False)

    # 14. CandidateOwnership --" has ondelete="CASCADE".
    db.query(CandidateOwnership).filter(
        CandidateOwnership.candidateID == candidate_id
    ).delete(synchronize_session=False)

    # 15. AI agentic tables
    conv_ids = [
        row.id for row in
        db.query(CandidateConversation.id).filter(
            CandidateConversation.candidate_id == candidate_id
        ).all()
    ]
    if conv_ids:
        db.query(ConversationEvent).filter(
            ConversationEvent.conversation_id.in_(conv_ids)
        ).delete(synchronize_session=False)
    db.query(CandidateConversation).filter(
        CandidateConversation.candidate_id == candidate_id
    ).delete(synchronize_session=False)
    db.query(CandidateAIAssignment).filter(
        CandidateAIAssignment.candidate_id == candidate_id
    ).delete(synchronize_session=False)

    # 16. CandidateJobApplication --" has ondelete="CASCADE".
    from app.models.candidate import CandidateJobApplication
    db.query(CandidateJobApplication).filter(
        CandidateJobApplication.candidate_id == candidate_id
    ).delete(synchronize_session=False)

    # 17. Finally delete the candidate row --" all FKs cleared above.
    db.delete(candidate)

    # TIER 1 FIX: Add try/except to db.commit() for transaction safety
    try:
        db.commit()
    except Exception as e:
        logger.error(f"Failed to commit deletion of candidate {candidate_id}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete candidate: {str(e)}")

    return DeleteResponse(
        status="Success",
        message=f"Candidate with ID {candidate_id} and all associated records deleted successfully"
    )

# ============================================
# Candidate-to-Employee Conversion
# ============================================

@router.post(
    "/candidates/{candidate_id}/convert-to-employee",
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Convert candidate to employee (only when status=OFFER and start_date met)"
)
def convert_candidate_to_employee(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Convert a candidate to an employee record.

    Prerequisites:
    - Candidate status must be "OFFER"
    - Start date must have arrived (candidateJoiningDate <= today)

    Creates Employee record and transitions candidate to "EMPLOYEE" status.
    """
    from app.models.candidate import CandidateStatus
    from app.models.employee import Employee

    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidate_status = db.query(CandidateStatus).filter(
        CandidateStatus.candidateID == candidate_id
    ).first()

    # TIER 3 FIX: Enhanced status validation
    if not candidate_status:
        raise HTTPException(status_code=400, detail="Candidate status record not found")

    if candidate_status.piplineStatus != CANDIDATE_PIPELINE_STATUS_OFFER:
        raise HTTPException(
            status_code=400,
            detail=f"Candidate status is '{candidate_status.piplineStatus}', must be 'OFFER' to convert to employee"
        )

    # TIER 3 FIX: Validate email and joining date
    if not candidate.candidateEmail or not _is_valid_email(candidate.candidateEmail):
        raise HTTPException(status_code=400, detail="Candidate email is missing or invalid")

    if not candidate.candidateJoiningDate:
        raise HTTPException(status_code=400, detail="Candidate joining date is required")

    if candidate.candidateJoiningDate > datetime.now().date():
        raise HTTPException(status_code=400, detail=f"Joining date ({candidate.candidateJoiningDate}) has not arrived yet")

    try:
        # Create Employee record
        # TIER 3 FIX: Use constants for status values
        employee = Employee(
            id=str(uuid.uuid4()),
            tenant_id=candidate.tenant_id or "default",
            first_name=candidate.candidateFirstName or "Employee",
            last_name=candidate.candidateLastName or "",
            email=candidate.candidateEmail,
            mobile=candidate.candidateMobile or "",
            gender=candidate.candidateGender,
            date_of_birth=candidate.candidateDateOfBirth,
            status="ACTIVE",
            employment_type=candidate.candidateEmployeeType or "Full-Time",
            designation=candidate.candidateJobTitle or "Employee",
            location=candidate.candidateCurrentLocation or "",
            joining_date=candidate.candidateJoiningDate,
            created_at=datetime.utcnow(),
        )
        db.add(employee)
        db.flush()

        # Update candidate status to EMPLOYEE (using constants)
        candidate_status.piplineStatus = CANDIDATE_PIPELINE_STATUS_EMPLOYEE
        candidate_status.status = CANDIDATE_STATUS_EMPLOYEE
        candidate_status.updatedAt = datetime.utcnow()

        # Log conversion event
        from app.models.candidate_ai import ConversationEvent
        db.add(ConversationEvent(
            event_type="CANDIDATE_CONVERTED_TO_EMPLOYEE",
            triggered_by="HR",
            event_data={
                "candidate_id": candidate_id,
                "employee_id": employee.id,
                "timestamp": datetime.utcnow().isoformat(),
                "triggered_by_user": user.UserID if user else "system"
            }
        ))

        # TIER 1 FIX: Add try/except to db.commit() for transaction safety
        try:
            db.commit()
        except Exception as e:
            logger.error(f"Failed to commit conversion of candidate {candidate_id}: {str(e)}", exc_info=True)
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to complete conversion: {str(e)}")

        logger.info(f"Successfully converted Candidate {candidate_id} to Employee {employee.id}")

        return {
            "status": "success",
            "candidate_id": candidate_id,
            "employee_id": employee.id,
            "message": f"Candidate {candidate.candidateFirstName} converted to employee successfully"
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        logger.error(f"âŒ Conversion failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")

# ============================================
# Candidate Contacts Endpoint
# ============================================

def _user_info(user: Users | None) -> dict | None:
    """Return a compact user info dict, or None if user not found."""
    if not user:
        return None
    return {
        "user_id":    user.UserID,
        "name":       user.UserName,
        "email":      user.UserEmail,
        "role":       user.UserRole,
    }

@router.get(
    "/hr/candidate/{candidate_id}/contacts",
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get assigned managers and job contact person for a candidate",
)
def get_candidate_contacts(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Returns the full contact details for everyone connected to a candidate:

    **From CandidateAssignment (direct assignment):**
    - `assigned_hiring_manager` --" the HR user directly assigned to manage this candidate
    - `assigned_reporting_manager` --" the reporting manager directly assigned to the candidate

    **From the candidate's linked Job (via `candidate.job_id`):**
    - `job_contact_person` --" the contact person recorded on the job posting
    - `job_hiring_manager` --" the hiring manager recorded on the job posting
    - `job_recruiter` --" the recruiter recorded on the job posting

    All fields are `null` when the corresponding record does not exist.
    """
    # 1. Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")

    # 2. Direct assignment (CandidateAssignment table)
    assignment = (
        db.query(CandidateAssignment)
        .filter(CandidateAssignment.candidate_id == candidate_id)
        .first()
    )

    assigned_hiring_manager   = None
    assigned_reporting_manager = None

    if assignment:
        if assignment.hiring_manager_id:
            hm = db.query(Users).filter(Users.UserID == assignment.hiring_manager_id).first()
            assigned_hiring_manager = _user_info(hm)
        if assignment.reporting_manager_id:
            rm = db.query(Users).filter(Users.UserID == assignment.reporting_manager_id).first()
            assigned_reporting_manager = _user_info(rm)

    # 3. Job-based contacts (Jobs table)
    job_info           = None
    job_contact_person = None
    job_hiring_manager = None
    job_recruiter      = None

    if candidate.job_id:
        job = db.query(Jobs).filter(Jobs.jobID == candidate.job_id).first()
        if job:
            job_info = {
                "job_id":    job.jobID,
                "job_title": job.jobTitle,
                "job_status": job.jobStatus,
            }
            if job.contactPerson:
                cp = db.query(Users).filter(Users.UserID == job.contactPerson).first()
                job_contact_person = _user_info(cp)
            if job.hiringManagerID:
                hm = db.query(Users).filter(Users.UserID == job.hiringManagerID).first()
                job_hiring_manager = _user_info(hm)
            if job.recuriterID:
                rec = db.query(Users).filter(Users.UserID == job.recuriterID).first()
                job_recruiter = _user_info(rec)

    return {
        "candidate_id":   candidate_id,
        "candidate_name": " ".join(
            p for p in [
                candidate.candidateFirstName,
                candidate.candidateMiddleName,
                candidate.candidateLastName,
            ] if p
        ).strip() or None,
        "candidate_email": candidate.candidateEmail,
        "job": job_info,
        # Directly assigned managers
        "assigned_hiring_manager":    assigned_hiring_manager,
        "assigned_reporting_manager": assigned_reporting_manager,
        # Job-level contacts
        "job_contact_person": job_contact_person,
        "job_hiring_manager": job_hiring_manager,
        "job_recruiter":      job_recruiter,
    }

