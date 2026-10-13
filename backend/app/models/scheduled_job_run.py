from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

from app.models.base import Base


class ScheduledJobRun(Base):
    """One row per scheduled job: the lease that stops two cron runs (or two
    hosts) executing the same job, plus the outcome of its latest run."""
    __tablename__ = "scheduled_job_runs"

    name = Column(String(128), primary_key=True)
    lease_token = Column(String(36), nullable=True)
    running_until = Column(DateTime, nullable=True)
    last_started_at = Column(DateTime, nullable=True)
    last_finished_at = Column(DateTime, nullable=True)
    last_status = Column(String(16), nullable=True)  # RUNNING / SUCCESS / FAILED / TIMEOUT
    last_error = Column(Text, nullable=True)
    last_result = Column(JSON, nullable=True)
    run_count = Column(Integer, nullable=False, default=0)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    first_enabled_at = Column(DateTime, nullable=True)
