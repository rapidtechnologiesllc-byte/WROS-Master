"""Shared world for business-unit visibility tests (CEO 2026-10-12): two business units, a
partner of each with IDENTICAL permissions (every module, not org-level), and an org-level
user. Whatever partner A can see of B's records -- or B of A's -- is a leak.

    w = two_bu_world(db)
    api = ApiClient(db)
    api.get(w.partner_a, "/api/v1/clients")

Each test adds the records it needs under w.bu_a / w.bu_b (client_a / client_b and
job_a / job_b are provided)."""
import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.models.business_unit import BusinessUnit
from app.models.client import Client
from app.models.user import Jobs, Users
from tests.hiring_fixtures import full_access_role


def uid() -> str:
    return uuid.uuid4().hex[:8]


def scoped_role(db):
    """Every permission, but BU-scoped (not org-level) -- a partner's or BU head's template."""
    role = full_access_role(db)
    role.org_level_access = False
    role.hierarchy_level = 16
    db.flush()
    return role


def person(db, role, name, business_unit_id=None) -> Users:
    user = Users(UserID=f"U-{uid()}", UserName=name, UserEmail=f"{uid()}@scope.test", UserPassword="x",
                 UserRole="x", tenant_id=1, role_template_id=role.id, business_unit_id=business_unit_id)
    db.add(user)
    db.flush()
    return user


def two_bu_world(db) -> SimpleNamespace:
    org_role, partner_role = full_access_role(db), scoped_role(db)
    bu_a = BusinessUnit(name=f"BU-A-{uid()}", display_name="BU A")
    bu_b = BusinessUnit(name=f"BU-B-{uid()}", display_name="BU B")
    db.add_all([bu_a, bu_b])
    db.flush()
    partner_a, partner_b = person(db, partner_role, "Partner A"), person(db, partner_role, "Partner B")
    bu_a.partner_user_id, bu_b.partner_user_id = partner_a.UserID, partner_b.UserID
    org_user = person(db, org_role, "Org user")
    client_a = Client(tenant_id=1, company_name=f"Client A {uid()}", business_unit_id=bu_a.id)
    client_b = Client(tenant_id=1, company_name=f"Client B {uid()}", business_unit_id=bu_b.id)
    prospect = Client(tenant_id=1, company_name=f"Prospect {uid()}")  # no BU yet: visible to all
    db.add_all([client_a, client_b, prospect])
    db.flush()
    job_a = Jobs(tenant_id=1, client_id=client_a.id, business_unit_id=bu_a.id, jobTitle="Job A", jobDescription="d",
                 jobSkills="x", jobExperience="5", jobLocation="Remote")
    job_b = Jobs(tenant_id=1, client_id=client_b.id, business_unit_id=bu_b.id, jobTitle="Job B", jobDescription="d",
                 jobSkills="x", jobExperience="5", jobLocation="Remote")
    db.add_all([job_a, job_b])
    db.commit()
    return SimpleNamespace(bu_a=bu_a, bu_b=bu_b, partner_a=partner_a, partner_b=partner_b, org_user=org_user,
                           client_a=client_a, client_b=client_b, prospect=prospect, job_a=job_a, job_b=job_b,
                           partner_role=partner_role, org_role=org_role)


class ApiClient:
    """TestClient on the test session, calling as a given user."""

    def __init__(self, db):
        from app.core.database import get_db
        from app.main import app

        self.app = app
        app.dependency_overrides[get_db] = lambda: db
        self.client = TestClient(app)

    @staticmethod
    def headers(user: Users) -> dict:
        from app.core.security import create_access_token

        return {"Authorization": "Bearer " + create_access_token(
            {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": user.role_template_id})}

    def get(self, user, path, **kw):
        return self.client.get(path, headers=self.headers(user), **kw)

    def post(self, user, path, **kw):
        return self.client.post(path, headers=self.headers(user), **kw)

    def put(self, user, path, **kw):
        return self.client.put(path, headers=self.headers(user), **kw)

    def patch(self, user, path, **kw):
        return self.client.patch(path, headers=self.headers(user), **kw)

    def delete(self, user, path, **kw):
        return self.client.delete(path, headers=self.headers(user), **kw)

    def close(self):
        self.app.dependency_overrides.clear()


def ids(payload, key="id") -> set:
    """Ids found anywhere in a JSON payload (lists nested under any key)."""
    found = set()

    def walk(node):
        if isinstance(node, dict):
            if key in node:
                found.add(node[key])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return found
