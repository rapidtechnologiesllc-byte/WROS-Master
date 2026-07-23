from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

import app.schemas as schema
from app.core.database import get_db
from app.services.ai_conversation_service import auto_assign_ai_agent_on_creation
from app.services.candidate_service import (
    create_candidate_safe,
    DuplicateCandidateError,
    parse_experience_to_months,
)
from app.core.tenant_context import get_tenant_scoped_query
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

from app.core.dependencies import get_current_hr_or_admin, get_current_candidate, require_permission

from app.schemas.candidate import (CandidateCreateRequest,
CandidateCreateResponse, CandidateCompleteResponse,
CandidateEducationResponse, CandidateExperienceResponse,
CandidateInfoResponse, CandidatePanResponse,
CandidateAadharResponse, DeleteResponse,
AllCandidatesResponse)
from app.schemas.user import CandidateUpdateRequest

from app.utils.uniq_id_generator import generate_password

router = APIRouter(prefix="/onboarding", tags=["onboarding"])



@router.post(
    "/hr/create_candidate",
    response_model=CandidateCreateResponse,
    dependencies=[Depends(require_permission("candidate.create"))],
)
def create_candidate(
    request: CandidateCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin),
):
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
    # R-07: createCandidateSafe() is the only sanctioned creation path --
    # runs email/phone/LinkedIn dedup (each independently) before any insert.
    password = generate_password()
    try:
        candidate = create_candidate_safe(
            db,
            email=request.candidate_email,
            mobile=request.candidate_mobile,
            plain_password=password,
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

    db.commit()
    db.refresh(candidate)
    # Create candidate status
    candidate_status = CandidateStatus(
        candidateID=candidate_id,
        piplineStatus="Applied",
        status="Active",
        createdAt=datetime.now(),
        updatedAt=datetime.now(),
    )
    db.add(candidate_status)
    db.commit()

    # Bulk-insert education records if provided
    if request.education_records:
        for edu in request.education_records:
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
            db.add(edu_row)

    # Bulk-insert experience records if provided
    if request.experience_records:
        for exp in request.experience_records:
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

    if request.education_records or request.experience_records:
        db.commit()

    # HRMS-0401: assign the AI recruiter automatically -- doesn't block
    # this response, doesn't fail candidate creation if it errors.
    background_tasks.add_task(auto_assign_ai_agent_on_creation, candidate_id, user.UserID, db)

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
    # HRMS-0109 -- scoped to the caller's own tenant, never all tenants'
    # candidates. See app.core.tenant_context; fails closed (403) if
    # `user` has no tenant assigned rather than silently showing everyone's.
    candidates = get_tenant_scoped_query(db, Candidate, current_user=user).all()

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

        # Get candidate status (scoped per candidate)
        candidate_status = db.query(CandidateStatus).filter(
            CandidateStatus.candidateID == candidate.candidateID
        ).first()

        # Build response object
        candidate_response = CandidateCompleteResponse(
            candidate_id=candidate.candidateID,
            candidate_name=candidate_name,
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
                    document_id=edu.document_id
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
                    document_id=exp.document_id
                ) for exp in experience_records
            ],
            aadhar=CandidateAadharResponse(
                formID=aadhar_form.formID if aadhar_form else None,
                aadhar=aadhar_form.aadhar if aadhar_form else None,
                name_in_aadhar=aadhar_form.name_in_aadhar if aadhar_form else None,
                enrollment_number=aadhar_form.enrollment_number if aadhar_form else None,
                aadhar_is_submitted=aadhar_form.aadhar_is_submitted if aadhar_form else None,
                is_verified=aadhar_form.is_verified if aadhar_form else None,
                document_id=aadhar_form.document_id if aadhar_form else None
            ) if aadhar_form else None,
            pan=CandidatePanResponse(
                formID=pan_form.formID if pan_form else None,
                pan=pan_form.pan if pan_form else None,
                name_in_pan=pan_form.name_in_pan if pan_form else None,
                father_name_in_pan=pan_form.father_name_in_pan if pan_form else None,
                pan_is_submitted=pan_form.pan_is_submitted if pan_form else None,
                is_verified=pan_form.is_verified if pan_form else None,
                document_id=pan_form.document_id if pan_form else None
            ) if pan_form else None,
            status=candidate_status.status if candidate_status else None,
            pipline_status=candidate_status.piplineStatus if candidate_status else None
        )
        
        candidates_data.append(candidate_response)
    
    return AllCandidatesResponse(
        total_candidates=len(candidates_data),
        candidates=candidates_data
    )


@router.get(
    "/hr/candidate/{candidate_id}",
    response_model=CandidateCompleteResponse,
    dependencies=[Depends(require_permission("candidate.view"))],
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

    Raises:
        HTTPException 404: If no candidate with the given ID exists.
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
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

    return CandidateCompleteResponse(
        candidate_id=candidate.candidateID,
        candidate_name=candidate_name,
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
            )
            for edu in education_records
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
            )
            for exp in experience_records
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
        pipline_status=candidate_status.piplineStatus if candidate_status else None
    )


@router.get(
    "/hr/my-bu/candidates",
    response_model=AllCandidatesResponse,
    dependencies=[Depends(require_permission("candidate.view"))],
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
      `business_unit_id` — no parameter needed.
    - Use `include_org_pool=true` to also fetch unassigned Org Pool candidates
      (useful for BU managers who want to pick new candidates).
    - Optionally filter by `pipeline_status`.

    **Requires:** `candidate.view` permission.
    """
    from app.models.candidate_ownership import CandidateOwnership, POOL_BU, POOL_ORG

    # ── Resolve the calling user's BU ─────────────────────────────────────────
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

    # ── Find candidate IDs that belong to this BU ─────────────────────────────
    ownership_query = db.query(CandidateOwnership).filter(
        CandidateOwnership.owned_by_bu_id == bu_id,
        CandidateOwnership.pool_status == POOL_BU,
    )
    bu_candidate_ids = {row.candidateID for row in ownership_query.all()}

    # ── Optionally include Org Pool candidates ────────────────────────────────
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

    # ── Fetch candidate rows ──────────────────────────────────────────────────
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

    # ── Build full response (reusing exact same pattern as get_all_candidates) ─
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
    if request.candidate_job_title is not None:
        candidate.candidateJobTitle = request.candidate_job_title
    if request.candidate_employee_type is not None:
        candidate.candidateEmployeeType = request.candidate_employee_type
    if request.assigned_hr_manager_id is not None:
        candidate.assignedHRManagerID = request.assigned_hr_manager_id
    if request.assigned_report_manager_id is not None:
        candidate.assignedReportManagerID = request.assigned_report_manager_id
    
    db.commit()
    db.refresh(candidate)
    
    return CandidateCreateResponse(
        candidate_id=candidate.candidateID,
        candidate_is_first_time=False,
        candidate_password=""
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
    
    # ---------------------------------------------------------------
    # Delete child records in FK-safe order (deepest children first)
    # ---------------------------------------------------------------

    # 1. InterviewFeedback → references interviews.id
    feedback_ids = [
        row.id for row in
        db.query(Interview.id).filter(Interview.candidate_id == candidate_id).all()
    ]
    if feedback_ids:
        db.query(InterviewFeedback).filter(InterviewFeedback.interview_id.in_(feedback_ids)).delete(synchronize_session=False)

    # 2. PanelMember → references interview_panels.id
    panel_ids = [
        row.id for row in
        db.query(InterviewPanel.id).filter(InterviewPanel.candidate_id == candidate_id).all()
    ]
    if panel_ids:
        db.query(PanelMember).filter(PanelMember.panel_id.in_(panel_ids)).delete(synchronize_session=False)

    # 3. Interviews → references interview_panels.id + candidates.candidateID
    db.query(Interview).filter(Interview.candidate_id == candidate_id).delete(synchronize_session=False)

    # 4. InterviewPanel → references candidates.candidateID
    db.query(InterviewPanel).filter(InterviewPanel.candidate_id == candidate_id).delete(synchronize_session=False)

    # 5. CandidateAssignment → references candidates.candidateID
    db.query(CandidateAssignment).filter(CandidateAssignment.candidate_id == candidate_id).delete(synchronize_session=False)

    # 6. CandidateDocument (SharePoint file metadata) → references candidates.candidateID
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

    # 9. CandidateHistory — has backref="history" which makes SQLAlchemy try to
    #    SET candidateID=NULL before the parent delete; column is NOT NULL so we
    #    must delete these rows explicitly first.
    db.query(CandidateHistory).filter(
        CandidateHistory.candidateID == candidate_id
    ).delete(synchronize_session=False)

    # 10. OfferLetter — no ondelete="CASCADE" on FK; must be deleted manually.
    db.query(OfferLetter).filter(
        OfferLetter.candidate_id == candidate_id
    ).delete(synchronize_session=False)

    # 11. InternalNote — has backref="internal_notes"; same NULL risk as CandidateHistory.
    db.query(InternalNote).filter(
        InternalNote.candidate_id == candidate_id
    ).delete(synchronize_session=False)

    # 12. ATSScore — has ondelete="CASCADE" but ORM may still interfere; explicit is safer.
    db.query(ATSScore).filter(
        ATSScore.candidate_id == candidate_id
    ).delete(synchronize_session=False)

    # 13. HRAssignment — has ondelete="CASCADE" but explicit delete ensures no ORM conflict.
    db.query(HRAssignment).filter(
        HRAssignment.candidate_id == candidate_id
    ).delete(synchronize_session=False)

    # 14. CandidateOwnership — has ondelete="CASCADE".
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

    # 16. CandidateJobApplication — has ondelete="CASCADE".
    from app.models.candidate import CandidateJobApplication
    db.query(CandidateJobApplication).filter(
        CandidateJobApplication.candidate_id == candidate_id
    ).delete(synchronize_session=False)

    # 17. Finally delete the candidate row — all FKs cleared above.
    db.delete(candidate)
    db.commit()
    
    return DeleteResponse(
        status="Success",
        message=f"Candidate with ID {candidate_id} and all associated records deleted successfully"
    )

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
    dependencies=[Depends(require_permission("candidate.view"))],
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
    - `assigned_hiring_manager` — the HR user directly assigned to manage this candidate
    - `assigned_reporting_manager` — the reporting manager directly assigned to the candidate

    **From the candidate's linked Job (via `candidate.job_id`):**
    - `job_contact_person` — the contact person recorded on the job posting
    - `job_hiring_manager` — the hiring manager recorded on the job posting
    - `job_recruiter` — the recruiter recorded on the job posting

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

