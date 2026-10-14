"""
HRMS-0711 Client Submission Pipeline — API Endpoints
=========================================================================
Prefix: /submissions
Tag:    submissions

No REST layer existed for this at all despite create_submission()/
update_client_response()/check_market_profile_rule() etc. being real,
tested backend (app.services.submission_service, pre-existing this
codebase). This also closes canonical S-249 ("Restrict Market Candidate
Submission") -- check_market_profile_rule() already IS the employee-
status submission guard that story calls for; it was just unreachable
over HTTP. No new/duplicate eligibility function was written.

Auth: get_current_internal_user, same posture as every Phase 4 endpoint
this program.

Routes:
  POST   /submissions
      Runs all three compliance gates (experience/market-profile/
      employment-type). 422 with every blocker if any gate fails
      (HRMS-0711 BR-01: all violations returned, not just the first).

  GET    /submissions
      List submissions, optionally filtered by demand_id.

  PATCH  /submissions/{submission_id}/client-response
      Client-response-driven status transition.

  GET    /submissions/violations
      The compliance audit log (every blocked attempt).
"""

from app.services.employee_allocation_service import (
    AllocationNeedsClient,
    AllocationOverCapacity,
    BuddyProgramNotGraduated,
    EmployeeAlreadyAllocated,
    ProjectClientMismatch,
)
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.bu_scope import candidate_scope_filter, ensure_candidate_visible
from app.core.data_scope import job_filter, visible_job_or_404
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.candidate import Candidate
from app.models.client import Client
from app.models.employee import Employee
from app.models.demand import Demand
from app.models.submission import Submission, SubmissionViolation
from app.models.user import Users
from app.schemas.submission import (
    ClientResponseRequest,
    CreateSubmissionRequest,
    SubmissionItem,
    SubmissionCandidateOption,
    SubmissionJobOption,
    SubmissionListResponse,
    SubmissionOptionsResponse,
    SubmissionViolationItem,
    SubmissionViolationListResponse,
)
from app.services.submission_service import (
    MARKET_PROFILE_ALLOWED_EMPLOYEE_STATUSES,
    DemandNotOpenForSubmission,
    check_employment_type_rule,
    check_experience_eligibility,
    DuplicateSubmission,
    InvalidSubmissionTransition,
    SubmissionComplianceError,
    create_submission,
    update_client_response,
)

router = APIRouter(prefix="/submissions", tags=["submissions"])


def _submissions_in_scope(db: Session, user: Users):
    """Submissions the caller may see: their tenant, a job (demand) in their business units
    or not yet assigned to one, and a candidate they may see (CEO 2026-10-12)."""
    return db.query(Submission).filter(
        Submission.tenant_id == user.tenant_id,
        job_filter(db, user, Submission.demand_id),
        candidate_scope_filter(db, user, Submission.candidate_id),
    )


def _to_item(db: Session, submission: Submission) -> SubmissionItem:
    demand = db.query(Demand).filter(Demand.id == submission.demand_id).first()
    candidate = db.query(Candidate).filter(Candidate.candidateID == submission.candidate_id).first()
    candidate_name = (
        f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''}".strip()
        if candidate else "(unknown candidate)"
    )
    client = db.query(Client).filter(Client.id == submission.client_id).first()
    return SubmissionItem(
        id=submission.id,
        demand_id=submission.demand_id,
        demand_job_title=demand.job_title if demand else "(unknown demand)",
        client_name=client.company_name if client else None,
        candidate_id=submission.candidate_id,
        candidate_name=candidate_name or "(unnamed candidate)",
        status=submission.status,
        submitted_at=submission.submitted_at,
        client_feedback=submission.client_feedback,
        client_response_at=submission.client_response_at,
        submission_rank=submission.submission_rank,
        source=submission.source,
    )

# the UI posts without the trailing slash; serve both instead of relying on a 307 redirect
@router.post(
    "",
    dependencies=[
        Depends(require_resource_permission("submissions", "create")),
        Depends(get_current_internal_user),
    ],
    response_model=SubmissionItem,
    include_in_schema=False,
)
@router.post(
    "/",
    dependencies=[
        Depends(require_resource_permission("submissions", "create")),
        Depends(get_current_internal_user),
    ],
    response_model=SubmissionItem,
    summary="Submit a candidate to a demand (runs all compliance gates)",
)
def submit_candidate(
    body: CreateSubmissionRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    # A demand and a job are the same record (jobs table). Both must be in the caller's
    # business-unit scope: another BU's job or candidate is "not found".
    demand = visible_job_or_404(db, current_user, body.demand_id, "Job")
    candidate = ensure_candidate_visible(db, body.candidate_id, current_user)

    try:
        submission = create_submission(
            db, tenant_id=current_user.tenant_id, demand=demand, candidate=candidate,
            submitted_by_user_id=current_user.UserID,
            submission_rank=body.submission_rank,
            submitted_as_resume_url=body.submitted_as_resume_url,
            source=body.source, subvendor_id=body.subvendor_id,
        )
    except SubmissionComplianceError as exc:
        # The submission itself is rejected, but the SubmissionViolation
        # audit rows create_submission() already flushed must still be
        # persisted (HRMS-0711's own audit-log requirement) -- commit
        # here rather than letting the request-scoped session roll back.
        db.commit()
        raise HTTPException(status_code=422, detail=[b for b in exc.blockers])
    except DemandNotOpenForSubmission as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except DuplicateSubmission as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(submission)
    from app.services.hiring_pipeline_service import notify

    notify(submission.candidate_id, "submission", f"{submission.id}:{submission.status}")
    return _to_item(db, submission)

@router.get(
    "",
    response_model=SubmissionListResponse,
    summary="List submissions",
    dependencies=[Depends(require_resource_permission("submissions", "view"))]
)
def list_submissions(
    demand_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    query = _submissions_in_scope(db, current_user)
    if demand_id:
        query = query.filter(Submission.demand_id == demand_id)
    submissions = query.order_by(Submission.submitted_at.desc()).all()
    return SubmissionListResponse(submissions=[_to_item(db, s) for s in submissions])

def _candidate_issues(candidate: Candidate) -> list:
    experience = check_experience_eligibility(candidate)
    employment_type = check_employment_type_rule(candidate)
    return [result["message"] for result in (experience, employment_type)
            if not (result.get("is_eligible") or result.get("allowed"))]


@router.get(
    "/options",
    dependencies=[
        Depends(require_resource_permission("submissions", "view")),
        Depends(get_current_internal_user),
    ],
    response_model=SubmissionOptionsResponse,
    summary="Jobs and candidates the Submissions screen can pick from",
)
def submission_options(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Open client jobs and bench/active/allocated employees' candidates in the caller's scope,
    with the jobs' BU, the candidates' BU lock, experience and employment type so the screen can
    say why a pair would be blocked. Job scope matches POST: the caller's business units plus
    jobs not yet assigned to one. The compliance gates still run on POST /submissions."""
    jobs = (
        db.query(Demand, Client.company_name)
        .join(Client, Client.id == Demand.client_id)
        .filter(
            or_(Demand.tenant_id == current_user.tenant_id, Demand.tenant_id.is_(None)),
            Demand.demand_status.in_(("OPEN", "IN_PROGRESS")),
            job_filter(db, current_user, Demand.jobID),
        )
        .order_by(Client.company_name, Demand.jobTitle)
        .all()
    )
    candidates = (
        db.query(Candidate, Employee.status)
        .join(Employee, Employee.candidate_id == Candidate.candidateID)
        .filter(
            Employee.status.in_(MARKET_PROFILE_ALLOWED_EMPLOYEE_STATUSES),
            candidate_scope_filter(db, current_user, Candidate.candidateID),
        )
        .order_by(Candidate.candidateFirstName, Candidate.candidateLastName)
        .all()
    )
    return SubmissionOptionsResponse(
        jobs=[
            SubmissionJobOption(id=job.id, job_title=job.job_title or "(untitled job)", client_id=job.client_id,
                                client_name=client_name, status=job.status, business_unit_id=job.business_unit_id)
            for job, client_name in jobs
        ],
        candidates=[
            SubmissionCandidateOption(
                id=c.candidateID,
                name=f"{c.candidateFirstName or ''} {c.candidateLastName or ''}".strip() or c.candidateID,
                employee_status=status, total_experience_months=c.total_experience_months,
                employment_type=c.employment_type, submission_bu_id=c.submission_bu_id,
                issues=_candidate_issues(c),
            )
            for c, status in candidates
        ],
    )

@router.get(
    "/violations",
    dependencies=[
        Depends(require_resource_permission("submissions", "view")),
        Depends(get_current_internal_user),
    ],
    response_model=SubmissionViolationListResponse,
    summary="Compliance violation audit log",
)
def list_violations(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    violations = (
        db.query(SubmissionViolation)
        .filter(SubmissionViolation.tenant_id == current_user.tenant_id,
                candidate_scope_filter(db, current_user, SubmissionViolation.candidate_id))
        .order_by(SubmissionViolation.attempted_at.desc())
        .all()
    )
    return SubmissionViolationListResponse(
        violations=[
            SubmissionViolationItem(
                id=v.id, candidate_id=v.candidate_id, violation_type=v.violation_type,
                candidate_status_at_time=v.candidate_status_at_time,
                blocked_message=v.blocked_message, attempted_at=v.attempted_at,
            )
            for v in violations
        ]
    )

@router.post(
    "/{submission_id}/client-response",
    dependencies=[
        Depends(require_resource_permission("submissions", "edit")),
        Depends(get_current_internal_user),
    ],
    response_model=SubmissionItem,
    summary="Record the client's response to a submission",
)
def client_response(
    submission_id: str,
    body: ClientResponseRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    submission = _submissions_in_scope(db, current_user).filter(Submission.id == submission_id).first()
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found.")
    try:
        submission = update_client_response(
            db, submission, body.new_status, client_feedback=body.client_feedback,
        )
    except InvalidSubmissionTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (EmployeeAlreadyAllocated, BuddyProgramNotGraduated, AllocationOverCapacity, AllocationNeedsClient,
            ProjectClientMismatch) as exc:
        # PLACED allocates the employee to the client; it can't be recorded half-done
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Cannot place: {exc}")
    db.commit()
    db.refresh(submission)
    from app.services.hiring_pipeline_service import notify

    notify(submission.candidate_id, "submission", f"{submission.id}:{submission.status}")
    return _to_item(db, submission)
