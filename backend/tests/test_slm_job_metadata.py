"""slm_job_metadata (and the other SLM tables) are declared in app.models, so every
Base.metadata.create_all creates them: before, the model lived in a service module, the test schema
never had the table, and every job's SLM metadata write failed (logged only)."""
import logging

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.base import Base
from app.models.slm_job_metadata import SLMJobMetadata
from app.schemas.user import JobCreateRequest
from app.services.slm_job_metadata_service import SLMJobMetadataService
from tests.flash_world import make_world, queued, uid  # noqa: F401 -- fixture


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def test_the_slm_tables_exist_after_create_all(test_db_engine):
    tables = set(inspect(test_db_engine).get_table_names(schema="app_schema"))
    assert {"slm_job_metadata", "slm_feedback", "slm_model_versions"} <= tables


def test_every_mapped_table_is_declared_in_app_models():
    """A model declared anywhere else is created only if something happens to import it first."""
    import app.main  # noqa: F401 -- every router and service the app loads

    outside = sorted(f"{m.class_.__module__}.{m.class_.__name__}" for m in Base.registry.mappers
                     if not m.class_.__module__.startswith("app.models."))
    assert outside == []


def test_metadata_is_stored_updated_and_counted(db):
    job_id = f"JOB-{uid()}"
    assert SLMJobMetadataService.store_job_metadata(db, job_id, "Rails Developer", required_skills=["Ruby on Rails"],
                                                    created_by="U-1")
    assert SLMJobMetadataService.store_job_metadata(db, job_id, "Senior Rails Developer")
    assert SLMJobMetadataService.record_hiring_outcome(db, job_id, candidate_interviewed=True)
    stored = SLMJobMetadataService.get_job_metadata(db, job_id)
    assert stored["job_title"] == "Senior Rails Developer" and stored["required_skills"] == ["Ruby on Rails"]
    assert stored["candidates_interviewed"] == 1
    assert db.query(SLMJobMetadata).filter_by(job_id=job_id).count() == 1


def test_creating_a_job_writes_its_metadata(db, queued, caplog):
    from app.services.job_creation_service import submit_job

    world = make_world(db)
    request = JobCreateRequest(
        job_title="Rails Developer", job_description="Rails work", job_skills="Ruby on Rails, PostgreSQL",
        job_experience="5+ years", min_experience_years=5, job_location="Remote", work_location="REMOTE",
        company_type="Full time", company_name=world.client_name, job_status="active", no_of_positions=1,
        client_id=world.client.id, business_unit=world.unit.id)
    with caplog.at_level(logging.ERROR):
        job_id = submit_job(db, world.requester, request)
    assert not [r for r in caplog.records if "[SLM]" in r.getMessage()]
    own = SessionLocal()  # written through its own session, committed
    try:
        row = own.query(SLMJobMetadata).filter_by(job_id=job_id).one()
        assert row.job_title == "Rails Developer" and row.required_skills == ["Ruby on Rails", "PostgreSQL"]
        assert row.business_unit_id == world.unit.id and row.created_by == world.requester.UserID
        own.delete(row)
        own.commit()
    finally:
        own.close()
