# Shared build rules (read fully before starting)

Repo: WROS (FastAPI + SQLAlchemy on Postgres `app_schema`, React CRA frontend). Read CLAUDE.md at repo root; the binding parts:
- FLAG IT = FIX IT: defects you find in files you touch get fixed at root with a test.
- Authority only from the role template (`RoleTemplate.hierarchy_level`, `is_super_user`, `specialization`, `org_level_access`, permissions). NEVER role-name strings. Look at `app/core/authority.py` for existing helpers and reuse them.
- Schema changes ONLY via `backend/app/core/db_contract.py` (idempotent: create_all for new tables, the `drifted_tables` ADD COLUMN IF NOT EXISTS mechanism for new columns, `data_migrations` marker table for one-time data moves). No alembic, no new *init*/*setup*/*migrate* files.
- Endpoints: permission via `require_role_template_permission(...)` / `require_resource_permission(...)` like neighbouring endpoints; no `get_current_<role>` deps. New screens need a resource + route registered the way existing ones are (`app/seeds/init_resources.py` RESOURCE_ROUTES/NAV_LABELS, `api_contract.MODULES_AND_RESOURCES`, `navigation.py`), and must pass `tests/test_navigation_rebuild.py`. Prefer adding a tab to an existing screen over a new nav item.
- No hardcoded business values: thresholds go in `app/core/config.py` settings (env with defaults) or a DB config table editable from the UI.
- Fail fast: no silent `except: return []`.
- Background jobs: register in `app/core/scheduled_jobs.py` (internal-only jobs need no backlog_guard; anything emailing people outside the company must declare a backlog_guard). Add the new internal job to the default list in `config.SCHEDULED_JOBS_ENABLED`.
- Tasks to people: use the existing Task model + service (`Task.link` deep links) like timesheet approvals / core certification do. Email via the existing MessageQueueService/email handlers.
- Tests: follow the savepoint fixture pattern in `backend/tests/test_core_certification.py`. `export TEST_DATABASE_URL=postgresql+psycopg2://postgres:123@localhost:5432/<your_db>_test` (conftest creates it). Postgres is running locally (`service postgresql start` if not).
- Gate: `git config core.hooksPath .githooks` (hook must be executable). Commit normally; the pre-commit hook runs the full backend suite + ESLint (`frontend/.eslintrc.gate.json`). NEVER `--no-verify`, never skip/disable tests. Also run `cd frontend && CI=true npx react-scripts build` before your final commit (run `npm ci` first if node_modules is missing).
- Do not touch production, do not configure API keys, do not push. Commit to your worktree branch only; I merge.
- Before coding, do a short design pass (upstream deps, downstream effects, what breaks) and write it at the top of your final report.
- Commit message ends with:
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01KKhkti8hBuguVmi3ABZAjJ
- Final report: design notes, what you built (files), tests added, gate result, anything you could not finish, and any business decision you defaulted (state the default).

Gap evidence with file:line references: wip/wfm_gap_research.md

# The three workstreams (CEO-approved, defaults from the gap research)

## WS-A remainder (A1-A6 shipped in PR #414)
- Certifications: `EmployeeCertification` (with expiry) had no writer while training dashboards read it. Endpoints to create, edit and delete; a Certifications section on the employee UI. Decide (and document) which is canonical against the Guidewire fields on `PUT /employees/{id}/certifications`.
- Intercompany ledger: replace free-text entity names (`intercompany_ledger.py`, `revenue_chain_service`) with company FKs. Backfill by exact name match through a `data_migrations` marker. New entries require the company id.
- `ResourceDemand` has no writer: remove it or wire it, and justify the choice.

## WS-B: renewals and margin floor (gaps 1 and 4)
**Allocations**
- `PATCH /allocations/{id}` changes end date, bill rate, utilization or billable. Each change writes a history row (who, when, old to new; a reason is required). It never rewrites past timesheets or P&L, and it re-runs every placement rule.
- Renewal fields: status (NOT_STARTED / IN_DISCUSSION / EXTENDED / ROLLING_OFF), owner, note.
- Owner default: the client account manager if the model has one, otherwise the BU head (via authority helpers, never a role name).
- Daily internal job `renewal_alerts`: one Task to the owner at 60, 30 and 15 days before end (`config`, idempotent), skipped when EXTENDED or ROLLING_OFF.
- UI: a Renewals tab on Demand vs Bench, plus Extend/Edit on the Employees allocations tab.

**Margin policy**
- Margin policy table by delivery engine and country, with `min_margin_pct` and `hard_floor_pct`. Editable in the UI. No rows means no floor, and the UI flags it. Do NOT seed any numbers.
- Margin is checked on allocation create and edit using CostBook loaded hourly cost.
- Below the minimum: PENDING_MARGIN_APPROVAL, which blocks timesheets and invoicing, plus a Task to an approver at BU Head level or above. Below the hard floor, the approver must be Partner level.
- Approve and reject need a reason. Existing ACTIVE allocations are unaffected.

## WS-C: client timesheet approval, PO, invoices (gaps 3 and 12)
**Client approval**
- `Client.requires_client_timesheet_approval` flag.
- Capture `EmployeeAllocation.timesheet_approver_email` in the UI.
- After internal approval, the timesheet goes to CLIENT_PENDING and the client gets a signed, expiring, single-use, rate-limited public link to Approve or Reject (reason required). A reject returns through the existing resubmit-task flow.
- Alternative: an internal approver uploads the client's VMS-approved file as evidence.
- Invoicing refuses weeks without client approval for flagged clients.

**Work orders**
- Routes and UI for work orders.
- `EmployeeAllocation.work_order_id`; the PO number is stored and printed on the invoice.
- Daily internal job: a Task to Finance when a PO is within 30 days of expiry (`config`).
- Hours dated after a PO's end date are refused.

**Invoices**
- Store `issuing_company_id`.
- Gapless sequential invoice number per issuing company (row-locked sequence table), with a backfill.
- `due_date` = sent date + `Client.payment_terms_days`.
- AR follow-up uses `due_date`, plus an AR aging tab on Invoices.
- Build on `timesheet_approval_service.resolve_approver`, which reads the org chart since #413.
