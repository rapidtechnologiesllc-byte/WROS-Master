"""
Proves the backfill logic in migration d6e7f8a9b0c1: every existing
NULL-tenant_id row gets pointed at a single seeded "BlitzenX" tenant,
and re-running is idempotent (doesn't create a second tenant row or
touch rows that already have a real tenant_id).

database built from the real models -- not a live alembic invocation
(that needs an active migration context), but the actual logic under
test, not a paraphrase of it.
"""
import os

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.user import Users
from app.models.candidate import Candidate

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

def _run_backfill(conn):
    """The exact logic from migration d6e7f8a9b0c1's upgrade(), run
    directly against a connection rather than through alembic's op."""
    existing = conn.execute(sa.text("SELECT id FROM tenants WHERE name = :name"), {"name": "BlitzenX"}).fetchone()
    if existing:
        tenant_id = existing[0]
    else:
        result = conn.execute(sa.text("INSERT INTO tenants (name, is_active) VALUES ('BlitzenX', 1)"))
        tenant_id = result.lastrowid
    conn.execute(sa.text("UPDATE users SET tenant_id = :tid WHERE tenant_id IS NULL"), {"tid": tenant_id})
    conn.execute(sa.text("UPDATE candidates SET tenant_id = :tid WHERE tenant_id IS NULL"), {"tid": tenant_id})
    conn.commit()
    return tenant_id

def test_existing_null_tenant_rows_get_backfilled(db_session):
    db_session.add(Users(UserID="U-EXISTING", UserRole="Recruiter", UserEmail="existing@blitzenx.com", UserPassword="x"))
    db_session.add(Candidate(candidateID="C-EXISTING", candidateEmail="c@example.com", candidatePassword="x"))
    db_session.commit()

    tenant_id = _run_backfill(db_session.connection())
    db_session.expire_all()

    user = db_session.query(Users).filter(Users.UserID == "U-EXISTING").first()
    candidate = db_session.query(Candidate).filter(Candidate.candidateID == "C-EXISTING").first()
    assert user.tenant_id == tenant_id
    assert candidate.tenant_id == tenant_id
    assert db_session.query(Tenant).filter(Tenant.name == "BlitzenX").count() == 1

def test_rerunning_is_idempotent_no_duplicate_tenant(db_session):
    db_session.add(Users(UserID="U-A", UserRole="Recruiter", UserEmail="a@blitzenx.com", UserPassword="x"))
    db_session.commit()

    tenant_id_1 = _run_backfill(db_session.connection())
    tenant_id_2 = _run_backfill(db_session.connection())

    assert tenant_id_1 == tenant_id_2
    assert db_session.query(Tenant).filter(Tenant.name == "BlitzenX").count() == 1

def test_rows_that_already_have_a_tenant_are_not_touched(db_session):
    other_tenant = Tenant(name="Some Other Client")
    db_session.add(other_tenant)
    db_session.commit()

    db_session.add(Users(
        UserID="U-OTHER", UserRole="Recruiter", UserEmail="other@client.com",
        UserPassword="x", tenant_id=other_tenant.id,
    ))
    db_session.commit()

    _run_backfill(db_session.connection())
    db_session.expire_all()

    user = db_session.query(Users).filter(Users.UserID == "U-OTHER").first()
    assert user.tenant_id == other_tenant.id  # unchanged, not reassigned to BlitzenX
