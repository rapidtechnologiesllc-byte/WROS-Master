from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel as _BM
from sqlalchemy.orm import Session
import os as _os

from app.core.database import get_db
from app.core.dependencies import (
    get_current_candidate,
    get_current_hr_or_admin,
    require_permission,
)
from app.models.offer_letter import OfferLetter
from app.models.candidate import Candidate
from app.models.user import Users, Jobs
from app.schemas.user import (
    OfferLetterCreateRequest,
    OfferLetterUpdateRequest,
    OfferLetterResponse,
    OfferAcceptanceRequest,
    OfferAcceptanceResponse,
    OfferCancelRequest,
    AllOffersResponse,
    DeleteResponse,
)
from app.services.offer_letter_generator import generate_filled_docx, generated_file_path
from app.services.sharepoint_service import upload_file, get_file_download_link, list_folder
from app.services.salary_structure_generator import (
    generate_salary_structure_docx,
    get_salary_filename,
    calculate_salary,
)


router = APIRouter(prefix="/offer-letter", tags=["offer-letter"])


# ── helpers ──────────────────────────────────────────────────────────────────

def _candidate_name(c) -> str | None:
    if not c:
        return None
    parts = [
        c.candidateFirstName,
        getattr(c, "candidateMiddleName", None),
        c.candidateLastName,
    ]
    return " ".join(p for p in parts if p) or None


# ============================================
# TEMPLATE LISTING
# ============================================

@router.get(
    "/templates",
    dependencies=[Depends(require_permission("offer.view"))],
    summary="List all offer-letter templates available in SharePoint",
)
def list_offer_templates(
    folder: Optional[str] = Query(
        None,
        description="Sub-folder inside the templates directory to list. "
                    "Leave blank to list the root templates folder.",
    ),
    user=Depends(get_current_hr_or_admin),
):
    """
    Returns all `.docx` (and other) template files stored in the SharePoint
    templates folder (`SHAREPOINT_TEMPLATE_PATH` parent directory).

    **Optional query param:**
    - `folder` — drill into a sub-folder, e.g. `?folder=full-time`

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

@router.post("/respond", response_model=OfferAcceptanceResponse)
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

    if offer.offer_status != "Pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot respond to offer with status '{offer.offer_status}'. Only pending offers can be responded to.",
        )

    offer.offer_status = "Accepted" if request.action.lower() == "accept" else "Rejected"
    offer.candidate_response = request.response_message
    offer.responded_at = datetime.now()
    db.commit()
    db.refresh(offer)

    return OfferAcceptanceResponse(
        status="Success",
        message=f"Offer {offer.offer_status.lower()} successfully",
        offer_id=offer.id,
        offer_status=offer.offer_status,
        responded_at=offer.responded_at,
    )


@router.get("/my-offers", response_model=AllOffersResponse)
def get_my_offers(
    db: Session = Depends(get_db),
    candidate=Depends(get_current_candidate),
):
    """Get all offer letters for the authenticated candidate."""
    offers = db.query(OfferLetter).filter(
        OfferLetter.candidate_id == candidate.candidateID
    ).all()

    offer_responses = []
    for offer in offers:
        c = db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()
        offer_responses.append(OfferLetterResponse(
            id=offer.id,
            candidate_id=offer.candidate_id,
            candidate_name=_candidate_name(c),
            candidate_email=c.candidateEmail if c else None,
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
        ))

    return AllOffersResponse(total_offers=len(offer_responses), offers=offer_responses)


# ============================================
# RECRUITER / HR ENDPOINTS
# ============================================

@router.post(
    "/create",
    response_model=OfferLetterResponse,
    dependencies=[Depends(require_permission("offer.manage"))],
)
def create_offer_letter(
    request: OfferLetterCreateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Create a new offer letter for a candidate (HR/Recruiter only)."""
    candidate = db.query(Candidate).filter(Candidate.candidateID == request.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {request.candidate_id} not found")

    hiring_manager = db.query(Users).filter(Users.UserID == request.hiring_manager_id).first()
    if not hiring_manager:
        raise HTTPException(status_code=404, detail=f"Hiring manager {request.hiring_manager_id} not found")

    reporting_manager = db.query(Users).filter(Users.UserID == request.reporting_manager_id).first()
    if not reporting_manager:
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
    dependencies=[Depends(require_permission("offer.manage"))],
)
def cancel_offer_letter(
    offer_id: int,
    request: OfferCancelRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
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
    dependencies=[Depends(require_permission("offer.manage"))],
)
def update_offer_letter(
    offer_id: int,
    request: OfferLetterUpdateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
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
    dependencies=[Depends(require_permission("offer.view"))],
)
def get_all_offers(
    status: Optional[str] = Query(None, description="Filter by offer status"),
    candidate_id: Optional[str] = Query(None, description="Filter by candidate ID"),
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
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
        offer_responses.append(OfferLetterResponse(
            id=offer.id,
            candidate_id=offer.candidate_id,
            candidate_name=_candidate_name(c),
            candidate_email=c.candidateEmail if c else None,
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
        ))

    return AllOffersResponse(total_offers=len(offer_responses), offers=offer_responses)


@router.get(
    "/{offer_id}",
    response_model=OfferLetterResponse,
    dependencies=[Depends(require_permission("offer.view"))],
)
def get_offer_by_id(
    offer_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Get a specific offer letter by ID (HR/Recruiter only)."""
    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail=f"Offer letter {offer_id} not found")

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


# ============================================
# OFFER LETTER DOCUMENT GENERATION
# ============================================

@router.post(
    "/generate/{offer_id}",
    dependencies=[Depends(require_permission("offer.manage"))],
    summary="Generate a filled offer letter .docx from the SharePoint template",
)
def generate_offer_letter_document(
    offer_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Auto-generate a filled `.docx` offer letter for the given offer.

    1. Load offer + candidate + job details from the database.
    2. Fetch the template `.docx` from SharePoint.
    3. Replace all `{{placeholder}}` tokens and inject the salary table.
    4. Upload the filled document back to SharePoint.
    5. Return the SharePoint web URL and a pre-authenticated download link.

    **Required permission:** `offer.manage`
    """
    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail=f"Offer letter {offer_id} not found")

    candidate = db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{offer.candidate_id}' not found")

    first_name = candidate.candidateFirstName or ""
    last_name  = candidate.candidateLastName  or ""

    # Job → location + department
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
    if offer.hiring_manager_id:
        hm = db.query(Users).filter(Users.UserID == offer.hiring_manager_id).first()
        if hm:
            hiring_manager_name = hm.UserName or hm.UserEmail or ""

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
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to generate offer letter document: {exc}")

    dest_path = generated_file_path(offer.candidate_id, offer_id)
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    try:
        web_url = upload_file(dest_path, docx_bytes, content_type=mime)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to upload offer letter to SharePoint: {exc}")

    download_link = get_file_download_link(dest_path) or web_url
    candidate_name = f"{first_name} {last_name}".strip() or offer.candidate_id

    return {
        "status":          "success",
        "message":         f"Offer letter generated for {candidate_name}",
        "offer_id":        offer_id,
        "candidate_id":    offer.candidate_id,
        "candidate_name":  candidate_name,
        "file_name":       f"offer_{offer_id}.docx",
        "sharepoint_path": dest_path,
        "sharepoint_url":  web_url,
        "download_url":    download_link,
    }


# ============================================
# SALARY STRUCTURE DOCUMENT
# ============================================

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

    # ── Identity ──────────────────────────────────────────────────────────────
    employee_name: str
    annual_ctc: float

    # ── Earnings (per month & per annum) ─────────────────────────────────────
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

    # ── Totals ────────────────────────────────────────────────────────────────
    gross_pm: float
    gross_pa: float

    # ── Deductions ────────────────────────────────────────────────────────────
    epf_employee_pm: float
    epf_employee_pa: float
    epf_employer_pm: float
    epf_employer_pa: float
    esic_employee_pm: float
    esic_employee_pa: float

    total_deductions_pm: float
    total_deductions_pa: float

    # ── Net ───────────────────────────────────────────────────────────────────
    net_pm: float
    net_pa: float

    # ── Other Benefits ────────────────────────────────────────────────────────
    esic_employer_pm: float
    esic_employer_pa: float

    # ── Document ──────────────────────────────────────────────────────────────
    filename: str
    docx_base64: str  # base64-encoded .docx bytes — decode on frontend to download


class SalaryStructureWithDetailsResponse(_BM):
    status: str = "success"
    message: str
    salary_structure: SalaryStructureDetailResponse


# ── existing file-download endpoint (unchanged) ───────────────────────────────

@router.post(
    "/salary-structure",
    dependencies=[Depends(require_permission("offer.manage"))],
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
    user=Depends(get_current_hr_or_admin),
):
    """
    Generate and **download** a professional salary-structure Word document.

    Components auto-calculated from annual CTC:
    - Basic = 50% CTC, HRA = 40% Basic
    - Medical = ₹15 000, Transport = ₹19 200, Performance = ₹19 800 (all fixed)
    - PT Deduction = ₹1 800 (fixed)

    **Required permission:** `offer.manage`
    """
    try:
        docx_bytes = generate_salary_structure_docx(
            employee_name=request.employee_name,
            annual_ctc=request.annual_ctc,
        )
    except Exception as exc:
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


# ── NEW: JSON response with salary breakdown + base64-encoded .docx ───────────

@router.post(
    "/salary-structure/details",
    response_model=SalaryStructureWithDetailsResponse,
    dependencies=[Depends(require_permission("offer.manage"))],
    summary="Generate salary-structure details + downloadable .docx in a single response",
)
def generate_salary_structure_with_details(
    request: SalaryStructureRequest,
    user=Depends(get_current_hr_or_admin),
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
    | Medical | Fixed ₹15,000 p.a. |
    | Transport | Fixed ₹19,200 p.a. |
    | Deployment / Performance | Remaining after above 4, capped ₹60,000 |
    | Fixed Allowance | Remainder after all above |
    | EPF Employee & Employer | 12% of EPF base, capped ₹21,600 each |
    | ESIC Employee | 0.75% of ESIC base (only if monthly base ≤ ₹21,000) |

    **Required permission:** `offer.manage`
    """
    import base64

    # ── 1. Calculate salary breakdown ─────────────────────────────────────────
    try:
        sal = calculate_salary(
            employee_name=request.employee_name,
            annual_ctc=request.annual_ctc,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Salary calculation failed: {exc}")

    # ── 2. Generate .docx document ────────────────────────────────────────────
    try:
        docx_bytes = generate_salary_structure_docx(
            employee_name=request.employee_name,
            annual_ctc=request.annual_ctc,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate salary structure document: {exc}")

    filename = get_salary_filename(request.employee_name)
    docx_b64 = base64.b64encode(docx_bytes).decode("utf-8")

    # ── 3. Build structured response ──────────────────────────────────────────
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
        message=f"Salary structure generated for '{request.employee_name}' (CTC: ₹{request.annual_ctc:,.2f})",
        salary_structure=detail,
    )



@router.get(
    "/salary-structure/preview/{offer_id}",
    dependencies=[Depends(require_permission("offer.view"))],
    summary="Preview salary breakdown for an existing offer letter",
)
def preview_salary_structure(
    offer_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Return the calculated salary breakdown (JSON) for an existing offer
    without generating a file — useful for UI previews.

    **Required permission:** `offer.view`
    """
    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail=f"Offer letter {offer_id} not found")

    try:
        ctc = float(str(offer.salary).replace(",", "").replace("₹", "").strip())
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
            "basic_salary":          {"monthly": sal.basic_pm,       "annual": sal.basic_pa},
            "hra":                   {"monthly": sal.hra_pm,         "annual": sal.hra_pa},
            "medical_allowance":     {"monthly": sal.medical_pm,     "annual": sal.medical_pa},
            "transport_allowance":   {"monthly": sal.transport_pm,   "annual": sal.transport_pa},
            "performance_allowance": {"monthly": sal.performance_pm, "annual": sal.performance_pa},
            "gross_salary":          {"monthly": sal.gross_pm,       "annual": sal.gross_pa},
        },
        "deductions": {
            "professional_tax": {"monthly": sal.pt_pm, "annual": sal.pt_pa},
            "total_deductions": {"monthly": sal.pt_pm, "annual": sal.total_deductions_pa},
        },
        "net_income": {"monthly": sal.net_pm, "annual": sal.net_pa},
        "other_benefits": {
            "health_insurance":  {"annual": 25_600.0},
            "paid_time_off":     {"annual": 30_000.0},
            "accidental_policy": {"annual":  1_440.0},
            "term_insurance":    {"annual":  3_000.0},
            "total":             {"annual": 60_040.0},
        },
    }
