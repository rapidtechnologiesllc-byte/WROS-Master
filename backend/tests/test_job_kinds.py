"""Job kinds (CEO 2026-11-27, docs/RECRUITMENT_VS_WORKFORCE_DESIGN.md 2.1): every job is a hiring REQUISITION or a
CLIENT_DEMAND, recorded when it is created and never inferred later; existing jobs are classified from every signal,
the disagreeing ones are UNCLASSIFIED and read-only until an administrator decides."""
import pytest
from fastapi import HTTPException

from app.models.client import Client
from app.models.job_kind import CLIENT_DEMAND, REQUISITION, UNCLASSIFIED, JobKind
from app.models.user import InterviewPanel
from app.services import job_kind_service as kinds
from app.services.job_creation_service import resolve_job_client
from tests import factories as f


def _client(db, name=None, tenant_id=1):
    f.tenant(db, tenant_id)
    client = Client(tenant_id=tenant_id, company_name=name or f"Client {f.uid()}")
    db.add(client)
    db.flush()
    return client


def test_a_new_job_records_its_kind_in_the_same_transaction(db):
    internal = f.job(db)
    client_role = f.job(db, client_id=_client(db).id)
    assert kinds.job_kind(db, internal) == REQUISITION
    assert kinds.job_kind(db, client_role) == CLIENT_DEMAND
    assert db.get(JobKind, internal.jobID).classified_by == "system"


def test_a_job_without_a_tenant_is_refused(db):
    with pytest.raises(ValueError):
        f.job(db, tenant_id=None)


def test_a_job_with_children_cannot_change_client(db):
    job = f.job(db, client_id=_client(db).id)
    kinds.assert_client_change_allowed(db, job, _client(db).id)  # nothing hangs off it yet: allowed
    db.add(InterviewPanel(candidate_id=f.candidate(db).candidateID, round_name="L1 Interview", job_id=job.jobID))
    db.flush()
    with pytest.raises(kinds.JobKindRefused):
        kinds.assert_client_change_allowed(db, job, None)
    kinds.assert_client_change_allowed(db, job, job.client_id)  # same client: fine


def test_an_unclassified_job_is_read_only_until_classified(db):
    job = f.job(db, client_id=_client(db).id)
    db.get(JobKind, job.jobID).kind = UNCLASSIFIED
    db.flush()
    with pytest.raises(kinds.JobKindRefused):
        kinds.assert_writable(db, job)
    kinds.set_kind(db, job, CLIENT_DEMAND, "admin-1", "client confirmed by the account manager")
    kinds.assert_writable(db, job)
    with pytest.raises(kinds.JobKindRefused):  # a requisition has no client
        kinds.set_kind(db, job, REQUISITION, "admin-1", "wrong")


def test_classification_uses_every_signal(db):
    from app.models.tenant import Tenant

    tenant = db.get(Tenant, 1) or f.tenant(db)
    internal = f.job(db)
    client_role = f.job(db, client_id=_client(db).id)
    ourselves = f.job(db, client_id=_client(db, name=tenant.name).id)  # a "client" that is the company itself
    for job in (internal, client_role, ourselves):  # forget the kinds recorded at creation
        db.delete(db.get(JobKind, job.jobID))
    db.flush()
    report = kinds.classify(db, dry_run=True)
    assert db.get(JobKind, internal.jobID) is None  # dry run writes nothing
    review_ids = {item["job_id"] for item in report["review"]}
    assert ourselves.jobID in review_ids and internal.jobID not in review_ids
    kinds.classify(db, dry_run=False)
    assert kinds.job_kind(db, internal) == REQUISITION
    assert kinds.job_kind(db, client_role) == CLIENT_DEMAND
    assert kinds.job_kind(db, ourselves) == UNCLASSIFIED


def test_an_unknown_company_name_is_refused_not_an_internal_hire(db):
    from app.models.tenant import Tenant

    tenant = db.get(Tenant, 1) or f.tenant(db)
    known = _client(db, name="Acme Insurance")
    assert resolve_job_client(db, 1, None, "acme insurance").id == known.id
    assert resolve_job_client(db, 1, None, tenant.name) is None  # our own name: an internal hire
    assert resolve_job_client(db, 1, None, "") is None
    with pytest.raises(HTTPException):
        resolve_job_client(db, 1, None, "Acme Insurnce")  # a typo is not a silent internal hire
