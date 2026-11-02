"""Client meeting updates and the roles a client is about to need (CEO 2026-11-02: "we met with this
client and they asked to start an inception for billingcenter which will require us a BC developer,
BC Business Analyst ... the underlying information is still missing to connect with the history of
the client ... Recruitment should start working on it as it takes 60-90 days to hire").

ClientUpdate     -- one meeting or conversation with a client: when, who, what was said, what was
                    agreed; its next steps are real tasks (task_ids). Shown on the client's History.
UpcomingRole     -- a role a client is expected to need, raised on an opportunity before the
                    contract is signed. It IS a job (jobs row, confirmation_status POTENTIAL,
                    source_type OPPORTUNITY) so recruiting starts at once; this row adds what the
                    job alone does not say: how candidates may hear the client described (never
                    its name) and whether Thunder emails matched candidates on its own.
RoleOutreach     -- one personal email to one matched candidate about one upcoming role: what it
                    says, why they fit, who wrote it (Claude or the rules) and what happened to it.
"""
from sqlalchemy import (
    JSON, Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func,
)

from app.models.base import Base

ROLE_OUTREACH_STATUSES = ("QUEUED", "SENT", "SKIPPED", "FAILED")


class ClientUpdate(Base):
    __tablename__ = "client_updates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    client_id = Column(String(512), ForeignKey("clients.id"), nullable=False, index=True)
    opportunity_id = Column(String(512), ForeignKey("opportunities.id"), nullable=True, index=True)
    meeting_date = Column(Date, nullable=False)
    attendees = Column(Text, nullable=True)      # who was there, as written
    summary = Column(Text, nullable=False)       # what was discussed
    decisions = Column(Text, nullable=True)      # what was agreed
    task_ids = Column(JSON, nullable=True)       # the next steps, created as tasks
    created_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class UpcomingRole(Base):
    __tablename__ = "upcoming_roles"

    job_id = Column(String(512), ForeignKey("jobs.jobID"), primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    opportunity_id = Column(String(512), ForeignKey("opportunities.id"), nullable=False, index=True)
    client_update_id = Column(Integer, ForeignKey("client_updates.id"), nullable=True)
    # how the client may be described to candidates, e.g. "a mid-size P&C carrier"; never its name
    client_description = Column(String(300), nullable=False)
    target_start = Column(Date, nullable=True)
    likelihood_pct = Column(Integer, nullable=True)
    # Thunder emails each matched candidate on its own (CEO 2026-11-02: fully automatic)
    auto_outreach = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class RoleOutreach(Base):
    __tablename__ = "role_outreach"
    __table_args__ = (UniqueConstraint("job_id", "candidate_id", name="uq_role_outreach_candidate"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    job_id = Column(String(512), ForeignKey("jobs.jobID"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False, index=True)
    status = Column(String(16), nullable=False, default="QUEUED")  # ROLE_OUTREACH_STATUSES
    match_score = Column(Integer, nullable=True)
    subject = Column(String(998), nullable=True)
    body_html = Column(Text, nullable=True)
    why_fit = Column(Text, nullable=True)        # the reason, for the recruiter
    composed_by = Column(String(16), nullable=True)  # "claude" / "rules"
    note = Column(String(512), nullable=True)        # why it was skipped / failed
    thunder_message_id = Column(String(36), ForeignKey("thunder_email_messages.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    sent_at = Column(DateTime, nullable=True)
