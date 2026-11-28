"""Job kinds (docs/RECRUITMENT_VS_WORKFORCE_DESIGN.md 2.1, CEO-approved 2026-11-27).

record on insert  every job row gets its kind in the transaction that inserts it: a client, an opportunity or a
                  project makes it a CLIENT_DEMAND, otherwise it is a REQUISITION. A job without a tenant is refused.
job_kind()        the stored kind; fails fast when a job has none
guards            assert_writable (UNCLASSIFIED jobs are read-only), assert_client_change_allowed (a job with
                  applications, rounds, offers, submissions or allocations never changes client)
classify()        the one-time classification of existing jobs, from every signal; disagreeing evidence ->
                  UNCLASSIFIED (manual review list). dry_run=True writes nothing and returns the report.
"""
import logging
from collections import Counter
from typing import Dict, List, Optional

from sqlalchemy import func, inspect
from sqlalchemy.orm import Session

from app.models.job_kind import CLIENT_DEMAND, REQUISITION, UNCLASSIFIED, JobKind, kind_at_creation  # noqa: F401
from app.models.user import Jobs

logger = logging.getLogger(__name__)


class JobKindMissing(RuntimeError):
    """A job without a stored kind: the classification has not run, or a job was inserted outside the ORM."""


class JobKindRefused(ValueError):
    """The change is not allowed for this job's kind; the message says why in plain words."""


def job_kind(db: Session, job) -> str:
    job_id = job if isinstance(job, str) else job.jobID
    row = db.get(JobKind, job_id)
    if row is None:
        raise JobKindMissing(f"Job {job_id} has no recorded kind (requisition or client demand)")
    return row.kind


def assert_writable(db: Session, job) -> None:
    if job_kind(db, job) == UNCLASSIFIED:
        raise JobKindRefused(f"Job {job.jobID} is waiting to be classified as a hiring requisition or a client "
                             f"role (Admin -> Job classification review); it can't be changed until then.")


# --------------------------------------------------------------------------- children

def _children(db: Session, job_id: str) -> Dict[str, int]:
    """How many records hang off the job (each one would follow the job into the wrong kind)."""
    from app.models.candidate import CandidateJobApplication
    from app.models.employee_allocation import EmployeeAllocation
    from app.models.offer import Offer
    from app.models.offer_letter import OfferLetter
    from app.models.submission import Submission
    from app.models.user import InterviewPanel

    counts = {
        "applications": db.query(func.count(CandidateJobApplication.id)).filter(CandidateJobApplication.job_id == job_id),
        "interview rounds": db.query(func.count(InterviewPanel.id)).filter(InterviewPanel.job_id == job_id),
        "offers": db.query(func.count(Offer.id)).filter(Offer.job_id == job_id),
        "offer letters": db.query(func.count(OfferLetter.id)).filter(OfferLetter.job_id == job_id),
        "submissions": db.query(func.count(Submission.id)).filter(Submission.demand_id == job_id),
        "allocations": db.query(func.count(EmployeeAllocation.id)).filter(EmployeeAllocation.demand_id == job_id),
    }
    return {name: query.scalar() or 0 for name, query in counts.items()}


def assert_client_change_allowed(db: Session, job, new_client_id: Optional[str]) -> None:
    """A job's client is fixed once anything hangs off it (CEO 2026-11-27: a rename used to re-match the client
    silently, turning a hiring job into a client role or back)."""
    if (new_client_id or None) == (job.client_id or None):
        return
    held = {name: n for name, n in _children(db, job.jobID).items() if n}
    if held:
        what = ", ".join(f"{n} {name}" for name, n in held.items())
        raise JobKindRefused(f"The client of this job can't change: it already has {what}. Open a new job instead.")


# --------------------------------------------------------------------------- one-time classification

def own_company_names(db: Session, tenant_id: int) -> set:
    """The tenant's own names (the parent company and its companies): a 'client' with one of them is BlitzenX."""
    from app.models.location import Location
    from app.models.tenant import Tenant

    names = set()
    tenant = db.get(Tenant, tenant_id)
    if tenant is not None:
        names |= {n.strip().lower() for n in (tenant.name, getattr(tenant, "parent_company_name", None)) if n}
    names |= {row[0].strip().lower() for row in db.query(Location.name).filter(Location.tenant_id == tenant_id) if row[0]}
    return names


def classify_one(db: Session, job, own_names_cache: Dict[int, set]) -> (str, str):
    """(kind, evidence) for an existing job, from every signal (design section 4 step 1)."""
    from app.models.client import Client
    from app.models.client_update import UpcomingRole

    children = _children(db, job.jobID)
    delivery = children["submissions"] + children["allocations"]
    hiring = children["applications"] + children["interview rounds"] + children["offers"] + children["offer letters"]
    client = db.get(Client, job.client_id) if job.client_id else None
    signals = {
        "client": bool(job.client_id), "opportunity": bool(job.opportunity_id), "project": bool(job.project_id),
        "source_opportunity": (job.source_type or "") == "OPPORTUNITY",
        "upcoming_role": db.get(UpcomingRole, job.jobID) is not None,
        "delivery_records": delivery, "hiring_records": hiring,
    }
    evidence = ", ".join(f"{k}={v}" for k, v in signals.items())
    if job.client_id and client is None:
        return UNCLASSIFIED, f"client {job.client_id} does not exist; {evidence}"
    if client is not None and client.tenant_id not in (None, job.tenant_id):
        return UNCLASSIFIED, f"client belongs to tenant {client.tenant_id}, job to {job.tenant_id}; {evidence}"
    if client is not None:
        own = own_names_cache.setdefault(job.tenant_id, own_company_names(db, job.tenant_id))
        if (client.company_name or "").strip().lower() in own:
            # an internal hiring job matched to a "client" that is BlitzenX itself
            if delivery or job.opportunity_id or job.project_id:
                return UNCLASSIFIED, f"client is the company itself but has delivery work; {evidence}"
            return UNCLASSIFIED, f"client is the company itself (likely an internal hire); {evidence}"
        return CLIENT_DEMAND, evidence
    if job.opportunity_id or job.project_id or signals["upcoming_role"] or delivery:
        return UNCLASSIFIED, f"no client but client-side records; {evidence}"
    return REQUISITION, evidence


def classify(db: Session, *, dry_run: bool) -> dict:
    """Classify every job that has no kind yet. Refuses (changes nothing) while any job has no tenant.
    Returns the report: counts per tenant and kind, and the manual review list with the reason for each."""
    missing_tenant = db.query(Jobs.jobID).filter(Jobs.tenant_id.is_(None)).limit(20).all()
    if missing_tenant:
        raise JobKindRefused(f"{len(missing_tenant)}+ job(s) have no tenant (e.g. {missing_tenant[0][0]}): "
                             f"give each its tenant before classifying")
    if dry_run and not inspect(db.get_bind()).has_table(JobKind.__tablename__, schema=JobKind.__table__.schema):
        have = set()  # previewing a database from before job kinds existed (e.g. the masked production copy)
    else:
        have = {row[0] for row in db.query(JobKind.job_id)}
    own: Dict[int, set] = {}
    counts: Counter = Counter()
    review: List[dict] = []
    for job in db.query(Jobs).order_by(Jobs.tenant_id, Jobs.jobCreatedAt).all():
        if job.jobID in have:
            continue
        kind, evidence = classify_one(db, job, own)
        counts[(job.tenant_id, kind)] += 1
        if kind == UNCLASSIFIED:
            review.append({"job_id": job.jobID, "tenant_id": job.tenant_id, "title": job.jobTitle, "reason": evidence})
        if not dry_run:
            db.add(JobKind(job_id=job.jobID, tenant_id=job.tenant_id, kind=kind, classified_by="migration",
                           evidence=evidence))
    if not dry_run:
        db.flush()
    report = {"dry_run": dry_run, "classified": sum(counts.values()),
              "by_tenant_and_kind": {f"{t}:{k}": n for (t, k), n in sorted(counts.items())}, "review": review}
    logger.info(f"[JobKinds] classify dry_run={dry_run}: {report['by_tenant_and_kind']}, {len(review)} for review")
    return report


def set_kind(db: Session, job, kind: str, user_id: str, reason: str) -> JobKind:
    """An administrator classifies a job from the review list (or corrects one)."""
    if kind not in (REQUISITION, CLIENT_DEMAND):
        raise JobKindRefused(f"Kind must be {REQUISITION} or {CLIENT_DEMAND}")
    if kind == CLIENT_DEMAND and not job.client_id:
        raise JobKindRefused("A client role needs its client: set the client on the job first")
    if kind == REQUISITION and (job.client_id or job.opportunity_id or job.project_id):
        raise JobKindRefused("A hiring requisition has no client, opportunity or project: clear them first "
                             "(or open a new requisition and link it)")
    if not (reason or "").strip():
        raise JobKindRefused("Say why (it is kept with the classification)")
    row = db.get(JobKind, job.jobID)
    if row is None:
        row = JobKind(job_id=job.jobID, tenant_id=job.tenant_id, kind=kind, classified_by=user_id, evidence=reason)
        db.add(row)
    else:
        row.kind, row.classified_by, row.evidence = kind, user_id, f"{reason} (was {row.kind})"
        row.classified_at = func.now()
    db.flush()
    return row

