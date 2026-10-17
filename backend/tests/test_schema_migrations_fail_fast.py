"""Startup schema migrations (db_contract._run_schema_migrations) are idempotent and fail fast:
on an up-to-date schema every statement is a no-op, so restarts run cleanly; a statement that
still fails is logged and raised, and startup stops instead of running half-migrated."""
import pytest
from sqlalchemy import inspect, text

from app.core import db_contract


def test_migrations_run_twice_on_an_up_to_date_schema(test_db_engine):
    db_contract._run_schema_migrations()
    db_contract._run_schema_migrations()
    db_contract._create_performance_indexes()
    db_contract._create_performance_indexes()


def test_a_dropped_column_comes_back(test_db_engine):
    with test_db_engine.begin() as conn:
        conn.execute(text("ALTER TABLE app_schema.candidate_status DROP COLUMN IF EXISTS thunder_assigned_at"))
    db_contract._run_schema_migrations()
    columns = {c["name"] for c in inspect(test_db_engine).get_columns("candidate_status", schema="app_schema")}
    assert "thunder_assigned_at" in columns


def test_a_failing_statement_stops_startup(test_db_engine, monkeypatch):
    def broken(db):
        db_contract._migration_step(db, "broken", "ALTER TABLE app_schema.no_such_table ADD COLUMN x INTEGER")

    monkeypatch.setattr(db_contract, "_widen_short_varchar_columns", broken)
    with pytest.raises(db_contract.SchemaMigrationError, match="broken"):
        db_contract._run_schema_migrations()


def test_initialize_database_does_not_swallow_a_migration_failure(monkeypatch):
    def broken():
        raise db_contract.SchemaMigrationError("Schema migration 'x' failed")

    monkeypatch.setattr(db_contract, "_run_schema_migrations", broken)
    with pytest.raises(db_contract.SchemaMigrationError):
        db_contract.initialize_database()
