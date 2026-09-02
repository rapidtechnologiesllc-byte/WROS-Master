"""
EPIC-02/03 access spec, 2026-08-05 (app.core.revenue_visibility_scope).
Avinash: "Epic 2,3 is only visible to ceo, partner (only for their
BU); BU head (Only for their BU); finance & HR manager (no actual
p&l)." Refined: "a partner has it's own clients and the work is done
import logging
in their BU only" -- BU ownership is Client.business_unit_id.

Real RBAC seed (RBACService.seed_roles_and_permissions), throwaway
SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.client import Client
from app.models.rbac_template import BusinessUnit, Permission, Role, RoleAttribute, RolePermission
from app.models.tenant import Tenant
from app.models.user import Users

from app.core.revenue_visibility_scope import (
    apply_revenue_bu_scope_to_client_query,
    can_view_pnl,
    get_revenue_scoped_client_ids,
    is_revenue_bu_scoped,
)
from app.services.rbac_service_template import RBACService


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Users.__table__, Client.__table__, BusinessUnit.__table__,
        Role.__table__, RoleAttribute.__table__, Permission.__table__, RolePermission.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        RBACService.seed_roles_and_permissions(session)
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def _make_user(db, user_id, role_name, business_unit_id=None):
    role = db.query(Role).filter(Role.name == role_name).first()
    user = Users(
        UserID=user_id, UserRole=role_name, UserEmail=f"{user_id}@blitzenx.com",
        UserPassword="h", role_id=role.id if role else None, business_unit_id=business_unit_id,
    )
    db.add(user)
    db.commit()
    return user


def _make_client(db, client_id, company_name, business_unit_id=None):
    client = Client(id=client_id, company_name=company_name, business_unit_id=business_unit_id)
    db.add(client)
    db.commit()
    return client


def test_is_revenue_bu_scoped_matches_the_exact_spec(db_session):
    partner = _make_user(db_session, "U-P", "Partner")
    bu_head = _make_user(db_session, "U-BH", "BU Head")
    super_user = _make_user(db_session, "U-SU", "Super User")
    finance = _make_user(db_session, "U-F", "Finance")
    hr_manager = _make_user(db_session, "U-HRM", "HR Manager")

    assert is_revenue_bu_scoped(db_session, partner) is True
    assert is_revenue_bu_scoped(db_session, bu_head) is True
    assert is_revenue_bu_scoped(db_session, super_user) is False
    assert is_revenue_bu_scoped(db_session, finance) is False
    assert is_revenue_bu_scoped(db_session, hr_manager) is False


def test_can_view_pnl_matches_the_exact_spec(db_session):
    """Finance and HR Manager both get revenue.view -- only Finance
    (not HR Manager) also gets revenue.view_pnl."""
    finance = _make_user(db_session, "U-F", "Finance")
    hr_manager = _make_user(db_session, "U-HRM", "HR Manager")
    partner = _make_user(db_session, "U-P", "Partner")
    super_user = _make_user(db_session, "U-SU", "Super User")

    assert can_view_pnl(db_session, finance) is True
    assert can_view_pnl(db_session, hr_manager) is False
    assert can_view_pnl(db_session, partner) is True
    assert can_view_pnl(db_session, super_user) is True


def test_partner_sees_only_their_own_bu_plus_unassigned_clients(db_session):
    bu_axion = BusinessUnit(name="AXION")
    bu_other = BusinessUnit(name="OTHER")
    db_session.add_all([bu_axion, bu_other])
    db_session.commit()
    partner = _make_user(db_session, "U-TROY", "Partner", business_unit_id=bu_axion.id)

    _make_client(db_session, "C-AXION-CLIENT", "Axion Client", business_unit_id=bu_axion.id)
    _make_client(db_session, "C-OTHER-CLIENT", "Other BU Client", business_unit_id=bu_other.id)
    _make_client(db_session, "C-UNASSIGNED", "Prospect, No Partner Yet", business_unit_id=None)

    query = apply_revenue_bu_scope_to_client_query(db_session, db_session.query(Client), partner)
    visible = {c.id for c in query.all()}

    assert visible == {"C-AXION-CLIENT", "C-UNASSIGNED"}
    assert "C-OTHER-CLIENT" not in visible


def test_bu_head_same_rule_as_partner(db_session):
    bu_a = BusinessUnit(name="BU-A")
    db_session.add(bu_a)
    db_session.commit()
    bu_head = _make_user(db_session, "U-BH", "BU Head", business_unit_id=bu_a.id)
    _make_client(db_session, "C-1", "Client A", business_unit_id=bu_a.id)
    _make_client(db_session, "C-2", "Client B", business_unit_id=None)

    query = apply_revenue_bu_scope_to_client_query(db_session, db_session.query(Client), bu_head)
    assert {c.id for c in query.all()} == {"C-1", "C-2"}


def test_ceo_finance_and_hr_manager_see_org_wide(db_session):
    bu_a = BusinessUnit(name="BU-A")
    bu_b = BusinessUnit(name="BU-B")
    db_session.add_all([bu_a, bu_b])
    db_session.commit()
    _make_client(db_session, "C-1", "Client A", business_unit_id=bu_a.id)
    _make_client(db_session, "C-2", "Client B", business_unit_id=bu_b.id)

    for role in ["Super User", "Finance", "HR Manager"]:
        user = _make_user(db_session, f"U-{role.replace(' ', '')}", role)
        query = apply_revenue_bu_scope_to_client_query(db_session, db_session.query(Client), user)
        assert {c.id for c in query.all()} == {"C-1", "C-2"}, f"{role} should see everything"


def test_partner_with_no_bu_assigned_sees_only_unassigned_clients(db_session):
    bu_a = BusinessUnit(name="BU-A")
    db_session.add(bu_a)
    db_session.commit()
    partner = _make_user(db_session, "U-P", "Partner", business_unit_id=None)
    _make_client(db_session, "C-1", "Client A", business_unit_id=bu_a.id)
    _make_client(db_session, "C-2", "Unassigned", business_unit_id=None)

    query = apply_revenue_bu_scope_to_client_query(db_session, db_session.query(Client), partner)
    assert {c.id for c in query.all()} == {"C-2"}


def test_get_revenue_scoped_client_ids_returns_none_for_org_wide_roles(db_session):
    finance = _make_user(db_session, "U-F", "Finance")
    assert get_revenue_scoped_client_ids(db_session, finance) is None


def test_get_revenue_scoped_client_ids_returns_the_real_visible_set(db_session):
    bu_a = BusinessUnit(name="BU-A")
    bu_b = BusinessUnit(name="BU-B")
    db_session.add_all([bu_a, bu_b])
    db_session.commit()
    partner = _make_user(db_session, "U-P", "Partner", business_unit_id=bu_a.id)
    _make_client(db_session, "C-1", "Client A", business_unit_id=bu_a.id)
    _make_client(db_session, "C-2", "Client B", business_unit_id=bu_b.id)

    ids = get_revenue_scoped_client_ids(db_session, partner)
    assert ids == {"C-1"}
