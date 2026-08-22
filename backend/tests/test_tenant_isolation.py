"""
Proves HRMS-0109's tenant-isolation guarantee for the smallest possible
slice: a `tenants` table, a `tenant_id` column on Users, and a dependency
(app.core.tenant_context) that resolves tenant_id from the authenticated
session only.

this test — never touches the real Azure SQL database configured in .env.
"""
import inspect
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.user import Users
from app.core.tenant_context import get_tenant_scoped_query

@pytest.fixture()
def db_session():
    engine = create_engine(f"sqlite:///{db_path}")
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

def _seed_two_tenants(db):
    blitzenx = Tenant(name="BlitzenX")
    other = Tenant(name="Other Client Co")
    db.add_all([blitzenx, other])
    db.commit()

    alice = Users(
        UserID="U-ALICE", UserRole="Recruiter", UserEmail="alice@blitzenx.com",
        UserPassword="hashed", tenant_id=blitzenx.id,
    )
    bob = Users(
        UserID="U-BOB", UserRole="Recruiter", UserEmail="bob@otherclient.com",
        UserPassword="hashed", tenant_id=other.id,
    )
    db.add_all([alice, bob])
    db.commit()
    return blitzenx, other, alice, bob

def test_positive_case_user_sees_only_their_own_tenants_data(db_session):
    """A user's scoped query returns rows from their own tenant."""
    blitzenx, other, alice, bob = _seed_two_tenants(db_session)

    alice_results = get_tenant_scoped_query(db_session, Users, current_user=alice).all()
    bob_results = get_tenant_scoped_query(db_session, Users, current_user=bob).all()

    assert [u.UserID for u in alice_results] == ["U-ALICE"]
    assert [u.UserID for u in bob_results] == ["U-BOB"]

def test_negative_case_no_way_to_pass_a_forged_tenant_id(db_session):
    """
    The core negative-case test (per BR-0109-01 / the Dev & Review
    Standard's Part 3 template): a caller must have no way to supply a
    different tenant_id and have it honored.

    get_tenant_scoped_query's signature intentionally has no parameter for
    a caller-supplied tenant id, so there is nothing to forge -- this test
    locks that shape in place so a future "convenience" refactor can't
    quietly reintroduce a tenant_id argument that trusts the caller.
    """
    params = list(inspect.signature(get_tenant_scoped_query).parameters)
    assert "tenant_id" not in params
    assert "requested_tenant_id" not in params

    blitzenx, other, alice, bob = _seed_two_tenants(db_session)
    results = get_tenant_scoped_query(db_session, Users, current_user=alice).all()

    assert all(u.tenant_id == alice.tenant_id for u in results)
    assert "U-BOB" not in [u.UserID for u in results]

def test_user_with_no_tenant_assigned_is_denied_not_shown_everything(db_session):
    """
    Fail-closed check: an account not yet linked to a tenant must be
    rejected, not silently treated as having access to all tenants' data.
    """
    from fastapi import HTTPException

    _seed_two_tenants(db_session)
    unassigned = Users(
        UserID="U-UNASSIGNED", UserRole="Recruiter",
        UserEmail="new@blitzenx.com", UserPassword="hashed", tenant_id=None,
    )
    db_session.add(unassigned)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        get_tenant_scoped_query(db_session, Users, current_user=unassigned)

    assert exc_info.value.status_code == 403
