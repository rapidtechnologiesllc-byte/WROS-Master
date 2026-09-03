"""
S-017/HRMS-0417 -- Candidate Self-Service Web Portal
==================================================================
Prefix: /portal
import logging
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
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_candidate, require_resource_permission
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

@router.get(
    "/home",
    response_model=PortalHomeResponse,
    dependencies=[Depends(require_resource_permission("home", "view"))]
)
def portal_home(
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    return PortalHomeResponse(**get_portal_home(db, candidate))

@router.get(
    "/messages",
    response_model=PortalThreadResponse,
    dependencies=[Depends(require_resource_permission("message", "view"))]
)
def portal_messages(
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    return PortalThreadResponse(**get_portal_thread(db, candidate))

@router.get(
    "/profile-fields",
    response_model=PortalProfileFieldsResponse,
    dependencies=[Depends(require_resource_permission("profile-field", "view"))]
)
def portal_profile_fields(
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    return PortalProfileFieldsResponse(**get_portal_profile_fields(db, candidate))

@router.patch(
    "/profile",
    response_model=PortalProfileUpdateResponse,
    dependencies=[Depends(require_resource_permission("profile", "update"))]
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
    response_model=PortalInterviewsResponse,
    dependencies=[Depends(require_resource_permission("interview", "view"))]
)
def portal_interviews(
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    return PortalInterviewsResponse(interviews=get_portal_interviews(db, candidate))

@router.get(
    "/interviews/{interview_id}/ics",
    dependencies=[Depends(require_resource_permission("interview", "view"))]
)
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

@router.post(
    "/interviews/{interview_id}/reschedule-request",
    response_model=PortalRescheduleResponse,
    dependencies=[Depends(require_resource_permission("interview", "create"))]
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

@router.post(
    "/track",
    response_model=PortalTrackResponse,
    dependencies=[Depends(require_resource_permission("track", "create"))]
)
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
