"""
Client Submissions (HRMS-0711) on the real routes and the real Postgres schema: the
Submissions screen (nav: Submissions) and the candidate profile's "Submit Job" modal both
post here. Only a bench employee with 5+ years, W2 and a passed BGV reaches a client.
"""
import uuid
from datetime import date, timedelta
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
from app.models.employee_allocation import EmployeeAllocation
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
    # status emails and job-application events are queued on their own connection; the queue
    # is not under test here
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True), \
            patch("app.api.v1.endpoints.create_job.MessageQueueService.enqueue", return_value=None):
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


def _candidate(db, *, employee_status=None, bgv="PASSED", months=72, employment_type="W2_FULLTIME", buddy="GRADUATED"):
    candidate = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"c{_uid()}@example.com", candidatePassword="x",
                          candidateFirstName="Sam", candidateLastName="Lee", tenant_id=1,
                          total_experience_months=months, employment_type=employment_type)
    db.add(candidate)
    db.flush()
    if employee_status:
        db.add(Employee(tenant_id=1, candidate_id=candidate.candidateID, first_name="Sam", last_name="Lee",
                        email=f"e{_uid()}@blitzenx.com", joining_date=date(2025, 1, 1), status=employee_status,
                        buddy_program_status=buddy))
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


def _role(db, grants, org_level=True, level=16):
    """A role holding exactly `grants` ({resource: (view, create, edit)}), e.g. the seeded Partner:
    submissions view/create/edit, resources view only."""
    role = RoleTemplate(tenant_id=1, name=f"role-{_uid()}", display_name="Partner", hierarchy_level=level,
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


# --------------------------------------------------------------------------- CEO 2026-10-14 gates
# Staff Aug (SPECIALITY) and Core (direct client, CORE): new hires prove themselves on Staff Aug,
# then are Core-certified and moved to Core. Both need Buddy graduated and no open escalation.

def _job(db, client_, **kw):
    job = Demand(tenant_id=1, client_id=client_.id, job_title=kw.pop("title", "Role"), min_experience_years=5.0,
                 work_location="REMOTE", status="OPEN", **kw)
    db.add(job)
    db.flush()
    return job


def _client(db, line):
    c = Client(tenant_id=1, company_name=f"{line} {_uid()}", line_type=line)
    db.add(c)
    db.flush()
    return c


def _allocate(db, candidate, client_, job, end_date=None):
    employee = db.query(Employee).filter_by(candidate_id=candidate.candidateID).one()
    db.add(EmployeeAllocation(tenant_id=1, employee_id=employee.id, demand_id=job.id, client_id=client_.id,
                              start_date=date.today() - timedelta(days=60), end_date=end_date, status="ACTIVE"))
    employee.status = "ALLOCATED"
    db.flush()
    return employee


def _errors(resp):
    return {b["error"] for b in resp.json()["detail"]}


def test_buddy_not_graduated_blocks_both_models(client, world, db):
    admin, _, job, _ = world
    fresh_hire = _candidate(db, employee_status="BENCH", buddy="NOT_STARTED")
    db.commit()
    resp = _submit(client, admin, job, fresh_hire)
    assert resp.status_code == 422 and "BUDDY_NOT_GRADUATED" in _errors(resp)


def test_core_job_needs_core_certification_staff_aug_does_not(client, world, db):
    admin, _, _, bench = world
    core_job, staff_aug_job = _job(db, _client(db, "CORE")), _job(db, _client(db, "SPECIALITY"))
    db.commit()
    resp = _submit(client, admin, core_job, bench)
    assert resp.status_code == 422 and _errors(resp) == {"CORE_CERTIFICATION_REQUIRED"}
    assert _submit(client, admin, staff_aug_job, bench).status_code == 200

    db.query(Employee).filter_by(candidate_id=bench.candidateID).update(
        {"core_certified": True, "core_certified_date": date.today()})
    db.commit()
    assert _submit(client, admin, core_job, bench).status_code == 200


def test_open_escalation_blocks_until_a_director_resolves_it(client, world, db):
    admin, _, job, bench = world
    employee = db.query(Employee).filter_by(candidate_id=bench.candidateID).one()
    raised = client.post(f"/api/v1/employees/{employee.id}/escalations", headers=_headers(admin),
                         json={"reason": "Client complaint about delivery", "severity": "HIGH"})
    assert raised.status_code == 201, raised.text
    resp = _submit(client, admin, job, bench)
    assert resp.status_code == 422 and "OPEN_ESCALATION" in _errors(resp)

    manager = _user(db, _role(db, {"employees": (True, True, True)}, level=9))  # Senior Manager: below Director
    director = _user(db, _role(db, {"employees": (True, True, True)}, level=11))
    db.commit()
    url = f"/api/v1/employees/escalations/{raised.json()['id']}/resolve"
    assert client.post(url, headers=_headers(manager), json={"resolution_note": "Discussed"}).status_code == 403
    assert client.post(url, headers=_headers(director), json={"resolution_note": ""}).status_code == 422
    resolved = client.post(url, headers=_headers(director), json={"resolution_note": "Resolved with client"})
    assert resolved.status_code == 200 and resolved.json()["resolved_by_user_id"] == director.UserID
    assert client.post(url, headers=_headers(director), json={"resolution_note": "Again"}).status_code == 409
    listed = client.get(f"/api/v1/employees/{employee.id}/escalations", headers=_headers(admin)).json()
    assert [e["status"] for e in listed["escalations"]] == ["RESOLVED"]
    assert _submit(client, admin, job, bench).status_code == 200


def test_core_allocation_holds_the_employee_until_rolling_off(client, world, db):
    admin, _, _, bench = world
    core_client = _client(db, "CORE")
    _allocate(db, bench, core_client, _job(db, core_client), end_date=date.today() + timedelta(days=90))
    next_job = _job(db, _client(db, "SPECIALITY"))
    db.commit()
    resp = _submit(client, admin, next_job, bench)
    assert resp.status_code == 422 and _errors(resp) == {"NOT_ON_BENCH"}

    db.query(EmployeeAllocation).filter_by(client_id=core_client.id).update(
        {"end_date": date.today() + timedelta(days=20)})  # rolling off within 30 days
    db.commit()
    assert _submit(client, admin, next_job, bench).status_code == 200


def test_staff_aug_employee_can_be_moved_to_core_but_not_to_more_staff_aug(client, world, db):
    admin, _, _, bench = world
    staff_aug = _client(db, "SPECIALITY")
    employee = _allocate(db, bench, staff_aug, _job(db, staff_aug))  # no end date: not rolling off
    employee.core_certified, employee.core_certified_date = True, date.today()
    core_job, other_staff_aug_job = _job(db, _client(db, "CORE")), _job(db, _client(db, "SPECIALITY"))
    db.commit()
    resp = _submit(client, admin, other_staff_aug_job, bench)
    assert resp.status_code == 422 and _errors(resp) == {"NOT_ON_BENCH"}
    assert _submit(client, admin, core_job, bench).status_code == 200


def test_job_minimum_experience_on_top_of_the_five_year_floor(client, world, db):
    admin, acme, _, bench = world  # 72 months
    senior_job = Demand(tenant_id=1, client_id=acme.id, job_title="Architect", min_experience_years=8.0,
                        work_location="REMOTE", status="OPEN")
    db.add(senior_job)
    db.commit()
    resp = _submit(client, admin, senior_job, bench)
    assert resp.status_code == 422 and _errors(resp) == {"JOB_EXPERIENCE_SHORT"}


def test_readiness_drives_the_profile_button(client, world, db):
    admin, _, job, bench = world
    market = _candidate(db, bgv=None)
    junior = _candidate(db, bgv=None, months=30)
    not_graduated = _candidate(db, employee_status="BENCH", buddy="IN_PROGRESS")
    db.commit()

    def readiness(candidate):
        r = client.get(f"/api/v1/submissions/readiness/{candidate.candidateID}?demand_id={job.id}",
                       headers=_headers(admin))
        assert r.status_code == 200, r.text
        return r.json()

    assert (readiness(market)["action"], readiness(market)["blockers"]) == ("SUBMIT_TO_JOB", [])
    assert readiness(junior)["action"] == "SUBMIT_TO_JOB" and readiness(junior)["blockers"][0]["error"] == \
        "EXPERIENCE_INELIGIBLE"
    blocked = readiness(not_graduated)
    assert blocked["action"] == "NONE" and [b["error"] for b in blocked["blockers"]] == ["BUDDY_NOT_GRADUATED"]
    assert readiness(bench)["action"] == "SUBMIT_TO_CLIENT"


def test_submit_to_job_enforces_the_five_year_rule_and_lists_internally(client, world, db):
    admin, acme, job, _ = world
    market, junior = _candidate(db, bgv=None), _candidate(db, bgv=None, months=30)
    db.commit()
    url = "/api/v1/jobs/{}/applications/{}"
    assert client.post(url.format(job.id, junior.candidateID), headers=_headers(admin), json={}).status_code == 422
    assert client.post(url.format(job.id, market.candidateID), headers=_headers(admin), json={}).status_code == 201

    internal = client.get("/api/v1/submissions/internal", headers=_headers(admin)).json()["submissions"]
    row = next(r for r in internal if r["candidate_id"] == market.candidateID)
    assert (row["job_id"], row["client_name"], row["stage"]) == (job.id, acme.company_name, "SCREEN")
    assert all(r["candidate_id"] != junior.candidateID for r in internal)


def test_external_rows_show_delivery_line_and_employee_status(client, world, db):
    admin, acme, job, bench = world
    acme.line_type = "SPECIALITY"
    db.commit()
    sid = _submit(client, admin, job, bench).json()["id"]
    row = next(s for s in client.get("/api/v1/submissions", headers=_headers(admin)).json()["submissions"]
               if s["id"] == sid)
    assert (row["delivery_line"], row["delivery_line_label"], row["employee_status"]) == \
        ("SPECIALITY", "Staff Aug", "BENCH")
    assert row["status_label"] == "Client submitted"
    assert [n["label"] for n in row["next_statuses"]] == ["Shortlisted", "Interview requested", "Rejected", "Withdrawn"]
