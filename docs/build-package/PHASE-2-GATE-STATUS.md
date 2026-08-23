# Phase 2 acceptance gate — final status, 2026-07-22

Checklist copied verbatim from `02-DATA-MODEL.md`. As with Phase 1, this
is an honest status, not a rubber stamp — the data model is functionally
complete and 337/337 tests pass (1 xfailed), but two items are the same
structural blockers already logged against Phase 1's gate, carried
forward rather than silently re-declared "done" here.

- [x] **Domain 1 — Platform Foundation.** Built in Phase 1 (tenants,
  users, business_units, bu_access, audit_log, error_log,
  consent_records, system_config, notifications, activity_timeline,
  file_uploads).

- [x] **Domain 2 — Candidate & Talent Pipeline (core).** candidates,
  candidate_conversations, candidate_desire_profiles, job_requisitions,
  demands, submissions, interviews, job_specifications all exist and are
  tested. `createCandidateSafe()` (R-07) is the one real creation path,
  retrofitted into both prior direct-insert call sites.
  **Deliberately out of this gate**: the EPIC-11 agent-produced tables
  (`sourcing_alerts`, `sourcing_search_runs`, `staged_candidates`,
  `outreach_sequences`) — `03-THUNDER-AGENTIC-LAYER.md` scopes these to
  Phase 3 Workstream 1 (Recruit), not Phase 2, despite `02-DATA-MODEL.md`
  listing them under this domain's full entity map.

- [x] **Domain 3 — Employee, HR & Delivery Engine (core).** employees,
  employee_allocations, timesheets/timesheet_entries, and
  `employee_engine_history` (insert-only SPECIALITY/CORE transition
  audit trail, HRMS-0101-REV) built and tested.
  **Deferred, not blocking**: the Core-Pull/HTD/buddy-program tables
  (`core_pull_events`, `htd_phase_gates`, `buddy_program_kpi_scores`,
  `core_eligibility_reviews`, etc.) — these are NEW-RM stories
  S-351–378, which `04-RESOURCE-MANAGEMENT.md` scopes to Phase 4,
  running in parallel with Phase 3 rather than inside Phase 2. This
  includes HRMS-0518's Core Eligibility AI Assessor — real, but its
  10-category weighted score (fed by the 35-KPI Buddy Program plus
  timesheet/milestone/escalation signal) is deterministic math; the
  LLM's role there is generating the evidence-summary narrative on an
  already-computed score, not deciding it.
  **Known open gap, tracked not silently dropped**: HRMS-0708
  (Candidate → Employee conversion) has no implementation yet — it
  depends on `offers`/`preboarding_documents` tables that don't exist in
  this codebase (see `submission_service.py:18`).

- [x] **Domain 4 — Client, Revenue & Financial.** clients, opportunities,
  projects, invoices, revenue_leakage/reconciliation, timesheet
  anomaly flags, and the client revenue dashboard are all built and
  tested (HRMS-0910/0909, commit `879ca27`, closes this domain out).
  Analytics/Executive Dashboard `[GAP-SPEC]` (7 undocumented stories)
  collapsed into the two aggregation services already built
  (`timesheet_analytics_service.py`, `client_revenue_dashboard_service.py`)
  per the Dev Review Standard's CRUD-reuse guidance, rather than 7
  separate components.

- [x] **Domain 5 — Sub-Vendor Portal.** Complete (see prior session
  notes) — sub_vendor_accounts, requests, submissions, tracking,
  scorecards, clarification Q&A all built and tested.

- [ ] **Domain 6 — Internal Collaboration, Scheduling & Interview
  Integrity (EPIC-14/15, S-379–386).** **Not built — cannot be built
  against anything real.** Verified four independent ways: no matching
  files, no EPIC-14/15 tag anywhere in any doc, no matching keyword
  cluster, and the requirements corpus literally stops at S-378.
  `02-DATA-MODEL.md`'s claim that these stories are "fully specified"
  does not hold up against the actual `Requirements/` folder. This is
  not a retry-able search failure — there is nothing to build against
  without either (a) confirmation from whoever maintains the
  Requirements folder that these docs exist in an unreceived drop, or
  (b) an explicit decision to build from `02-DATA-MODEL.md`'s schema
  sketch alone plus hand-written business rules, which that same
  document explicitly says to treat as non-authoritative. **Blocked on
  a product decision, not on more engineering effort.**

- [ ] **"Every table has `tenant_id` NOT NULL, indexed."** Same Phase 1
  carry-forward, not re-solved here: every new Phase 2 table follows the
  established nullable-for-safe-upgrade pattern (existing rows backfilled
  to a single tenant via migration `d6e7f8a9b0c1`). The end state is
  still NOT NULL; getting there needs the same real-database access
  Phase 1's gate status already flagged as blocked.

- [ ] **"`employee_performance_events` and `audit_log` confirmed
  append-only at the grant level."** Same Phase 1 blocker, not
  re-solved here — true at the ORM level (tested), not yet at the
  database-grant level, which needs the real SQL Server login name and
  someone with production database access.

- [x] **"A migration can run cleanly end-to-end against an empty
  database and produce every table in this document"** (built-tables
  subset only — Domain 6 excluded per above). Every test in this repo
  spins up a fresh throwaway SQLite via Alembic and passes.

- [x] **"No monetary column exists anywhere outside the `*_usd_cents`
  BIGINT convention."** Held throughout — every financial field added
  this phase (`Invoice.total_usd_cents`, `RevenueLeakageFlag`'s impact
  fields, `Project`'s revenue estimate) follows it, no exceptions found.

## What "done" actually requires from here

Three things, same posture as Phase 1 — infra/product decisions, not
more code from a session like this one:
1. Real database access to flip `tenant_id` to NOT NULL and apply the
   `audit_log`/`employee_performance_events` DENY-grant SQL — identical
   ask to Phase 1's item 1, now covering the Phase 2 tables too.
2. A decision on Domain 6: confirm the EPIC-14/15 docs exist in an
   unreceived drop, or explicitly authorize building from the thin
   schema sketch alone.
3. A decision on HRMS-0708: authorize building the minimum `offers`/
   `preboarding_documents` tables it depends on, or confirm it's
   intentionally deferred to whenever Phase 3's Onboarding workstream
   (which touches the same candidate→employee lifecycle) picks it up.

Everything else on the original Domain 1–5 checklist is done and
tested. **Per Avinash's 2026-07-22 direction, Phase 3 is starting now
in parallel with these three open items** — none of them block Part A
(Thunder Conversation Core / Orchestration Router), which depends only
on Phase 1's `notifications`/`audit_log` tables and Phase 2's
`candidates`/`candidate_conversations` existing, not on Domain 6, the
tenant_id NOT NULL migration, or HRMS-0708.
