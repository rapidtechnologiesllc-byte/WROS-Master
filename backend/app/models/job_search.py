"""A job's search criteria and the candidates the recruiter agent captured with them.

JobSearchCriteria -- one per job: the boolean search over skills and resumes that finds its candidates.
                     Written by the system from the job's skills when the job goes live; a recruiter may
                     edit it, and may go back to the system's version.
JobSearchMatch    -- one candidate found for one job by its criteria: where each term was found, and what
                     the agent did about it (captured, written to, or why not).
"""
from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func

from app.models.base import Base

MATCH_STATUSES = ("CAPTURED", "CONTACTED", "SKIPPED")


class JobSearchCriteria(Base):
    __tablename__ = "job_search_criteria"

    job_id = Column(String(512), ForeignKey("jobs.jobID", ondelete="CASCADE"), primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    boolean_query = Column(Text, nullable=False)     # the one in use
    generated_query = Column(Text, nullable=False)   # what the system wrote from the job
    edited_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)  # None: the system's version
    edited_at = Column(DateTime, nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class JobSearchMatch(Base):
    __tablename__ = "job_search_matches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    job_id = Column(String(512), ForeignKey("jobs.jobID", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Integer, nullable=False, default=0)
    found = Column(JSON, nullable=True)        # term -> where it was found (skills / title / resume)
    snippet = Column(Text, nullable=True)      # the resume line that matched
    status = Column(String(16), nullable=False, default="CAPTURED")  # MATCH_STATUSES
    note = Column(String(512), nullable=True)  # why not written to
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    contacted_at = Column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("job_id", "candidate_id", name="uq_job_search_match"),)


class SkillSynonym(Base):
    """Other names a skill goes by, added by the team (P902, CEO 2026-11-16). Used by boolean search on top of the
    built-in list (app.constants.skill_synonyms): searching the skill also finds these names. One row per skill per
    tenant; `skill_key` is the skill lower-cased."""
    __tablename__ = "skill_synonyms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    skill = Column(String(200), nullable=False)
    skill_key = Column(String(200), nullable=False)
    other_names = Column(JSON, nullable=False)  # ["PC", "Policy Center"]
    updated_by = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("tenant_id", "skill_key", name="uq_skill_synonym_per_tenant"),)


class SavedCandidateSearch(Base):
    """A boolean candidate search someone kept, to run again (P911). Its last run says when and how many matched."""
    __tablename__ = "saved_candidate_searches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    user_id = Column(String(512), ForeignKey("users.UserID", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    query = Column(Text, nullable=False)
    min_experience_years = Column(Float, nullable=True)
    location = Column(String(200), nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    last_result_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_saved_candidate_search_name"),)
