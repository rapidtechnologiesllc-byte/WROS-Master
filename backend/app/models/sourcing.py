"""
HRMS-1102 -- Workforce Demand Monitoring Agent (Phase 3 Workstream 1 /
Recruit), EPIC-11.

Two tables, per S-271_HRMS-1102.docx's Data Mapping section:

  demand_gap_scores -- one row per (demand_id, scored_at), full history
                       retained (BR-1102-04: append-only, feeds
                       HRMS-1109's Learning Optimisation job later).
  sourcing_alerts    -- this agent's actual output; HRMS-1103 (LinkedIn
                       Sourcing Agent Loop) consumes rows from here.

R-04 (bench-first) itself is NOT reimplemented here -- this codebase's
real R-04 gate already exists as `Demand.bench_first_checked` /
`app.services.demand_service.enable_sourcing()`. This agent reads that
existing flag as its insufficiency signal rather than building a
second bench-first mechanism, same "don't build the same rule twice"
discipline as everywhere else in this session.

bench_match_count is a genuinely unresolved dependency: the doc's
`BenchFirstPolicyEngine.check(demand_id)` is specified to count bench
candidates against `Demand.required_skills` via a skill-matching index
-- no such index, skill-tagged bench pool, or `bench_pool` table exists
in this codebase yet (it's explicitly Phase 4 / "Resource & Bench
Management basics" GAP-SPEC territory, per `04-RESOURCE-MANAGEMENT.md`
Part B). `app.services.demand_gap_monitoring_service.scan_demand_gap()`
takes bench_match_count as a required, caller-supplied value rather
than inventing a fake skill-matching engine to produce it -- flagged
here, not silently faked with a number that would look real but isn't.
"""
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base

GAP_SEVERITIES = ("NONE", "WATCH", "ALERT", "CRITICAL")
# OPEN/ACKNOWLEDGED/RESOLVED are HRMS-1102's own RM-facing states;
# PROCESSING/SOURCED are HRMS-1103's, added here rather than in a
# second enum since both stories share the one sourcing_alerts table.
SOURCING_ALERT_STATUSES = ("OPEN", "PROCESSING", "SOURCED", "ACKNOWLEDGED", "RESOLVED")
SEARCH_RUN_STATUSES = ("QUEUED", "RUNNING", "COMPLETE", "FAILED")
DEDUP_STATUSES = ("NEW", "POSSIBLE_DUPLICATE", "CONFIRMED_DUPLICATE")
STAGED_CANDIDATE_STATUSES = ("PENDING_REVIEW", "PROMOTED", "REJECTED")


def _new_uuid() -> str:
    return str(uuid.uuid4())


class DemandGapScore(Base):
    """BR-1102-04: append-only -- app.services.demand_gap_monitoring_
    service never updates or deletes an existing row, only inserts."""
    __tablename__ = "demand_gap_scores"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    demand_id = Column(String(512), ForeignKey("demands.id"), nullable=False, index=True)

    bench_match_count = Column(Integer, nullable=False)
    bench_first_check_passed = Column(Boolean, nullable=False)
    gap_severity = Column(String(20), nullable=False)  # one of GAP_SEVERITIES
    rationale = Column(Text, nullable=True)             # max 300 chars per UI spec, not enforced at DB level
    llm_parse_failed = Column(Boolean, nullable=False, default=False)
    days_open = Column(Integer, nullable=False)

    scored_at = Column(DateTime(timezone=False), server_default=func.now())


class SourcingAlert(Base):
    """HRMS-1102's actual output -- HRMS-1103 (LinkedIn Sourcing Agent
    Loop) picks up OPEN rows from here."""
    __tablename__ = "sourcing_alerts"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    demand_id = Column(String(512), ForeignKey("demands.id"), nullable=False, index=True)
    gap_score_id = Column(String(512), ForeignKey("demand_gap_scores.id"), nullable=True)

    severity = Column(String(20), nullable=False)  # ALERT | CRITICAL -- WATCH/NONE never create a row
    rationale = Column(Text, nullable=True)
    bench_first_check_passed = Column(Boolean, nullable=False)
    status = Column(String(20), nullable=False, default="OPEN")

    created_at = Column(DateTime(timezone=False), server_default=func.now())
    acknowledged_at = Column(DateTime(timezone=False), nullable=True)
    acknowledged_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)

    # HRMS-1103 fields -- this agent consumes OPEN rows from this same table.
    sourced_at = Column(DateTime(timezone=False), nullable=True)
    # BR-1103's Boolean Search Engine failure counter -- 2 consecutive
    # failures pages the RM (AC-6). Reset to 0 on any successful search.
    consecutive_search_failures = Column(Integer, nullable=False, default = False)

    demand = relationship("Demand", foreign_keys=[demand_id], lazy="select")


class SourcingSearchRun(Base):
    """HRMS-1103 -- one row per attempt to source against a
    sourcing_alerts row (a re-queued alert gets a new run, not an
    update to the old one, so the history of attempts is preserved)."""
    __tablename__ = "sourcing_search_runs"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    sourcing_alert_id = Column(String(512), ForeignKey("sourcing_alerts.id"), nullable=False, index=True)

    boolean_query = Column(Text, nullable=True)          # max 2000 chars per UI spec
    alt_queries = Column(Text, nullable=True)             # JSON-encoded array
    search_rationale = Column(Text, nullable=True)        # max 300 chars per UI spec
    estimated_result_volume = Column(Integer, nullable=True)
    manual_query_override = Column(Text, nullable=True)   # recruiter-supplied, takes precedence when set

    status = Column(String(20), nullable=False, default="QUEUED")  # one of SEARCH_RUN_STATUSES
    staged_candidate_count = Column(Integer, nullable=False, default = False)

    created_at = Column(DateTime(timezone=False), server_default=func.now())
    completed_at = Column(DateTime(timezone=False), nullable=True)


class StagedCandidate(Base):
    """
    BR-1103-01: deliberately NOT a candidates table row and has NO FK
    to `candidates` -- non-authoritative until a recruiter explicitly
    promotes it (BR-1103-02), which is the only path that ever calls
    createCandidateSafe()'s CREATE path for one of these.
    """
    __tablename__ = "staged_candidates"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    search_run_id = Column(String(512), ForeignKey("sourcing_search_runs.id"), nullable=False, index=True)

    linkedin_profile_url = Column(String(512), nullable=True)  # one of the dedup keys
    email = Column(String(512), nullable=True)
    mobile = Column(String(20), nullable=True)
    full_name = Column(String(300), nullable=True)
    raw_profile_data = Column(Text, nullable=True)  # JSON-encoded, whatever the search API returned

    dedup_status = Column(String(30), nullable=False)  # one of DEDUP_STATUSES -- CONFIRMED_DUPLICATE rows are filtered before insert, see service module
    status = Column(String(20), nullable=False, default="PENDING_REVIEW")

    # BR-1103-02: set only via the explicit recruiter promotion action.
    promoted_to_candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=True)
    promoted_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    promoted_at = Column(DateTime(timezone=False), nullable=True)

    created_at = Column(DateTime(timezone=False), server_default=func.now())
