"""
LinkedIn Candidate Pipeline Endpoints

A recruiter queues a LinkedIn profile for manual outreach. Queuing creates
the candidate straight away (Thunder off) so every follow-up task is tied to
a real candidate; the recruiter then moves it Pending Connection ->
Connected -> Phone Collected, and Import adds phone/email and switches
Thunder on.

Endpoints are plain `def` on purpose: candidate creation waits on the queue
worker (blocking poll), which must not run on the event loop.
"""
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.consent import ConsentRecord
from app.models.event_log import EventLog
from app.models.linkedin_candidate_pipeline import LinkedInCandidatePipeline, LinkedInPipelineStatus
from app.models.user import Users
from app.services.candidate_activity_service import log_linkedin_pipeline_step
from app.services.candidate_contact_policy import rejection_cooldown_until
from app.services.message_handlers.enrich_linkedin_candidate_handler import queue_enrichment
from app.services.linkedin_pipeline_task_service import (
    creation_pending, is_placeholder_email, link_candidate_to_pipeline, name_from_slug,
    queue_pipeline_candidate, sync_outreach_task,
)

router = APIRouter(prefix="/linkedin-candidate-pipeline", tags=["LinkedIn Pipeline"])

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

PENDING_ACTIONS = {
    "PENDING_CONNECTION": "Send LinkedIn Connection Request",
    "CONNECTED": "Collect Phone Number and Email",
    "PHONE_COLLECTED": "Import to Thunder",
    "IMPORTED_TO_THUNDER": "Monitor Engagement",
}

# Forward-only manual transitions. IMPORTED_TO_THUNDER is only reachable via
# /complete-import, which finalises the candidate and turns Thunder on.
_ALLOWED_TRANSITIONS = {
    LinkedInPipelineStatus.PENDING_CONNECTION: {LinkedInPipelineStatus.CONNECTED},
    LinkedInPipelineStatus.CONNECTED: {LinkedInPipelineStatus.PHONE_COLLECTED},
    LinkedInPipelineStatus.PHONE_COLLECTED: set(),
    LinkedInPipelineStatus.IMPORTED_TO_THUNDER: set(),
}

class LinkedInQueueRequest(BaseModel):
    linkedin_url: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None

class LinkedInImportRequest(BaseModel):
    linkedin_url: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None

class LinkedInStatusUpdateRequest(BaseModel):
    status: str
    notes: Optional[str] = None

def parse_linkedin_url(linkedin_url: str) -> str:
    """Extract profile slug from LinkedIn URL."""
    match = re.search(r'/in/([a-z0-9_%-]+)', (linkedin_url or "").lower())
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid LinkedIn URL format. Expected: https://linkedin.com/in/profile-slug"
        )
    return match.group(1)

def canonical_linkedin_url(profile_slug: str) -> str:
    """One stored form per profile, so http/https, www, trailing slash and
    query strings can't create duplicate entries for the same person."""
    return f"https://www.linkedin.com/in/{profile_slug}"

def _clean_email(email: Optional[str]) -> Optional[str]:
    email = (email or "").strip().lower()
    if not email:
        return None
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=400, detail=f"Invalid email address: {email}")
    return email

def _candidate_with_profile(db: Session, profile_slug: str):
    """Existing candidate whose LinkedIn URL points at the same profile."""
    rows = db.query(Candidate).filter(Candidate.linkedin_url.ilike(f"%/in/{profile_slug}%")).all()
    for candidate in rows:
        try:
            if parse_linkedin_url(candidate.linkedin_url) == profile_slug:
                return candidate
        except HTTPException:
            continue
    return None

def _candidate_name(candidate: Candidate) -> str:
    return " ".join(filter(None, [candidate.candidateFirstName, candidate.candidateLastName])) or candidate.candidateEmail

def _user_display_name(db: Session, user_id: Optional[str]) -> Optional[str]:
    if not user_id:
        return None
    user = db.query(Users).filter(Users.UserID == user_id).first()
    return (user.UserName or user.UserEmail) if user else user_id

_STEP_LABELS = {
    LinkedInPipelineStatus.PENDING_CONNECTION: "Pending Connection",
    LinkedInPipelineStatus.CONNECTED: "Connected",
    LinkedInPipelineStatus.PHONE_COLLECTED: "Phone Collected",
    LinkedInPipelineStatus.IMPORTED_TO_THUNDER: "Imported to Thunder",
}

def _log_step(db: Session, item: LinkedInCandidatePipeline, current_user: Users, notes: Optional[str] = None):
    """Record the item's current stage on its candidate's History tab."""
    if item.candidate_id:
        log_linkedin_pipeline_step(
            db, item.candidate_id, _STEP_LABELS[item.status], notes=notes,
            performed_by_id=current_user.UserID,
            performed_by_name=current_user.UserName or current_user.UserEmail,
        )

def _ensure_candidate(db: Session, item: LinkedInCandidatePipeline, current_user: Users) -> Optional[Candidate]:
    """The item's candidate if it exists. Links one already created for this
    profile; for items queued before candidates were created at queue time,
    queues creation now. Returns None while creation is still pending."""
    if item.candidate_id:
        return db.query(Candidate).filter(Candidate.candidateID == item.candidate_id).first()
    candidate = _candidate_with_profile(db, item.linkedin_profile_slug)
    if candidate is not None:
        link_candidate_to_pipeline(db, str(item.id), candidate.candidateID)
        return candidate
    if not creation_pending(db, item, current_user.tenant_id):  # don't queue twice
        queue_pipeline_candidate(
            db, item, created_by_user_id=current_user.UserID, tenant_id=current_user.tenant_id,
        )
    return None

def _owned_item(db: Session, pipeline_id: str, current_user: Users) -> LinkedInCandidatePipeline:
    """The pipeline item, only if it is assigned to the caller (same 404 for
    missing and not-yours, so ids of other people's items aren't confirmed)."""
    item = db.query(LinkedInCandidatePipeline).filter(LinkedInCandidatePipeline.id == pipeline_id).first()
    if item is None or item.assigned_to_user_id != current_user.UserID:
        raise HTTPException(status_code=404, detail="Pipeline item not found")
    return item

def _item_payload(db: Session, item: LinkedInCandidatePipeline, owner_names: dict) -> dict:
    status_value = item.status.value if hasattr(item.status, "value") else str(item.status)
    candidate = (
        db.query(Candidate).filter(Candidate.candidateID == item.candidate_id).first()
        if item.candidate_id else _candidate_with_profile(db, item.linkedin_profile_slug)
    )
    if candidate is not None:
        name = _candidate_name(candidate)
        email = None if is_placeholder_email(candidate.candidateEmail) else candidate.candidateEmail
        phone = item.phone_number or candidate.candidateMobile
    else:
        name = " ".join(name_from_slug(item.linkedin_profile_slug)).replace(" (LinkedIn)", "")
        email = None
        phone = item.phone_number
    return {
        "id": str(item.id),
        "linkedin_url": item.linkedin_url,
        "linkedin_profile_slug": item.linkedin_profile_slug,
        "candidate_id": candidate.candidateID if candidate is not None else None,
        "candidate_pending": candidate is None,
        "candidate_name": name,
        "email": email,
        "phone_number": phone,
        "status": status_value,
        "pending_action": PENDING_ACTIONS.get(status_value, "Unknown"),
        "assigned_to": owner_names.get(item.assigned_to_user_id) or item.assigned_to_user_id,
        "days_in_pipeline": (datetime.utcnow() - item.created_at).days if item.created_at else 0,
        "notes": item.notes,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }

def _items_for_user(db: Session, current_user: Users, status_filter: Optional[str] = None) -> list:
    query = db.query(LinkedInCandidatePipeline).filter(
        LinkedInCandidatePipeline.assigned_to_user_id == current_user.UserID
    )
    if status_filter:
        try:
            query = query.filter(LinkedInCandidatePipeline.status == LinkedInPipelineStatus[status_filter])
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid status filter: {status_filter}")
    items = query.order_by(LinkedInCandidatePipeline.created_at.desc()).all()
    owner_names = {current_user.UserID: current_user.UserName or current_user.UserEmail}
    return [_item_payload(db, item, owner_names) for item in items]

@router.post("/linkedin-queue", dependencies=[Depends(require_resource_permission("candidates", "create"))])
def queue_linkedin_candidate(
    request: LinkedInQueueRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Queue a LinkedIn profile for manual outreach and create its candidate.

    Duplicates (matched on the profile, not the raw URL string):
    1. Already in the pipeline (any owner) -> ALREADY_QUEUED
    2. Already a candidate (same LinkedIn profile or same email) -> ALREADY_EXISTS
    """
    if not current_user.UserID or str(current_user.UserID).strip() == "system":
        raise HTTPException(status_code=400, detail="Invalid user ID: authenticate with a real user account.")

    profile_slug = parse_linkedin_url(request.linkedin_url)
    linkedin_url = canonical_linkedin_url(profile_slug)
    email = _clean_email(request.email)

    existing_pipeline = db.query(LinkedInCandidatePipeline).filter(
        LinkedInCandidatePipeline.linkedin_profile_slug == profile_slug
    ).first()
    if existing_pipeline:
        owner = _user_display_name(db, existing_pipeline.assigned_to_user_id)
        mine = existing_pipeline.assigned_to_user_id == current_user.UserID
        pipeline_status = existing_pipeline.status.value if hasattr(existing_pipeline.status, "value") else str(existing_pipeline.status)
        return {
            "status": "ALREADY_QUEUED",
            "message": "Already in your LinkedIn queue" if mine else f"Already in {owner}'s LinkedIn queue",
            "pipeline_item": {"id": str(existing_pipeline.id), "status": pipeline_status, "assigned_to": owner},
        }

    existing_candidate = _candidate_with_profile(db, profile_slug)
    if existing_candidate is None and email:
        existing_candidate = db.query(Candidate).filter(Candidate.candidateEmail == email).first()
    if existing_candidate:
        return {
            "status": "ALREADY_EXISTS",
            "message": "Candidate already in the system",
            "candidate": {"id": existing_candidate.candidateID, "name": _candidate_name(existing_candidate)},
        }

    pipeline_item = LinkedInCandidatePipeline(
        linkedin_url=linkedin_url,
        linkedin_profile_slug=profile_slug,
        status=LinkedInPipelineStatus.PENDING_CONNECTION,
        assigned_to_user_id=str(current_user.UserID),
        created_by_user_id=str(current_user.UserID),
        tenant_id=str(current_user.tenant_id) if current_user.tenant_id is not None else None,
    )
    try:
        db.add(pipeline_item)
        db.flush()
        sync_outreach_task(db, pipeline_item, current_user.tenant_id)
        db.commit()
        db.refresh(pipeline_item)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"[LinkedInPipeline] Queue failed for {linkedin_url}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add the profile to the pipeline.")

    # Candidate is created by the queue worker and linked to this item (and
    # its task) by the handler. Enqueued after the commit so the worker can
    # always find the item; if this fails, the next status change re-queues.
    try:
        message_id = queue_pipeline_candidate(
            db, pipeline_item,
            created_by_user_id=current_user.UserID, tenant_id=current_user.tenant_id,
            first_name=request.first_name, last_name=request.last_name, email=email,
        )
    except Exception as exc:
        logger.error(f"[LinkedInPipeline] Candidate creation not queued for {pipeline_item.id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Added to your pipeline, but creating the candidate record failed. It will be retried on the next status change.",
        )

    # Autonomous enrichment replaces the manual connect/collect/import steps;
    # the recruiter task stays as the fallback if enrichment is exhausted.
    enrichment_queued = True
    try:
        queue_enrichment(str(pipeline_item.id), current_user.tenant_id)
    except Exception as exc:
        enrichment_queued = False
        logger.error(f"[LinkedInPipeline] Enrichment not queued for {pipeline_item.id}: {exc}", exc_info=True)

    return {
        "status": "QUEUED",
        "enrichment_queued": enrichment_queued,
        "message": "Added to your LinkedIn pipeline; the candidate record is being created",
        "pipeline_item_id": str(pipeline_item.id),
        "candidate_message_id": message_id,
        "profile_slug": profile_slug,
    }

@router.get("/list", dependencies=[Depends(require_resource_permission("candidates", "view"))])
def list_pipeline_items(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """The logged-in user's pipeline items with candidate name and contact details."""
    items = _items_for_user(db, current_user, status_filter)
    return {"count": len(items), "items": items}

@router.get("/dashboard/activity", dependencies=[Depends(require_resource_permission("candidates", "view"))])
def get_linkedin_activity_for_dashboard(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Dashboard view of the logged-in user's LinkedIn outreach."""
    items = _items_for_user(db, current_user)
    return {"count": len(items), "items": items}

@router.put("/{pipeline_id}/status", dependencies=[Depends(require_resource_permission("candidates", "edit"))])
def update_pipeline_status(
    pipeline_id: str,
    request: LinkedInStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Move a pipeline item to its next stage (JSON body: {status, notes}).

    Forward-only: Pending Connection -> Connected -> Phone Collected.
    Imported to Thunder is set by /complete-import. Each move completes the
    current follow-up task and opens the next one, linked to the candidate.
    """
    pipeline_item = _owned_item(db, pipeline_id, current_user)

    try:
        new_status = LinkedInPipelineStatus[request.status]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {request.status}. Valid values: {[s.value for s in LinkedInPipelineStatus]}"
        )

    current_status = pipeline_item.status
    if new_status not in _ALLOWED_TRANSITIONS.get(current_status, set()):
        if new_status == LinkedInPipelineStatus.IMPORTED_TO_THUNDER:
            detail = "Use Import (with phone number and email) to move a candidate to Imported to Thunder."
        else:
            detail = f"Cannot move from {current_status.value} to {new_status.value}."
        raise HTTPException(status_code=400, detail=detail)

    try:
        # Links/queues the candidate for items added before candidates were
        # created at queue time; the move itself doesn't wait for it
        _ensure_candidate(db, pipeline_item, current_user)
        pipeline_item.status = new_status
        if new_status == LinkedInPipelineStatus.CONNECTED:
            pipeline_item.connected_at = datetime.utcnow()
        if request.notes:
            pipeline_item.notes = request.notes
        pipeline_item.updated_at = datetime.utcnow()
        _log_step(db, pipeline_item, current_user, notes=request.notes)
        sync_outreach_task(db, pipeline_item, current_user.tenant_id)
        db.commit()
        db.refresh(pipeline_item)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"[LinkedInPipeline] Status update failed for {pipeline_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update the pipeline status.")

    return {
        "id": str(pipeline_item.id),
        "status": pipeline_item.status.value,
        "candidate_id": pipeline_item.candidate_id,
        "updated_at": pipeline_item.updated_at.isoformat(),
    }

@router.post("/{pipeline_id}/complete-import", dependencies=[Depends(require_resource_permission("candidates", "edit"))])
def complete_linkedin_import(
    pipeline_id: str,
    request: LinkedInImportRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Finish outreach: save phone + email on the candidate, record WhatsApp
    consent, switch Thunder on and mark the item Imported to Thunder.
    """
    pipeline_item = _owned_item(db, pipeline_id, current_user)
    if pipeline_item.status != LinkedInPipelineStatus.PHONE_COLLECTED:
        raise HTTPException(status_code=400, detail="Only items in Phone Collected can be imported.")

    phone = (request.phone_number or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required to import.")
    email = _clean_email(request.email)

    try:
        candidate = _ensure_candidate(db, pipeline_item, current_user)
        if candidate is None:
            db.commit()  # keep any creation that _ensure_candidate just queued
            raise HTTPException(
                status_code=409,
                detail="The candidate record is still being created. Try Import again in a minute.",
            )

        if is_placeholder_email(candidate.candidateEmail):
            if not email:
                raise HTTPException(status_code=400, detail="Email address is required to import.")
            taken = db.query(Candidate).filter(
                Candidate.candidateEmail == email, Candidate.candidateID != candidate.candidateID
            ).first()
            if taken:
                raise HTTPException(
                    status_code=409,
                    detail=f"{email} already belongs to candidate {_candidate_name(taken)}.",
                )
            candidate.candidateEmail = email
        elif email and email != candidate.candidateEmail:
            raise HTTPException(
                status_code=400,
                detail=f"This candidate already has email {candidate.candidateEmail}.",
            )

        # CRITICAL FIX: Check if phone already belongs to another candidate
        # (can't overwrite phone for a different candidate)
        if phone and candidate.candidateMobile != phone:
            phone_conflict = db.query(Candidate).filter(
                Candidate.candidateMobile == phone, Candidate.candidateID != candidate.candidateID
            ).first()
            if phone_conflict:
                raise HTTPException(
                    status_code=409,
                    detail=f"Phone {phone} already belongs to candidate {_candidate_name(phone_conflict)}.",
                )

        candidate.candidateMobile = phone

        no_contact_until = rejection_cooldown_until(db, candidate.candidateID)
        if no_contact_until is not None:
            raise HTTPException(
                status_code=403,
                detail=f"Candidate is in a post-rejection no-contact period until "
                       f"{no_contact_until.isoformat()}. Cannot enable Thunder until it expires.",
            )

        candidate.thunder_enabled = True
        db.add(candidate)

        # Phone collected through outreach = consent for WhatsApp follow-up,
        # same rule create_candidate() applies to phones given at creation
        has_consent = db.query(ConsentRecord).filter(
            ConsentRecord.subject_id == candidate.candidateID,
            ConsentRecord.consent_type == "whatsapp_outreach",
        ).first()
        if not has_consent:
            db.add(ConsentRecord(
                subject_type="candidate", subject_id=candidate.candidateID,
                consent_type="whatsapp_outreach", consent_given=True,
                captured_by="linkedin_pipeline_import",
            ))

        pipeline_item.status = LinkedInPipelineStatus.IMPORTED_TO_THUNDER
        pipeline_item.phone_number = phone
        pipeline_item.imported_at = datetime.utcnow()
        pipeline_item.updated_at = datetime.utcnow()
        _log_step(db, pipeline_item, current_user, notes="Phone and email collected; Thunder enabled")
        # Closes the "import to Thunder" task; Thunder owns outreach from here
        sync_outreach_task(db, pipeline_item, current_user.tenant_id)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"[LinkedInPipeline] Import failed for {pipeline_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to import the candidate.")

    return {
        "status": "SUCCESS",
        "message": "Candidate imported and ready for Thunder autonomous outreach",
        "candidate_id": candidate.candidateID,
        "phone": phone,
        "email": candidate.candidateEmail,
        "pipeline_id": str(pipeline_item.id),
    }
