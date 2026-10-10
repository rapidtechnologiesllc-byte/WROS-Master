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
  GET   /portal/offers
  GET   /portal/onboarding                      documents to upload, checklists
  POST  /portal/onboarding/documents/{doc_id}   upload one requested document
  POST  /portal/offers/{offer_id}/respond     body {action: accept|decline, message}
"""
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_candidate
from app.models.candidate import Candidate
from app.schemas.candidate_portal import (
    PortalHomeResponse,
    PortalInterviewsResponse,
    PortalOfferRespondRequest,
    PortalProfileFieldsResponse,
    PortalProfileUpdateRequest,
    PortalProfileUpdateResponse,
    PortalRescheduleRequest,
    PortalRescheduleResponse,
    PortalThreadResponse,
)
from app.schemas.user import AllOffersResponse, OfferAcceptanceResponse
from app.services import offer_response_service
from app.services.ai_conversation_service import get_missing_fields, merge_fields_to_db
from app.services.candidate_portal_service import (
    PortalInterviewNotFound,
    create_reschedule_request,
    get_portal_home,
    get_portal_interviews,
    get_portal_profile_fields,
    get_interview_ics,
    get_portal_thread,
)

router = APIRouter(prefix="/portal", tags=["candidate-portal"])

@router.get(
    "/home",
    response_model=PortalHomeResponse
)
def portal_home(
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    return PortalHomeResponse(**get_portal_home(db, candidate))

@router.get(
    "/messages",
    response_model=PortalThreadResponse
)
def portal_messages(
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    return PortalThreadResponse(**get_portal_thread(db, candidate))

@router.get(
    "/profile-fields",
    response_model=PortalProfileFieldsResponse
)
def portal_profile_fields(
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    return PortalProfileFieldsResponse(**get_portal_profile_fields(db, candidate))

@router.patch(
    "/profile",
    response_model=PortalProfileUpdateResponse
)
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

@router.get(
    "/interviews",
    response_model=PortalInterviewsResponse
)
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
        body = get_interview_ics(db, candidate, interview_id)
    except PortalInterviewNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return Response(content=body, media_type="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="interview-{interview_id}.ics"'})


@router.post(
    "/interviews/{interview_id}/reschedule-request",
    response_model=PortalRescheduleResponse
)
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


@router.get("/offers", response_model=AllOffersResponse)
def portal_offers(
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    from app.api.v1.endpoints.offer_letters import _build_offer_response

    offers = [_build_offer_response(o, candidate) for o in offer_response_service.candidate_offers(db, candidate)]
    return AllOffersResponse(total_offers=len(offers), offers=offers)


@router.post("/offers/{offer_id}/respond", response_model=OfferAcceptanceResponse)
def portal_offer_respond(
    offer_id: int,
    body: PortalOfferRespondRequest,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    try:
        offer = offer_response_service.respond_to_offer(db, candidate, offer_id, body.action, body.message)
    except offer_response_service.OfferResponseError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return OfferAcceptanceResponse(status="Success", message=f"Offer {offer.offer_status.lower()}",
                                   offer_id=offer.id, offer_status=offer.offer_status,
                                   responded_at=offer.responded_at)


@router.get("/onboarding")
def portal_onboarding_status(
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    from app.services.hiring_onboarding_service import portal_onboarding

    return portal_onboarding(db, candidate)


@router.post("/onboarding/documents/{doc_id}")
async def portal_upload_onboarding_document(
    doc_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    """Stores the file (SharePoint, virus-scanned) and marks the requested document received."""
    from app.api.v1.endpoints.documents import _upload_document_helper
    from app.services.hiring_onboarding_service import OnboardingError, _own_document, receive_document

    try:
        _own_document(db, candidate, doc_id)
    except OnboardingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    stored = await _upload_document_helper(file, "preboarding", candidate, db)
    try:
        doc = receive_document(db, candidate, doc_id, stored.sharepoint_url)
    except OnboardingError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return {"id": doc.id, "label": doc.document_label, "status": doc.status, "received_at": doc.received_at}
