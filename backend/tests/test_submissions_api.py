"""
Client Submissions (HRMS-0711) on the real routes and the real Postgres schema: the
Submissions screen (nav: Submissions) and the candidate profile's "Submit Job" modal both
post here. Only a bench employee with 5+ years, W2 and a passed BGV reaches a client.
"""
import uuid
from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.background_verification import BackgroundVerification
from app.models.business_unit import BusinessUnit
from app.models.candidate import Candidate
from app.models.candidate_ownership import POOL_BU, CandidateOwnership
from app.models.client import Client
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.role_template import Resource, RoleTemplate, RoleTemplatePermission
from app.models.submission import Submission, SubmissionViolation
from app.models.tenant import Tenant
from app.models.user import Users
from tests.hiring_fixtures import full_access_role


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def client(db):
    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    # status emails are queued on their own connection; the queue is not under test here
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True):
        yield TestClient(app)
    app.dependency_overrides.clear()


def _user(db, role):
    user = Users(UserID=f"U-{_uid()}", UserName="Recruiter", UserEmail=f"r{_uid()}@blitzenx.com", UserPassword="x",
                 UserRole="user", tenant_id=1, role_template_id=role.id, password_reset_required=False)
    db.add(user)
    db.flush()
    return user


def _headers(user):
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": user.role_template_id})}


def _candidate(db, *, employee_status=None, bgv="PASSED", months=72, employment_type="W2_FULLTIME"):
    candidate = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"c{_uid()}@example.com", candidatePassword="x",
                          candidateFirstName="Sam", candidateLastName="Lee", tenant_id=1,
                          total_experience_months=months, employment_type=employment_type)
    db.add(candidate)
    db.flush()
    if employee_status:
        db.add(Employee(tenant_id=1, candidate_id=candidate.candidateID, first_name="Sam", last_name="Lee",
                        email=f"e{_uid()}@blitzenx.com", joining_date=date(2025, 1, 1), status=employee_status))
    if bgv:
        db.add(BackgroundVerification(tenant_id=1, candidate_id=candidate.candidateID, status=bgv))
    db.flush()
    return candidate


@pytest.fixture
def world(db):
    admin = _user(db, full_access_role(db))
    acme = Client(tenant_id=1, company_name=f"Acme {_uid()}")
    db.add(acme)
    db.flush()
    job = Demand(tenant_id=1, client_id=acme.id, job_title="Sr. Guidewire Developer", min_experience_years=5.0,
                 work_location="REMOTE", status="OPEN")
    db.add(job)
    db.flush()
    bench = _candidate(db, employee_status="BENCH")
    db.commit()
    return admin, acme, job, bench


def _submit(client, user, job, candidate, **extra):
    return client.post("/api/v1/submissions", headers=_headers(user),
                       json={"demand_id": job.id, "candidate_id": candidate.candidateID, **extra})


def test_unauthenticated_request_is_rejected(client):
    assert client.get("/api/v1/submissions").status_code in (401, 403)


def test_bench_employee_is_submitted_to_the_client(client, world):
    admin, acme, job, bench = world
    resp = _submit(client, admin, job, bench)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["status"], body["candidate_name"], body["demand_job_title"], body["source"]) == \
        ("SUBMITTED", "Sam Lee", "Sr. Guidewire Developer", "INTERNAL")
    assert body["client_name"] == acme.company_name


def test_candidate_profile_modal_payload_is_accepted(client, world):
    """The profile's Submit Job modal sends submission_rank 1 and source INTERNAL."""
    admin, _, job, bench = world
    resp = _submit(client, admin, job, bench, submission_rank=1, source="INTERNAL")
    assert resp.status_code == 200, resp.text


def test_unknown_source_is_a_validation_error_not_a_500(client, world):
    admin, _, job, bench = world
    resp = _submit(client, admin, job, bench, source="hrms")
    assert resp.status_code == 422
    assert client.get("/api/v1/submissions", headers=_headers(admin)).json()["submissions"] == []


def test_candidate_not_yet_an_employee_is_blocked_and_logged(client, world, db):
    admin, _, job, _ = world
    fresh = _candidate(db, bgv=None)
    db.commit()
    resp = _submit(client, admin, job, fresh)
    assert resp.status_code == 422
    assert "MARKET_PROFILE_SUBMISSION_BLOCKED" in [b["error"] for b in resp.json()["detail"]]
    violations = client.get("/api/v1/submissions/violations", headers=_headers(admin)).json()["violations"]
    assert any(v["candidate_id"] == fresh.candidateID and v["violation_type"] == "NO_MARKET_PROFILE"
               for v in violations)


def test_five_year_rule_blocks_submission(client, world, db):
    admin, _, job, _ = world
    junior = _candidate(db, employee_status="BENCH", months=48)
    db.commit()
    options = client.get("/api/v1/submissions/options", headers=_headers(admin)).json()["candidates"]
    assert any("5 years" in issue for c in options if c["id"] == junior.candidateID for issue in c["issues"])
    resp = _submit(client, admin, job, junior)
    assert resp.status_code == 422
    assert "EXPERIENCE_INELIGIBLE" in [b["error"] for b in resp.json()["detail"]]


def test_duplicate_submission_is_rejected(client, world):
    admin, _, job, bench = world
    assert _submit(client, admin, job, bench).status_code == 200
    assert _submit(client, admin, job, bench).status_code == 409


def test_list_filtered_by_job(client, world):
    admin, _, job, bench = world
    _submit(client, admin, job, bench)
    resp = client.get(f"/api/v1/submissions?demand_id={job.id}", headers=_headers(admin))
    assert resp.status_code == 200
    assert [s["candidate_id"] for s in resp.json()["submissions"]] == [bench.candidateID]


def test_client_response_walks_the_pipeline_and_rejects_skips(client, world):
    admin, _, job, bench = world
    sid = _submit(client, admin, job, bench).json()["id"]
    url = f"/api/v1/submissions/{sid}/client-response"
    assert client.post(url, headers=_headers(admin), json={"new_status": "PLACED"}).status_code == 409
    for status in ("SHORTLISTED", "CLIENT_INTERVIEW_REQUESTED", "OFFER_EXTENDED"):
        resp = client.post(url, headers=_headers(admin), json={"new_status": status})
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == status


def test_submit_to_unknown_job_is_404(client, world):
    admin, _, _, bench = world
    resp = client.post("/api/v1/submissions", headers=_headers(admin),
                       json={"demand_id": "does-not-exist", "candidate_id": bench.candidateID})
    assert resp.status_code == 404


def _role(db, grants, org_level=True):
    """A role holding exactly `grants` ({resource: (view, create, edit)}), e.g. the seeded Partner:
    submissions view/create/edit, resources view only."""
    role = RoleTemplate(tenant_id=1, name=f"role-{_uid()}", display_name="Partner", hierarchy_level=16,
                        org_level_access=org_level, enabled=True)
    db.add(role)
    db.flush()
    for name, (view, create, edit) in grants.items():
        resource = db.query(Resource).filter_by(tenant_id=1, name=name).one()
        db.add(RoleTemplatePermission(role_template_id=role.id, resource_id=resource.id, tenant_id=1,
                                      can_view=view, can_create=create, can_edit=edit, can_delete=False))
    db.flush()
    return role


def test_submissions_permission_alone_runs_the_whole_screen(client, world, db):
    """A role with the submissions permission (and only view on resources) can list, read the
    violation log, submit and record the client's response -- one permission, one screen."""
    _, _, job, bench = world
    partner = _user(db, _role(db, {"submissions": (True, True, True), "resources": (True, False, False)}))
    db.commit()
    assert client.get("/api/v1/submissions/options", headers=_headers(partner)).status_code == 200
    assert client.get("/api/v1/submissions/violations", headers=_headers(partner)).status_code == 200
    resp = _submit(client, partner, job, bench)
    assert resp.status_code == 200, resp.text
    resp = client.post(f"/api/v1/submissions/{resp.json()['id']}/client-response", headers=_headers(partner),
                       json={"new_status": "SHORTLISTED"})
    assert resp.status_code == 200, resp.text


def test_view_only_role_cannot_submit_or_record_responses(client, world, db):
    admin, _, job, bench = world
    sid = _submit(client, admin, job, bench).json()["id"]
    viewer = _user(db, _role(db, {"submissions": (True, False, False), "resources": (True, True, True)}))
    db.commit()
    assert client.get("/api/v1/submissions", headers=_headers(viewer)).status_code == 200
    assert _submit(client, viewer, job, _candidate(db, employee_status="BENCH")).status_code == 403
    resp = client.post(f"/api/v1/submissions/{sid}/client-response", headers=_headers(viewer),
                       json={"new_status": "SHORTLISTED"})
    assert resp.status_code == 403


def test_options_list_open_client_jobs_and_bench_employees_only(client, world, db):
    admin, acme, job, bench = world
    closed = Demand(tenant_id=1, client_id=acme.id, job_title="Closed role", min_experience_years=5.0,
                    work_location="REMOTE", status="CANCELLED")
    no_client = Demand(tenant_id=1, job_title="Internal role", min_experience_years=5.0,
                       work_location="REMOTE", status="OPEN")
    db.add_all([closed, no_client])
    fresh = _candidate(db, bgv=None)
    exited = _candidate(db, employee_status="EXITED")
    db.commit()
    resp = client.get("/api/v1/submissions/options", headers=_headers(admin))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    jobs = {j["id"]: j for j in body["jobs"]}
    assert job.id in jobs and jobs[job.id]["client_name"] == acme.company_name
    assert closed.id not in jobs and no_client.id not in jobs
    candidates = {c["id"]: c for c in body["candidates"]}
    assert bench.candidateID in candidates and candidates[bench.candidateID]["employee_status"] == "BENCH"
    assert candidates[bench.candidateID]["issues"] == []
    assert fresh.candidateID not in candidates and exited.candidateID not in candidates



def test_job_without_a_client_is_409_not_500(client, world, db):
    admin, _, _, bench = world
    internal = Demand(tenant_id=1, job_title="Internal role", min_experience_years=5.0, work_location="REMOTE",
                      status="OPEN")
    db.add(internal)
    db.commit()
    resp = _submit(client, admin, internal, bench)
    assert resp.status_code == 409
    assert "no client" in resp.json()["detail"]


def test_blocked_attempt_keeps_its_audit_row_and_inserts_no_submission(client, world, db):
    admin, _, job, _ = world
    fresh = _candidate(db, bgv=None)
    db.commit()
    assert _submit(client, admin, job, fresh).status_code == 422
    assert db.query(SubmissionViolation).filter_by(candidate_id=fresh.candidateID).count() == 1
    assert db.query(Submission).filter_by(candidate_id=fresh.candidateID).count() == 0


def test_options_respect_tenant_and_business_unit_scope(client, world, db):
    """A user outside every business unit sees unassigned jobs and Org Pool candidates only,
    and never another tenant's jobs."""
    admin, acme, job, bench = world
    if db.query(Tenant).filter_by(id=2).first() is None:
        db.add(Tenant(id=2, name="other-tenant"))
        db.flush()
    unit = BusinessUnit(tenant_id=1, name=f"bu-{_uid()}", display_name="BU")
    db.add(unit)
    db.flush()
    other_tenant_job = Demand(tenant_id=2, client_id=acme.id, job_title="Other tenant", min_experience_years=5.0,
                              work_location="REMOTE", status="OPEN")
    bu_job = Demand(tenant_id=1, client_id=acme.id, job_title="BU job", min_experience_years=5.0,
                    work_location="REMOTE", status="OPEN", business_unit_id=unit.id)
    db.add_all([other_tenant_job, bu_job])
    bu_candidate = _candidate(db, employee_status="BENCH")
    db.add(CandidateOwnership(candidateID=bu_candidate.candidateID, pool_status=POOL_BU, owned_by_bu_id=unit.id))
    outsider = _user(db, _role(db, {"submissions": (True, True, True)}, org_level=False))
    db.commit()

    body = client.get("/api/v1/submissions/options", headers=_headers(outsider)).json()
    job_ids = {j["id"] for j in body["jobs"]}
    candidate_ids = {c["id"] for c in body["candidates"]}
    assert job.id in job_ids and bu_job.id not in job_ids and other_tenant_job.id not in job_ids
    assert bench.candidateID in candidate_ids and bu_candidate.candidateID not in candidate_ids

    body = client.get("/api/v1/submissions/options", headers=_headers(admin)).json()
    assert bu_job.id in {j["id"] for j in body["jobs"]} and other_tenant_job.id not in {j["id"] for j in body["jobs"]}
