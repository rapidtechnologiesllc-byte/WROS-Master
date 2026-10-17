"""The one way a job is created: POST /jobs/create_job and Flash both call submit_job.

Creation is asynchronous: submit_job validates (users, client, business-unit scope, project),
fills the defaults (hiring manager = the client's BU head, recruiter round-robin) and queues
job_created_flash; JobCreationFlashHandler writes the Jobs row. Gate failures raise
HTTPException (the repo's convention for request-level validation).
"""
import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.core.data_scope import ensure_assignable
from app.models.user import Users
from app.schemas.user import JobCreateRequest
from app.services.message_queue_service import MessageQueueService
from app.utils.uniq_id_generator import job_id_generator

logger = logging.getLogger(__name__)

PUBLISHED_STATUS = "active"


def resolve_job_client(db: Session, tenant_id, client_id, company_name):
    """The Client a job is for. client_id wins; otherwise the company name is
    matched (case-insensitively) against Client Management. None = internal hire."""
    from app.models.client import Client

    if client_id:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None or client.tenant_id not in (None, tenant_id):
            raise HTTPException(status_code=400, detail="Unknown client")
        return client
    if company_name and company_name.strip():
        return db.query(Client).filter(
            sa_func.lower(sa_func.trim(Client.company_name)) == company_name.strip().lower(),
            (Client.tenant_id == tenant_id) | Client.tenant_id.is_(None),
        ).first()
    return None


def validate_job_project(db: Session, project_id, client):
    """A job's project must exist and belong to the job's client."""
    from app.models.project import Project

    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=400, detail="Unknown project")
    if client is None or project.client_id != client.id:
        raise HTTPException(status_code=400, detail="The project must belong to the job's client")


def _blank(value: Optional[str]) -> Optional[str]:
    """Swagger's default "string" and empty strings mean "not given"."""
    return None if value in ("string", "") else value


def submit_job(db: Session, user: Users, request: JobCreateRequest) -> str:
    """Validate and queue a new job as `user`; returns the job id. The Jobs row is written by
    JobCreationFlashHandler. Every job is published immediately (job approval is disabled,
    2026-10-05 product decision; when it returns the approver is chosen by role template,
    app.core.authority.is_bu_leader, never by name)."""
    request.contact_person = _blank(request.contact_person)
    request.hiring_manager_id = _blank(request.hiring_manager_id)
    request.recuriter_id = _blank(request.recuriter_id)

    # No hiring manager given -> the head of the business unit in the client's company
    # (BU heads are per company; BU structure, not a role name)
    if request.business_unit and not request.hiring_manager_id:
        from app.services.bu_leadership import head_for_client

        head_id = head_for_client(db, request.business_unit, request.client_id)
        if head_id:
            request.hiring_manager_id = head_id
            logger.info(f"[JobCreation] Hiring manager defaulted to the head of BU {request.business_unit}")

    for user_id, field_name in [
        (request.contact_person, "contact_person"),
        (request.hiring_manager_id, "hiring_manager_id"),
        (request.recuriter_id, "recuriter_id"),
    ]:
        if user_id and db.query(Users).filter(Users.UserID == user_id).first() is None:
            raise HTTPException(
                status_code=400,
                detail=f"User '{user_id}' provided for {field_name} does not exist in the system.",
            )

    job_id = job_id_generator()

    # One requisition record: link the client (and its BU) instead of only its name
    client = resolve_job_client(db, user.tenant_id, request.client_id, request.company_name)
    business_unit_id = request.business_unit or (client.business_unit_id if client else None)
    company_name = request.company_name or (client.company_name if client else None)
    # Business-unit scope (CEO 2026-10-12): never create a job in, or for a client of, a BU
    # outside the caller's scope
    ensure_assignable(db, user, business_unit_id, "job")
    if client is not None:
        ensure_assignable(db, user, client.business_unit_id, "job")
    if request.project_id:
        validate_job_project(db, request.project_id, client)

    # Every job has a recruiter: none given -> the tenant's recruiter with the fewest open jobs
    if not request.recuriter_id:
        from app.services.recruiter_assignment_service import assign_to_recruiter_roundrobin

        recruiter = assign_to_recruiter_roundrobin(db, user.tenant_id)
        if recruiter is not None:
            request.recuriter_id = recruiter.UserID
            logger.info(f"[JobCreation] Recruiter assigned round-robin: {recruiter.UserID}")

    # Queue-driven: JobCreationFlashHandler creates the job and starts recruiting
    MessageQueueService.enqueue(
        task_name="job_created_flash",
        task_id=f"job_created:{job_id}",
        data={
            "job_id": job_id,
            "job_title": request.job_title,
            "job_location": request.job_location,
            "job_description": request.job_description,
            "job_skills": request.job_skills,
            # Structured skills drive candidate matching (Jobs.required_skills_canonical)
            "structured_skills": [s.model_dump() for s in request.structured_skills or []],
            "job_experience": request.job_experience,
            "min_experience_years": request.min_experience_years,
            "company_type": request.company_type,
            "company_name": company_name,
            "contact_person": request.contact_person,
            "no_of_positions": request.no_of_positions,
            "start_date": request.start_date.isoformat() if request.start_date else None,
            "hiring_manager_id": request.hiring_manager_id,
            "recuriter_id": request.recuriter_id,
            "business_unit_id": business_unit_id,
            "client_id": client.id if client else None,
            "project_id": request.project_id,
            "billing_rate_usd_cents": request.billing_rate_usd_cents,
            "department_id": request.department_id,
            "salary_range": request.salary_range,
            "work_location": request.work_location,
            "job_status": PUBLISHED_STATUS,
            "created_by_user_id": user.UserID,
            "tenant_id": user.tenant_id,
        },
        tenant_id=user.tenant_id,
    )

    _store_slm_metadata(db, user, job_id, request)
    return job_id


def _store_slm_metadata(db: Session, user: Users, job_id: str, request: JobCreateRequest) -> None:
    """Job metadata for SLM learning. Optional by design: the job is already queued, so a
    failure here is logged and never fails the creation. It is written through its own session:
    store_job_metadata commits (and on failure rolls back) the session it is given, which must
    never be the caller's -- Flash's turn (the user's message, the job draft) lives there."""
    from app.core.database import SessionLocal
    from app.services.slm_job_metadata_service import SLMJobMetadataService

    own = SessionLocal()
    try:
        SLMJobMetadataService.store_job_metadata(
            db=own,
            job_id=job_id,
            job_title=request.job_title,
            job_description=request.job_description,
            business_unit_id=request.business_unit,
            department=request.department_id,
            required_skills=request.job_skills.split(',') if request.job_skills else None,
            min_experience_months=None,
            max_experience_months=None,
            created_by=user.UserID,
        )
        logger.info(f"[SLM] Stored metadata for job: {job_id} ({request.job_title})")
    except Exception as exc:
        logger.error(f"[SLM] Failed to store job metadata for {job_id}: {exc}", exc_info=True)
    finally:
        own.close()
