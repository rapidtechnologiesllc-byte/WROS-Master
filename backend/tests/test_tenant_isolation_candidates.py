"""
Extends HRMS-0109's tenant-isolation proof to the Candidate table --
import logging
the highest-value target, since it holds real candidate PII.

Same pattern as test_tenant_isolation.py: throwaway SQLite file, never
the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.candidate import Candidate
from app.core.tenant_context import get_tenant_scoped_query


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[Tenant.__table__, Candidate.__table__])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

logger = logging.getLogger(__name__)

class _FakeUser:
    """Stand-in for a Users row -- get_tenant_scoped_query only reads .tenant_id."""
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id


def _seed_two_tenants_of_candidates(db):
    blitzenx = Tenant(name="BlitzenX")
    other = Tenant(name="Other Client Co")
    db.add_all([blitzenx, other])
    db.commit()

    aisha = Candidate(
        candidateID="C-AISHA", candidateEmail="aisha@example.com",
        candidatePassword="hashed", tenant_id=blitzenx.id,
    )
    ravi = Candidate(
        candidateID="C-RAVI", candidateEmail="ravi@example.com",
        candidatePassword="hashed", tenant_id=other.id,
    )
    db.add_all([aisha, ravi])
    db.commit()
    return blitzenx, other, aisha, ravi


def test_recruiter_only_sees_their_own_tenants_candidates(db_session):
    blitzenx, other, aisha, ravi = _seed_two_tenants_of_candidates(db_session)

    blitzenx_recruiter = _FakeUser(tenant_id=blitzenx.id)
    other_recruiter = _FakeUser(tenant_id=other.id)

    blitzenx_results = get_tenant_scoped_query(db_session, Candidate, current_user=blitzenx_recruiter).all()
    other_results = get_tenant_scoped_query(db_session, Candidate, current_user=other_recruiter).all()

    assert [c.candidateID for c in blitzenx_results] == ["C-AISHA"]
    assert [c.candidateID for c in other_results] == ["C-RAVI"]


def test_negative_case_candidate_pii_never_crosses_tenants(db_session):
    """
    The negative case that matters most here: a recruiter at one client
    must never be able to see another client's candidate PII, no matter
    what they pass in a request.
    """
    blitzenx, other, aisha, ravi = _seed_two_tenants_of_candidates(db_session)
    blitzenx_recruiter = _FakeUser(tenant_id=blitzenx.id)

    results = get_tenant_scoped_query(db_session, Candidate, current_user=blitzenx_recruiter).all()

    assert "C-RAVI" not in [c.candidateID for c in results]
    assert all(c.tenant_id == blitzenx.id for c in results)
