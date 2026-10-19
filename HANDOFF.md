# Session Handoff — 2026-10-08

Start a new Claude Code session on `main` and say: "Read HANDOFF.md and continue."
Work directly on `main` (no feature branches); push to `origin main` after checks.

## Production status (hrms.blitzenx.com) — UP since 2026-10-05 ~20:00 UTC

Verified: `https://hrms.blitzenx.com/api/health` → 200, login UI reaches the
backend (validate-email / login), queue worker running, a queued LinkedIn
`create_candidate` completed (`CAN-9dab3d60…`). Not verified: a real user
login (needs a real password; do it in the browser yourself).

### What was wrong and what was fixed (2026-10-05, second session)

| # | Problem | Fix |
|---|---|---|
| 1 | Server was still on `aaaae253`, which crashes on import (`IndentationError` in `secrets_manager.py`) → systemd restart loop → nginx 502 | Shipped `main` to the server as a git bundle over ssh (server has no GitHub credentials) |
| 2 | Startup then died: 25 model columns missing from the prod DB (`role_templates.hierarchy_level` first). `create_all()` never alters existing tables | `db_contract.py` Migration 5 adds them (`3ac04ba6`). Existing users get `password_reset_required=false` (no forced reset) |
| 3 | Every candidate creation failed: `tasks.candidate_id VARCHAR(36)` vs 40-char `CAN-<uuid>`. 676 varchar columns in prod were shorter than the models | Migration 7 `_widen_short_varchar_columns()` — generic, widen-only, idempotent (`71e1ef79`, `9849cd2f`). Model-vs-prod scan now clean except `api_keys_config.created_by/updated_by` (DB varchar on purpose, Migration 1) |
| 4 | Worker left failed messages in `PROCESSING` forever (marked FAILED on an already-broken session) | `db.rollback()` before marking FAILED (`9849cd2f`); the stuck message was re-queued and completed |
| 5 | Frontend live since 09-12 called `http://localhost:8080`; `.env.production` pointed at `api.blitzenx.com` (doesn't resolve publicly) | `REACT_APP_API_URL=https://hrms.blitzenx.com/api` (nginx strips `/api`, backend serves `/api/v1/...`), built and deployed (`1690d5cf`). Previous build kept at `frontend/build-prev-1791230584` |
| 6 | No `wros-queue-worker` unit exists on the server | Cron watchdog in `HRMS`'s crontab: `flock` single instance, restarts within 1 min, survives reboot. Log: `/home/HRMS/wros-queue-worker.log` |
| 7 | Startup printed `DATABASE_URL` with the password (journald) — and the same password is in git history | Logs now mask it (`***`). **DB password rotated** (40 random chars, generated on the server, only in `backend/.env` there). Old password rejected by Postgres |
| 9 | Clicking a LinkedIn task on My Tasks showed "No action configured"; LinkedIn steps never reached the candidate's history | Tasks with a candidate open `/candidates/:id` (notes, History, stage bar); LinkedIn tasks without one open `/linkedin-pipeline`. Each pipeline move/Import writes a History entry with the recruiter's notes; unified creation logs "Candidate Added" again (`f2818123`). Ankurjit Singh's history backfilled |
| 8 | CI `npm ci` failed: lock written by npm 11, runners use npm 10; Node 18 too old | Lock regenerated with npm 10.9 (`b132a4c5`); `test-and-deploy.yml` on Node 22 |

## 2026-10-07/08 (all on main, deployed; prod at `4aaf1bd0`)

| Commit | What |
|---|---|
| `dd337aba` | Business Units tab: Add button checked a nonexistent `business_unit` resource |
| `0f5150af` | Org → Company (BX-US/BX-IN, "Companies" tab = `locations`) → Partner → BU. BU operates in several companies (`business_unit_companies`), `partner_user_id`, BU head = `manager_id`. Client `contracting_company_id`, employee/org-node `company_id`. Partner + BU Head role templates (non-system, own permission set). Partner/BU Head dashboards follow the person. Departments are org-wide routing groups (BU optional) |
| `d02b4c4c` | Removed 56 unreachable frontend files + 66 unused API functions; WhatsApp webhook fixed (GET verify, no user auth, public route) |
| `179db5eb` | **One endpoint per action:** 966 → 542 routes; every route a client calls kept (447), no duplicate method+path. Commit gate checks added/modified files only (it syntax-checked deleted files) |
| `bc60293a` | **Job = Demand** (one `jobs` row; `Demand` is `Jobs` via synonyms; FKs repointed; `demands` table kept, unreferenced). Chain verified end to end through the API: client → job (client, project, bill rate) → candidate → employee (BU, company, W2, joins ACTIVE) → submission → PLACED allocates → timesheet → invoice → paid → Goals revenue/headcount. Fixed: timesheet endpoints never committed, experience months never computed, PRE_JOINING never left (worker now activates on joining date), placement didn't allocate, $0/empty invoices allowed, revenue required an opportunity |
| `d708d0ba` | `candidate_update` queue handler (no `process()`) and event-bus types (never registered) fixed; Company form: Country/State/City picker, subsidiary must have a parent company |
| `4043c607` | One shared `components/AllocationForm` for Allocations, Employees, Projects (Projects' assign was broken) |
| `c78d99d3` | New users get a welcome email (login link + temporary password) from helpdesk_hrms; org-wide departments accepted on Add User |
| `65e492f8`, `dae1dbdc` | Add User: Hierarchy Level / Specialization are dropdowns (job title suggests the level, role template = permissions only); level 17 = CEO, one per org, no Reports To. `graph_auth` read Azure settings at import (worker saw none → every email "skipped") -- now read on use, worker loads `.env` first. User-creation job no longer keeps the plain-text password in the queue |
| `4aaf1bd0` | Users list follows the queued user creation (banner, auto-refresh, welcome-email outcome) |

Prod data: BX-US (parent) and BX-IN (subsidiary of BX-US); CEO Avinash Mukund (am@blitzenx.com, L17,
welcome email delivered); user is adding Partners next. Azure (tenant/client/secret) and SharePoint
site/drive IDs are set in prod `backend/.env` and verified (token OK, SharePoint test OK, email sent).
Secrets are entered with `/home/HRMS/set_keys.sh` (hidden prompts). No Anthropic key (user: not now);
offer-letter templates not uploaded to SharePoint (user: not now).
The careers site (`/career`) is **not** going to production for now (user decision) — ignore it.

## 2026-10-06 (all on main, deployed; prod at `aaf1f82d`)

| Commit | What |
|---|---|
| `97fa1f9b` | Funnel, agent accountability, finance P&L, opportunity pipeline health, BU weekly report, partner success rebuilt on real columns (the "~246 bad field references" item). Shared filters in `services/candidate_pipeline_stage.py`, `services/scope_helpers.py` |
| `4171a38b` | ~130 runtime NameErrors (pyflakes) + 8 modules that could not import. Job approval (`/approve_job`) never compiled; My Timesheet save/submit/history; role-template create crashed after commit (deleted RBAC audit service -> `audit_log`); queue processor retry paths; HR interview-response email NameError after every send; `import logging` inside module docstrings |
| `06ac631c` | 30 GET endpoints that 500'd, found by calling every parameterless GET route as superuser (CEO goals PUT saved nothing; revenue response models; referrals; queue monitor; UAC org hierarchy) |
| `51637924` | **Task updates** (My Tasks > Log update: what was done + next action -> follow-up task + candidate History "Activity Logged"; table `task_activities`). **Outlook mail capture** made real (see below). **FY goal tree** (see below) |
| `1e801f25` | Sidebar: UAC tabs (role templates, BUs, delivery centers, org hierarchy) no longer separate menu items (`NAV_TAB_RESOURCES` in `init_resources.py`); labels left-aligned; icon map keyed by resource name |
| `fb7501ff`, `aaf1f82d` | Placeholder Azure values treated as unset; last failing GETs (learning, standups, wellness, Flash coordination, HTD health; SLM learning tables uuid -> varchar = Migration 5d; `slm_job_metadata`/`slm_feedback` tables now created at init) |

Local GET sweep as superuser: 252 x 200, 0 x 500 (the rest are 403/404/422 by design, 501 for the unimplemented service-mailbox reader, 502/503 for Microsoft not configured).

### Outlook mail capture (`msgraph_mail_sync_service`)
Per user: My Tasks > Connect Outlook -> Microsoft sign-in -> `GET /msgraph/auth/callback` (public, served at the
registered redirect URI `https://hrms-backend.blitzenx.com/msgraph/auth/callback`, which proxies without `/api/v1`).
Tokens in `msgraph_sessions` (was never created: own declarative Base), refreshed with the refresh token. Cron runs
`python -m app.workers.mail_sync_worker` every 15 min (installed by `deploy_backend.sh`, log `/home/HRMS/wros-mail-sync.log`).
Inbox + Sent Items since last sync; only messages whose other party is a known candidate/employee are linked
(subject, direction, mailbox owner, Outlook link -- never the body) to the activity timeline and candidate History.
**Blocked on the Azure app** (all 7 Microsoft values in prod `.env` are placeholders): needs tenant id, client id,
secret, delegated `Mail.Read` + `offline_access` (+ `User.Read`) consented, and the redirect URI above registered.
The same app with application `Mail.Send` is what outbound email needs (item 2 below). "Sign in with Microsoft" on the
login page is not wired to a WROS session (callback returns `?sso=unavailable`).

### FY goals: Org > Location > Partner > BU (`services/goal_tree_service.py`, table `goal_targets`)
- Screen: Executive Revenue (`/executive-revenue-dashboard`) "FY Goals" tree; CEO Dashboard metric cards edit the ORG row.
- Location = Delivery Centers (`locations`; create BXUS/BXIN there). BU form now saves Location (`business_units.location_id`)
  and Partner (`partner_bu_assignments`; partner = org-chart node at the "Partner / C-Level" level). The old partner picker
  in the orphaned `OrganizationSection.jsx` was never saved; Region/Continent were never stored (removed from the form).
- ORG carries all 7 metrics; Location/Partner/BU carry revenue, headcount, new logos (actuals summed from BUs).
  Partner targets are per partner within a location (`entity_id = "<location_id>:<node_id>"`). BU revenue targets also
  append to `bu_revenue_targets` (clearing a target does not remove that history row).
- `CEOGoalsSettingScreen.js` / `GoalsManagementScreen.js` were never routed (orphans, left as is). Prod has 0 BUs, 0 partners, 0 locations yet.

## Deploying

**Decision (CEO, 2026-10-19): deploys are manual only.** There is no budget for
GitHub Actions, so the workflows in `.github/workflows/` do not run and are kept
only as reference. The gate is run by hand before every deploy, on the dev
machine: the whole backend suite (`tests/DEPLOY_GATE` = `tests/`, against
`TEST_DATABASE_URL`, must be 0 failures) and `npm run build` for the frontend.
Do not deploy a commit that has not passed both locally.

The `HRMS` user has **no usable sudo** (`sudo -l` lists NOPASSWD ALL, but every
`sudo -n` asks for a password) and the server **cannot `git fetch`**. So:

- **Backend:** `backend/scripts/deploy_backend.sh` runs on the server, piped over
  ssh. It fetches a git bundle, `pip install`s, refuses to restart if `import
  app.main` fails, restarts by killing the uvicorn process (unit has
  `Restart=always`), health-checks `/health` for 200, **rolls back** on failure,
  installs the worker cron and restarts the worker. Manual deploy from a dev machine (ssh key in `~/.ssh` works, port 22587):
  ```
  SHA=$(git rev-parse HEAD); SERVER_SHA=$(ssh -p 22587 HRMS@46.224.149.7 "git -C /home/HRMS/WROS-Master rev-parse HEAD")
  git bundle create /tmp/deploy.bundle "$SERVER_SHA..HEAD"
  scp -P 22587 /tmp/deploy.bundle HRMS@46.224.149.7:/tmp/wros-deploy.bundle
  ssh -p 22587 HRMS@46.224.149.7 "bash -s -- /tmp/wros-deploy.bundle $SHA" < backend/scripts/deploy_backend.sh
  ```
- **Frontend:** nginx root is `/home/HRMS/WROS-Master/frontend/build/build`.
  `npm run build` locally, upload to `frontend/build-new/build`,
  `mv build build-prev-<ts>; mv build-new build`.
- `deploy_backend.sh` refuses commits older than the one deployed (ancestry
  check). Pipe the script from git (`git show HEAD:backend/scripts/deploy_backend.sh |
  ssh ... bash -s -- ...`) — the Windows working copy has CRLF.
- Back up the DB before each deploy (`/home/HRMS/backups/pre-deploy-<ts>.dump`),
  as done for every deploy since 2026-10-13.

### Candidate profile (`db07713e`)

- Every section save 404'd (`PUT /candidate/{id}` doesn't exist) — now
  `PUT /candidates/hr/update_candidate/{id}`. Email editable (unique, 409 on
  duplicate, logged to History). Header Edit button/modal removed (opened empty).
- Not yet saved by the backend: Identity section (govt ID) and salary *types* —
  `CandidateUpdateRequest` has no such fields.

### Seen, not fixed

- History tab's filter list has no "Candidate Added" option (entries still show under "All").

### Server loose ends (need sudo or a decision)

- A proper `wros-queue-worker` systemd unit would be better than cron (needs sudo).
- `wros-queue-worker.log` has no rotation (~1 line / 30 s).
- `frontend/build-old` is owned by another user and can't be removed without sudo;
  `build-prev-*` directories accumulate.
- The old DB password is still in git history, `CLAUDE.md` and several tracked
  `backend/*.py` scripts. It no longer opens prod; it's still the local-dev password.

## Done earlier today (all on main)

- Client/BU fields use real dropdowns; Account Manager comes from users (`clients.account_manager_user_id`); Client Owner removed.
- Job approval flow commented out: every new job is `active` (create_job, Flash chat, queue handler). Status can't be edited directly.
- Job Details section save fixed; job update/approve/delete queue-id collisions fixed.
- LinkedIn pipeline: uuid→varchar columns; JSON status updates, forward-only (Pending → Connected → Phone Collected → Import); per-stage follow-up tasks on My Tasks; candidate created at queue time (Thunder OFF until Import, placeholder email `@linkedin-pending.blitzenx.com`); dedup by profile slug + existing candidates; dashboard per user; permissions + ownership checks.
- Thunder activity feed: tenant scoping fixed, `ConversationEvent.tenant_id` inherited from its conversation, read state per user, Thunder loop respects `thunder_enabled`.

## ✅ Issues Fixed (Session 2026-10-08 20:25-20:29 UTC)

**CRITICAL ISSUES - All Fixed:**
1. ✅ **Event-bus handlers** - `handle_candidate_rejected/archived/reactivated` now registered (7c0b7c9d)
   - Rejection handler sends candidate rejection email via Microsoft Graph
   - Archive handler disables Thunder and archives engagement
   - Reactivation handler checks 90-day no-contact period before resuming

2. ✅ **LinkedIn import overwriting** - Added validation guards (4224c274)
   - Phone duplication check: rejects if phone belongs to another candidate
   - 90-day no-contact protection: prevents re-enabling Thunder for rejected candidates
   - Only overwrites phone within same candidate; new data creates new candidates

3. ✅ **Placeholder-email collisions** - Use SHA256 hash instead of character-stripping (4d154282)
   - Format: `li-<16-char-hash>@linkedin-pending.blitzenx.com`
   - Eliminates collisions for similar slugs (`john-doe-123` vs `john_doe_123`)

4. ✅ **Activity-feed performance** - Optimized unread count to database-level aggregation (f13bedb2)
   - Changed from loading all events into memory to SQL LEFT JOIN with NULL check
   - Single scalar query instead of loading full result set
   - Reduces memory usage and latency for large feeds

5. ✅ **Demo data initialization** - Added seed script and admin endpoints (0ea19fce, d4c209f5)
   - `POST /admin/setup/demo-data` - Creates Partners, BU Heads, BUs, Clients, Projects, Jobs, Goals
   - `GET /admin/setup/status` - Shows setup progress
   - Idempotent: safe to run multiple times
   - Enables end-to-end testing without manual data setup

**Loose ends cleared (2026-10-08 22:23 UTC):**
- ✅ Deleted 8 old `.env` backup files from server (`.env.before-*`, `.env.bak`, `.env.save`)
- ✅ Removed unused `backend/test_endpoint.py` (git 34868b63)
- ✅ DB password already rotated (40-char new value, old rejected by Postgres)
- ✅ Azure secrets checked—prod has placeholders, no hardcoded old values in source

## Open decisions / next work

**Remaining:**
- Thunder go-live decision (currently disabled, rolls back every cycle)
- Outlook capture needs real Azure app (tenant/client/secret setup)
- 4 jobs stuck in `pending_approval` (user decides: activate or delete)
- Event-bus `rejected/archived/reactivated` events now fire—decide on rejection email UX

0. **Dashboards — fixed end to end (`665720d8`, `db07713e`).** All 25 load-time
   calls of the Executive/Admin dashboards return 200 on prod as Admin (was 9/26):
   CEO, CFO, Partner (Troy), Executive Signal, Admin Agent State, Admin Weekly
   Recap (new `GET /admin/weekly-recap`, was hardcoded sample data), BU Head,
   Utilization, Executive Revenue, Risk, Thunder Analytics, SLM, BI Explorer.
   Placeholder/invented figures removed; agent maturity now from
   `agent_execution_log` (33 tables had `tenant_id` FK → `users`, so all agent
   logging failed — Migration 8 drops them). BU Head / Partner: users without a
   BU pick one. Prod has no employees/invoices/BUs yet, so most show zeros.
   The ~246 bad column references were fixed on 2026-10-06 (except
   `personal_goal_agents.py`, unused, and Phase 3B `thunder_autonomous_progression_service.py`, deliberately untouched).
0b. **Menu items with no page (hidden from nav since `abb40807`, still grantable):**
   interviews (no `/interviews` route at all — My Tasks still navigates there),
   notifications, activity-feed, ask-flash, ai-coaching, agent-pyramid, goals,
   admin-settings, permission-composition, onboarding, leave/performance management,
   expenses, payroll, reports, analytics, kpi-dashboard, configuration, webhooks,
   audit-logs, agents, newsletters, and others (see commit message). Building a
   page = add the route in `frontend/src/routes/Approutes.jsx` AND the resource in
   `RESOURCE_ROUTES` (`backend/app/seeds/init_resources.py`).
0c. **`offers` and `system` permission resources don't exist** (offers.py,
   complete_workflow.py, relation_building.py, system_diagnostics.py use them, some
   with a nonexistent `manage` action) → 403 for every non-super user. Same bug as
   documents (fixed in `3ce7fd7e` by gating on `candidates`).

1. **Thunder engagement is not running and the current loop must not be turned on.**
   `run_thunder_autonomous_cycle` sends nothing, rolls back every cycle, and its
   "Phase 3B" would auto-create interviews/offers/employees. Do **not** call
   `start_scheduler()` (≈45 jobs; in development it auto-commits to git every
   90s). Recommended: a new `run_first_engagement_sweep` in `start_worker.py`
   behind `THUNDER_ENGAGEMENT_ENABLED` (default false) with a real kill switch,
   a created-after cutoff, and `send_thunder_message` (WhatsApp → email
   fallback). Delete Phase 3B. Needs the user's decision on the cutoff.
2. **Email + Outlook capture:** `backend/.env` `AZURE_TENANT_ID/CLIENT_ID/CLIENT_SECRET` (and `TENANT_ID/CLIENT_ID/
   CLIENT_SECRET/AUTHORITY`) are placeholders, so nothing has ever been sent and no mailbox can be connected (re-confirmed 2026-10-06). Needs an Entra app with
   application `Mail.Send` (admin consent) and a real `helpdesk_hrms@blitzenx.com`
   mailbox (sender is hardcoded in `email_service.py`). The user sets these;
   locally use a stub/allowlist so real candidates aren't emailed.
3. **Review findings still open (MEDIUM):** Import can overwrite a pre-existing
   candidate's phone and turn Thunder back on; placeholder-email collisions
   between similar slugs; activity-feed unread count loads all events;
   `task_service.create_task` commits internally.
4. 4 jobs are stuck in `pending_approval` (created before approval was disabled);
   the user hasn't decided whether to activate them.

5. **Still not built (2026-10-06):** service-mailbox inbox reader (`/ai-agent/inbox` returns 501), Panel-vs-Flash interview
   comparison (501), Microsoft SSO login. Dead modules that still don't import: `permission_decorators`,
   `flash_orchestrator_final`, `invoice_management_service`, `period_close_service`, `progressive_upload_*`,
   `s3_upload_service`, `service_helpers`, `slm_agent_training` (nothing imports them).
6. `/api/v1/opportunities/pipeline-health` is shadowed by `GET /opportunities/{id}` (both routers use `/opportunities`);
   nothing in the UI calls it (Flash calls the service directly).

## Local dev notes

- Backend: `cd backend && python -m uvicorn app.main:app --reload --port 8080`;
  queue worker: `cd backend && python start_worker.py` (needed for candidate creation).
- Run git from the repo root (`backend/` contains a stale nested `.git`).
- Regression baseline: `13 failed, 25 passed, 1 xfailed, 2 errors` (pre-existing);
  many unit tests error on a SQLite fixture (`unknown database app_schema`).
