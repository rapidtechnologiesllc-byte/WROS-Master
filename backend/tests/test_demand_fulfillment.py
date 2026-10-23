"""Demand fulfillment KPI reads client demand where it lives -- Jobs (Demand) headcount vs
positions filled. ResourceDemand had no writer anywhere, so the KPI always read an empty table;
the model is gone (CEO 2026-10-23)."""
import importlib
import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.tenant import Tenant
from app.models.user import Jobs
from app.services.kpi_service import KPIService


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _kpi(db):
    return KPIService.calculate_kpi(db, "resource_management", "demand_fulfillment", "monthly")


def _job(db, client, positions, filled, status="OPEN"):
    job = Jobs(tenant_id=1, client_id=client.id, jobTitle="Dev", jobDescription="d", jobSkills="x",
               jobExperience="5", jobLocation="Remote", noOfPositions=positions, positions_filled=filled,
               demand_status=status)
    db.add(job)
    db.flush()


def test_fulfillment_is_positions_filled_over_positions_asked(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    before = _kpi(db)
    client = Client(tenant_id=1, company_name=f"Insurer {uuid.uuid4().hex[:6]}")
    db.add(client)
    db.flush()
    _job(db, client, 4, 3)
    _job(db, client, 1, 0)
    _job(db, client, 10, 0, status="CANCELLED")  # withdrawn demand is not unmet demand
    after = _kpi(db)
    assert after["quantity_needed"] == before.get("quantity_needed", 0) + 5
    assert after["quantity_fulfilled"] == before.get("quantity_fulfilled", 0) + 3
    assert 0 < after["value"] <= 100


def test_the_writerless_resource_demand_model_is_gone():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.models.resource_demand")
