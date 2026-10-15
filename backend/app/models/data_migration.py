"""One-time data migrations that have run on this database.

A row is the persisted proof that a named migration ran; `db_contract._run_data_migrations`
inserts it in the same transaction as the migration itself, so a migration runs exactly once
even when several instances start at the same time.
"""
from sqlalchemy import Column, DateTime, String, func

from app.models.base import Base


class DataMigration(Base):
    __tablename__ = "data_migrations"

    name = Column(String(120), primary_key=True)
    applied_at = Column(DateTime, nullable=False, server_default=func.now())
