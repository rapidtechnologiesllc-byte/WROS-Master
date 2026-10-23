"""Schema declared on the models is the schema PostgreSQL enforces.

PostgreSQL is the only database: an index filter written for another dialect (sqlite_where,
mssql_where) is silently ignored and leaves a full unique index that rejects legitimate rows.
"""
from sqlalchemy import text

import app.models  # noqa: F401 -- registers every model on Base.metadata
from app.core.database import SessionLocal
from app.core.db_contract import _initialize_partial_unique_indexes
from app.models.base import Base


def _indexes():
    for table in Base.metadata.tables.values():
        for index in table.indexes:
            yield table, index


def test_no_index_filters_for_other_dialects(test_db_engine):
    foreign = [f"{t.name}.{i.name}: {d}" for t, i in _indexes()
               for d, opts in i.dialect_options.items() if d != "postgresql" and opts.get("where") is not None]
    assert not foreign, f"Index filters PostgreSQL ignores (use postgresql_where): {foreign}"


def test_full_index_is_rebuilt_as_declared_partial_index(test_db_engine):
    db = SessionLocal()
    try:
        db.execute(text('DROP INDEX IF EXISTS app_schema.ix_one_current_interview_per_level'))
        db.execute(text('CREATE UNIQUE INDEX ix_one_current_interview_per_level '
                        'ON app_schema.submission_interviews (submission_id, level)'))
        db.commit()

        _initialize_partial_unique_indexes(db)
        _initialize_partial_unique_indexes(db)  # idempotent

        definition = db.execute(text("SELECT indexdef FROM pg_indexes WHERE schemaname = 'app_schema' "
                                     "AND indexname = 'ix_one_current_interview_per_level'")).scalar()
        assert definition and "WHERE (superseded_at IS NULL)" in definition, definition
    finally:
        db.close()
