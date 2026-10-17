"""A small company for Flash agent and mission tests: tenant 1, one business unit operating in one
company with a BU Head, a requester with an administrator role, and a client (named once per test,
so name searches only ever find this test's client) in that business unit."""
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core.security import create_access_token
from app.models.business_unit import BusinessUnit, BusinessUnitCompany, BusinessUnitLocationHead
from app.models.client import Client
from app.models.location import Location
from app.models.role_template import Resource, RoleTemplate, RoleTemplatePermission
from app.models.tenant import Tenant
from app.models.user import Users
from tests.hiring_fixtures import full_access_role

ENQUEUE = "app.services.message_queue_service.MessageQueueService.enqueue"
ENQUEUE_ONCE = "app.services.thunder_mail.cadence_service.enqueue_once"


def uid() -> str:
    return uuid.uuid4().hex[:8]


def user(db, role, name="User", *, business_unit_id=None, email=None) -> Users:
    row = Users(UserID=f"U-{uid()}", UserName=name, UserEmail=email or f"{uid()}@blitzenx.com", UserPassword="x",
                UserRole="user", tenant_id=1, role_template_id=role.id, password_reset_required=False,
                business_unit_id=business_unit_id)
    db.add(row)
    db.flush()
    return row


def headers(person) -> dict:
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": person.UserID, "type": "user", "tenant_id": 1, "role_template_id": person.role_template_id})}


def role_without(db, *revoked: str) -> RoleTemplate:
    """An administrator role minus some permissions ("jobs.create", "interviews.create", ...)."""
    role = full_access_role(db)
    for permission in revoked:
        resource_name, _, action = permission.rpartition(".")
        resource_ids = [r.id for r in db.query(Resource).filter(Resource.name == resource_name)]
        for row in db.query(RoleTemplatePermission).filter(RoleTemplatePermission.role_template_id == role.id,
                                                           RoleTemplatePermission.resource_id.in_(resource_ids)):
            setattr(row, f"can_{action}", False)
    db.flush()
    return role


def make_world(db) -> SimpleNamespace:
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="tenant-1"))
        db.flush()
    role = full_access_role(db)
    unit = BusinessUnit(tenant_id=1, name=f"bu-{uid()}", display_name="Rails BU")
    company = Location(tenant_id=1, name=f"co-{uid()}")
    db.add_all([unit, company])
    db.flush()
    db.add(BusinessUnitCompany(tenant_id=1, business_unit_id=unit.id, company_id=company.id))
    head = user(db, role, "Hema Head", business_unit_id=unit.id)
    db.add(BusinessUnitLocationHead(tenant_id=1, business_unit_id=unit.id, company_id=company.id,
                                    head_user_id=head.UserID))
    requester = user(db, role, "Rita Requester", business_unit_id=unit.id)
    recruiter = user(db, role, "Rohan Recruiter", business_unit_id=unit.id)
    name = f"Acme{uid()}"
    client = Client(tenant_id=1, company_name=name, line_type="SPECIALITY", business_unit_id=unit.id,
                    contracting_company_id=company.id)
    db.add(client)
    db.flush()
    return SimpleNamespace(role=role, unit=unit, company=company, head=head, requester=requester,
                           recruiter=recruiter, client=client, client_name=name)


@pytest.fixture
def queued():
    """Every MessageQueueService.enqueue and enqueue_once call, captured instead of committed."""
    calls = SimpleNamespace(enqueue=[], once=[])

    def enqueue(task_name, task_id=None, data=None, **kw):
        calls.enqueue.append(SimpleNamespace(task_name=task_name, task_id=task_id, data=data, kw=kw))
        return {"status": "queued", "task_id": task_id}

    def enqueue_once(task_name, task_id, data, tenant_id=None, **kw):
        calls.once.append(SimpleNamespace(task_name=task_name, task_id=task_id, data=data, kw=kw))
        return True

    with patch(ENQUEUE, side_effect=enqueue), patch(ENQUEUE_ONCE, side_effect=enqueue_once):
        yield calls
