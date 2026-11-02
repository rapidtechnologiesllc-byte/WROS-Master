"""C-level roles see every business unit; partners and below see their own (CEO 2026-11-02: "if the
job title is C-Level (CEO, CFO, and so on) they are defaulted to all business unit. If the job title
is partner or below then they are defaulted to their BU"). Decided by the role's designation, never
by its name."""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.core.visibility import scope_bu_ids
from app.models.org_structure import OrgRole
from app.services.org_roles_service import DESIGNATION_LEVELS, ensure_permission_set
from tests.scope_fixtures import person, scoped_role, two_bu_world


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
def w(db):
    return two_bu_world(db)


def _role(db, name, level, designation=None):
    role = OrgRole(tenant_id=1, name=f"{name} {uuid.uuid4().hex[:6]}", hierarchy_level=level, designation=designation)
    db.add(role)
    db.flush()
    return role, ensure_permission_set(db, role)


@pytest.mark.parametrize("designation", sorted(DESIGNATION_LEVELS))
def test_every_c_level_designation_sees_all_business_units(db, w, designation):
    _, template = _role(db, "Chief", DESIGNATION_LEVELS[designation], designation)
    assert template.org_level_access is True


def test_partner_level_without_designation_stays_scoped(db, w):
    _, template = _role(db, "Partner", 16)
    assert template.org_level_access is False


def test_cfo_holder_sees_all_and_partner_holder_sees_own_bu(db, w):
    cfo_role, _ = _role(db, "CFO", 16, "cfo")
    partner_role, _ = _role(db, "Partner", 16)
    addon = scoped_role(db)  # no org-level add-on: the role alone decides
    cfo = person(db, addon, "Chief Financial", business_unit_id=w.bu_a.id)
    partner = person(db, addon, "Partner Two", business_unit_id=w.bu_b.id)
    cfo.job_title, partner.job_title = cfo_role.name, partner_role.name
    db.flush()
    db.info.pop("authority_cache", None)
    assert scope_bu_ids(db, cfo) is None
    assert scope_bu_ids(db, partner) == {w.bu_b.id}
