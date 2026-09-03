"""
S-207 -- proves app.core.tenant_context's global with_loader_criteria
scoping on real routes that were NEVER part of the original 6-route
import logging
HRMS-0109 fix (tests/test_tenant_scoping_real_routes.py covers those).

Three things this file has to prove, matching the gap doc's own explicit
ask ("thorough concurrent-request testing" before trusting this):
1. A plain single-record-by-PK lookup (the bulk of the ~180 sites) is
   now tenant-scoped even though its route code was never touched.
2. The onboarding.py BU-pool route (the one case the gap doc flagged as
   too complex for a copy-paste fix) is closed as a side effect of the
   final Candidate fetch going through the same global scoping.
3. Two concurrent requests for two different tenants never see each
   other's data -- the actual risk the doc warned a global mechanism
   could introduce if done wrong.

Throwaway SQLite app, throwaway JWT keys -- never the real database or
real signing keys.
"""
import os
import tempfile
import threading

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.security as security
from app.models.base import Base
from app.models.tenant import Tenant
from app.models.user import Users
from app.models.candidate import Candidate
from app.models.candidate_ownership import CandidateOwnership, POOL_BU
from app.models.rbac_template import BusinessUnit
import app.models  # noqa: F401 -- registers every model on Base.metadata


@pytest.fixture()
def throwaway_jwt_keys(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    monkeypatch.setattr(security, "PRIVATE_KEY", private_pem)
    monkeypatch.setattr(security, "PUBLIC_KEY", public_pem)


@pytest.fixture()
def client(throwaway_jwt_keys):
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    from app.api.v1.endpoints.onboarding import router as onboarding_router
    from app.api.v1.endpoints.users import router as users_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(onboarding_router)
    app.include_router(users_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    blitzenx = Tenant(name="BlitzenX")
    other = Tenant(name="Other Client Co")
    db.add_all([blitzenx, other])
    db.commit()

    bu_bx = BusinessUnit(name="BX Delivery")
    bu_other = BusinessUnit(name="Other Delivery")
    db.add_all([bu_bx, bu_other])
    db.commit()

    from app.core.security import get_password_hash
    db.add(Users(
        UserID="U-BX-RECRUITER", UserRole="Super User", UserEmail="recruiter@blitzenx.com",
        UserPassword=get_password_hash("x"), tenant_id=blitzenx.id, business_unit_id=bu_bx.id,
    ))
    db.add(Users(
        UserID="U-OTHER-RECRUITER", UserRole="Super User", UserEmail="recruiter@otherclient.com",
        UserPassword=get_password_hash("x"), tenant_id=other.id, business_unit_id=bu_other.id,
    ))
    db.add(Users(
        UserID="U-BX-EMPLOYEE", UserRole="Employee", UserEmail="employee@blitzenx.com",
        UserPassword=get_password_hash("x"), tenant_id=blitzenx.id, business_unit_id=bu_bx.id,
    ))
    db.add(Users(
        UserID="U-OTHER-EMPLOYEE", UserRole="Employee", UserEmail="employee@otherclient.com",
        UserPassword=get_password_hash("x"), tenant_id=other.id, business_unit_id=bu_other.id,
    ))
    db.add(Candidate(
        candidateID="C-BX-1", candidateEmail="bx1@example.com", candidatePassword="x",
        candidateFirstName="Aisha", tenant_id=blitzenx.id,
    ))
    db.add(Candidate(
        candidateID="C-OTHER-1", candidateEmail="other1@example.com", candidatePassword="x",
        candidateFirstName="Confidential", tenant_id=other.id,
    ))
    db.commit()
    db.add(CandidateOwnership(
        candidateID="C-BX-1", owned_by_bu_id=bu_bx.id, pool_status=POOL_BU,
    ))
    db.add(CandidateOwnership(
        candidateID="C-OTHER-1", owned_by_bu_id=bu_other.id, pool_status=POOL_BU,
    ))
    db.commit()
    db.close()

    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)


def _token_for(email, role):
    return security.create_access_token(data={"sub": email, "type": role, "name": email})


def test_single_record_lookup_never_leaks_across_tenant(client):
    """
    /hr/users/details/{id} was never touched by the original 6-route
    fix -- this is exactly the "vast majority" IDOR-shaped category the
    gap doc flagged as still open. A BlitzenX recruiter looking up the
    other tenant's employee by ID (as if they'd guessed/enumerated it)
    must get 404, not the real record.
    """
    token = _token_for("recruiter@blitzenx.com", "Super User")
    resp = client.get(
        "/hr/users/details/U-OTHER-EMPLOYEE",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    own_resp = client.get(
        "/hr/users/details/U-BX-EMPLOYEE",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert own_resp.status_code == 200
    assert own_resp.json()["user_id"] == "U-BX-EMPLOYEE"


def test_bu_pool_route_closed_as_side_effect_of_global_scoping(client):
    """
    docs/build-package/HRMS-0109-tenant-scoping-gap.md flagged
    onboarding.py:516 (BU-pool candidate listing) as needing a real
    person to resolve, not a copy-paste fix, because CandidateOwnership
    itself has no tenant_id. The global fix closes it anyway: the
    route's final fetch is db.query(Candidate)..., and Candidate is one
    of the three globally-scoped models, so even if BU-pool membership
    were ever miscomputed across tenants, the candidate rows returned
    are still hard-filtered to the caller's own tenant.
    """
    token = _token_for("recruiter@blitzenx.com", "Super User")
    resp = client.get(
        "/onboarding/hr/my-bu/candidates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    ids = [c["candidate_id"] for c in resp.json()["candidates"]]
    assert ids == ["C-BX-1"]
    assert "C-OTHER-1" not in ids


def test_concurrent_requests_for_different_tenants_never_bleed(client):
    """
    The gap doc's explicit fear: a stale/shared context value leaking
    between requests. Fires real concurrent requests for two different
    tenants against the same TestClient (same process, same thread
    pool) and asserts neither ever sees so much as a hint of the other
    tenant's data, across many interleavings.
    """
    bx_token = _token_for("recruiter@blitzenx.com", "Super User")
    other_token = _token_for("recruiter@otherclient.com", "Super User")

    results = {"bx": [], "other": []}
    errors = []

    def hit_bx():
        try:
            for _ in range(15):
                r = client.get(
                    "/hr/users/details/U-BX-EMPLOYEE",
                    headers={"Authorization": f"Bearer {bx_token}"},
                )
                results["bx"].append(r.status_code)
        except Exception as exc:
            # pragma: no cover -- surfaced via errors list
            errors.append(exc)

            def hit_other():
                pass
        try:
            for _ in range(15):
                r = client.get(
                    "/hr/users/details/U-BX-EMPLOYEE",
                    headers={"Authorization": f"Bearer {other_token}"},
                )
                results["other"].append(r.status_code)
        except Exception as exc:
            # pragma: no cover
            errors.append(exc)

            threads = [threading.Thread(target=hit_bx) for _ in range(4)] + [
        threading.Thread(target=hit_other) for _ in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    # BlitzenX's own recruiter, looking up BlitzenX's own employee: always 200.
    assert results["bx"] == [200] * (15 * 4)
    # Other tenant's recruiter, looking up BlitzenX's employee by ID: always
    # 404 -- never a leaked 200, on any interleaving.
    assert results["other"] == [404] * (15 * 4)
