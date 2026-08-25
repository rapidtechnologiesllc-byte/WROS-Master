import os
from dotenv import load_dotenv
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

load_dotenv()

config = context.config  # ✅ VALID when run via alembic

# Skip fileConfig to avoid interpolation issues with % in DATABASE_URL
# if config.config_file_name is not None:
#     fileConfig(config.config_file_name)

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL not set")

# Use RawConfigParser to completely disable interpolation
# This allows % characters in the database URL without errors
from configparser import RawConfigParser

# Replace the config's file_config with a RawConfigParser
raw_config = RawConfigParser()

# Read the original alembic.ini if it exists
if config.config_file_name and os.path.exists(config.config_file_name):
    raw_config.read(config.config_file_name)

# Ensure the alembic section exists
if not raw_config.has_section(config.config_ini_section):
    raw_config.add_section(config.config_ini_section)

# Set the database URL (no interpolation will occur)
raw_config.set(config.config_ini_section, 'sqlalchemy.url', database_url)

# Replace the config's file_config with our raw config
config.file_config = raw_config

# Import Base and all models from the app package
from app.models.base import Base

# Import all models to ensure they're registered with Base
# Using selective imports to avoid AttributeError from deleted models
from app.models.tenant import Tenant
from app.models.audit_log import AuditLog
from app.models.consent import ConsentRecord
from app.models.user import Users, Jobs, CandidateAssignment, InterviewPanel, PanelMember, Interview, InterviewFeedback
from app.models.candidate import Candidate, CandidateInfoForm, CandidateEducationForm, CandidateExperienceForm, CandidateAadharForm, CandidatePanForm, CandidateStatus, CandidateJobApplication
from app.models.document import CandidateDocument
from app.models.offer_letter import OfferLetter
from app.models.offer import Offer, OfferStatus
from app.models.newsletter import Newsletter, NewsletterSubscriber
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from app.models.org_structure import Department, OrgNode, OrgPosition, ApprovalChain, PartnerBUAssignment
from app.models.permission import JobTitle, JobTitleRole
from app.models.employee import Employee, EmployeeEmploymentHistory, EmployeeDocuments, EmployeeEngineHistory
from app.models.client import Client, ClientContact, ClientHistory
from app.models.demand import Demand, DemandHistory
from app.models.submission import Submission, SubmissionViolation
from app.models.interview_pipeline import DemandInterviewPanel, SubmissionInterview
from app.models.interview import InterviewFeedback, InterviewDecisionLog, InterviewPanelDecision

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
