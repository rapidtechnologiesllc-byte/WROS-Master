"""
S-017/HRMS-0417 -- Candidate Self-Service Web Portal
==================================================================
Prefix: /portal
Tag:    candidate-portal

Candidate-authenticated (get_current_candidate). The "magic link" the
candidate taps in WhatsApp/Email IS the JWT bearer token itself --
see app.services.candidate_portal_service module docstring for why
this replaces the spec's never-built HRMS-P111 magic-link/session-
cookie system. BR-02 (candidate sees only their own data) is enforced
by every route resolving candidate.candidateID from the token, never
from a URL/body param.

Routes:
  GET   /portal/home
  GET   /portal/messages
  GET   /portal/profile-fields
  PATCH /portal/profile
  GET   /portal/interviews
  GET   /portal/interviews/{interview_id}/ics
  POST  /portal/interviews/{interview_id}/reschedule-request
"""
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_candidate
from app.models.candidate import Candidate
from app.schemas.candidate_portal import (
    PortalHomeResponse,
    PortalInterviewsResponse,
    PortalProfileFieldsResponse,
    PortalProfileUpdateRequest,
    PortalProfileUpdateResponse,
    PortalRescheduleRequest,
    PortalRescheduleResponse,
    PortalThreadResponse,
    PortalTrackRequest,
    PortalTrackResponse,
)
from app.services.ai_conversation_service import get_missing_fields, merge_fields_to_db
from app.services.candidate_portal_service import (
    PortalInterviewNotFound,
    create_reschedule_request,
    get_interview_ics,
    get_portal_home,
    get_portal_interviews,
    get_portal_profile_fields,
    get_portal_thread,
    track_portal_page_view,
)

router = APIRouter(prefix="/portal", tags=["candidate-portal"])


@router.get("/home", response_model=PortalHomeResponse)
def portal_home(
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    return PortalHomeResponse(**get_portal_home(db, candidate))


@router.get("/messages", response_model=PortalThreadResponse)
def portal_messages(
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    return PortalThreadResponse(**get_portal_thread(db, candidate))


@router.get("/profile-fields", response_model=PortalProfileFieldsResponse)
def portal_profile_fields(
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    return PortalProfileFieldsResponse(**get_portal_profile_fields(db, candidate))


@router.patch("/profile", response_model=PortalProfileUpdateResponse)
def portal_profile_update(
    body: PortalProfileUpdateRequest,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    result = merge_fields_to_db(candidate.candidateID, body.fields, db)
    db.commit()
    db.refresh(candidate)
    missing = get_missing_fields(candidate, db)
    return PortalProfileUpdateResponse(
        updated=result.get("updated", []),
        skipped=result.get("skipped", []),
        total_missing=len(missing),
        missing_fields=missing,
    )


@router.get("/interviews", response_model=PortalInterviewsResponse)
def portal_interviews(
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    return PortalInterviewsResponse(interviews=get_portal_interviews(db, candidate))


@router.get("/interviews/{interview_id}/ics")
def portal_interview_ics(
    interview_id: int,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    try:
        ics_bytes = get_interview_ics(db, candidate, interview_id)
    except PortalInterviewNotFound:
        raise HTTPException(status_code=404, detail="Interview not found.")
    return Response(
        content=ics_bytes,
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename=interview-{interview_id}.ics"},
    )


@router.post("/interviews/{interview_id}/reschedule-request", response_model=PortalRescheduleResponse)
def portal_reschedule_request(
    interview_id: int,
    body: PortalRescheduleRequest,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    try:
        result = create_reschedule_request(db, candidate, interview_id, body.note)
    except PortalInterviewNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return PortalRescheduleResponse(**result)


@router.post("/track", response_model=PortalTrackResponse)
def portal_track_page_view(
    body: PortalTrackRequest,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    """S-346 Step 4 / S-347 Step 4 -- called by the frontend on page
    leave (beforeunload) or after 30s on page. Always 200 -- this is a
    behavioral-telemetry beacon, not a business action; a missing
    conversation just means the signal is silently skipped (see
    track_portal_page_view()'s own docstring)."""
    recorded = track_portal_page_view(db, candidate, body.page, body.time_on_page_seconds, body.scroll_depth_pct)
    return PortalTrackResponse(recorded=recorded)


@router.get("/offers")
def portal_offers(
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    """S-089 (HRMS-P109): Candidate Portal - Offer Viewer
    Retrieve all offers for the candidate."""
    from sqlalchemy import and_
    from app.models.offer import Offer

    offers = db.query(Offer).filter(
        and_(
            Offer.candidate_id == candidate.candidateID,
            Offer.tenant_id == candidate.tenant_id
        )
    ).all()

    return {
        "offers": [
            {
                "id": o.id,
                "position_title": o.position_title,
                "salary_amount": o.salary_amount_usd_cents / 100 if o.salary_amount_usd_cents else 0,
                "start_date": o.start_date.isoformat() if o.start_date else None,
                "expiry_date": o.expiry_date.isoformat() if o.expiry_date else None,
                "description": o.description,
                "status": o.status,
                "accepted_date": o.accepted_date.isoformat() if o.accepted_date else None,
                "declined_date": o.declined_date.isoformat() if o.declined_date else None,
            }
            for o in offers
        ]
    }


@router.get("/documents")
def portal_documents(
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    """S-090 (HRMS-P110): Candidate Portal - Document Upload
    Retrieve all documents uploaded by the candidate."""
    from sqlalchemy import and_
    from app.models.document import CandidateDocument

    documents = db.query(CandidateDocument).filter(
        and_(
            CandidateDocument.candidate_id == candidate.candidateID,
            CandidateDocument.is_deleted == False,
        )
    ).order_by(CandidateDocument.uploaded_at.desc()).all()

    return {
        "documents": [
            {
                "id": d.id,
                "filename": d.original_filename,
                "file_size": d.file_size,
                "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
                "download_url": f"/portal/documents/{d.id}/download",
            }
            for d in documents
        ]
    }


@router.post("/documents/upload")
async def portal_upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    """S-090 (HRMS-P110): Candidate Portal - Document Upload
    Upload a document for the candidate."""
    import os
    from datetime import datetime

    if file.size and file.size > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be under 50MB.")

    from app.models.document import CandidateDocument

    # Store file metadata
    import uuid
    unique_filename = f"{uuid.uuid4()}_{file.filename}"

    doc = CandidateDocument(
        candidate_id=candidate.candidateID,
        document_type="portal_upload",
        original_filename=file.filename,
        stored_filename=unique_filename,
        file_size=file.size or 0,
        file_extension=os.path.splitext(file.filename)[1],
        mime_type=file.content_type,
        is_virus_scanned=False,
        uploaded_by=candidate.candidateID,
        uploaded_at=datetime.utcnow(),
    )

    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {
        "id": doc.id,
        "filename": doc.original_filename,
        "file_size": doc.file_size,
        "uploaded_at": doc.uploaded_at.isoformat(),
    }


@router.get("/documents/{document_id}/download")
def portal_download_document(
    document_id: int,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    """Download a document."""
    from app.models.document import CandidateDocument

    doc = db.query(CandidateDocument).filter(
        CandidateDocument.id == document_id,
        CandidateDocument.candidate_id == candidate.candidateID,
        CandidateDocument.is_deleted == False,
    ).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Note: In production, this would retrieve from SharePoint or storage
    # For now, return metadata only
    return Response(
        content=b"",
        media_type=doc.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={doc.original_filename}"},
    )
