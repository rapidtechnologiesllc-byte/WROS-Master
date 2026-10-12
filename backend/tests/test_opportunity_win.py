"""Signing the contract is the win (CEO 2026-10-12: the system must carry a sold opportunity
into delivery on its own): CONTRACT creates the project once, needs the client's business
unit, and role demands for it open at once with project, BU and hiring manager, and start
recruiting."""
from unittest import mock

import pytest
from sqlalchemy.orm import Session

from app.models.project import Project
from tests.scope_fixtures import ApiClient, two_bu_world


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
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


@pytest.fixture
def w(db):
    return two_bu_world(db)


def _open(api, w, client=None):
    response = api.post(w.org_user, "/api/v1/opportunities",
                        json={"client_id": (client or w.client_a).id, "revenue_value_usd_cents": 100_000_00})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _move(api, w, opp, stage):
    return api.post(w.org_user, f"/api/v1/opportunities/{opp}/transition", json={"new_stage": stage})


def test_contract_creates_the_project_once_and_then_only_active(db, api, w):
    opp = _open(api, w)
    response = _move(api, w, opp, "CONTRACT")
    assert response.status_code == 200, response.text
    assert response.json()["project_id"]
    assert db.query(Project).filter(Project.opportunity_id == opp).count() == 1
    assert _move(api, w, opp, "NEGOTIATION").status_code == 400   # signed: no going back
    assert _move(api, w, opp, "ACTIVE").status_code == 200
    assert _move(api, w, opp, "LOST").status_code == 400          # terminal


def test_won_is_not_a_stage_and_contract_needs_a_business_unit(api, w):
    assert _move(api, w, _open(api, w), "WON").status_code == 400
    response = _move(api, w, _open(api, w, w.prospect), "CONTRACT")  # prospect: no BU yet
    assert response.status_code == 400 and "business unit" in response.json()["detail"]


def test_role_demand_needs_the_win_then_opens_staffed_for_the_project(db, api, w):
    opp = _open(api, w)
    body = {"job_title": "Guidewire Developer", "required_skills": "PolicyCenter", "min_experience_years": 5,
            "work_location": "Remote", "quantity": 2, "duration_hours": 2080, "billing_rate_usd_cents": 9000}
    early = api.post(w.org_user, f"/api/v1/opportunities/{opp}/role-demand", json=body)
    assert early.status_code == 400
    bad = api.post(w.org_user, f"/api/v1/opportunities/{opp}/role-demand", json={**body, "work_location": "Mars"})
    assert bad.status_code == 422  # refused, not a database error
    project_id = _move(api, w, opp, "CONTRACT").json()["project_id"]

    with mock.patch("app.services.message_queue_service.MessageQueueService.enqueue") as enqueue:
        response = api.post(w.org_user, f"/api/v1/opportunities/{opp}/role-demand", json=body)
    assert response.status_code == 201, response.text
    from app.models.user import Jobs

    job = db.query(Jobs).filter(Jobs.opportunity_id == opp).one()
    assert (job.project_id, job.business_unit_id, job.demand_status) == (project_id, w.bu_a.id, "OPEN")
    assert job.hiringManagerID == w.org_user.UserID  # no BU head seated: the client owner hires
    assert {c.kwargs["task_name"] for c in enqueue.call_args_list} == {"flash_recruiter", "source_candidates_for_job"}


def test_stage_rules_endpoint_matches_the_server(api, w):
    rules = api.get(w.org_user, "/api/v1/opportunities/stages").json()
    assert rules["won"] == ["CONTRACT", "ACTIVE"]
    assert rules["transitions"]["CONTRACT"] == ["ACTIVE"] and rules["transitions"]["LOST"] == []
