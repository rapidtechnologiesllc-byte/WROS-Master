"""The menu is built from the role template's permission matrix (CEO 2026-10-11/12). The
LinkedIn pipeline has no resource of its own -- its endpoints all check "candidates" -- so
every role that can view candidates (CEO, CFO, partner, BU head, recruiter) gets
Recruitment > LinkedIn Pipeline right after Candidates, and a role that cannot gets neither."""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.api.v1.endpoints.navigation import get_user_navigation
from app.models.role_template import RoleTemplate
from app.models.user import Users
from tests.hiring_fixtures import full_access_role


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _user(db, role):
    uid = uuid.uuid4().hex[:8]
    user = Users(UserID=f"U-{uid}", UserName="Nav User", UserEmail=f"n{uid}@x.com", UserPassword="x",
                 UserRole="x", tenant_id=1, role_template_id=role.id)
    db.add(user)
    db.flush()
    return user


def _recruitment_routes(db, user):
    groups = get_user_navigation(db=db, current_user=user)["data"]["groups"]
    recruitment = next((g for g in groups if g["label"] == "Recruitment"), {"items": []})
    return [item["route"] for item in recruitment["items"]]


def test_linkedin_pipeline_follows_candidates_for_any_role_that_can_view_candidates(db):
    routes = _recruitment_routes(db, _user(db, full_access_role(db)))
    assert "/linkedin-pipeline" in routes
    assert routes.index("/linkedin-pipeline") == routes.index("/candidates") + 1


def test_no_candidates_permission_means_no_linkedin_pipeline(db):
    role = RoleTemplate(tenant_id=1, name=f"none-{uuid.uuid4().hex[:8]}", display_name="None",
                        hierarchy_level=1, org_level_access=False, enabled=True)
    db.add(role)
    db.flush()
    routes = _recruitment_routes(db, _user(db, role))
    assert "/candidates" not in routes and "/linkedin-pipeline" not in routes
