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

Auth: get_current_hr_or_admin, same posture as every Phase 4 endpoint
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

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin
from app.models.candidate import Candidate
from app.models.demand import Demand
from app.models.submission import Submission, SubmissionViolation
from app.models.user import Users
from app.schemas.submission import (
    ClientResponseRequest,
    CreateSubmissionRequest,
    SubmissionItem,
    SubmissionListResponse,
    SubmissionViolationItem,
    SubmissionViolationListResponse,
)
from app.services.submission_service import (
    DemandNotOpenForSubmission,
    DuplicateSubmission,
    InvalidSubmissionTransition,
    SubmissionComplianceError,
    create_submission,
    update_client_response,
)

router = APIRouter(prefix="/submissions", tags=["submissions"])


def _to_item(db: Session, submission: Submission) -> SubmissionItem:
    demand = db.query(Demand).filter(Demand.id == submission.demand_id).first()
    candidate = db.query(Candidate).filter(Candidate.candidateID == submission.candidate_id).first()
    candidate_name = (
        f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''}".strip()
        if candidate else "(unknown candidate)"
    )
    return SubmissionItem(
        id=submission.id,
        demand_id=submission.demand_id,
        demand_job_title=demand.job_title if demand else "(unknown demand)",
        candidate_id=submission.candidate_id,
        candidate_name=candidate_name or "(unnamed candidate)",
        status=submission.status,
        submitted_at=submission.submitted_at,
        client_feedback=submission.client_feedback,
        client_response_at=submission.client_response_at,
        submission_rank=submission.submission_rank,
        source=submission.source,
    )


@router.post(
    "", response_model=SubmissionItem,
    summary="Submit a candidate to a demand (runs all compliance gates)",
)
def submit_candidate(
    body: CreateSubmissionRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    demand = db.query(Demand).filter(Demand.id == body.demand_id).first()
    if demand is None:
        raise HTTPException(status_code=404, detail="Demand not found.")
    candidate = db.query(Candidate).filter(Candidate.candidateID == body.candidate_id).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")

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
    return _to_item(db, submission)


@router.get("", response_model=SubmissionListResponse, summary="List submissions")
def list_submissions(
    demand_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    query = db.query(Submission).filter(Submission.tenant_id == current_user.tenant_id)
    if demand_id:
        query = query.filter(Submission.demand_id == demand_id)
    submissions = query.order_by(Submission.submitted_at.desc()).all()
    return SubmissionListResponse(submissions=[_to_item(db, s) for s in submissions])


@router.get(
    "/violations", response_model=SubmissionViolationListResponse,
    summary="Compliance violation audit log",
)
def list_violations(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    violations = (
        db.query(SubmissionViolation)
        .filter(SubmissionViolation.tenant_id == current_user.tenant_id)
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


@router.patch(
    "/{submission_id}/client-response", response_model=SubmissionItem,
    summary="Record the client's response to a submission",
)
def client_response(
    submission_id: str,
    body: ClientResponseRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found.")
    try:
        submission = update_client_response(
            db, submission, body.new_status, client_feedback=body.client_feedback,
        )
    except InvalidSubmissionTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(submission)
    return _to_item(db, submission)
