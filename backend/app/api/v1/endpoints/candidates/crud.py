from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import app.schemas as schema
from app.core.database import get_db
from app.core.logging import logger
from app.services.ai_conversation_service import run_auto_assign_ai_agent_in_background
from app.services.candidate_service import (
    create_candidate_safe,
    DuplicateCandidateError,
    parse_experience_to_months,
)
from app.services.guidewire_candidate_service import is_guidewire_candidate
from app.core.bu_scope import apply_bu_scope_to_candidate_query, get_candidate_by_id_with_bu_scope
from app.models.candidate import (
    Candidate,
    CandidateInfoForm,
    CandidateEducationForm,
    CandidateExperienceForm,
    CandidateAadharForm,
    CandidatePanForm,
    CandidateStatus,
    CandidateJobApplication,
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
from app.models.candidate_ownership import CandidateOwnership, POOL_BU

from app.core.dependencies import get_current_hr_or_admin, require_resource_permission
from app.services.message_queue_service import MessageQueueService

from app.schemas.candidate import (
    CandidateCreateRequest,
    CandidateCreateResponse,
    CandidateCompleteResponse,
    CandidateEducationResponse,
    CandidateExperienceResponse,
    CandidateInfoResponse,
    CandidatePanResponse,
    CandidateAadharResponse,
    DeleteResponse,
    AllCandidatesResponse
)
from app.schemas.user import CandidateUpdateRequest

from app.utils.uniq_id_generator import generate_password

router = APIRouter(prefix="/candidates", tags=["candidates-crud"])


@router.post(
    "/create",
    response_model=CandidateCreateResponse,
    summary="Create new candidate (CRUD operation)"
)
def create_candidate(
    request: CandidateCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Create a new candidate with comprehensive information.

    CRUD operation: Create only (no workflows).
    Queue integration: Enqueues candidate_created message to THUNDER_QUEUE.

    CRITICAL: Candidate is assigned to user's business unit so Thunder can access it
    via proper tenant/BU scoping. Without this, Thunder has no visibility.
    """
    if not request.candidate_current_location or not request.candidate_current_location.strip():
        raise HTTPException(
            status_code=400,
            detail="Location (City, State, Country) is mandatory for candidate creation"
        )

    password = generate_password()
    try:
        # Get user's BU from the authenticated user object
        user_bu_id = getattr(user, 'business_unit_id', None)
        logger.info(f"[CreateCandidate] User {user.UserID} has BU ID: {user_bu_id}")

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
            total_experience_months=parse_experience_to_months(request.candidate_experience),
            candidateSkills=request.candidate_skills,
            candidateJoiningDate=request.candidate_joining_date,
            candidateExpectedSalary=request.candidate_expected_salary,
            candidateCurrentSalary=request.candidate_current_salary,
            candidateCurrentLocation=request.candidate_current_location,
            candidateCreatedAt=datetime.now(),
            associated_bu_id=user_bu_id,  # CRITICAL: Assign to user's BU for Thunder access
        )
        logger.info(f"[CreateCandidate] Candidate {candidate.candidateID} assigned to BU: {candidate.associated_bu_id}")
    except DuplicateCandidateError:
        raise HTTPException(
            status_code=400,
            detail=f"Account already exists with email {request.candidate_email}"
        )

    candidate_id = candidate.candidateID

    # ATOMIC TRANSACTION: Add all objects before commit
    candidate_status = CandidateStatus(
        candidateID=candidate_id,
        piplineStatus="Applied",
        status="Active",
        createdAt=datetime.now(),
        updatedAt=datetime.now(),
    )
    db.add(candidate_status)

    candidate_info = CandidateInfoForm(
        candidateID=candidate_id,
        dob=request.candidate_date_of_birth,
        gender=request.candidate_gender,
        submittedAt=datetime.now().date(),
    )
    db.add(candidate_info)

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

    # CRITICAL: Create CandidateOwnership record so candidate is visible via BU scoping
    if user_bu_id:
        ownership = CandidateOwnership(
            candidateID=candidate_id,
            owned_by_bu_id=user_bu_id,
            pool_status=POOL_BU,
            bu_owned_since=datetime.now(),
        )
        db.add(ownership)
        logger.info(f"[CreateCandidate] Created CandidateOwnership for BU: {user_bu_id}")

    # Enqueue message (will commit the entire transaction atomically)
    candidate_name = f"{request.candidate_first_name or ''} {request.candidate_last_name or ''}".strip()
    payload = {
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "candidate_email": request.candidate_email,
        "candidate_phone": request.candidate_mobile,
        "candidate_location": request.candidate_current_location,
        "candidate_job_title": request.candidate_job_title,
        "created_at": datetime.utcnow().isoformat(),
    }
    # Extract UUID from candidate_id (e.g., "CAN-abc123..." -> "abc123...")
    resource_uuid = candidate_id.split("-", 1)[1] if "-" in candidate_id else candidate_id
    # Extract UUID from user.UserID (e.g., "USER-abc123..." -> "abc123...")
    created_by_uuid = user.UserID.split("-", 1)[1] if "-" in user.UserID else user.UserID

    try:
        logger.info(f"[CreateCandidate] Enqueuing message for candidate {candidate_id}")
        message_id = MessageQueueService.enqueue(
            message_type="candidate_created",
            payload=payload,
            resource_id=resource_uuid,
            created_by=created_by_uuid,
            db=db,
        )
        logger.info(f"[CreateCandidate] Message enqueued successfully: {message_id}")
    except Exception as e:
        logger.error(f"[CreateCandidate] Failed to enqueue message: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create candidate message queue: {str(e)}"
        )

    # enqueue() commits the transaction, refresh candidate from session
    db.refresh(candidate)

    # Background tasks AFTER commit
    background_tasks.add_task(run_auto_assign_ai_agent_in_background, candidate_id)

    return CandidateCreateResponse(
        candidate_id=candidate_id,
        candidate_is_first_time=True,
        candidate_password=password
    )


@router.get(
    "/all",
    response_model=AllCandidatesResponse,
    summary="List all candidates (CRUD operation)"
)
def get_all_candidates(
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin)
):
    """
    Get all candidates with their complete information.

    CRUD operation: Read only (no modifications).
    BU scoped: Respects business unit access policies.
    """
    candidates = apply_bu_scope_to_candidate_query(
        db, db.query(Candidate), current_user=user,
    ).all()

    candidates_data = []
    for candidate in candidates:
        name_parts = [
            candidate.candidateFirstName or "",
            candidate.candidateMiddleName or "",
            candidate.candidateLastName or ""
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

        candidate_response = CandidateCompleteResponse(
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
    "/{candidate_id}",
    response_model=CandidateCompleteResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get candidate by ID (CRUD operation)"
)
def get_candidate_by_id(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin)
):
    """
    Get full details of a single candidate by ID.

    CRUD operation: Read only (no modifications).
    BU scoped: Respects business unit access policies.
    """
    candidate = get_candidate_by_id_with_bu_scope(db, candidate_id, user)
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID '{candidate_id}' not found"
        )

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

    candidate_status = db.query(CandidateStatus).filter(
        CandidateStatus.candidateID == candidate_id
    ).first()

    return CandidateCompleteResponse(
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
        resume_completeness_score=candidate.resume_completeness_score,
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
    "/by-bu",
    response_model=AllCandidatesResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get candidates by Business Unit (CRUD operation)"
)
def get_candidates_by_my_bu(
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
    include_org_pool: bool = Query(
        default=False,
        description="Include Org Pool candidates in result"
    ),
    pipeline_status: Optional[str] = Query(
        default=None,
        description="Filter by pipeline status"
    ),
):
    """
    Get all candidates owned by the user's Business Unit.

    CRUD operation: Read only (no modifications).
    BU scoped: Returns only BU-owned candidates.
    """
    from app.models.candidate_ownership import CandidateOwnership, POOL_BU, POOL_ORG

    calling_user = db.query(Users).filter(Users.UserID == user.UserID).first()
    bu_id = calling_user.business_unit_id if calling_user else None

    if not bu_id:
        raise HTTPException(
            status_code=400,
            detail="Your account is not assigned to any Business Unit"
        )

    ownership_query = db.query(CandidateOwnership).filter(
        CandidateOwnership.owned_by_bu_id == bu_id,
        CandidateOwnership.pool_status == POOL_BU,
    )
    bu_candidate_ids = {row.candidateID for row in ownership_query.all()}

    if include_org_pool:
        owned_ids = {row.candidateID for row in db.query(CandidateOwnership).all()}
        all_candidate_ids = db.query(Candidate.candidateID).all()
        org_pool_ids = {row.candidateID for row in all_candidate_ids} - owned_ids
        org_pool_rows = db.query(CandidateOwnership).filter(
            CandidateOwnership.pool_status == POOL_ORG
        ).all()
        org_pool_ids.update(row.candidateID for row in org_pool_rows)
        bu_candidate_ids.update(org_pool_ids)

    if not bu_candidate_ids:
        return AllCandidatesResponse(total_candidates=0, candidates=[])

    candidate_query = db.query(Candidate).filter(
        Candidate.candidateID.in_(bu_candidate_ids)
    )

    if pipeline_status:
        candidate_query = candidate_query.join(
            CandidateStatus,
            CandidateStatus.candidateID == Candidate.candidateID,
            isouter=True,
        ).filter(CandidateStatus.piplineStatus == pipeline_status)

    candidates = candidate_query.all()

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
    "/{candidate_id}",
    response_model=CandidateCompleteResponse,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Update candidate (CRUD operation)"
)
def update_candidate(
    candidate_id: str,
    request: CandidateUpdateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin)
):
    """
    Update an existing candidate.

    CRUD operation: Update only (no workflows).
    Single atomic commit with no queue messages.
    """
    candidate = get_candidate_by_id_with_bu_scope(db, candidate_id, user)
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {candidate_id} not found"
        )

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

    try:
        db.commit()
        db.refresh(candidate)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update candidate: {str(e)}"
        )

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
    "/{candidate_id}",
    response_model=DeleteResponse,
    dependencies=[Depends(require_resource_permission("candidates", "delete"))],
    summary="Delete candidate (CRUD operation)"
)
def delete_candidate(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin)
):
    """
    Delete a candidate and all associated records.

    CRUD operation: Delete only (no workflows).
    Cascades deletion through all child records in proper FK order.
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {candidate_id} not found"
        )

    # Delete child records in FK-safe order (deepest children first)
    feedback_ids = [
        row.id for row in
        db.query(Interview.id).filter(Interview.candidate_id == candidate_id).all()
    ]
    if feedback_ids:
        db.query(InterviewFeedback).filter(InterviewFeedback.interview_id.in_(feedback_ids)).delete(synchronize_session=False)

    panel_ids = [
        row.id for row in
        db.query(InterviewPanel.id).filter(InterviewPanel.candidate_id == candidate_id).all()
    ]
    if panel_ids:
        db.query(PanelMember).filter(PanelMember.panel_id.in_(panel_ids)).delete(synchronize_session=False)

    db.query(Interview).filter(Interview.candidate_id == candidate_id).delete(synchronize_session=False)
    db.query(InterviewPanel).filter(InterviewPanel.candidate_id == candidate_id).delete(synchronize_session=False)
    db.query(CandidateAssignment).filter(CandidateAssignment.candidate_id == candidate_id).delete(synchronize_session=False)
    db.query(CandidateDocument).filter(CandidateDocument.candidate_id == candidate_id).delete(synchronize_session=False)

    db.query(CandidateInfoForm).filter(CandidateInfoForm.candidateID == candidate_id).delete(synchronize_session=False)
    db.query(CandidateEducationForm).filter(CandidateEducationForm.candidateID == candidate_id).delete(synchronize_session=False)
    db.query(CandidateExperienceForm).filter(CandidateExperienceForm.candidateID == candidate_id).delete(synchronize_session=False)
    db.query(CandidateAadharForm).filter(CandidateAadharForm.candidateID == candidate_id).delete(synchronize_session=False)
    db.query(CandidatePanForm).filter(CandidatePanForm.candidateID == candidate_id).delete(synchronize_session=False)
    db.query(CandidateStatus).filter(CandidateStatus.candidateID == candidate_id).delete(synchronize_session=False)

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

    db.query(CandidateHistory).filter(
        CandidateHistory.candidateID == candidate_id
    ).delete(synchronize_session=False)

    db.query(OfferLetter).filter(
        OfferLetter.candidate_id == candidate_id
    ).delete(synchronize_session=False)

    db.query(InternalNote).filter(
        InternalNote.candidate_id == candidate_id
    ).delete(synchronize_session=False)

    db.query(ATSScore).filter(
        ATSScore.candidate_id == candidate_id
    ).delete(synchronize_session=False)

    db.query(HRAssignment).filter(
        HRAssignment.candidate_id == candidate_id
    ).delete(synchronize_session=False)

    db.query(CandidateOwnership).filter(
        CandidateOwnership.candidateID == candidate_id
    ).delete(synchronize_session=False)

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

    db.query(CandidateJobApplication).filter(
        CandidateJobApplication.candidate_id == candidate_id
    ).delete(synchronize_session=False)

    db.delete(candidate)
    db.commit()

    return DeleteResponse(
        status="Success",
        message=f"Candidate with ID {candidate_id} and all associated records deleted successfully"
    )
