"""Speed guards (2026-10-24): list endpoints run a fixed number of queries however many rows they
return (no query per row), batching keeps every row's data right, and the per-request authority
cache never answers from before a change."""
import contextlib
import pytest
from sqlalchemy import event

from app.core import authority
from app.models.candidate import CandidateStatus
from app.models.client import Client
from app.models.role_template import Module, Resource, RoleTemplatePermission
from tests import factories
from tests.hiring_fixtures import full_access_role
from tests.scope_fixtures import ApiClient


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


@contextlib.contextmanager
def count_queries(db):
    statements = []
    engine = db.get_bind().engine

    def _count(conn, cursor, statement, params, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _count)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", _count)


def _queries(api, db, user, path):
    with count_queries(db) as statements:
        response = api.get(user, path)
    assert response.status_code == 200, response.text
    return len(statements), response.json()


def test_candidate_list_queries_do_not_grow_with_candidates(api, db):
    admin = factories.user(db, role_template_id=full_access_role(db).id, UserRole="admin")
    first = [factories.candidate(db) for _ in range(2)]
    db.add_all([CandidateStatus(candidateID=c.candidateID, status="Active", piplineStatus="Screening") for c in first])
    db.commit()
    small, _ = _queries(api, db, admin, "/api/v1/candidates/all")
    more = [factories.candidate(db) for _ in range(8)]
    db.add_all([CandidateStatus(candidateID=c.candidateID, status="Active", piplineStatus="Offer") for c in more])
    db.commit()
    large, body = _queries(api, db, admin, "/api/v1/candidates/all")
    assert large == small  # was one extra query per candidate
    by_id = {c["candidate_id"]: c for c in body["candidates"]}
    assert {by_id[c.candidateID]["pipline_status"] for c in first} == {"Screening"}
    assert {by_id[c.candidateID]["pipline_status"] for c in more} == {"Offer"}


def test_candidate_without_a_status_row_keeps_the_defaults(api, db):
    admin = factories.user(db, role_template_id=full_access_role(db).id, UserRole="admin")
    lonely = factories.candidate(db)
    db.commit()
    _, body = _queries(api, db, admin, "/api/v1/candidates/all")
    row = next(c for c in body["candidates"] if c["candidate_id"] == lonely.candidateID)
    assert (row["status"], row["pipline_status"]) == ("Active", "Applied")


def test_allocation_list_queries_do_not_grow_with_allocations(api, db):
    admin = factories.user(db, role_template_id=full_access_role(db).id, UserRole="admin")
    unit = factories.business_unit(db)
    client = Client(tenant_id=1, company_name=f"Client {factories.uid()}", business_unit_id=unit.id,
                    payment_terms_days=30)
    db.add(client)
    db.flush()

    def place(count):
        for _ in range(count):
            employee = factories.employee(db, status="BENCH", bu_id=unit.id, buddy_program_status="GRADUATED")
            job = factories.job(db, client_id=client.id, business_unit_id=unit.id)
            db.commit()
            response = api.post(admin, "/api/v1/allocations", json={
                "employee_id": employee.id, "demand_id": job.jobID, "start_date": "2026-10-01"})
            assert response.status_code == 200, response.text

    place(1)
    small, _ = _queries(api, db, admin, "/api/v1/allocations")
    place(5)
    large, body = _queries(api, db, admin, "/api/v1/allocations")
    assert len(body["allocations"]) == 6
    assert large == small  # was up to eight queries per allocation
    assert all(a["client_name"] == client.company_name and a["employee_name"] for a in body["allocations"])


def test_authority_cache_drops_on_flush_so_a_new_grant_counts(db):
    from app.services.role_template_permission_service import RoleTemplatePermissionService as perms

    role = factories.role(db)
    user = factories.user(db, role_template_id=role.id)
    module = Module(tenant_id=1, name=f"m-{factories.uid()}", display_name="M", enabled=True)
    db.add(module)
    db.flush()
    resource = Resource(tenant_id=1, module_id=module.id, name=f"r-{factories.uid()}", display_name="R", enabled=True)
    db.add(resource)
    db.flush()
    assert perms.has_permission(db, user.UserID, resource.name, "view", 1) is False
    assert perms.has_permission(db, user.UserID, resource.name, "view", 1) is False  # cached
    db.add(RoleTemplatePermission(role_template_id=role.id, resource_id=resource.id, tenant_id=role.tenant_id,
                                  can_view=True))
    db.flush()  # the cache is dropped here
    assert perms.has_permission(db, user.UserID, resource.name, "view", 1) is True


def test_role_change_on_the_user_is_never_answered_from_the_cache(db):
    first = factories.role(db, hierarchy_level=3)
    second = factories.role(db, hierarchy_level=9)
    user = factories.user(db, role_template_id=first.id)
    assert authority.role_of(db, user).id == first.id
    user.role_template_id = second.id  # the key includes the template id, so no flush is needed
    assert authority.role_of(db, user).id == second.id
