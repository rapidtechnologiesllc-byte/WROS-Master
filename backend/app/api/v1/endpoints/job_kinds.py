"""Job kinds review (CEO 2026-11-27, docs/RECRUITMENT_VS_WORKFORCE_DESIGN.md 2.1): the jobs the one-time classification
could not decide (UNCLASSIFIED: read-only until classified), and classifying one as a hiring requisition or a client
role. Shown under Admin -> System -> Job Kinds."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.job_kind import UNCLASSIFIED, JobKind
from app.models.user import Jobs, Users
from app.services import job_kind_service

router = APIRouter(prefix="/job-kinds", tags=["Job kinds"])


class JobKindItem(BaseModel):
    job_id: str
    title: str
    company: Optional[str] = None
    client_id: Optional[str] = None
    kind: str
    evidence: Optional[str] = None


class JobKindReview(BaseModel):
    jobs: List[JobKindItem]


class SetKindRequest(BaseModel):
    kind: str
    reason: str


def _item(job: Jobs, row: JobKind) -> JobKindItem:
    return JobKindItem(job_id=job.jobID, title=job.jobTitle, company=job.companyName, client_id=job.client_id,
                       kind=row.kind, evidence=row.evidence)


@router.get("/review", response_model=JobKindReview,
            dependencies=[Depends(require_resource_permission("jobs", "edit"))])
def jobs_to_classify(db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    """The caller's tenant's UNCLASSIFIED jobs, with the evidence that disagreed."""
    rows = db.query(Jobs, JobKind).join(JobKind, JobKind.job_id == Jobs.jobID).filter(
        JobKind.kind == UNCLASSIFIED, JobKind.tenant_id == user.tenant_id).order_by(Jobs.jobCreatedAt).all()
    return JobKindReview(jobs=[_item(job, row) for job, row in rows])


@router.put("/{job_id}", response_model=JobKindItem,
            dependencies=[Depends(require_resource_permission("jobs", "edit"))])
def classify_job(job_id: str, body: SetKindRequest, db: Session = Depends(get_db),
                 user: Users = Depends(get_current_internal_user)):
    job = db.query(Jobs).filter(Jobs.jobID == job_id, Jobs.tenant_id == user.tenant_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        row = job_kind_service.set_kind(db, job, body.kind, user.UserID, body.reason)
    except job_kind_service.JobKindRefused as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    return _item(job, row)
