# WROS — Open Defects & Requirements (single source of truth)

**Built:** 2026-10-13 by validating ~430 unique documents and the 346 open GitHub issues against `main` (`a91e408d`).
**Rule:** an item is listed only if it was checked against the current code. Status documents that only made claims were archived (see `archive/README.md`).
**Production:** `hrms.blitzenx.com` runs `0bcb2d6e` (last successful deploy, 2026-10-12 22:50). Everything on `main` after that has **not** been tested or deployed. See P0-1.

Other live documents: `HANDOFF.md` (deploy procedure, prod state) · `docs/OPEN_REQUIREMENTS_BACKLOG.md` (246 open backlog stories) · `CLAUDE.md` (rules) · `LOCAL_DEVELOPMENT.md`, `DEVELOPER_ONBOARDING.md` (setup).

## Progress log (working tree, not yet committed)

Verification method for every fix: pyflakes over `backend/app` (0 undefined names, 0 syntax errors), the live route table (all registered routes and their real dependencies), a GET sweep of every parameterless route through the real app and middleware as a super user, and targeted checks that run real code against `wros_dev` inside one transaction that is always rolled back.

| Item | Status | What changed |
|---|---|---|
| P0-1 | **Open (CEO)** | GitHub Actions billing |
| P0-2 | Done | `opportunity_service.transition_stage`: `STAGE_TRANSITIONS` is the single rule; `Project` imported; duplicate BU check removed. Verified PROPOSAL → CONTRACT (one project) → ACTIVE; illegal moves rejected. `tests/test_project.py` updated from the removed WON stage. |
| P0-3 | Done | `visibility.py`, `bu_head_dashboard.py` and its service restored to the deployed version (the 10-13 merge reversed the CEO's 2026-10-12 BU-only scope rule). 27 real dashboard calls pass. |
| P0-4, P0-6 | Done | The 10-13 merge of an old branch had deleted the learning system production runs (endpoints, services, models, webhooks, frontend screens). Restored to the deployed version. |
| P0-5 | Done | `ai_conversation_service.py` restored. The merged block was dead (no callers, no handlers for its messages), used role-name authority, and put a user id in `tenant_id`. |
| New P0 | Done | `recruiter_assignment_service.py` did not parse (`SyntaxError`), which broke recruiter auto-assignment on every new candidate. Rebuilt on one rule (`active_recruiters`): Recruitment function plus a role template that can edit candidates, never role-name text (so HR Managers are excluded by data). Job round-robin is now tenant-scoped. |
| New P0 | Done | 10-13 role-string regressions reverted: partner lookups back to BU structure (`partner_user_ids`); `core/roles.py`, `role_validation_service.py`, the one-off migration script, the re-added `thunder_autonomous_loop.py` and `personal_goal_agents.py`, and the dead `thunder_send_outreach` registration removed. |
| Learning endpoints (live in prod) | Done | 3 crashed (`current_user.get`), 2 compared varchar `tenant_id` with an int, `learning_analytics` took `tenant_id` **from the query string** (cross-tenant read), `learning_transcript` had no permission gate. All now take the tenant from the session; transcript gated on `slm-dashboard` view. GET sweep: 0 x 500 (was 5). |
| Tenant fail-fast | Done | One helper, `tenant_context.tenant_id_of(user)`: fails closed with 403 and replaces 9 copy-pasted checks, including generator-throw hacks that surfaced as bare 500s. |
| P1-1, P1-2 | Done | `/api-keys` gated on `api-keys` view/edit; `/message-templates` on `admin-settings` view/edit. Verified 403 for a role without the grant. **Data note:** in local `wros_dev` the Recruiter template grants both; review production role grants. |
| P1-3 | Done | CSRF removed: bearer-header auth with `credentials: 'omit'` and no cookies is not CSRF-exposed, and the in-memory single-use token store broke on restart and let anyone grow memory through the public `/csrf/token`. Job approval verified 200 → active, re-approve 400. |
| P1-4 | Done | `monitoring.py` and `config.py` were unregistered and unused, so they were deleted. Stuck-message recovery is now autonomous inside the worker (`_reclaim_stuck_processing`): PROCESSING past 2x handler timeout + 60s goes back to retry, or DEAD_LETTER after 5. `processing_started_at` is now recorded. |
| New P1 | Done | Delivery-outcome webhooks (SendGrid, Mailgun, Twilio SMS/WhatsApp) were blocked by the auth middleware and had no signature check. They are now public in the middleware and verified fail-closed with each provider's real algorithm (`app/core/delivery_webhook_auth.py`): 503 until configured, 401 on bad or stale signatures. Needs `WEBHOOK_PUBLIC_BASE_URL`, `SENDGRID_WEBHOOK_PUBLIC_KEY`, `MAILGUN_WEBHOOK_SIGNING_KEY`, `TWILIO_AUTH_TOKEN` (in the env templates). |
| P1-5 | **In progress** | ~100 `tenant_id` 1 defaults (44 default params, 32 `or 1` fallbacks, bootstrap literals) |
| P1-6 | Done | DB password scrubbed from every tracked file, archive included; `docker-compose.yml` requires `DB_PASSWORD`. Still in git history (no longer opens prod). |
| P1-7 | **Open (plan)** | GitHub plan |
| Dead code | Done (backend) | Reachability scan from the real entry points (app, workers, cron): **831 → 737 modules, ~25,900 lines removed** (architect/SDLC/phase tooling, duplicate monitors, unwired learning services, unused schemas and utils, superseded services, the old migrations backup, `frontend/.github` workflows that never ran). `get_current_hr_or_admin` had already been deleted; its 4 stale test imports now use `get_current_internal_user`. 60 modules remain unreachable on purpose: see "Built, not wired" below. |
| New P0 | Done | `initialize_database()` crashed on any fresh database: commit `d2c66c46` put `linkedin-pipeline`, a sub-page of `candidates` rather than a resource, into the Partner/BU Head seeds. Removed; both roles already have `candidates`. |
| P2-1 | Done | One idempotent `candidate_contact_policy.record_rejection()` used by every path: manual "Rejected", the interview No Hire verdict (neither recorded anything before), and the queue handler. It writes `candidate_rejections` (starts the 90-day no-contact period), switches Thunder off, and logs a correct EventLog entry. The rejection email is off behind `REJECTION_EMAIL_ENABLED` (decision 5) and never shows the internal reason. Verified end to end through the API. |
| P2-2 | Done | My Tasks routes by the task's links (`candidate_id`, new `interview_id` in TaskItem) to `/candidates/{id}?tab=interview`; offer tasks pointed at a missing `/offer-letters`, now `ROUTES.OFFERS_LISTING`. |
| P2-10 | Done | Timesheets editable only in DRAFT; a REJECTED one reopens to DRAFT on first correction; SUBMITTED, APPROVED and DISPUTED are locked. |
| New P1 | Done | Forgot-password throttle only counted sent tokens, so rapid requests queued several reset emails. It now also counts queued ones. |
| New P0 (data) | Done | DB sessions now run in UTC (`SET TIME ZONE 'UTC'`). 264 columns default to `now()` (server-local) but the code compares with `utcnow()`; on a non-UTC server every time window (throttles, cooldowns, stuck-message reclaim) was shifted by the offset. |
| Test safety | Done | `backend/.env.local` (override=True), and a second copy of that logic in `database.py`, sent app code under test to **wros_dev**. Environment loading now lives only in `config.py`, and `TEST_DATABASE_URL` wins. 10 queue rows leaked into wros_dev by verification runs were dead-lettered with an explanation (not deleted). |
| Access model (decision 6) | Done | Access = the Manage Role's permission set (new `org_roles.role_template_id`, one per role, **created empty**) ∪ the function add-on (`users.role_template_id`, unchanged) ∪ personal overrides. Level = the Manage Role's (authenticator rule uses the higher of role/add-on level, so nobody loses a second factor). One choke point (`role_template_permission_service`) feeds API checks, menu, `/hr/me`, authority, pickers (users authority filter, invoice approvers, BU leader options, recruiter pool, opportunity owners). Role sets can't be deleted/disabled; editing one needs `org-roles` edit; nobody changes their own role/add-on; add-ons must be enabled, same-tenant, not a role set. Analysis: `docs/ACCESS_MODEL_IMPACT.md`. **Parity on wros_dev (all 22 users, every resource x action): 0 lost; 7 Employee users gained Notifications (bug below); levels changed only am@ 5→17, superuser@ 5→14.** |
| New P1 | Done | ~67 resource names existed twice (legacy seeds); checks used whichever row Postgres returned while Partner/BU Head/Employee grants sat on the legacy row, so those templates were silently denied candidates, jobs, interviews, employees, projects, invoices, notifications. Lookups now use one canonical row (contract module); startup moves grants/overrides onto it and **disables** (not deletes) the 68 duplicates. Also: `get_user_permissions` ignored grant-only overrides; template edit endpoints wrote permission rows without the template's tenant. |
| Delete buttons (all 5 admin tabs) | Done | Two causes. (1) Every delete used `window.confirm`, which embedded browsers suppress (returns false at once), so nothing happened: replaced app-wide (21 confirms + 8 alerts in 12 files) by one in-app dialog (`components/ConfirmHost`, `utils/dialogs`). (2) Users, business units, companies and seats were hard-deleted while other rows still referenced them -> bare 500. One checker reads the database's own foreign keys (`app/core/references.py`): unreferenced -> deleted; referenced -> 409 naming what uses it. A **person with history is deactivated** (`terminated_at`), not erased. Role-template add-ons got a delete button. Also fixed: deactivated users could still sign in or use tokens (now refused at login, refresh and on every request); token refresh looked users up by email with a UserID so it never worked for staff; company delete had no tenant filter; user delete required `edit` while the button showed for `delete`; `authenticate_user` logged every stored password hash and a fingerprint of the typed password. |
| Role templates: what a new one is for | Done | "New role template" now creates a **function add-on** with a Function (Recruitment, HR, Finance, Sales, Development ...); each role's own permissions are edited from Manage Roles. Departments report their function, and the user form suggests the matching add-on for a new user. The dead `POST users-access-control/role-templates` (would crash: `is_active` is not a column) was removed. |
| Production deploys (2026-10-13) | Done | `83cf40ea` then `dc3b30e9` deployed by hand over SSH (git bundle + `deploy_backend.sh`, frontend build swap) since GitHub Actions can't run. DB backed up first (`/home/HRMS/backups/pre-deploy-20261013-191942.dump`, `.env` backups alongside). Prod `.env`: `UPLOAD_DIR=/home/HRMS/wros-uploads`, `SCHEDULED_JOBS_ENABLED=thunder_engagement_sweep`. |
| Thunder go-live | Done | Engagement conversations were created as owner 'Thunder', which every send gate refuses, so engagement failed and rolled back; now 'ai_agent' (1 prod conversation repaired). `thunder_engagement_sweep` (every 10 min) engages every contactable candidate from the last 30 days; first prod run engaged the one candidate never contacted. Kill switches: `THUNDER_ENGAGEMENT_ENABLED`, global queue pause. WhatsApp needs `THUNDER_WHATSAPP_NUMBER` (and Twilio) to add a WhatsApp first touch. |
| Candidate status emails | Done | Every pipeline-status change (all 6 writers, via one model hook after commit) emails the candidate an editable per-stage template; rejection included, reason never shown. The old handler compared 'INTERVIEW' with 'Interview' and never sent. |
| Tenants | Done | A tenant is a parent company; sub-companies are Companies inside it. Modules/resources are one shared catalog; permission rows read under the template's tenant (other tenants were locked out). |
| Expense receipts | Done | Receipt upload (image/PDF) read by Gemini and checked against amount (2%, min $1) and date (7 days): match -> manager step auto-approved; mismatch/unreadable -> manager with reasons; Finance still approves payment. |
| Pending jobs (decision 4) | Closed | No jobs exist in prod (0) and none are pending in dev; approval routing already goes BU head -> org-level approver. |
| **DNS (open, user)** | **Open** | `hrms.blitzenx.com` has no record in the Cloudflare zone (NXDOMAIN); the server itself is healthy. Add `A hrms 46.224.149.7`. |
| Deploy `430b672a` (2026-10-14) | Done | Functions replace departments (managed list, add/rename/retire; 8 seeded in prod); holding company = tenant BlitzenX (ID 1), companies numbered BX-US `1-1`, BX-IN `1-2`, all report to the holding; company P&L under the org P&L; tenant never assumed (primary tenant looked up, model/DB defaults removed, ~60 fallbacks + `TenantID` bugs fixed); edit-user fixes (Consultant position seeded, add-on editable); History filter from backend. DB backup `pre-deploy-20261014-001838.dump`. |
| P1-5 | Done | See above. |
| P2-6 | Closed (obsolete) | The Identity section no longer exists; government IDs are uploaded as documents in the candidate portal. |
| P2-7 | Done | History filter options come from the backend (adds Candidate Added). |
| **Company dimension across the system** | **Design, waiting on decisions** | `docs/COMPANY_MODEL_DESIGN.md`: jobs/offers/invoices/opportunities carry the company (derived), automatic intercompany charges; 4 decisions (markup, invoicing entity, BX-Canada/currency, per-company letterhead). |
| **Still open** | Open | P2-4 Flash intent classifier, P2-5 mailbox reader + panel-vs-Flash (501), P2-8 grantable resources without a page, P2-3 SQLite test suite; ops needing sudo (worker service, log rotation, monitoring, backup drill). **User actions:** DNS record in the right Cloudflare zone, shut SQL Server (public 1433, leaked password), revoke old Gemini/Azure secrets, WhatsApp/Twilio credentials, fill role permissions and add-on functions. |
| CI deploy gate | **207/207 pass** | Locally against `wros_test` (177 + 10 in `tests/test_access_model.py` + 7 in `tests/test_access_control_deletes.py`, both added to the gate lists). Was 163 pass / 14 fail on both `main` and the deployed commit. |
| Tests | **In progress (P2-3)** | Both conftests refuse any database not named `*_test` (they drop the schema) and pin the psycopg2 driver. 188 test files still build SQLite engines, which cannot hold `app_schema` models. |

### Built, not wired (agents to switch on, not delete)

These are implemented but nothing calls them. Most send email or WhatsApp to candidates, so they wait on the Azure app (decision 3) and the Thunder go-live decision (decision 2): interview reminder / confirmation / no-show / reschedule, reactivation campaign, mellow keep-warm, no-response detection, outreach agent and orchestrator, email-first engagement, onboarding agent, relation-building agent + tracker + dashboard, personal intelligence, drop-risk and abandonment scoring, KPI / HR / employee mental-health agents, supervisor agent, HTD pipeline accountability, partner success, opportunity tracker, Flash orchestration engine, career portal service (careers site out of scope), LinkedIn sourcing and recruiter workload, timesheet bulk/complete, invoice complete, pipeline leakage, resume search/compare/completeness/SLM parser, calendar matching, candidate scoring, sub-vendor service, Slack integration, ticket SLA, task escalation.

---

## P0 — `main` is broken / blocked (fix before the next deploy)

| # | Defect | Evidence (verified 2026-10-13) |
|---|---|---|
| P0-1 | **GitHub Actions is not running.** Every run since 2026-10-13 06:16 was not started: "recent account payments have failed or your spending limit needs to be increased". No gate, test or deploy has run on the 2026-10-13 commits, even though their messages claim "passed 52-criteria gate". | `gh run view 38356524187`, job annotation. **Business action:** fix GitHub billing. |
| P0-2 | **Opportunity stage transitions crash.** `transition_stage()` uses `CLOSED_STAGES`, `STAGE_TRANSITIONS` and `Project`, none of which are defined or imported. Every stage move, including "signed contract wins → project", raises `NameError`. | `backend/app/services/opportunity_service.py:147,160,194` (pyflakes). Last touched by `d9d194dd` / merge `3fee574f` (2026-10-13). |
| P0-3 | **BU Head dashboard crashes.** `companies_in_scope` is undefined. | `backend/app/api/v1/endpoints/bu_head_dashboard.py:55,87`. Merge `21239d1c` (2026-10-13). |
| P0-4 | **Cascade-prediction endpoints crash.** `CrossModuleIntelligence` was replaced by an empty `pass` stub (`b2c196c7`), but `cascade_prediction.py` (registered) calls `_infer_candidate_segment`, `_infer_job_segment` and `get_cascade_success_prediction`. | `backend/app/services/cross_module_intelligence.py`; `endpoints/cascade_prediction.py:118-122,197-200`. |
| P0-5 | **Thunder outreach preparation crashes.** `CandidateConversation` is not imported. | `backend/app/services/ai_conversation_service.py:159-160`. |
| P0-6 | **`webhooks` router is an empty stub.** It is registered with zero routes, so the SendGrid/Mailgun/Twilio outcome webhooks described in the learning-system docs do not exist. `learning_dashboard` / `learning_transcript` are disabled in `routes.py`. | `backend/app/api/v1/endpoints/webhooks.py` (3 lines); `routes.py`. The learning commits were reverted 2026-10-12 (`c65f56d4`), then partly re-added 2026-10-13. |

Recommendation: either fix P0-2..P0-6 forward or revert the 2026-10-13 commits `08f2c853..a91e408d`. Either way, run pyflakes and the API tests locally before pushing, because CI cannot run until P0-1 is fixed.

## P1 — Security / access control (verified against the live route table)

Route audit (all 603 registered routes, real FastAPI dependencies including router-level ones): **534 permission-gated, 43 login-only, 26 no auth dependency.** The 26 are public by design (login, signup, OAuth callback, WhatsApp webhook, public Thunder chat, health) or are covered by `AuthenticationMiddleware`.

| # | Defect | Evidence |
|---|---|---|
| P1-1 | **Any internal user can read and overwrite the tenant's provider API keys.** `GET/POST /api-keys` and `POST /api-keys/test` only require `get_current_internal_user`, with no permission check. | `backend/app/api/v1/endpoints/api_keys.py:54-137` |
| P1-2 | **Any internal user can create and activate message templates.** Only `GET /message-templates/keys` is gated. | `backend/app/api/v1/endpoints/message_templates.py:57-173` |
| P1-3 | **Job approval always 403s.** `POST /jobs/{id}/approve` requires `X-CSRF-Token`, but the frontend never sends one (zero hits in `frontend/src`). This also blocks the 4 jobs stuck in `pending_approval`. | `create_job.py:757-759` |
| P1-4 | Monitoring routes are mounted at `/api/v1/api/v1/monitoring/*` because the router prefix includes `/api/v1` again. They are login-only, with no permission check. | `endpoints/monitoring.py:15` |
| P1-5 | `tenant_id=1` literals remain in 27 places (db_contract seeding, `certifications_admin.py` ×3, others). Acceptable for single-tenant BlitzenX; blocks a second tenant. | `git grep "tenant_id\s*=\s*1"` |
| P1-6 | The old DB password (still the local-dev password) is in 25 tracked files, including `CLAUDE.md` and `LOCAL_DEVELOPMENT.md`, and in git history. It no longer opens prod. | `git grep -l P7kQmR9x` |
| P1-7 | Branch protection cannot be enabled: GitHub returns "Upgrade to GitHub Pro or make this repository public". The CLAUDE.md "force push blocked" rule is not enforceable today. | `gh api .../branches/main/protection` → 403 |

## P2 — Functional defects (verified)

| # | Defect | Evidence |
|---|---|---|
| P2-1 | Candidate rejections are never recorded. The handler writes `EventLog(entity_id, entity_type, data, created_at)`; the model has `candidate_id, payload, emitted_at`. | GH #382 · `candidate_rejection_handler.py:81-87` vs `models/event_log.py:31-37` |
| P2-2 | My Tasks navigates to `/interviews`, which has no frontend route. | `frontend/src/screens/MyTasksScreen.js:228,236` |
| P2-3 | Regression suite can never pass (23/23 error in setup). `sqlalchemy` is unpinned below 3.0, and 2.1 switches bare `postgresql://` to psycopg3, which is not installed. | GH #381 · `requirements.txt:15` |
| P2-4 | Flash chat is regex-only: 8 of 15 realistic messages get "I can't answer that". | GH #405 · `flash_service.py:258` |
| P2-5 | The service-mailbox inbox reader returns 501. Panel-vs-Flash interview comparison returns 501. | `ai_agent.py:894`; HANDOFF item 5 |
| P2-6 | Candidate Identity section (government ID) is not saved by `CandidateUpdateRequest`. Salary types are now saved. | `schemas/candidate.py` |
| P2-7 | History tab filter has no "Candidate Added" option. | HANDOFF "Seen, not fixed"; no match in `frontend/src` |
| P2-8 | Menu resources with no page (hidden from nav, still grantable): interviews, notifications, activity-feed, ask-flash, goals, onboarding, leave, performance, expenses, payroll, reports, analytics, webhooks, audit-logs and others. | HANDOFF item 0b |
| P2-9 | Dead services nobody imports: `kpi_agent_service.py`, `employee_mental_health_agent_service.py`. | 0 importers |
| P2-10 | Timesheet "lock after submit" is not enforced: a SUBMITTED timesheet can still be edited (S-221). | `timesheet_service.upsert_entries` |

## P3 — Operations / post-release requirements (still true per HANDOFF; no evidence of change)

- No `wros-queue-worker` systemd unit (cron watchdog only); the worker log is not rotated; `build-prev-*` directories accumulate (needs sudo, which the `HRMS` user doesn't have).
- No monitoring/alerting, APM or error tracking (Sentry/Prometheus). No documented, tested DB backup/restore. No WAF or admin IP allowlist.
- Rate limiting is in-memory, so it only works with a single worker.
- Load testing for 1500-HC scale was never executed.
- Frontend has no automated tests; there are no E2E browser tests.
- `backend/scripts/` still holds many one-off fixer/migration scripts. Triage them separately; `deploy_backend.sh` and `code_gate_validator.py` are required.

## Business decisions waiting on the CEO (from HANDOFF, still open)

1. **GitHub billing** (P0-1).
2. **Thunder go-live:** currently disabled; needs an engagement cutoff date and a kill switch.
3. **Azure app for email and Outlook capture:** prod `.env` Microsoft values are placeholders, so no email has ever been sent. Needs an Entra app with `Mail.Send` (+ `Mail.Read`, `offline_access`) and a real `helpdesk_hrms@` mailbox.
4. **4 jobs stuck in `pending_approval`:** activate or delete (approval is also blocked by P1-3).
5. **Rejection email UX:** now that rejected/archived/reactivated events fire.
6. ~~Role model~~ **Decided and built (2026-10-13):** Manage Role permission set ∪ function add-on ∪ overrides; day-1 access unchanged; recruiters/HR get a level + function add-on (an admin picks each person's role on the Users screen); authenticator enrolled at next login. Next for the CEO/admins: fill each role's permissions (Organizational Hierarchy → Manage Roles → Permissions), then trim the add-ons (Recruiter, HR Manager, Finance Manager, Manager, User, Ops each still grant almost everything).
7. **Tenants 2 and 3 are locked out (bug, needs a yes):** resources exist only for tenant 1, so every user in tenant 2 ("Test Organization") and 3 ("BlitzenX": am@, hr1/hr2, test@, recruiter1/2) is denied everything and can't log in. Fixing it gives them their templates' access at once (their Recruiter/Admin templates grant nearly everything). Recommended: confirm whether production has users outside tenant 1; if those tenants are real, fix with a cross-tenant smoke test; if they are test data, leave them locked.

---

## GitHub issues — validity against current code (346 open)

| Issues | Count | Verdict | Evidence |
|---|---|---|---|
| #85–#363 "Code quality issues in X.py" (auto scan, 2026-09-02) | 278 | **Not valid as tracked: close.** No line numbers or defect description, and 42 are duplicates. **72** files no longer exist; **24** files now scan clean; the other 182 are flagged only by heuristics (1,571× "external operation without error handling", 350× "assignment without validation"). Silent catches, the scan's headline item, are now **0**. The real permission gaps are captured precisely in P1-1..P1-4. | re-ran `backend/scripts/code_gate_validator.py` on every named file, 2026-10-13 |
| #59–#84 "endpoint not registered (orphaned)" | 26 | **Resolved: close.** Every file is now registered or deleted. | `app/api/v1/routes.py` |
| #23–#40 AGENT-001..018 | 18 | **Implemented: close.** Every service exists (134–529 lines, no stub markers). Two are unused (P2-9). | `app/services/*_service.py` |
| #45–#50 EPIC-FLASH-001..006 | 6 | Labeled `completed` but never closed: **close**. | labels |
| #41–#43 BX-HRMS-DEFECT-002/003/004 | 3 | Fixed 2026-08-22: **close.** | commits `6944467d`, `41e08e6f`, `efc09866` |
| #44 backend port mismatch | 1 | Obsolete: ports are now env-driven (`REACT_APP_API_URL`). **Close.** | `frontend/.env*` |
| #52, #58 careers portal | 2 | #58 duplicates #52. Careers site is out of production scope. **Close #58, park #52.** | user decision 2026-10-07 |
| #383 thunder_memory_update | 1 | Fixed in code: **close.** | `candidate_note_added_handler.py:75` |
| #373 db.commit error handling | 1 | Vague (now 815 commits). **Close; replace** with targeted items as found. | |
| #19 REFACTOR-004 employee roles | 1 | Superseded by "roles as data" (#403, `0bcb2d6e`). **Verify, then close.** | |
| #53 Thunder Phase 3B | 1 | Phase 3B code was deleted. **Replace** with the Thunder go-live decision. | `thunder_autonomous_progression_service.py` gone |
| #55 resume upload | 1 | `POST /documents/upload/resume` exists. **Verify the UI, then close.** | route table |
| **Still valid: keep** | 7 | #381, #382, #405, #375 (test DB role), #51 HM screening, #54 interview regrouping, #56 candidate portal, #57 YoY goals | above |

**Net: about 335 of the 346 open issues can be closed or replaced. Roughly 11 remain real, plus the new verified items P0-2..P2-10 above, which have no issue yet.**
