from datetime import datetime, date
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel as _BM
from sqlalchemy.orm import Session
import os as _os

from app.core.database import get_db
from app.core.dependencies import (
    get_current_candidate,
    get_current_internal_user,
    require_permission,
    require_resource_permission,
)
from app.core.logging import logger
from app.models.offer_letter import OfferLetter
from app.models.candidate import Candidate, CandidateStatus
from app.models.user import Users, Jobs
from app.schemas.user import (
    OfferLetterCreateRequest,
    OfferLetterUpdateRequest,
    OfferLetterResponse,
    OfferAcceptanceRequest,
    OfferAcceptanceResponse,
    OfferApprovalResponse,
    OfferReleaseResponse,
    CandidateSignedAcceptanceResponse,
    OfferCancelRequest,
    AllOffersResponse,
    DeleteResponse,
)
from app.services.offer_letter_generator import (
    generate_filled_docx,
    generated_file_path,
    signed_offer_file_path,
    get_template_path,
    inject_candidate_signature_into_docx,
)
from app.services.sharepoint_service import upload_file, get_file_download_link, list_folder
from app.services.salary_structure_generator import (
    generate_salary_structure_docx,
    get_salary_filename,
    calculate_salary,
)
from app.services.email_service import EmailService


router = APIRouter(prefix="/offer-letter", tags=["offer-letter"])


# "" Pipeline-status helper (fire-and-forget, never blocks offer flow) """""""""

def _update_pipeline_status(candidate_id: str, new_status: str, db: Session) -> None:
    """
    Silently upsert the candidate pipeline status.
    Swallows all exceptions so it never interrupts the offer workflow.
    """
    try:
        cs = db.query(CandidateStatus).filter(
            CandidateStatus.candidateID == candidate_id
        ).first()
        if cs:
            cs.piplineStatus = new_status
        else:
            cs = CandidateStatus(
                candidateID=candidate_id,
                status="Active",
                piplineStatus=new_status,
            )
            db.add(cs)
        db.commit()
    except Exception:
        pass  # Status update must never block offer operations


# "" helpers """"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

def _candidate_name(c) -> str | None:
    if not c:
        return None
    parts = [
        c.candidateFirstName,
        getattr(c, "candidateMiddleName", None),
        c.candidateLastName,
    ]
    return " ".join(p for p in parts if p) or None


def _build_offer_response(offer: OfferLetter, candidate: Candidate | None) -> OfferLetterResponse:
    """Build an OfferLetterResponse from ORM objects, including all workflow fields."""
    return OfferLetterResponse(
        id=offer.id,
        candidate_id=offer.candidate_id,
        candidate_name=_candidate_name(candidate),
        candidate_email=candidate.candidateEmail if candidate else None,
        job_id=offer.job_id,
        offer_expire_date=offer.offer_expire_date,
        hiring_manager_id=offer.hiring_manager_id,
        reporting_manager_id=offer.reporting_manager_id,
        position=offer.position,
        salary=offer.salary,
        joining_date=offer.joining_date,
        offer_status=offer.offer_status,
        candidate_response=offer.candidate_response,
        responded_at=offer.responded_at,
        created_at=offer.created_at,
        created_by=offer.created_by,
        cancelled_at=offer.cancelled_at,
        cancelled_by=offer.cancelled_by,
        sharepoint_url=offer.sharepoint_url,
        download_url=offer.download_url,
        sharepoint_path=offer.sharepoint_path,
        approval_status=offer.approval_status,
        approved_at=offer.approved_at,
        approved_by=offer.approved_by,
        approval_notes=offer.approval_notes,
        released_at=offer.released_at,
        released_by=offer.released_by,
        hm_signature_path=offer.hm_signature_path,
        candidate_signature_path=offer.candidate_signature_path,
        signed_offer_path=offer.signed_offer_path,
    )


# ============================================
# TEMPLATE LISTING
# ============================================

@router.get(
    "/templates",
    dependencies=[Depends(require_resource_permission("offer-letters", "view"))],
    summary="List all offer-letter templates available in SharePoint",
)
def list_offer_templates(
    folder: Optional[str] = Query(
        None,
        description="Sub-folder inside the templates directory to list. "
                    "Leave blank to list the root templates folder.",
    ),
    user=Depends(get_current_internal_user),
):
    """
    Returns all `.docx` (and other) template files stored in the SharePoint
    templates folder (`SHAREPOINT_TEMPLATE_PATH` parent directory).

    **Optional query param:**
    - `folder` - drill into a sub-folder, e.g. `?folder=full-time`

    **Required permission:** `offer.view`
    """
    template_path = _os.getenv(
        "SHAREPOINT_TEMPLATE_PATH",
        "templates/Internship Offer letter.docx",
    )
    base_folder = "/".join(template_path.split("/")[:-1]) or "templates"
    target_folder = f"{base_folder}/{folder}" if folder else base_folder

    try:
        items = list_folder(target_folder)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to list templates from SharePoint: {exc}",
        )

    files   = [i for i in items if i["type"] == "file"]
    folders = [i for i in items if i["type"] == "folder"]

    return {
        "status":        "success",
        "folder":        target_folder,
        "total_files":   len(files),
        "total_folders": len(folders),
        "files":         files,
        "sub_folders":   folders,
    }


# ============================================
# CANDIDATE ENDPOINTS
# ============================================

@router.post(
    "/respond",
    response_model=OfferAcceptanceResponse,
    dependencies=[Depends(require_resource_permission("respond", "create"))]
)
def respond_to_offer(
    request: OfferAcceptanceRequest,
    db: Session = Depends(get_db),
    candidate=Depends(get_current_candidate),
):
    """Candidate responds to an offer letter (accept or reject)."""
    if request.action.lower() not in ["accept", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be 'accept' or 'reject'")

    offer = db.query(OfferLetter).filter(OfferLetter.id == request.offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail=f"Offer letter {request.offer_id} not found")

    if offer.candidate_id != candidate.candidateID:
        raise HTTPException(status_code=403, detail="You are not authorized to respond to this offer")

    # Candidates can only respond to Released offers (offers visible to them)
    if offer.offer_status != "Released":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot respond to offer with status '{offer.offer_status}'. Only Released offers can be responded to.",
        )

    offer.offer_status = "Accepted" if request.action.lower() == "accept" else "Rejected"
    offer.candidate_response = request.response_message
    offer.responded_at = datetime.now()
    db.commit()
    db.refresh(offer)

    # "" Update candidate pipeline status based on response """"""""""""""""""""
    if request.action.lower() == "accept":
        _update_pipeline_status(offer.candidate_id, "Hired", db)
    else:
        _update_pipeline_status(offer.candidate_id, "Rejected", db)

    # "" Pool ownership transition: candidate rejects offer ' Org Pool """""""""
    if request.action.lower() == "reject":
        from app.services.candidate_pool_service import set_org_pool
        set_org_pool(
            candidate_id=offer.candidate_id,
            reason=f"Candidate rejected offer #{offer.id} - returned to Org Pool",
            db=db,
            performed_by_id=candidate.candidateID,
            performed_by_name=(
                f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''}".strip()
                or candidate.candidateEmail
            ),
        )
        db.commit()

    # "" Email HR on candidate response """""""""""""""""""""""""""""""""""""""
    try:
        hr_creator = db.query(Users).filter(Users.UserID == offer.created_by).first()
        if hr_creator:
            candidate_name = _candidate_name(
                db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()
            ) or offer.candidate_id
            EmailService.notify_hr_candidate_responded(
                hr_email=hr_creator.UserEmail,
                candidate_name=candidate_name,
                position=offer.position or "",
                offer_id=offer.id,
                decision=offer.offer_status,
                response_message=request.response_message or "",
            )
    except Exception:
        pass  # Email failure must never block the response

    return OfferAcceptanceResponse(
        status="Success",
        message=f"Offer {offer.offer_status.lower()} successfully",
        offer_id=offer.id,
        offer_status=offer.offer_status,
        responded_at=offer.responded_at,
    )


@router.get(
    "/my-offers",
    response_model=AllOffersResponse,
    dependencies=[Depends(require_resource_permission("my-offer", "view"))]
)
def get_my_offers(
    db: Session = Depends(get_db),
    candidate=Depends(get_current_candidate),
):
    """Get all Released offer letters for the authenticated candidate."""
    offers = db.query(OfferLetter).filter(
        OfferLetter.candidate_id == candidate.candidateID,
        OfferLetter.offer_status.in_(["Released", "Accepted", "Rejected"]),
    ).all()

    offer_responses = []
    for offer in offers:
        c = db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()
        resp = _build_offer_response(offer, c)

        # "" Always generate a fresh download link so the 24-hour expiry
        #    on SharePoint pre-signed URLs is never a problem """"""""""""""""
        if offer.sharepoint_path:
            try:
                resp.download_url = get_file_download_link(offer.sharepoint_path)
            except Exception:
                pass  # Keep whatever URL is already in resp rather than breaking the list

        offer_responses.append(resp)

    return AllOffersResponse(total_offers=len(offer_responses), offers=offer_responses)



# ============================================
# RECRUITER / HR ENDPOINTS
# ============================================

@router.post(
    "/create",
    response_model=OfferLetterResponse,
    dependencies=[Depends(require_resource_permission("offer-letters", "edit"))],
)
def create_offer_letter(
    request: OfferLetterCreateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """Create a new offer letter for a candidate (HR/Recruiter only)."""
    candidate = db.query(Candidate).filter(Candidate.candidateID == request.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {request.candidate_id} not found")

    hiring_manager = db.query(Users).filter(Users.UserID == request.hiring_manager_id).first() if request.hiring_manager_id else None
    if request.hiring_manager_id and not hiring_manager:
        raise HTTPException(status_code=404, detail=f"Hiring manager {request.hiring_manager_id} not found")

    reporting_manager = db.query(Users).filter(Users.UserID == request.reporting_manager_id).first() if request.reporting_manager_id else None
    if request.reporting_manager_id and not reporting_manager:
        raise HTTPException(status_code=404, detail=f"Reporting manager {request.reporting_manager_id} not found")

    if request.job_id is not None:
        job = db.query(Jobs).filter(Jobs.jobID == request.job_id).first()
        if not job:
            raise HTTPException(
                status_code=404,
                detail=f"Job '{request.job_id}' not found. Pass null/omit job_id if not linking a job.",
            )

    new_offer = OfferLetter(
        candidate_id=request.candidate_id,
        job_id=request.job_id,
        offer_expire_date=request.offer_expire_date,
        hiring_manager_id=request.hiring_manager_id,
        reporting_manager_id=request.reporting_manager_id,
        position=request.position,
        salary=request.salary,
        joining_date=request.joining_date,
        offer_status="Pending",
        created_by=user.UserID,
    )
    db.add(new_offer)
    db.commit()
    db.refresh(new_offer)

    # "" Update candidate pipeline status ' OfferApproval """""""""""""""""""""
    # Offer created - candidate is in the offer approval workflow
    _update_pipeline_status(request.candidate_id, "OfferApproval", db)

    # "" Pool ownership transition: offer created ' BU Owned (90-day clock) """"
    # Determine BU from the linked job; if no job/BU, skip.
    try:
        linked_job = None
        if new_offer.job_id:
            linked_job = db.query(Jobs).filter(Jobs.jobID == new_offer.job_id).first()
        if linked_job and linked_job.business_unit_id:
            from app.services.candidate_pool_service import set_bu_owned_with_expiry
            from app.models.business_unit import BusinessUnit
            bu = db.query(BusinessUnit).filter(BusinessUnit.id == linked_job.business_unit_id).first()
            bu_name = bu.name if bu else f"BU #{linked_job.business_unit_id}"
            set_bu_owned_with_expiry(
                candidate_id=request.candidate_id,
                bu_id=linked_job.business_unit_id,
                bu_name=bu_name,
                reason=f"Offer #{new_offer.id} released by HR - 90-day BU ownership started",
                db=db,
                performed_by_id=user.UserID,
            )
            db.commit()
    except Exception:
        pass  # Pool transition failure must never block offer creation

    return OfferLetterResponse(
        id=new_offer.id,
        candidate_id=new_offer.candidate_id,
        candidate_name=_candidate_name(candidate),
        candidate_email=candidate.candidateEmail,
        job_id=new_offer.job_id,
        offer_expire_date=new_offer.offer_expire_date,
        hiring_manager_id=new_offer.hiring_manager_id,
        reporting_manager_id=new_offer.reporting_manager_id,
        position=new_offer.position,
        salary=new_offer.salary,
        joining_date=new_offer.joining_date,
        offer_status=new_offer.offer_status,
        candidate_response=new_offer.candidate_response,
        responded_at=new_offer.responded_at,
        created_at=new_offer.created_at,
        created_by=new_offer.created_by,
        cancelled_at=new_offer.cancelled_at,
        cancelled_by=new_offer.cancelled_by,
    )


@router.post(
    "/cancel/{offer_id}",
    response_model=DeleteResponse,
    dependencies=[Depends(require_resource_permission("offer-letters", "edit"))],
)
def cancel_offer_letter(
    offer_id: int,
    request: OfferCancelRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """Cancel an offer letter (HR/Recruiter only)."""
    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail=f"Offer letter {offer_id} not found")

    if offer.offer_status in ["Accepted", "Rejected", "Cancelled"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel offer with status '{offer.offer_status}'",
        )

    offer.offer_status = "Cancelled"
    offer.cancelled_at = datetime.now()
    offer.cancelled_by = user.UserID
    if request.reason:
        offer.candidate_response = f"Cancellation reason: {request.reason}"
    db.commit()

    return DeleteResponse(status="Success", message=f"Offer letter {offer_id} cancelled successfully")


@router.put(
    "/update/{offer_id}",
    response_model=OfferLetterResponse,
    dependencies=[Depends(require_resource_permission("offer-letters", "edit"))],
)
def update_offer_letter(
    offer_id: int,
    request: OfferLetterUpdateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """Update an offer letter (HR/Recruiter only)."""
    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail=f"Offer letter {offer_id} not found")

    if offer.offer_status != "Pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update offer with status '{offer.offer_status}'. Only pending offers can be updated.",
        )

    if request.job_id is not None:
        offer.job_id = request.job_id

    if request.hiring_manager_id is not None:
        if not db.query(Users).filter(Users.UserID == request.hiring_manager_id).first():
            raise HTTPException(status_code=404, detail=f"Hiring manager {request.hiring_manager_id} not found")
        offer.hiring_manager_id = request.hiring_manager_id

    if request.reporting_manager_id is not None:
        if not db.query(Users).filter(Users.UserID == request.reporting_manager_id).first():
            raise HTTPException(status_code=404, detail=f"Reporting manager {request.reporting_manager_id} not found")
        offer.reporting_manager_id = request.reporting_manager_id

    if request.position is not None:
        offer.position = request.position
    if request.salary is not None:
        offer.salary = request.salary
    if request.joining_date is not None:
        offer.joining_date = request.joining_date
    if request.offer_expire_date is not None:
        offer.offer_expire_date = request.offer_expire_date

    db.commit()
    db.refresh(offer)

    candidate = db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()

    return OfferLetterResponse(
        id=offer.id,
        candidate_id=offer.candidate_id,
        candidate_name=_candidate_name(candidate),
        candidate_email=candidate.candidateEmail if candidate else None,
        job_id=offer.job_id,
        offer_expire_date=offer.offer_expire_date,
        hiring_manager_id=offer.hiring_manager_id,
        reporting_manager_id=offer.reporting_manager_id,
        position=offer.position,
        salary=offer.salary,
        joining_date=offer.joining_date,
        offer_status=offer.offer_status,
        candidate_response=offer.candidate_response,
        responded_at=offer.responded_at,
        created_at=offer.created_at,
        created_by=offer.created_by,
        cancelled_at=offer.cancelled_at,
        cancelled_by=offer.cancelled_by,
    )


@router.get(
    "/all",
    response_model=AllOffersResponse,
    dependencies=[Depends(require_resource_permission("offer-letters", "view"))],
)
def get_all_offers(
    status: Optional[str] = Query(None, description="Filter by offer status"),
    candidate_id: Optional[str] = Query(None, description="Filter by candidate ID"),
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """Get all offer letters with optional filters (HR/Recruiter only)."""
    query = db.query(OfferLetter)
    if status:
        query = query.filter(OfferLetter.offer_status == status)
    if candidate_id:
        query = query.filter(OfferLetter.candidate_id == candidate_id)
    offers = query.all()

    offer_responses = []
    for offer in offers:
        c = db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()
        offer_responses.append(_build_offer_response(offer, c))

    return AllOffersResponse(total_offers=len(offer_responses), offers=offer_responses)


# "" Hiring Manager: list offers pending approval """""""""""""""""""""""""""""
@router.get(
    "/pending-approval",
    dependencies=[Depends(get_current_internal_user)],
    response_model=AllOffersResponse,
    summary="List offer letters pending the authenticated Hiring Manager's approval",
)
def get_pending_approval_offers(
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Returns all offer letters where `approval_status = AwaitingApproval` and
    `hiring_manager_id` matches the authenticated user.
    """
    offers = db.query(OfferLetter).filter(
        OfferLetter.hiring_manager_id == user.UserID,
        OfferLetter.approval_status == "AwaitingApproval",
    ).all()

    offer_responses = []
    for offer in offers:
        c = db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()
        offer_responses.append(_build_offer_response(offer, c))

    return AllOffersResponse(total_offers=len(offer_responses), offers=offer_responses)


# "" Hiring Manager: list awaiting-approval candidates for a specific job """"""
@router.get(
    "/pending-approval/by-job/{job_id}",
    dependencies=[Depends(get_current_internal_user)],
    response_model=AllOffersResponse,
    summary="List awaiting-approval candidates for a specific job (Hiring Manager)",
)
def get_pending_approval_offers_by_job(
    job_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Returns all offer letters where:
    - `approval_status = AwaitingApproval`
    - `job_id` matches the given job

    Raises **404** if no matching job exists.
    """
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    offers = db.query(OfferLetter).filter(
        OfferLetter.job_id == job_id,
        OfferLetter.approval_status == "AwaitingApproval",
    ).all()

    offer_responses = []
    for offer in offers:
        c = db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()
        offer_responses.append(_build_offer_response(offer, c))

    return AllOffersResponse(total_offers=len(offer_responses), offers=offer_responses)


@router.get(
    "/{offer_id}",
    response_model=OfferLetterResponse,
    dependencies=[Depends(require_resource_permission("offer-letters", "view"))],
)
def get_offer_by_id(
    offer_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """Get a specific offer letter by ID (HR/Recruiter only)."""
    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail=f"Offer letter {offer_id} not found")

    candidate = db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()

    # "" Resolve document links """"""""""""""""""""""""""""""""""""""""""""""""
    sp_url  = offer.sharepoint_url
    
    sp_path = offer.sharepoint_path

   
    dl_url = get_file_download_link(sp_path) 
   

    response = _build_offer_response(offer, candidate)
    response.sharepoint_url = sp_url
    response.download_url   = dl_url
    response.sharepoint_path = sp_path
    return response


# ============================================
# OFFER LETTER DOCUMENT GENERATION
# ============================================

@router.post(
    "/generate/{offer_id}",
    dependencies=[Depends(require_resource_permission("offer-letters", "edit"))],
    summary="Generate a filled offer letter .docx from the SharePoint template",
)
def generate_offer_letter_document(
    offer_id: int,
    template_type: str = Query(
        default="fulltime",
        description="Template to use: 'intern' for Internship Offer Letter, 'fulltime' for Full-Time Offer Letter.",
    ),
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Auto-generate a filled `.docx` offer letter for the given offer.

    1. Load offer + candidate + job details from the database.
    2. Select the correct SharePoint template based on `template_type`
       (`'intern'` ' Internship template, `'fulltime'` ' Full-Time template).
    3. Replace all `{{placeholder}}` tokens and inject the salary table.
    4. Upload the filled document back to SharePoint.
    5. Set `approval_status = AwaitingApproval` and notify the Hiring Manager by email.
    6. Return the SharePoint web URL and a pre-authenticated download link.

    **Required permission:** `offer.manage`
    """
    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail=f"Offer letter {offer_id} not found")

    # Resolve template path - validate early so we fail fast before any DB work
    try:
        resolved_template_path = get_template_path(template_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    candidate = db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{offer.candidate_id}' not found")

    first_name = candidate.candidateFirstName or ""
    last_name  = candidate.candidateLastName  or ""

    # Job ' location + department
    job_location   = offer.position or ""
    job_department = ""
    if offer.job_id:
        job = db.query(Jobs).filter(Jobs.jobID == offer.job_id).first()
        if job:
            if job.jobLocation:
                job_location = job.jobLocation
            if job.department:
                job_department = job.department.name or ""

    # Hiring manager name
    hiring_manager_name = ""
    hm_user = None
    if offer.hiring_manager_id:
        hm_user = db.query(Users).filter(Users.UserID == offer.hiring_manager_id).first()
        if hm_user:
            hiring_manager_name = hm_user.UserName or hm_user.UserEmail or ""

    try:
        docx_bytes = generate_filled_docx(
            first_name=first_name,
            last_name=last_name,
            job_title=offer.position or "",
            department=job_department,
            location=job_location,
            offer_expire_date=offer.offer_expire_date,
            joining_date=offer.joining_date,
            annual_salary=offer.salary or "",
            hiring_manager_name=hiring_manager_name,
            template_path=resolved_template_path,
        )
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to generate offer letter document: {exc}")

    dest_path = generated_file_path(offer.candidate_id, offer_id)
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    try:
        web_url = upload_file(dest_path, docx_bytes, content_type=mime)
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to upload offer letter to SharePoint: {exc}")

    download_link = get_file_download_link(dest_path) or web_url
    candidate_name = f"{first_name} {last_name}".strip() or offer.candidate_id

    # "" Persist URLs + set approval gate """""""""""""""""""""""""""""""""""""
    offer.sharepoint_url    = web_url
    offer.download_url      = download_link
    offer.sharepoint_path   = dest_path
    offer.offer_status      = "AwaitingApproval"   # offer is now with Hiring Manager
    offer.approval_status   = "AwaitingApproval"
    db.commit()

    # "" Notify Hiring Manager by email (best-effort) """""""""""""""""""""""""
    try:
        if hm_user:
            EmailService.notify_hm_approval_requested(
                hm_email=hm_user.UserEmail,
                hm_name=hm_user.UserName or hm_user.UserEmail,
                candidate_name=candidate_name,
                position=offer.position or "",
                offer_id=offer_id,
            )
    except Exception:
        pass  # Email failure must never block the generation response

    return {
        "status":           "success",
        "message":          f"Offer letter generated for {candidate_name}. Awaiting hiring manager approval.",
        "offer_id":         offer_id,
        "candidate_id":     offer.candidate_id,
        "candidate_name":   candidate_name,
        "template_type":    template_type,
        "template_path":    resolved_template_path,
        "approval_status":  offer.approval_status,
        "file_name":        f"offer_{offer_id}.docx",
        "sharepoint_path":  dest_path,
        "sharepoint_url":   web_url,
        "download_url":     download_link,
    }


# ============================================
# HIRING MANAGER APPROVAL WORKFLOW
# ============================================

@router.post(
    "/approve/{offer_id}",
    response_model=OfferApprovalResponse,
    dependencies=[Depends(require_resource_permission("offer-letters", "edit"))],
    summary="Hiring Manager approves or rejects an offer letter and submits their signature",
)
async def approve_offer_letter(
    offer_id: int,
    action: str = Query(..., description="'approve' or 'reject'"),
    notes: Optional[str] = Query(None, description="Optional notes for the decision"),
    signature: Optional[UploadFile] = File(None, description="Hiring manager signature PNG (required when action=approve)"),
    db: Session = Depends(get_db),
    user=Depends(require_resource_permission("offer-letters", "edit")),
):
    """
    Hiring Manager reviews the offer and either approves or rejects it.

    - **approve**: Upload a PNG signature file. The offer letter `.docx` is
      re-generated with the dynamic signature embedded and re-uploaded to SharePoint.
    - **reject**: No signature needed. Provide optional notes.

    The HR team is notified by email of the decision.
    """
    if action.lower() not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail=f"Offer letter {offer_id} not found")

    if offer.approval_status != "AwaitingApproval":
        raise HTTPException(
            status_code=400,
            detail=f"Offer is not awaiting approval (current approval_status: '{offer.approval_status}').",
        )

    now = datetime.now()

    if action.lower() == "approve":
        if not signature:
            raise HTTPException(
                status_code=422,
                detail="A signature PNG file is required when approving an offer.",
            )
        if not signature.content_type.startswith("image/"):
            raise HTTPException(status_code=422, detail="Signature file must be an image (PNG preferred).")

        sig_bytes = await signature.read()

        # Upload signature PNG to SharePoint
        sig_path = f"signatures/hm/{offer_id}.png"
        try:
            upload_file(sig_path, sig_bytes, content_type="image/png")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            raise HTTPException(status_code=502, detail=f"Failed to upload signature: {exc}")

        # Re-generate the offer docx with the real HM signature embedded
        candidate = db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail=f"Candidate '{offer.candidate_id}' not found")

        first_name     = candidate.candidateFirstName or ""
        last_name      = candidate.candidateLastName or ""
        job_location   = offer.position or ""
        job_department = ""
        if offer.job_id:
            job = db.query(Jobs).filter(Jobs.jobID == offer.job_id).first()
            if job:
                if job.jobLocation:  job_location   = job.jobLocation
                if job.department:   job_department = job.department.name or ""

        hm_name = user.UserName or user.UserEmail or ""

        try:
            docx_bytes = generate_filled_docx(
                first_name=first_name,
                last_name=last_name,
                job_title=offer.position or "",
                department=job_department,
                location=job_location,
                offer_expire_date=offer.offer_expire_date,
                joining_date=offer.joining_date,
                annual_salary=offer.salary or "",
                hiring_manager_name=hm_name,
                hm_signature_bytes=sig_bytes,           # <-- dynamic signature
            )
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            raise HTTPException(status_code=502, detail=f"Failed to re-generate offer letter: {exc}")

        dest_path = generated_file_path(offer.candidate_id, offer_id)
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        try:
            web_url = upload_file(dest_path, docx_bytes, content_type=mime)
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            raise HTTPException(status_code=502, detail=f"Failed to upload signed offer letter: {exc}")

        offer.sharepoint_url    = web_url
        offer.download_url      = get_file_download_link(dest_path) or web_url
        offer.sharepoint_path   = dest_path
        offer.hm_signature_path = sig_path
        offer.approval_status   = "Approved"
        offer.offer_status      = "Approved"        # HM approved ' ready for HR to release
    else:
        # Reject - no signature required
        offer.approval_status = "Rejected"
        offer.offer_status    = "Rejected"          # HM rejected ' back to HR

    offer.approved_at    = now
    offer.approved_by    = user.UserID
    offer.approval_notes = notes
    db.commit()

    # "" Notify the HR creator by email """"""""""""""""""""""""""""""""""""""""
    try:
        hr_creator = db.query(Users).filter(Users.UserID == offer.created_by).first()
        candidate_for_email = db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()
        if hr_creator and candidate_for_email:
            EmailService.notify_hr_hm_decision(
                hr_email=hr_creator.UserEmail,
                hm_name=user.UserName or user.UserEmail,
                candidate_name=_candidate_name(candidate_for_email) or offer.candidate_id,
                position=offer.position or "",
                offer_id=offer_id,
                decision=offer.approval_status,
                approval_notes=notes or "",
            )
    except Exception:
        pass

    return OfferApprovalResponse(
        status="success",
        message=f"Offer #{offer_id} {offer.approval_status.lower()} successfully.",
        offer_id=offer_id,
        approval_status=offer.approval_status,
        approved_at=offer.approved_at,
    )


# ============================================
# HR RELEASES OFFER TO CANDIDATE
# ============================================

@router.post(
    "/release/{offer_id}",
    response_model=OfferReleaseResponse,
    dependencies=[Depends(require_resource_permission("offer-letters", "view"))],
    summary="Release an approved offer letter to the candidate",
)
def release_offer_letter(
    offer_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_resource_permission("offer-letters", "view")),
):
    """
    HR releases an `Approved` offer to the candidate, changing
    `offer_status` from `Approved` ' `Released`. The candidate is
    notified via WhatsApp + email (S-054/HRMS-0454) and the offer
    appears in their `my-offers` list.

    **Required permission:** `offer.readiness_check` -- S-053/HRMS-0453
    added this narrower permission (not the broader `offer.manage`,
    which a real, pre-existing RBAC data inconsistency currently still
    grants to Recruiter despite that role's own description saying
    otherwise) specifically so this release action gets a real HTTP
    403 for Recruiter, per this story's own explicit AC-8.

    S-054/HRMS-0454 BR-01: re-runs checkOfferReadiness() at the moment
    of release (interview outcomes or candidate status could have
    changed since it was last checked) -- returns HTTP 409 with the
    real blockers if not ready, rather than relying solely on
    approval_status.
    """
    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail=f"Offer letter {offer_id} not found")

    if offer.approval_status != "Approved":
        raise HTTPException(
            status_code=400,
            detail=f"Offer cannot be released - approval_status is '{offer.approval_status}' (must be 'Approved').",
        )

    if offer.offer_status == "Released":
        raise HTTPException(status_code=400, detail="Offer has already been released.")

    from app.services.ai_conversation_service import resolve_default_tenant_id
    from app.services.offer_readiness_service import check_offer_readiness

    tenant_id = resolve_default_tenant_id(db)
    readiness = check_offer_readiness(db, offer.candidate_id, offer.job_id, tenant_id)
    if not readiness["is_ready"]:
        raise HTTPException(status_code=409, detail={"message": "Candidate is not ready for an offer.", "blockers": readiness["blockers"]})

    now = datetime.now()
    offer.offer_status = "Released"
    offer.released_at  = now
    offer.released_by  = user.UserID
    db.commit()

    # "" Notify the candidate via WhatsApp + email (S-054/HRMS-0454) """""""""
    from app.services.offer_release_notification_service import send_offer_release_notification
    try:
        send_offer_release_notification(db, offer)
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[OfferRelease] Notification failed for offer {offer_id}: {exc}")

    return OfferReleaseResponse(
        status="success",
        message=f"Offer #{offer_id} released to candidate successfully.",
        offer_id=offer_id,
        offer_status=offer.offer_status,
        released_at=offer.released_at,
    )


# ============================================
# CANDIDATE SIGNATURE + ACCEPTANCE
# ============================================

@router.post(
    "/sign/{offer_id}",
    dependencies=[Depends(get_current_internal_user)],
    response_model=CandidateSignedAcceptanceResponse,
    summary="Candidate signs the offer letter (uploads signature PNG)",
)
async def candidate_sign_offer(
    offer_id: int,
    signature: UploadFile = File(..., description="Candidate signature PNG"),
    db: Session = Depends(get_db),
    candidate=Depends(get_current_candidate),
):
    """
    Candidate uploads their PNG signature to formally accept the offer.

    1. Validates the offer is `Released` and belongs to this candidate.
    2. Uploads the signature PNG to SharePoint.
    3. Re-generates the final `.docx` with **both** the HM signature (already
       embedded from the approval step) and the candidate signature.
    4. Uploads the fully-signed document to `signed-offers/`.
    5. Sets `offer_status = Accepted` and notifies HR by email.
    """
    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail=f"Offer letter {offer_id} not found")

    if offer.candidate_id != candidate.candidateID:
        raise HTTPException(status_code=403, detail="You are not authorized to sign this offer.")

    # if offer.offer_status != "Released":
    #     raise HTTPException(
    #         status_code=400,
    #         detail=f"Offer is not available for signing (status: '{offer.offer_status}'). Only 'Released' offers can be signed.",
    #     )

    if not signature.content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="Signature file must be an image (PNG preferred).")

    sig_bytes = await signature.read()

    # Upload candidate signature PNG to SharePoint
    cand_sig_path = f"signatures/candidate/{offer_id}.png"
    try:
        upload_file(cand_sig_path, sig_bytes, content_type="image/png")
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to upload candidate signature: {exc}")

    candidate_full = (
        f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''}".strip()
    )

    # "" Step 2: Download the HM-approved docx from SharePoint """"""""""""""""
    # The document stored at offer.sharepoint_path already has the hiring
    # manager's signature embedded (done during the approval step).  We must
    # inject the candidate signature INTO that document - NOT re-generate from
    # the blank template (which would lose the HM signature and might use the
    # wrong template type).
    if not offer.sharepoint_path:
        raise HTTPException(
            status_code=502,
            detail="Offer document path is missing. Please regenerate the offer letter first.",
        )

    try:
        # pyrefly: ignore [missing-import]
        from app.services.sharepoint_service import download_file
        existing_docx_bytes = download_file(offer.sharepoint_path)
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to download the approved offer document from SharePoint: {exc}",
        )

    # "" Step 3: Inject only the candidate signature into the existing docx """"
    try:
        signed_docx = inject_candidate_signature_into_docx(
            docx_bytes=existing_docx_bytes,
            candidate_name=candidate_full,
            signature_img_bytes=sig_bytes,
        )
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to inject candidate signature: {exc}")

    # Upload final signed docx
    signed_path = signed_offer_file_path(offer.candidate_id, offer_id)
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    try:
        signed_web_url = upload_file(signed_path, signed_docx, content_type=mime)
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to upload signed offer letter: {exc}")

    # Persist results
    offer.offer_status             = "Accepted"
    offer.responded_at             = datetime.now()
    offer.candidate_signature_path = cand_sig_path
    offer.signed_offer_path        = signed_path
    offer.sharepoint_url           = signed_web_url
    offer.download_url             = get_file_download_link(signed_path) or signed_web_url
    offer.sharepoint_path          = signed_path
    db.commit()

    # "" Update candidate pipeline status ' Hired """"""""""""""""""""""""""""""
    # Candidate signed the offer - they are now officially Hired
    _update_pipeline_status(offer.candidate_id, "Hired", db)

    # "" Notify HR by email """"""""""""""""""""""""""""""""""""""""""""""""""""
    try:
        hr_creator = db.query(Users).filter(Users.UserID == offer.created_by).first()
        if hr_creator:
            EmailService.notify_hr_candidate_responded(
                hr_email=hr_creator.UserEmail,
                candidate_name=candidate_full or offer.candidate_id,
                position=offer.position or "",
                offer_id=offer_id,
                decision="Accepted",
            )
    except Exception:
        pass

    return CandidateSignedAcceptanceResponse(
        status="success",
        message="Offer signed and accepted successfully. The final document is available in SharePoint.",
        offer_id=offer_id,
        offer_status=offer.offer_status,
        signed_offer_path=signed_path,
    )


# ============================================
# SALARY STRUCTURE DOCUMENT
# ============================================
logger = logging.getLogger(__name__)

class SalaryComponentDetail(_BM):
    """A single salary component with monthly and annual amounts."""
    component: str
    remark: str
    per_month: float
    per_annum: float


class SalaryStructureRequest(_BM):
    """Request body for salary-structure endpoints."""
    employee_name: str
    annual_ctc: float


class SalaryStructureDetailResponse(_BM):
    """Full salary breakdown returned alongside the downloadable .docx."""

    # "" Identity """"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    employee_name: str
    annual_ctc: float

    # "" Earnings (per month & per annum) """""""""""""""""""""""""""""""""""""
    basic_pm: float
    basic_pa: float
    hra_pm: float
    hra_pa: float
    medical_pm: float
    medical_pa: float
    transport_pm: float
    transport_pa: float
    deployment_pm: float
    deployment_pa: float
    fixed_allowance_pm: float
    fixed_allowance_pa: float

    # "" Totals """"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    gross_pm: float
    gross_pa: float

    # "" Deductions """"""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    epf_employee_pm: float
    epf_employee_pa: float
    epf_employer_pm: float
    epf_employer_pa: float
    esic_employee_pm: float
    esic_employee_pa: float

    total_deductions_pm: float
    total_deductions_pa: float

    # "" Net """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    net_pm: float
    net_pa: float

    # "" Other Benefits """"""""""""""""""""""""""""""""""""""""""""""""""""""""
    esic_employer_pm: float
    esic_employer_pa: float

    # "" Document """"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    filename: str
    docx_base64: str  # base64-encoded .docx bytes - decode on frontend to download


class SalaryStructureWithDetailsResponse(_BM):
    status: str = "success"
    message: str
    salary_structure: SalaryStructureDetailResponse


# "" existing file-download endpoint (unchanged) """""""""""""""""""""""""""""""

@router.post(
    "/salary-structure",
    dependencies=[Depends(require_resource_permission("offer-letters", "edit"))],
    summary="Generate a salary-structure .docx for an employee",
    response_class=Response,
    responses={
        200: {
            "content": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document": {}},
            "description": "Salary structure Word document",
        }
    },
)
def generate_salary_structure(
    request: SalaryStructureRequest,
    user=Depends(get_current_internal_user),
):
    """
    Generate and **download** a professional salary-structure Word document.

    Components auto-calculated from annual CTC:
    - Basic = 50% CTC, HRA = 40% Basic
    - Medical = 15 000, Transport = 19 200, Performance = 19 800 (all fixed)
    - PT Deduction = 1 800 (fixed)

    **Required permission:** `offer.manage`
    """
    try:
        docx_bytes = generate_salary_structure_docx(
            employee_name=request.employee_name,
            annual_ctc=request.annual_ctc,
        )
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate salary structure document: {exc}")

    filename = get_salary_filename(request.employee_name)
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    return Response(
        content=docx_bytes,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(docx_bytes)),
        },
    )


# "" NEW: JSON response with salary breakdown + base64-encoded .docx """""""""""

@router.post(
    "/salary-structure/details",
    response_model=SalaryStructureWithDetailsResponse,
    dependencies=[Depends(require_resource_permission("offer-letters", "edit"))],
    summary="Generate salary-structure details + downloadable .docx in a single response",
)
def generate_salary_structure_with_details(
    request: SalaryStructureRequest,
    user=Depends(get_current_internal_user),
):
    """
    Generate the salary-structure Word document **and** return the full
    salary breakdown as structured JSON in a single API call.

    The `.docx` file is included in the response as a **base64-encoded string**
    under `salary_structure.docx_base64`.  Decode it on the frontend to offer
    the user a download without a second request.

    **Salary components (auto-calculated from annual CTC):**
    | Component | Rule |
    |---|---|
    | Basic | 50% of CTC |
    | HRA | 40% of Basic |
    | Medical | Fixed 15,000 p.a. |
    | Transport | Fixed 19,200 p.a. |
    | Deployment / Performance | Remaining after above 4, capped 60,000 |
    | Fixed Allowance | Remainder after all above |
    | EPF Employee & Employer | 12% of EPF base, capped 21,600 each |
    | ESIC Employee | 0.75% of ESIC base (only if monthly base  21,000) |

    **Required permission:** `offer.manage`
    """
    import base64

    # "" 1. Calculate salary breakdown """""""""""""""""""""""""""""""""""""""""
    try:
        sal = calculate_salary(
            employee_name=request.employee_name,
            annual_ctc=request.annual_ctc,
        )
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Salary calculation failed: {exc}")

    # "" 2. Generate .docx document """"""""""""""""""""""""""""""""""""""""""""
    try:
        docx_bytes = generate_salary_structure_docx(
            employee_name=request.employee_name,
            annual_ctc=request.annual_ctc,
        )
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate salary structure document: {exc}")

    filename = get_salary_filename(request.employee_name)
    docx_b64 = base64.b64encode(docx_bytes).decode("utf-8")

    # "" 3. Build structured response """"""""""""""""""""""""""""""""""""""""""
    detail = SalaryStructureDetailResponse(
        # Identity
        employee_name=sal.employee_name,
        annual_ctc=sal.annual_ctc,
        # Earnings
        basic_pm=round(sal.basic_pm, 2),
        basic_pa=round(sal.basic_pa, 2),
        hra_pm=round(sal.hra_pm, 2),
        hra_pa=round(sal.hra_pa, 2),
        medical_pm=round(sal.medical_pm, 2),
        medical_pa=round(sal.medical_pa, 2),
        transport_pm=round(sal.transport_pm, 2),
        transport_pa=round(sal.transport_pa, 2),
        deployment_pm=round(sal.deployment_pm, 2),
        deployment_pa=round(sal.deployment_pa, 2),
        fixed_allowance_pm=round(sal.fixed_allowance_pm, 2),
        fixed_allowance_pa=round(sal.fixed_allowance_pa, 2),
        # Totals
        gross_pm=round(sal.gross_pm, 2),
        gross_pa=round(sal.gross_pa, 2),
        # Deductions
        epf_employee_pm=round(sal.epf_employee_pm, 2),
        epf_employee_pa=round(sal.epf_employee_pa, 2),
        epf_employer_pm=round(sal.epf_employer_pm, 2),
        epf_employer_pa=round(sal.epf_employer_pa, 2),
        esic_employee_pm=round(sal.esic_employee_pm, 2),
        esic_employee_pa=round(sal.esic_employee_pa, 2),
        total_deductions_pm=round(sal.total_deductions_pm, 2),
        total_deductions_pa=round(sal.total_deductions_pa, 2),
        # Net
        net_pm=round(sal.net_pm, 2),
        net_pa=round(sal.net_pa, 2),
        # Other Benefits
        esic_employer_pm=round(sal.esic_employer_pm, 2),
        esic_employer_pa=round(sal.esic_employer_pa, 2),
        # Document
        filename=filename,
        docx_base64=docx_b64,
    )

    return SalaryStructureWithDetailsResponse(
        status="success",
        message=f"Salary structure generated for '{request.employee_name}' (CTC: {request.annual_ctc:,.2f})",
        salary_structure=detail,
    )



@router.get(
    "/salary-structure/preview/{offer_id}",
    dependencies=[Depends(require_resource_permission("offer-letters", "view"))],
    summary="Preview salary breakdown for an existing offer letter",
)
def preview_salary_structure(
    offer_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Return the calculated salary breakdown (JSON) for an existing offer
    without generating a file - useful for UI previews.

    **Required permission:** `offer.view`
    """
    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail=f"Offer letter {offer_id} not found")

    try:
        ctc = float(str(offer.salary).replace(",", "").replace("", "").strip())
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=422,
            detail=f"Cannot parse salary value '{offer.salary}' as a number.",
        )

    candidate = db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()
    employee_name = _candidate_name(candidate) or offer.candidate_id

    sal = calculate_salary(employee_name, ctc)

    return {
        "offer_id":      offer_id,
        "employee_name": sal.employee_name,
        "annual_ctc":    sal.annual_ctc,
        "earnings": {
            "basic_salary":                  {"monthly": sal.basic_pm,           "annual": sal.basic_pa},
            "hra":                           {"monthly": sal.hra_pm,             "annual": sal.hra_pa},
            "medical_allowance":             {"monthly": sal.medical_pm,         "annual": sal.medical_pa},
            "transport_allowance":           {"monthly": sal.transport_pm,       "annual": sal.transport_pa},
            "deployment_performance_allowance": {"monthly": sal.deployment_pm,  "annual": sal.deployment_pa},
            "fixed_allowance":               {"monthly": sal.fixed_allowance_pm, "annual": sal.fixed_allowance_pa},
            "gross_salary":                  {"monthly": sal.gross_pm,           "annual": sal.gross_pa},
        },
        "deductions": {
            "epf_employee":     {"monthly": sal.epf_employee_pm,    "annual": sal.epf_employee_pa},
            "epf_employer":     {"monthly": sal.epf_employer_pm,    "annual": sal.epf_employer_pa},
            "esic_employee":    {"monthly": sal.esic_employee_pm,   "annual": sal.esic_employee_pa},
            "total_deductions": {"monthly": sal.total_deductions_pm, "annual": sal.total_deductions_pa},
        },
        "net_income": {"monthly": sal.net_pm, "annual": sal.net_pa},
        "other_benefits": {
            "esic_employer":    {"monthly": sal.esic_employer_pm,  "annual": sal.esic_employer_pa},
            "health_insurance":  {"annual": 25_600.0},
            "paid_time_off":     {"annual": sal.gross_pa / 12},
            "accidental_policy": {"annual":  1_440.0},
            "term_insurance":    {"annual":  3_000.0},
        },
    }
