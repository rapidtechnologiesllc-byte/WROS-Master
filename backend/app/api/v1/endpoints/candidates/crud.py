from datetime import datetime
import logging
import uuid
from typing import Optional, List
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
import time

import app.schemas as schema
from app.core.database import get_db
from app.core.logging import logger
from app.core.rate_limiter import rate_limit
from app.services.message_queue_service import MessageQueueService
from app.services.ai_conversation_service import run_auto_assign_ai_agent_in_background
from app.services.candidate_service import (
    create_candidate,
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
from app.models.candidate_profile_extras import CandidateCertification, CandidateProfileSkill
from app.models.candidate_ai import CandidateConversation, CandidateAIAssignment, ConversationEvent
from app.models.offer_letter import OfferLetter
from app.models.internal_note import InternalNote
from app.models.ats import ATSScore
from app.models.hr_assignment import HRAssignment
from app.models.candidate_ownership import CandidateOwnership

from app.core.dependencies import get_current_user, get_current_candidate, require_role_template_permission

from app.schemas.candidate import (CandidateCreateRequest, HrEducationItem, HrExperienceItem, HrSkillItem, HrCertificationItem,
CandidateCreateResponse, CandidateCompleteResponse,
CandidateEducationResponse, CandidateExperienceResponse,
CandidateInfoResponse, CandidatePanResponse,
CandidateAadharResponse, DeleteResponse,
AllCandidatesResponse, candidateFormRequest, candidateFormResponse,
CandidateUpdateRequest)

from app.utils.uniq_id_generator import generate_password

from app.services.candidate_service import experience_years

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
        candidate_notice_period=getattr(candidate, 'candidate_notice_period', None),
        candidate_current_location=candidate.candidateCurrentLocation,
        candidate_current_salary=getattr(candidate, 'candidateCurrentSalary', None),
        candidate_current_salary_type=getattr(candidate, 'candidateCurrentSalaryType', None),
        candidate_expected_salary=getattr(candidate, 'candidateExpectedSalary', None),
        candidate_expected_salary_type=getattr(candidate, 'candidateExpectedSalaryType', None),
        candidate_employee_type=getattr(candidate, 'candidateEmployeeType', None),
        is_guidewire_candidate=is_guidewire,
        job_id=getattr(candidate, 'job_id', None),
        # Recruiter & Business Unit Assignment
        assigned_recruiter_id=getattr(candidate, 'assigned_recruiter_id', None),
        assigned_recruiter_name=(
            (candidate.assigned_recruiter.UserName or candidate.assigned_recruiter.UserEmail)
            if getattr(candidate, 'assigned_recruiter', None) else None
        ),
        submission_bu_id=getattr(candidate, 'submission_bu_id', None),
        submission_bu_name=(
            candidate.submission_bu.name if getattr(candidate, 'submission_bu', None) else None
        ),
        associated_bu_id=getattr(candidate, 'associated_bu_id', None),
        associated_bu_name=(
            candidate.associated_bu.name if getattr(candidate, 'associated_bu', None) else None
        ),
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
                education_level=edu.education_level,
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
                responsibilities=exp.responsibilities,
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

@router.get(
    "/all",
    response_model=dict,
    dependencies=[Depends(require_role_template_permission("candidates", "can_view"))]
)
def get_all_candidates(db: Session = Depends(get_db)):
    """Get all candidates for tenant 1 with dashboard-ready fields"""
    try:
        candidates = db.query(Candidate).filter(Candidate.tenant_id == 1).all()
        candidates_data = []

        for c in candidates:
            # Get candidate status
            candidate_status = db.query(CandidateStatus).filter(
                CandidateStatus.candidateID == c.candidateID
            ).first()

            # Build name
            name_parts = [c.candidateFirstName or "", c.candidateLastName or ""]
            name = " ".join(filter(None, name_parts)).strip() or "N/A"

            candidates_data.append({
                'candidateID': c.candidateID,
                'candidate_name': name,
                'candidate_email': c.candidateEmail or '',
                'candidateEmail': c.candidateEmail or '',
                'candidateFirstName': c.candidateFirstName or '',
                'candidateLastName': c.candidateLastName or '',
                'candidateRole': c.candidateRole or '',
                'candidateSource': c.candidateSource or '',
                'candidateJobTitle': c.candidateJobTitle or '',
                'candidate_current_location': c.candidateCurrentLocation or '',
                'status': candidate_status.status if candidate_status else 'Active',
                'pipline_status': candidate_status.piplineStatus if candidate_status else 'Applied',
                'candidateCreatedAt': c.candidateCreatedAt.isoformat() if c.candidateCreatedAt else None,
                # snake_case keys read by the frontend list mapper (Approutes.jsx
                # mapCandidateFromApi), CandidateSearch, ChecklistTemplates and
                # MessageTemplates. Additive: every key above is kept unchanged.
                'candidate_id': c.candidateID,
                'candidate_first_name': c.candidateFirstName or '',
                'candidate_last_name': c.candidateLastName or '',
                'candidate_mobile': c.candidateMobile or '',
                'candidate_job_title': c.candidateJobTitle or '',
                'candidate_gender': c.candidateGender or '',
                'candidate_date_of_birth': c.candidateDateOfBirth.isoformat() if c.candidateDateOfBirth else None,
                'candidate_joining_date': c.candidateJoiningDate.isoformat() if c.candidateJoiningDate else None,
                'candidate_source': c.candidateSource or '',
                'candidate_experience': c.candidateExperience or '',
                'candidate_skills': _serialize_skills(c.candidateSkills),
                'candidate_expected_salary': c.candidateExpectedSalary or '',
                'candidate_current_salary': c.candidateCurrentSalary or '',
                # Real flag for the list's Thunder toggle (it defaulted to
                # "Enabled" when this key was missing)
                'thunder_enabled': bool(c.thunder_enabled),
            })

        return {
            'total_candidates': len(candidates_data),
            'candidates': candidates_data
        }
    except Exception as e:
        logger.error(f"Error in get_all_candidates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get(
    "/{candidate_id}",
    response_model=CandidateCompleteResponse,
    dependencies=[Depends(require_role_template_permission("candidates", "can_view"))],
)
def get_candidate_by_id(
    candidate_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
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

    response = _build_candidate_response(
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
    response.profile_skills = [
        {"name": s.name, "years_of_experience": s.years_of_experience,
         "last_used_date": s.last_used_date.isoformat() if s.last_used_date else None, "is_primary": s.is_primary}
        for s in db.query(CandidateProfileSkill).filter(CandidateProfileSkill.candidate_id == candidate_id)
        .order_by(CandidateProfileSkill.id).all()
    ]
    response.certifications = [
        {"name": c.name, "organization": c.organization,
         "issue_date": c.issue_date.isoformat() if c.issue_date else None,
         "expiry_date": c.expiry_date.isoformat() if c.expiry_date else None, "credential_id": c.credential_id}
        for c in db.query(CandidateCertification).filter(CandidateCertification.candidate_id == candidate_id)
        .order_by(CandidateCertification.id).all()
    ]
    return response

@router.get(
    "/hr/my-bu/candidates",
    response_model=AllCandidatesResponse,
    dependencies=[Depends(require_role_template_permission("candidates", "can_view"))],
    summary="Get all candidates owned by the calling user's Business Unit",
)
def get_candidates_by_my_bu(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
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
            candidate_notice_period=getattr(candidate, 'candidate_notice_period', None),
            candidate_current_location=candidate.candidateCurrentLocation,
            candidate_current_salary=candidate.candidateCurrentSalary,
            candidate_current_salary_type=candidate.candidateCurrentSalaryType,
            candidate_expected_salary=candidate.candidateExpectedSalary,
            candidate_expected_salary_type=candidate.candidateExpectedSalaryType,
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
                education_level=edu.education_level,
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
                responsibilities=exp.responsibilities,
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

def _record_profile_edit(db: Session, candidate_id: str, user, note: str):
    db.add(CandidateHistory(
        candidateID=candidate_id,
        event_type="Candidate Edited",
        note=note,
        performed_by_id=getattr(user, "UserID", None),
        performed_by_name=getattr(user, "UserName", None) or getattr(user, "UserEmail", None),
        event_at=datetime.utcnow(),
    ))


@router.put(
    "/{candidate_id}/education",
    dependencies=[Depends(require_role_template_permission("candidates", "can_edit"))],
)
def replace_candidate_education(
    candidate_id: str, items: list[HrEducationItem], db: Session = Depends(get_db), user = Depends(get_current_user)
):
    """Replace the candidate's education list (HR profile Save & Close)."""
    candidate = get_candidate_by_id_with_bu_scope(db, candidate_id, user)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate with ID {candidate_id} not found")
    db.query(CandidateEducationForm).filter(CandidateEducationForm.candidateID == candidate_id).delete()
    for item in items:
        db.add(CandidateEducationForm(
            candidateID=candidate_id,
            education_level=item.level,
            education_institute=item.institute,
            degree=item.degree,
            field_of_study=item.field_of_study,
            starting_year=item.start,
            year_of_passing=item.end,
            percentage=item.percentage,
        ))
    _record_profile_edit(db, candidate_id, user, f"Education updated ({len(items)} entries)")
    db.commit()
    return {"status": "success", "count": len(items)}


@router.put(
    "/{candidate_id}/experience",
    dependencies=[Depends(require_role_template_permission("candidates", "can_edit"))],
)
def replace_candidate_experience(
    candidate_id: str, items: list[HrExperienceItem], db: Session = Depends(get_db), user = Depends(get_current_user)
):
    """Replace the candidate's experience list (HR profile Save & Close)."""
    candidate = get_candidate_by_id_with_bu_scope(db, candidate_id, user)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate with ID {candidate_id} not found")
    db.query(CandidateExperienceForm).filter(CandidateExperienceForm.candidateID == candidate_id).delete()
    for item in items:
        db.add(CandidateExperienceForm(
            candidateID=candidate_id,
            company_name=item.company,
            job_title=item.job_title,
            start_date=item.start_date,
            end_date=item.end_date,
            year_of_experience=experience_years(item.start_date, item.end_date),
            responsibilities=item.responsibilities,
        ))
    _record_profile_edit(db, candidate_id, user, f"Experience updated ({len(items)} entries)")
    db.commit()
    return {"status": "success", "count": len(items)}


@router.put(
    "/{candidate_id}/skills",
    dependencies=[Depends(require_role_template_permission("candidates", "can_edit"))],
)
def replace_candidate_skills(
    candidate_id: str, items: list[HrSkillItem], db: Session = Depends(get_db), user = Depends(get_current_user)
):
    """Replace the candidate's skills (profile Skills modal). Also keeps the
    comma-separated candidateSkills in sync for matching and list views."""
    candidate = get_candidate_by_id_with_bu_scope(db, candidate_id, user)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate with ID {candidate_id} not found")
    if items and sum(1 for i in items if i.is_primary) != 1:
        raise HTTPException(status_code=400, detail="Mark exactly one primary skill")
    db.query(CandidateProfileSkill).filter(CandidateProfileSkill.candidate_id == candidate_id).delete()
    for item in items:
        db.add(CandidateProfileSkill(candidate_id=candidate_id, name=item.name.strip(),
                                     years_of_experience=item.years_of_experience,
                                     last_used_date=item.last_used_date, is_primary=item.is_primary))
    candidate.candidateSkills = ", ".join(i.name.strip() for i in items) or None
    _record_profile_edit(db, candidate_id, user, f"Skills updated ({len(items)} skills)")
    db.commit()
    return {"status": "success", "count": len(items)}


@router.put(
    "/{candidate_id}/certifications",
    dependencies=[Depends(require_role_template_permission("candidates", "can_edit"))],
)
def replace_candidate_certifications(
    candidate_id: str, items: list[HrCertificationItem], db: Session = Depends(get_db), user = Depends(get_current_user)
):
    """Replace the candidate's certifications (profile Certifications modal)."""
    candidate = get_candidate_by_id_with_bu_scope(db, candidate_id, user)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate with ID {candidate_id} not found")
    db.query(CandidateCertification).filter(CandidateCertification.candidate_id == candidate_id).delete()
    for item in items:
        db.add(CandidateCertification(candidate_id=candidate_id, name=item.name.strip(),
                                      organization=item.organization, issue_date=item.issue_date,
                                      expiry_date=item.expiry_date, credential_id=item.credential_id))
    _record_profile_edit(db, candidate_id, user, f"Certifications updated ({len(items)} entries)")
    db.commit()
    return {"status": "success", "count": len(items)}


@router.put(
    "/hr/update_candidate/{candidate_id}",
    response_model=CandidateCompleteResponse,
    dependencies=[Depends(require_role_template_permission("candidates", "can_edit"))],
)
def update_candidate(candidate_id: str, request: CandidateUpdateRequest, db: Session = Depends(get_db), user = Depends(get_current_user)):
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

    if request.candidate_notice_period is not None:
        old_val = candidate.candidate_notice_period
        candidate.candidate_notice_period = request.candidate_notice_period
        if old_val != request.candidate_notice_period:
            corrections['candidate_notice_period'] = (old_val, request.candidate_notice_period)

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

    for field, column in (("candidate_expected_salary_type", "candidateExpectedSalaryType"),
                          ("candidate_current_salary_type", "candidateCurrentSalaryType")):
        new_val = getattr(request, field)
        if new_val is not None:
            old_val = getattr(candidate, column)
            setattr(candidate, column, new_val or None)
            if old_val != (new_val or None):
                corrections[field] = (old_val, new_val)

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

    # Email can be corrected (e.g. a LinkedIn lead's placeholder address once
    # the real one is known); it is the dedup key, so it must stay unique
    if request.candidate_email is not None:
        new_email = str(request.candidate_email).strip().lower()
        old_val = candidate.candidateEmail
        if new_email != (old_val or "").lower():
            taken = db.query(Candidate).filter(
                func.lower(Candidate.candidateEmail) == new_email,
                Candidate.candidateID != candidate_id,
            ).first()
            if taken:
                raise HTTPException(
                    status_code=409,
                    detail=f"{new_email} already belongs to candidate {taken.candidateID}",
                )
            candidate.candidateEmail = new_email
            corrections['candidate_email'] = (old_val, new_email)
            db.add(CandidateHistory(
                candidateID=candidate_id,
                event_type="Candidate Edited",
                note=f"Email changed from {old_val} to {new_email}",
                performed_by_id=getattr(user, "UserID", None),
                performed_by_name=getattr(user, "UserName", None) or getattr(user, "UserEmail", None),
                event_at=datetime.utcnow(),
            ))

    if request.assigned_recruiter_id is not None and request.assigned_recruiter_id != candidate.assigned_recruiter_id:
        recruiter = db.query(Users).filter(Users.UserID == request.assigned_recruiter_id).first()
        if not recruiter:
            raise HTTPException(status_code=404, detail=f"User {request.assigned_recruiter_id} not found")
        candidate.assigned_recruiter_id = recruiter.UserID
        candidate.assigned_recruiter_changed_at = datetime.utcnow()
        candidate.assigned_recruiter_changed_by = getattr(user, "UserID", None)
        _record_profile_edit(db, candidate_id, user, f"Recruiter set to {recruiter.UserName or recruiter.UserEmail}")

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

    # ENQUEUE UPDATE FOR ASYNC PROCESSING (history, events, SLM, etc.)
    # This gives us full audit trail visibility in the message queue
    try:
        performer_id = getattr(user, "userID", None) or getattr(user, "UserID", None)
        performer_name = (
            f"{getattr(user, 'userFirstName', '') or getattr(user, 'UserFirstName', '')or ''} "
            f"{getattr(user, 'userLastName', '') or getattr(user, 'UserLastName', '') or ''}".strip()
            or getattr(user, "userEmail", None) or getattr(user, "UserEmail", None)
            or "Unknown User"
        )

        # Build updates dict from corrections
        updates = {}
        for field_name, (old_val, new_val) in corrections.items():
            updates[field_name] = new_val

        MessageQueueService.enqueue(
            task_name='candidate_update',
            task_id=candidate_id,
            data={
                'candidate_id': candidate_id,
                'updates': updates,
                'performer_id': performer_id,
                'performer_name': performer_name,
            }
        )
        logger.info(f"[CRUD] Enqueued candidate_update for {candidate_id} ({len(corrections)} fields)")
    except Exception as e:
        logger.error(f"[CRUD] Failed to enqueue update: {e}", exc_info=True)
        # Don't fail the response if queue enqueue fails - at least the sync update succeeded

    # NOTE: History creation, event publishing, and SLM feedback now handled by CandidateUpdateHandler
    # in the async queue - this removes duplication and provides audit trail visibility

    # Emit candidate_data_changed event with all changed fields
    if corrections:
        try:
            from app.services.candidate_event_bus import CandidateEventBus
            CandidateEventBus.publish_data_changed(
                candidate_id=candidate_id,
                changed_fields=list(corrections.keys()),
                **{field: corrections[field][1] for field in corrections}  # new values
            )
            logger.info(f"[CRUD] Emitted candidate_data_changed event for {candidate_id} ({len(corrections)} fields)")
        except Exception as e:
            logger.error(f"[CRUD] Failed to emit event: {e}", exc_info=True)
            # Don't fail update if event emission fails

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
        candidate_notice_period=getattr(candidate, 'candidate_notice_period', None),
        candidate_expected_salary=candidate.candidateExpectedSalary,
        candidate_expected_salary_type=getattr(candidate, 'candidateExpectedSalaryType', None),
        candidate_current_salary=candidate.candidateCurrentSalary,
        candidate_current_salary_type=getattr(candidate, 'candidateCurrentSalaryType', None),
        candidate_source=candidate.candidateSource,
    )

@router.patch(
    "/{candidate_id}/thunder-config",
    response_model=CandidateCompleteResponse,
    dependencies=[Depends(require_role_template_permission("candidates", "can_edit"))],
)
def update_thunder_config(
    candidate_id: str,
    body: dict,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Update Thunder autonomous processing flag for a candidate.

    Args:
        candidate_id: ID of candidate to update
        body: {"thunder_enabled": true/false}
        db: Database session
        user: Authenticated HR/Admin user

    Returns:
        Updated CandidateCompleteResponse

    Raises:
        HTTPException: If candidate not found or user lacks permission
    """
    if "thunder_enabled" not in body:
        raise HTTPException(status_code=400, detail="Missing 'thunder_enabled' field in request body")

    candidate = get_candidate_by_id_with_bu_scope(db, candidate_id, user)
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {candidate_id} not found"
        )

    old_value = candidate.thunder_enabled
    candidate.thunder_enabled = bool(body["thunder_enabled"])

    try:
        db.commit()
        db.refresh(candidate)
        logger.info(f"Thunder config updated for {candidate_id}: {old_value} → {candidate.thunder_enabled}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update thunder config: {str(e)}")

    return _build_candidate_response(candidate)

@router.delete(
    "/{candidate_id}",
    response_model=DeleteResponse,
    dependencies=[Depends(require_role_template_permission("candidates", "can_delete"))],
)
def delete_candidate_restful(candidate_id: str, db: Session = Depends(get_db), user = Depends(get_current_user)):
    """
    Delete a candidate and all associated records (RESTful endpoint).

    This is the standard DELETE /candidates/{candidate_id} endpoint.
    The old /candidates/hr/delete_candidate/{candidate_id} is deprecated
    but kept for backward compatibility.

    Args:
        candidate_id: ID of the candidate to delete
        db: Database session
        user: Authenticated HR/Admin user

    Returns:
        DeleteResponse with success message

    Raises:
        HTTPException: If candidate not found or user lacks BU permission
    """
    # Delegate to the legacy implementation
    return delete_candidate_legacy(candidate_id, db, user)

@router.delete(
    "/hr/delete_candidate/{candidate_id}",
    response_model=DeleteResponse,
    dependencies=[Depends(require_role_template_permission("candidates", "can_delete"))],
    deprecated=True,
)
def delete_candidate_legacy(candidate_id: str, db: Session = Depends(get_db), user = Depends(get_current_user)):
    """
    ⚠️ DEPRECATED: Use DELETE /candidates/{candidate_id} instead.

    This endpoint will be removed on 2027-03-23. Please migrate to the RESTful endpoint.

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

    # Queue candidate deletion for THUNDER orchestrator
    MessageQueueService.enqueue(
        task_name='candidate_deleted',
        task_id=candidate_id,
        data={
            'candidate_id': candidate_id,
            'candidate_email': candidate.candidateEmail,
            'deleted_at': datetime.now().isoformat()
        }
    )

    # Emit candidate_deleted event
    try:
        from app.services.candidate_event_bus import CandidateEventBus
        CandidateEventBus.publish_event(
            event_type="candidate_deleted",
            candidate_id=candidate_id,
            data={"deleted_at": datetime.utcnow().isoformat(), "deleted_by_user_id": user.UserID if hasattr(user, 'UserID') else None}
        )
        logger.info(f"[CRUD] Emitted candidate_deleted event for {candidate_id}")
    except Exception as e:
        logger.error(f"[CRUD] Failed to emit candidate_deleted event: {e}", exc_info=True)
        # Don't fail delete if event emission fails

    return DeleteResponse(
        status="Success",
        message=f"Candidate with ID {candidate_id} and all associated records deleted successfully"
    )

# ============================================
# Candidate-to-Employee Conversion
# ============================================

@router.post(
    "/{candidate_id}/convert-to-employee",
    dependencies=[Depends(require_role_template_permission("candidates", "can_edit"))],
    summary="Convert candidate to employee (only when status=OFFER and start_date met)"
)
def convert_candidate_to_employee(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
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

        # Queue candidate-to-employee conversion for THUNDER orchestrator
        MessageQueueService.enqueue(
            task_name='candidate_converted_to_employee',
            task_id=candidate_id,
            data={
                'candidate_id': candidate_id,
                'employee_id': str(employee.id),
                'candidate_email': candidate.candidateEmail,
                'converted_at': datetime.now().isoformat()
            }
        )

        logger.info(f"Successfully converted Candidate {candidate_id} to Employee {employee.id}")

        # Emit candidate_status_changed event with Thunder pause flag
        try:
            from app.services.candidate_event_bus import CandidateEventBus
            CandidateEventBus.publish_status_changed(
                candidate_id=candidate_id,
                old_status=CANDIDATE_PIPELINE_STATUS_OFFER,
                new_status=CANDIDATE_PIPELINE_STATUS_EMPLOYEE,
                reason="Candidate converted to employee",
                pause_thunder=True,  # CRITICAL: Signal Thunder to pause
                employee_id=employee.id
            )
            logger.info(f"[CRUD] Emitted candidate_status_changed event with Thunder pause for {candidate_id}")
        except Exception as e:
            logger.error(f"[CRUD] Failed to emit event: {e}", exc_info=True)
            # Don't fail conversion if event emission fails

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
    dependencies=[Depends(require_role_template_permission("candidates", "can_view"))],
    summary="Get assigned managers and job contact person for a candidate",
)
def get_candidate_contacts(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
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


# ============================================================
# Include legacy candidate routes (self-service + creation)
# ============================================================
# Load and include the legacy candidates.py module which contains
# self-service routes (/candidate/create, /candidate/import/linkedin, etc.)
# This consolidates both HR admin routes (/candidates/*) and candidate
# self-service routes (/candidate/*) into a single integrated router
try:
    import importlib.util
    from pathlib import Path
    _legacy_path = Path(__file__).parent.parent / "candidates.py"
    _spec = importlib.util.spec_from_file_location("candidates_legacy", str(_legacy_path))
    _legacy_module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_legacy_module)

    # Re-register each route through proper FastAPI mechanism (add_api_route)
    # This ensures Starlette rebuilds its routing tree correctly
    # The legacy router uses prefix="/candidate", we convert to use crud's "/candidates" prefix
    _legacy_routes_count = 0
    for _route in _legacy_module.router.routes:
        if hasattr(_route, 'endpoint') and hasattr(_route, 'methods'):
            # Extract the path and remove the legacy "/candidate" prefix
            path = _route.path
            if path.startswith("/candidates"):
                # Remove "/candidates" from "/candidates/create" -> "/create"
                path = path[len("/candidates"):]
                if not path:
                    path = "/"
            elif path.startswith("/candidate"):
                # Also handle old "/candidate" prefix (without 's')
                path = path[len("/candidate"):]
                if not path:
                    path = "/"

            # Re-register each HTTP method separately through proper FastAPI mechanism
            for method in (_route.methods or ["GET"]):
                router.add_api_route(
                    path,
                    _route.endpoint,
                    methods=[method],
                    response_model=getattr(_route, 'response_model', None),
                    dependencies=getattr(_route, 'dependencies', None),
                    status_code=getattr(_route, 'status_code', None),
                    tags=getattr(_route, 'tags', ['legacy-candidates']),
                    summary=getattr(_route, 'summary', None),
                    description=getattr(_route, 'description', None),
                    name=getattr(_route, 'name', None),
                    include_in_schema=getattr(_route, 'include_in_schema', True),
                )
                _legacy_routes_count += 1

    logger.info(f"[CANDIDATES] Legacy routes re-registered: {_legacy_routes_count} route handlers")
except Exception as e:
    logger.error(f"[CANDIDATES] Failed to load legacy routes: {e}", exc_info=True)

