"""
HR-Manager/BU-restricted visibility gap fix, 2026-08-05
(app.core.bu_scope). Proves: global-access roles are unaffected,
bu_restricted roles see Org Pool + their own BU, never another BU's
owned candidates, and a bu_restricted user with no BU assigned fails
closed to Org-Pool-only rather than seeing everything. Real RBAC seed
(RBACService.seed_roles_and_permissions), throwaway SQLite -- never
the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ownership import CandidateOwnership, POOL_BU, POOL_ORG
from app.models.rbac_template import BusinessUnit, Permission, Role, RoleAttribute, RolePermission
from app.models.tenant import Tenant
from app.models.user import Users

from app.core.bu_scope import apply_bu_scope_to_candidate_query, get_bu_scoped_candidate_ids, is_bu_restricted
from app.services.rbac_service_template import RBACService


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Users.__table__, Candidate.__table__, CandidateOwnership.__table__,
        BusinessUnit.__table__, Role.__table__, RoleAttribute.__table__,
        Permission.__table__, RolePermission.__table__,
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


def _make_candidate(db, candidate_id, email):
    candidate = Candidate(candidateID=candidate_id, candidateEmail=email, candidatePassword="h")
    db.add(candidate)
    db.commit()
    return candidate


def _own_bu(db, candidate_id, bu_id):
    db.add(CandidateOwnership(candidateID=candidate_id, pool_status=POOL_BU, owned_by_bu_id=bu_id))
    db.commit()


def test_is_bu_restricted_matches_the_real_rbac_seed(db_session):
    hr_manager = _make_user(db_session, "U-HRM", "HR Manager")
    super_user = _make_user(db_session, "U-SU", "Super User")
    assert is_bu_restricted(db_session, hr_manager) is True
    assert is_bu_restricted(db_session, super_user) is False


def test_global_access_role_sees_everything_unfiltered(db_session):
    super_user = _make_user(db_session, "U-SU", "Super User")
    bu_a = BusinessUnit(name="BU-A")
    bu_b = BusinessUnit(name="BU-B")
    db_session.add_all([bu_a, bu_b])
    db_session.commit()
    _make_candidate(db_session, "C-1", "c1@example.com")
    _make_candidate(db_session, "C-2", "c2@example.com")
    _own_bu(db_session, "C-2", bu_b.id)

    query = apply_bu_scope_to_candidate_query(db_session, db_session.query(Candidate), super_user)
    assert {c.candidateID for c in query.all()} == {"C-1", "C-2"}


def test_bu_restricted_role_sees_org_pool_and_own_bu_only(db_session):
    bu_a = BusinessUnit(name="BU-A")
    bu_b = BusinessUnit(name="BU-B")
    db_session.add_all([bu_a, bu_b])
    db_session.commit()
    hr_manager = _make_user(db_session, "U-HRM", "HR Manager", business_unit_id=bu_a.id)

    _make_candidate(db_session, "C-POOL", "pool@example.com")            # never assigned -- Org Pool
    _make_candidate(db_session, "C-OWN-BU", "own@example.com")
    _own_bu(db_session, "C-OWN-BU", bu_a.id)                              # owned by caller's own BU
    _make_candidate(db_session, "C-OTHER-BU", "other@example.com")
    _own_bu(db_session, "C-OTHER-BU", bu_b.id)                            # owned by a DIFFERENT BU

    query = apply_bu_scope_to_candidate_query(db_session, db_session.query(Candidate), hr_manager)
    visible = {c.candidateID for c in query.all()}

    assert visible == {"C-POOL", "C-OWN-BU"}
    assert "C-OTHER-BU" not in visible


def test_explicit_org_pool_status_is_visible_too(db_session):
    bu_a = BusinessUnit(name="BU-A")
    db_session.add(bu_a)
    db_session.commit()
    hr_manager = _make_user(db_session, "U-HRM", "HR Manager", business_unit_id=bu_a.id)
    _make_candidate(db_session, "C-1", "c1@example.com")
    db_session.add(CandidateOwnership(candidateID="C-1", pool_status=POOL_ORG, owned_by_bu_id=None))
    db_session.commit()

    query = apply_bu_scope_to_candidate_query(db_session, db_session.query(Candidate), hr_manager)
    assert {c.candidateID for c in query.all()} == {"C-1"}


def test_bu_restricted_user_with_no_bu_assigned_fails_closed_to_org_pool_only(db_session):
    bu_a = BusinessUnit(name="BU-A")
    db_session.add(bu_a)
    db_session.commit()
    hr_manager = _make_user(db_session, "U-HRM", "HR Manager", business_unit_id=None)

    _make_candidate(db_session, "C-POOL", "pool@example.com")
    _make_candidate(db_session, "C-OWN-BU", "own@example.com")
    _own_bu(db_session, "C-OWN-BU", bu_a.id)

    query = apply_bu_scope_to_candidate_query(db_session, db_session.query(Candidate), hr_manager)
    assert {c.candidateID for c in query.all()} == {"C-POOL"}


def test_get_bu_scoped_candidate_ids_returns_none_for_global_access(db_session):
    super_user = _make_user(db_session, "U-SU", "Super User")
    assert get_bu_scoped_candidate_ids(db_session, super_user) is None


def test_get_bu_scoped_candidate_ids_returns_the_real_visible_set(db_session):
    bu_a = BusinessUnit(name="BU-A")
    bu_b = BusinessUnit(name="BU-B")
    db_session.add_all([bu_a, bu_b])
    db_session.commit()
    hr_manager = _make_user(db_session, "U-HRM", "HR Manager", business_unit_id=bu_a.id)
    _make_candidate(db_session, "C-POOL", "pool@example.com")
    _make_candidate(db_session, "C-OTHER-BU", "other@example.com")
    _own_bu(db_session, "C-OTHER-BU", bu_b.id)

    ids = get_bu_scoped_candidate_ids(db_session, hr_manager)
    assert ids == {"C-POOL"}
