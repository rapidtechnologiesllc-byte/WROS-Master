"""
POST /auth/v1/signup -- proves the privilege-escalation fix: this route
is public (no auth possible, see auth_middleware.PUBLIC_ROUTES), so it
must never trust a caller-supplied user_role. Every self-signup gets
SELF_SIGNUP_DEFAULT_ROLE regardless of what's in the request body.

"""
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.user import Users
import app.models  # noqa: F401 -- registers every model on Base.metadata

@pytest.fixture()
def client():
    engine = create_engine(f"sqlite:///{db_path}")

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    from app.api.v1.endpoints.auth import router as auth_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(auth_router)
    app.dependency_overrides[get_db] = override_get_db

    test_client = TestClient(app)
    try:
        yield test_client, TestSessionLocal
    finally:
        engine.dispose()
        os.remove(db_path)

def test_signup_ignores_caller_supplied_super_user_role(client):
    test_client, SessionLocal = client
    response = test_client.post("/auth/v1/signup", json={
        "user_name": "Attacker",
        "user_email": "attacker@example.com",
        "user_password": "whatever123",
        "user_role": "Super User",
    })
    assert response.status_code == 200

    db = SessionLocal()
    try:
        user = db.query(Users).filter(Users.UserEmail == "attacker@example.com").first()
    finally:
        db.close()

    assert user is not None
    assert user.UserRole == "Employee"
    assert user.UserRole != "Super User"

def test_signup_ignores_caller_supplied_admin_role(client):
    test_client, SessionLocal = client
    response = test_client.post("/auth/v1/signup", json={
        "user_name": "Another Attacker",
        "user_email": "attacker2@example.com",
        "user_password": "whatever123",
        "user_role": "Admin",
    })
    assert response.status_code == 200

    db = SessionLocal()
    try:
        user = db.query(Users).filter(Users.UserEmail == "attacker2@example.com").first()
    finally:
        db.close()

    assert user.UserRole == "Employee"
