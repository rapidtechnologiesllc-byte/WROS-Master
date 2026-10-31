"""The user directory never crosses tenants: list, search and by-ID lookups (CEO 2026-10-12)."""
import pytest
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.user import Users
from tests.scope_fixtures import ApiClient, ids, two_bu_world, uid


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


def test_users_of_another_tenant_are_invisible(db, api):
    w = two_bu_world(db)
    other = db.query(Tenant).filter(Tenant.id != 1).first()
    if other is None:
        # tenant 1 is seeded with an explicit id, so the id sequence still says 1: pick a free id
        other = Tenant(id=(db.query(func.max(Tenant.id)).scalar() or 0) + 1, name=f"other-{uid()}")
        db.add(other)
        db.flush()
    outsider = Users(UserID=f"U-{uid()}", UserName="Outsider", UserEmail=f"{uid()}@other.test", UserPassword="x",
                     UserRole="x", tenant_id=other.id, role_template_id=w.org_role.id)
    db.add(outsider)
    db.commit()

    listed = ids(api.get(w.org_user, "/api/v1/hr/users/all").json(), "user_id")
    assert w.partner_a.UserID in listed and outsider.UserID not in listed
    found = ids(api.get(w.org_user, "/api/v1/hr/users/search", params={"name": "Outsider"}).json(), "user_id")
    assert outsider.UserID not in found
    assert api.get(w.org_user, f"/api/v1/hr/users/{outsider.UserID}").status_code == 404
