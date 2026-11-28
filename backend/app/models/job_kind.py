"""What a job record is (CEO 2026-11-27, docs/RECRUITMENT_VS_WORKFORCE_DESIGN.md 2.1): a hiring REQUISITION
(Recruitment: BlitzenX hires external people as employees) or a CLIENT_DEMAND (Workforce: a client's open role,
filled only by bench employees). Stored, never inferred from client_id, which a company-name edit used to change.

Every job row gets its kind in the transaction that inserts it (app.services.job_kind_service listens on the
insert). Existing jobs are classified once by the job_kinds_classify data migration; those whose evidence
disagrees are UNCLASSIFIED: readable, and every write to them is refused until an administrator classifies them.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, event, func
from sqlalchemy.dialects.postgresql import insert

from app.models.base import Base
from app.models.user import Jobs

REQUISITION = "REQUISITION"
CLIENT_DEMAND = "CLIENT_DEMAND"
UNCLASSIFIED = "UNCLASSIFIED"
JOB_KINDS = (REQUISITION, CLIENT_DEMAND, UNCLASSIFIED)


class JobKind(Base):
    __tablename__ = "job_kinds"

    job_id = Column(String(512), ForeignKey("jobs.jobID"), primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    kind = Column(String(20), nullable=False, index=True)
    # a user id, "system" (recorded at creation) or "migration"
    classified_by = Column(String(512), nullable=False)
    classified_at = Column(DateTime, nullable=False, server_default=func.now())
    evidence = Column(Text, nullable=True)


def kind_at_creation(job) -> str:
    """A client, an opportunity or a project makes a new job a client role; otherwise it is a hiring requisition."""
    return CLIENT_DEMAND if (job.client_id or job.opportunity_id or job.project_id) else REQUISITION


@event.listens_for(Jobs, "after_insert")
def _record_kind_on_insert(mapper, connection, job) -> None:
    """Every insert path (endpoints, Flash, opportunities, imports, tests) records the kind in the same
    transaction as the job row. A kind already recorded for the job is not overwritten."""
    if not job.tenant_id:
        raise ValueError(f"Job {job.jobID} has no tenant: every job belongs to one (there is no default tenant)")
    connection.execute(insert(JobKind.__table__).values(
        job_id=job.jobID, tenant_id=job.tenant_id, kind=kind_at_creation(job), classified_by="system",
        evidence="recorded at creation").on_conflict_do_nothing(index_elements=["job_id"]))
