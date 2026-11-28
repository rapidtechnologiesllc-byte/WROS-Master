# WROS — Open Defects & Requirements (single source of truth)

**Built:** 2026-10-13 by validating ~430 unique documents and the 346 open GitHub issues against `main` (`a91e408d`).
**Rule:** an item is listed only if it was checked against the current code. Status documents that only made claims were archived (see `archive/README.md`).
**Production:** `hrms.blitzenx.com` runs `main` @ `8d401ef9` (PR #434), deployed 2026-10-29 by GitHub Actions (`test-and-deploy.yml`: backend tests, frontend build, SSH deploy with health check and auto-rollback; `deploy.yml` for the frontend). Every merge to `main` deploys; manual SSH deploys are no longer needed.
**Re-verified:** 2026-10-30 against `main` @ `8d401ef9` and the Production Status workflow (run 41074196166).

Other live documents: `HANDOFF.md` (deploy procedure, prod state) · `docs/OPEN_REQUIREMENTS_BACKLOG.md` (246 open backlog stories) · `CLAUDE.md` (rules) · `LOCAL_DEVELOPMENT.md`, `DEVELOPER_ONBOARDING.md` (setup).

## End-to-end check, 2026-11-09 (`main` @ `05d696e2`)

Method: pyflakes over `backend/app`; the whole backend suite; the live route table (666 paths) against every API call in `frontend/src` (526), both directions; every catalogue resource against its page, API gate and frontend use; a keyword probe of the code for each open backlog story (story ids are no longer in the code, so the "Signal today" column of `docs/OPEN_REQUIREMENTS_BACKLOG.md` is out of date).

Found sound: 0 undefined names; 1816 tests pass; no screen calls a route that does not exist; every resource with a menu route has a page.

Built in this pass:

| Item | What |
|---|---|
| Bank reconciliation (S-391) | The API existed with no screen. Now: P&L > Bank Reconciliation. Upload the statement as CSV (each credit recorded once; debits left out; unreadable lines listed with the reason), or type one credit. Each unmatched credit shows the sent invoices for exactly that amount and one suggested (the only one, or the one whose number is in the bank description). Finance confirms; nothing is paid by itself. Paid invoices with no bank credit are listed. `tests/test_bank_reconciliation.py` |
| Hiring analytics (S-333, S-330, S-327) | Recruitment Dashboard > Hiring Analytics: source of hire, each recruiter's results, and open positions against people who joined, read from the hiring pipeline's stages and history, in the reader's tenant and business-unit scope. `GET /analytics/hiring`. `tests/test_hiring_analytics.py` |

Built APIs that still have no screen (decide: build the screen or remove the API): ATS scores (`/ats/*`), learning dashboards (`/learning/dashboard`, `/recommendations`, `/cross-module`, analytics), cascade predictions, Spartan forecasting summary, `/agents/cfo/cost-breakdown`, `/jobs/my-jobs`, `/org/positions`, `/invoices/{id}/mark-paid` (replaced by record-payment), `/core-certification/eligibility/{id}`.

Backlog epics with no code today (each is a product build, not a gap in an existing module): client portal (26 stories), boolean and saved search (14), sub-vendor portal login (vendors are served by email today), ad hoc staffing demand (8), demand plan from revenue targets and scenario planning, LinkedIn crawl and InMail (9), voice calling, job boards, Greenhouse/Lever import, payroll sync, ERP export, outbound webhook engine, GST, panel-split and experience-override workflows, nurture campaigns and relationship score, new-hire onboarding content steps (induction, policies, NDA, benefits, equipment), Teams chat dock, load testing.

Left as they are because they wait on a decision or on production access: the 31 unused service files and unused jobs, the unscheduled daily digest, stale hand-off tasks in production (Thunder now acts on new replies itself; the old tasks are production data), staff notification emails are composed in code and are not in the template catalogue.

## Open now (verified 2026-10-30)

Everything in the P0/P1/P2 tables further down is fixed on `main` (details in the progress log). What is still open:

### Production configuration (owner: CEO / server access; code cannot do these)

| Item | State | Action |
|---|---|---|
| Background jobs off | `SCHEDULED_JOBS_ENABLED=thunder_engagement_sweep` only; timesheet drafts/reminders, AR follow-up, auto-invoicing, client start date and the other internal jobs last ran 2026-10-13 | Set in `/home/HRMS/WROS-Master/backend/.env`: `SCHEDULED_JOBS_ENABLED=thunder_engagement_sweep,timesheet_draft_creation,timesheet_reminders,ar_follow_up,auto_invoicing,client_start_date,daily_revenue_scan,hiring_pipeline_sweep,engagement_metrics,expire_bu_ownerships,birthday_drafts,core_certification_sweep,interview_reminders,utilization_snapshot,renewal_alerts,po_expiry_alerts,performance_reviews` (every registered job except `flash_mission_sweep`, which waits on the model keys; names in `backend/app/core/scheduled_jobs.py`) |
| `FRONTEND_BASE_URL` not set | Candidate portal links in Thunder emails and WhatsApp point at `http://localhost:3000` | Set `FRONTEND_BASE_URL=https://hrms.blitzenx.com` in `backend/.env` |
| SQL Server 1433 | Public port with a leaked password; reported stopped 2026-10-19 but a probe the same day still got a reply | Verify closed; change the password |
| Old secrets | Old Gemini/Azure secrets not revoked | Revoke |
| Cost rates | 0 cost-rate configs, so bench loss and P&L cost read $0 | Set BU × country cost rates |
| Org chart | 2 of 4 users seated; the manager is read from the org chart (#413), so imports refuse anyone whose manager has no seat | Seat managers under Organizational Hierarchy, then import employees |
| Role permission sets | Every "(role)" set except Partner grants 0 of 114 resources (created empty by design) | Grant access per role (Manage Roles → Permissions) |
| Branch protection | Off (no GitHub Pro, decision 2026-10-19) | Process only: run the local gate before every merge |
| Production data | 0 employees, projects, timesheets, invoices | Import staff (dry run first, 5 people) |

### Thunder engagement failures (resolved 2026-10-30)

- 4 `engage_candidate_with_thunder` messages FAILED between 2026-10-16 and 2026-10-30. Two (last 2026-10-24 17:10) were the aborted-transaction bug fixed by `868787b2` (#432). Two (last 2026-10-25) were WhatsApp sends attempted for a tenant with no WhatsApp provider: the engagement was retried and marked FAILED although its email cadence had started. Fixed: WhatsApp is now added only when the tenant has an active, tested Twilio provider (`delivery_factory.whatsapp_delivery_ready`); otherwise the candidate is engaged by email only.

### Decisions waiting on the CEO

1. Org reporting rule: a manager may sit only 1–2 levels above the report (Consultant 4 cannot report to Manager 8). Keep or relax?
2. Margin floor values per delivery engine and country, and who approves below them (the policy table ships empty, #417).
3. Imported employees: create a client-submittable profile automatically? (recommended yes)
4. P&L: split "bench (unallocated)" from "idle on a project"? (recommended yes)
5. Activation emails on import: batch by business unit?
6. Fixed-price / retainer billing and PM / Program Manager / Delivery Head roles: deferred until Core's share of revenue is known (the staff-aug side was built in #414, #417, #419, #422).
7. Company model Part 2: the 4 decisions in `docs/COMPANY_MODEL_DESIGN.md`.
8. Tenants 2 and 3 (decision 7 below).
9. `kpi_agent_service.py` and `employee_mental_health_agent_service.py` have no callers: switch on or delete.

### GitHub issues

347 open on 2026-10-30. About 335 should be closed (table at the end, re-verified 2026-10-30: all 26 "orphaned endpoint" files are now registered or deleted; #381, #382, #383, #375 and #406 are fixed). Closing needs the repo owner (the bulk close was not done from the agent session). Keep open: #405, #57, #56, #55, #54, #52, #51, #19.

## Progress log (2026-10-13 to 2026-10-20)

Verification method for every fix: pyflakes over `backend/app` (0 undefined names, 0 syntax errors), the live route table (all registered routes and their real dependencies), a GET sweep of every parameterless route through the real app and middleware as a super user, and targeted checks that run real code against `wros_dev` inside one transaction that is always rolled back.

| Item | Status | What changed |
|---|---|---|
| P0-1 | Closed (decision) | CEO, 2026-10-19: no GitHub budget; deploys stay manual over SSH. The gate is run locally before each deploy (whole backend suite + frontend build). Procedure: `HANDOFF.md` → Deploying. |
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
| P1-7 | Closed (decision) | No GitHub Pro (2026-10-19), so branch protection stays off; force-push/bypass rules are enforced by process (local gate before every deploy), not by GitHub. |
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
| Deploy `cc13565f` (2026-10-14) | Done | Everything below, deployed over SSH. DB backup `pre-deploy-20261014-053825.dump`. Prod startup: 24 catalog entries aligned to the contract, both partial indexes rebuilt, 2 conversations + 1 metrics row re-keyed to the candidate's tenant, all systems ready, health 200. Frontend unchanged since `430b672a`. |
| P2-4 Flash | Done | More realistic phrasings route (finance, tasks, bench incl. "anyone free who knows X", status, sourcing, requisitions, all-caps names); new pipeline summary (stage counts, BU-scoped, optionally per client). `tests/test_flash_intents.py`. |
| P2-5 Panel vs Flash | Done | `GET /interviews/flash-calibration` (agreement rate, every disagreement) and `/interviews/{id}/flash-comparison`; threshold `FLASH_ADVANCE_SCORE` (60). The dead mailbox stub is gone (mail is read by the Thunder poll). |
| P2-8 | Done | 15 resources no page or check used left the API contract; startup disables (reversible) anything not in the contract. |
| P2-3 SQLite | Done | Everything driven by SQLite deleted: 160 backend test files, their archived copies, SQLite migration scripts, the deprecated loader, SQLite branches/kwargs in app code. The remaining legacy tests were fixed against the real code or deleted when they tested code that no longer exists. **Whole backend suite: 552 pass, 0 fail; the deploy gate is now the whole suite (`tests/DEPLOY_GATE` = `tests/`).** Shared factories: `tests/factories.py`. |
| Found while fixing tests (all fixed, with tests) | Done | **Candidate conversation service had been reduced to stubs (2026-09-03 auto-fix):** portal profile saves were dropped while reporting success, nothing was ever "missing", "Check replies" did nothing -- restored against today's models (`ai_conversation_service`). **Thunder kill switch** saved on the clicking admin's user row while the pause check read another user's: now one tenant setting, honoured by the Thunder email send (deferred, not dropped). **Engagement records** were keyed by arbitrary user ids (even a candidate id) while readers looked for the tenant: keyed by tenant everywhere, existing rows re-keyed at startup (dev: 10 conversations, 1 signal, 2 events). **Token expiry** was computed from naive UTC as local time: on a server west of UTC an expired token stayed valid for hours. **Allocation end** never benched the employee (unflushed query saw itself). **Thunder learning**: every engagement outcome failed to record (formatting None) and none was linked to its prediction; segments were always "unknown". **Two unique indexes** were full instead of partial in Postgres (blocked a second interview after supersede, re-opening a resolved intervention). **HM decision** "approve"/"reject" recorded as MAYBE. **Referral visibility** crossed tenants; recording a referral without job settings was never saved. **WhatsApp/SMS/Slack queue** reported mock sends as delivered; the queue's email path used Graph `/me` (never works with an app token). **Queue idempotency key** was stored but never checked (a double-submitted candidate queued twice). Also: 26 generic `"Operation failed"` raises replaced (3 broke documented never-raise contracts, incl. facts extraction which blocked every inbound reply without the LLM); raw `print()` removed (one logged the JWT secret length); dead modules removed (onboarding workflow, old candidate creation handler, shadowed activity logger). |
| Referral capture (2026-10-19) | Done | Nothing ever wrote a referral, so My Referrals was always empty. Add Candidate with source "Employee Referral" now requires **Referred By** (current employees of the tenant, `GET /referrals/referrers`); "Refer a Candidate" opens it with you preselected. The creation handler saves the referral and links the candidate in the same transaction (job optional, so `employee_referrals.job_id` is now nullable); the referral follows the candidate's pipeline (Offer, Hired -> one pending bonus for Finance, Rejected; a paid bonus is final). Also fixed: the source dropdown's options had no values (mapped `.value` over plain strings); My Referrals read field names the API never sent (it would have crashed on the first referral) and showed bonuses /100; the referral history entry used an Employee id as the acting user (FK violation that rolled back the whole candidate creation). Default bonus is `REFERRAL_BONUS_DEFAULT_USD_CENTS` (50000). `tests/test_referral_capture.py`. |
| Referral of an existing candidate (2026-10-20) | Done | CEO rule: someone already in the system can be referred only when dormant -- no activity (created, History entry, pipeline change) for `REFERRAL_DORMANT_DAYS` (60). An active one, one inside the 90-day post-rejection no-contact period, or one already hired through a referral is refused at submit with a warning (409, nothing queued); a dormant one is credited to the new referrer and an earlier unfinished referral becomes SUPERSEDED. Re-checked in the creation handler. |
| Archive candidate (2026-10-20) | Done | Archive set `candidate_status.status = Inactive` and nothing read it: the candidate stayed in the list and Thunder kept contacting them. Now archived candidates are hidden from the candidate list (toggle "Show archived", Archived tag), get no outreach (`is_contactable`), and Archive/Unarchive go on History; the row menu can unarchive. Also fixed: the main table ignored the list filter, the row handlers matched on the wrong id, errors were swallowed, and "Message on WhatsApp" crashed (read a field the menu never got). `tests/test_candidate_archive.py`. |
| Call transcripts / SLM learning | **Open** | Transcripts come only from Teams via Graph (needs the Azure app, decision 3), are analysed on demand and never stored; there is no upload path. Nothing writes `learning_transcript`, so the SLM Learning screens stay empty. Needs a build: upload + Teams fetch, store, analyse, write learning. |
| **Still open** | Open | **Product work:** automatic reply poll for the profile-completion email is not scheduled ("Check replies" works; enabling a candidate-facing job is a product call). Ops needing sudo (worker service, log rotation, monitoring, backup drill). **User actions:** shut SQL Server (public 1433, leaked password; CloudMinister reported it stopped on 2026-10-19, but a TDS pre-login probe to `46.224.149.7:1433` the same day still got a SQL Server reply, version 17.0.1000: **not yet verified closed**), revoke old Gemini/Azure secrets (reply reading and facts extraction need a working `GEMINI_API_KEY`), WhatsApp/Twilio credentials, fill role permissions and add-on functions. Company Part 2 waits on the 4 decisions in `docs/COMPANY_MODEL_DESIGN.md`. |

### Built, not wired (agents to switch on, not delete)

These are implemented but nothing calls them. Most send email or WhatsApp to candidates, so they wait on the Azure app (decision 3) and the Thunder go-live decision (decision 2): interview reminder / confirmation / no-show / reschedule, reactivation campaign, mellow keep-warm, no-response detection, outreach agent and orchestrator, email-first engagement, onboarding agent, relation-building agent + tracker + dashboard, personal intelligence, drop-risk and abandonment scoring, KPI / HR / employee mental-health agents, supervisor agent, HTD pipeline accountability, partner success, opportunity tracker, Flash orchestration engine, career portal service (careers site out of scope), LinkedIn sourcing and recruiter workload, timesheet bulk/complete, invoice complete, pipeline leakage, resume search/compare/completeness/SLM parser, calendar matching, candidate scoring, sub-vendor service, Slack integration, ticket SLA, task escalation.

---

## P0 — `main` is broken / blocked (as found 2026-10-13; all resolved, see the progress log)

| # | Defect | Evidence (verified 2026-10-13) |
|---|---|---|
| P0-1 | **GitHub Actions is not running.** Every run since 2026-10-13 06:16 was not started: "recent account payments have failed or your spending limit needs to be increased". No gate, test or deploy has run on the 2026-10-13 commits, even though their messages claim "passed 52-criteria gate". | `gh run view 38356524187`, job annotation. **Business action:** fix GitHub billing. |
| P0-2 | **Opportunity stage transitions crash.** `transition_stage()` uses `CLOSED_STAGES`, `STAGE_TRANSITIONS` and `Project`, none of which are defined or imported. Every stage move, including "signed contract wins → project", raises `NameError`. | `backend/app/services/opportunity_service.py:147,160,194` (pyflakes). Last touched by `d9d194dd` / merge `3fee574f` (2026-10-13). |
| P0-3 | **BU Head dashboard crashes.** `companies_in_scope` is undefined. | `backend/app/api/v1/endpoints/bu_head_dashboard.py:55,87`. Merge `21239d1c` (2026-10-13). |
| P0-4 | **Cascade-prediction endpoints crash.** `CrossModuleIntelligence` was replaced by an empty `pass` stub (`b2c196c7`), but `cascade_prediction.py` (registered) calls `_infer_candidate_segment`, `_infer_job_segment` and `get_cascade_success_prediction`. | `backend/app/services/cross_module_intelligence.py`; `endpoints/cascade_prediction.py:118-122,197-200`. |
| P0-5 | **Thunder outreach preparation crashes.** `CandidateConversation` is not imported. | `backend/app/services/ai_conversation_service.py:159-160`. |
| P0-6 | **`webhooks` router is an empty stub.** It is registered with zero routes, so the SendGrid/Mailgun/Twilio outcome webhooks described in the learning-system docs do not exist. `learning_dashboard` / `learning_transcript` are disabled in `routes.py`. | `backend/app/api/v1/endpoints/webhooks.py` (3 lines); `routes.py`. The learning commits were reverted 2026-10-12 (`c65f56d4`), then partly re-added 2026-10-13. |

Recommendation: either fix P0-2..P0-6 forward or revert the 2026-10-13 commits `08f2c853..a91e408d`. Either way, run pyflakes and the API tests locally before pushing, because CI cannot run until P0-1 is fixed.

## P1 — Security / access control (as found 2026-10-13; P1-1..P1-6 resolved, P1-7 closed by decision)

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

## P2 — Functional defects (as found 2026-10-13; all resolved or obsolete, see the progress log)

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

1. ~~GitHub billing~~ **Decided (2026-10-19):** no GitHub spend; manual deploys only (P0-1, P1-7).
2. **Thunder go-live:** currently disabled; needs an engagement cutoff date and a kill switch.
3. **Azure app for email and Outlook capture:** prod `.env` Microsoft values are placeholders, so no email has ever been sent. Needs an Entra app with `Mail.Send` (+ `Mail.Read`, `offline_access`) and a real `helpdesk_hrms@` mailbox.
4. **4 jobs stuck in `pending_approval`:** activate or delete (approval is also blocked by P1-3).
5. **Rejection email UX:** now that rejected/archived/reactivated events fire.
6. ~~Role model~~ **Decided and built (2026-10-13):** Manage Role permission set ∪ function add-on ∪ overrides; day-1 access unchanged; recruiters/HR get a level + function add-on (an admin picks each person's role on the Users screen); authenticator enrolled at next login. Next for the CEO/admins: fill each role's permissions (Organizational Hierarchy → Manage Roles → Permissions), then trim the add-ons (Recruiter, HR Manager, Finance Manager, Manager, User, Ops each still grant almost everything).
7. **Tenants 2 and 3 are locked out (bug, needs a yes):** resources exist only for tenant 1, so every user in tenant 2 ("Test Organization") and 3 ("BlitzenX": am@, hr1/hr2, test@, recruiter1/2) is denied everything and can't log in. Fixing it gives them their templates' access at once (their Recruiter/Admin templates grant nearly everything). Recommended: confirm whether production has users outside tenant 1; if those tenants are real, fix with a cross-tenant smoke test; if they are test data, leave them locked.

---

## GitHub issues — validity against current code (346 open on 2026-10-13; 347 on 2026-10-30)

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

---

## Master backlog (compiled 2026-11-28)

Compiled from every open item recorded under C:\dev: this file, `docs/OPEN_REQUIREMENTS_BACKLOG.md` (246 stories), the design docs (`docs/RECRUITMENT_VS_WORKFORCE_DESIGN.md`, `docs/CLIENT_CONTACT_CONFIDENTIALITY_DESIGN.md`, `docs/COMPANY_MODEL_DESIGN.md`, `docs/ACTION_EMAIL_MATRIX.md`, `docs/ACCESS_MODEL_IMPACT.md`), `HANDOFF.md`, `backend/app/DEFECTS_LOG.md`, `C:\dev\defect_log.md`, the CLAUDE.md files, code markers (TODO / not built / stub / NotImplementedError) in `backend/app` and `frontend/src`, the session memory notes, and the 348 open GitHub issues. `archive/` (and its copy in `C:\dev\WROS-deploy`) is historical by its own README and was not re-mined; pre-consolidation repos (`OnboardingModule-*`) and the August root docs at `C:\dev` were scanned, and items fixed since were skipped.

Priority: **P0** blocks or endangers production now · **P1** high impact, do next · **P2** real gap · **P3** improvement, clean-up or close. **CEO** = needs a business decision rather than a technical fix. **verify** = a document says open but the code suggests it is built or changed.
Story lines (S-nnn) keep the 2026-08-22 verification status; titles start with Build (not done) or Finish (partial).

| Area | P0 | P1 | P2 | P3 | Total | CEO |
|---|---|---|---|---|---|---|
| Recruitment | 0 | 5 | 57 | 44 | 106 | 38 |
| Workforce | 0 | 1 | 48 | 23 | 72 | 33 |
| Sales | 0 | 0 | 1 | 46 | 47 | 43 |
| Finance | 0 | 11 | 13 | 6 | 30 | 13 |
| Leadership | 0 | 0 | 6 | 10 | 16 | 3 |
| Admin/System | 0 | 2 | 4 | 12 | 18 | 5 |
| Platform/Infra | 0 | 4 | 9 | 44 | 57 | 8 |
| Security/Compliance | 1 | 7 | 11 | 1 | 20 | 4 |
| AI agents (Flash/Thunder) | 0 | 0 | 7 | 66 | 73 | 30 |
| Data/Migration | 0 | 4 | 4 | 4 | 12 | 5 |
| Frontend/UX | 0 | 1 | 2 | 8 | 11 | 0 |
| Testing/Quality | 0 | 1 | 3 | 238 | 242 | 0 |
| Docs | 0 | 0 | 3 | 4 | 7 | 0 |
| **Total** | 1 | 36 | 168 | 506 | 711 | 182 |

### Recruitment (106)

- **P1** Finish: Experience Eligibility Engine — <5yr hard rule, flag INELIGIBLE, block from interview (S-107/HRMS-P601, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:301 — note -- 5-year floor is enforced on submissions; check every interview entry point, pipeline and offer
- **P1** Recruitment vs Workforce PR 2: link tables, requisition status path (DRAFT->APPROVED->OPEN->FILLED|CANCELLED), sourcing gate (Thunder, sub-vendors, Flash only on OPEN requisitions), Flash/Thunder split — docs/RECRUITMENT_VS_WORKFORCE_DESIGN.md:246; rapidtechnologiesllc-byte/WROS-Master#588 — CEO approved 2026-11-27 (D1-D8)
- **P1** Recruitment vs Workforce PR 4 screens: Workforce -> Client open roles, Submissions move, Recruitment requisitions, candidate page, opportunity role flow — docs/RECRUITMENT_VS_WORKFORCE_DESIGN.md:231-248
- **P1** Client submissions: recheck the Submissions screen and profile 'Submit Job', and build the CEO direct-submission gates (bench = buddy graduated and unallocated, Core certified for CORE, 5-year/W2/min experience, no open escalation, button by bench state) — rapidtechnologiesllc-byte/WROS-Master#406; auto-memory `next_session_autonomy_backlog.md` (2026-11-05)
- **P1** Concurrency: lost updates when two users edit the same candidate; duplicate-email create race; handler idempotency; message ordering — auto-memory `critical_finding_concurrent_race_conditions.md` (2026-09-20) — verify: idempotency key fixed 2026-10-14; the edit race may remain
- **P2** Finish: Unified Conversation Timeline UI (S-005/HRMS-0405, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:71 — verify: code touched after 2026-08-22
- **P2** Finish: Interview Availability Collection (S-047/HRMS-0447, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:74 — verify: code touched after 2026-08-22
- **P2** Build: Auto Create Job from Workforce Demand (S-289/HRMS-0701, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:133 — see design -- covered by docs/RECRUITMENT_VS_WORKFORCE_DESIGN.md (requisition from demand)
- **P2** Finish: View Job Requisition List & Status (S-290/HRMS-0702, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:134 — see design -- requisition list is delivery PR 4 of docs/RECRUITMENT_VS_WORKFORCE_DESIGN.md
- **P2** Finish: Trigger LinkedIn Sourcing Agent (S-292/HRMS-0704, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:135
- **P2** Finish: External Candidate Import & Deduplication (S-293/HRMS-0705, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:136
- **P2** Finish: Interview Panel Assignment & Calendar Sync (S-294/HRMS-0706, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:137 — verify: code touched after 2026-08-22
- **P2** Finish: Universal Candidate Identity Engine (dedup, merge, log) (S-081/HRMS-P101, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:230 — verify: possibly done -- candidate merge built 2026-11-09 (fbd74e35)
- **P2** Build: LinkedIn Entry — Skeleton Profile Creation (S-082/HRMS-P102, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:231
- **P2** Finish: Cross-Channel Conversation Merge (S-083/HRMS-P103, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:232
- **P2** Finish: Session Resume across channels (S-084/HRMS-P104, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:233
- **P2** Finish: Candidate Portal — Home Dashboard (S-085/HRMS-P105, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:234 — note -- candidate portal exists; re-check against story
- **P2** Finish: Candidate Portal — Message Thread View (S-086/HRMS-P106, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:235
- **P2** Finish: Candidate Portal — Profile Completion Wizard (S-087/HRMS-P107, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:236
- **P2** Finish: Candidate Portal — Interview Tracker (S-088/HRMS-P108, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:237
- **P2** Build: Candidate Portal — Offer Viewer (S-089/HRMS-P109, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:238
- **P2** Build: Candidate Portal — Document Upload (S-090/HRMS-P110, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:239 — verify: possibly done -- government IDs are uploaded as documents in the candidate portal (OPEN_ITEMS P2-6)
- **P2** Finish: Magic Link Authentication (S-091/HRMS-P111, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:240 — verify: code touched after 2026-08-22
- **P2** Build: Candidate Source Attribution Tracking (S-093/HRMS-P113, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:242
- **P2** Finish: WhatsApp Deep Link to Portal (S-094/HRMS-P114, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:243
- **P2** Finish: Admin Portal — Recruiting Dashboard (S-096/HRMS-P201, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:249
- **P2** Finish: Technical Portal — Interview Queue (S-100/HRMS-P205, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:253
- **P2** Finish: Technical Portal — Hiring Manager Decision View (S-102/HRMS-P207, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:254 — verify: code touched after 2026-08-22
- **P2** Build: Ineligibility auto-message (AI acknowledges, explains 5yr min, encourages reapply) (S-109/HRMS-P603, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:302
- **P2** Build: Experience override workflow (Director→BU Head sequential, both must approve, immutable audit log) (S-110/HRMS-P604, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:303 — **needs CEO decision** — verify: code touched after 2026-08-22
- **P2** Build: Override escalation notifications (WhatsApp+Email+portal, 24h SLA, auto-escalate) (S-111/HRMS-P605, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:304 — verify: code touched after 2026-08-22
- **P2** Finish: Two-level interview config (L1 Tech Lead / L2 Tech Manager per job track, 1-2 panelists/level) (S-112/HRMS-P606, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:305 — verify: code touched after 2026-08-22
- **P2** Build: Panel split decision engine (2 panelists conflict → flag PANEL_SPLIT → HM final call) (S-113/HRMS-P607, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:306 — **needs CEO decision** — verify: code touched after 2026-08-22
- **P2** Build: L1 pass + L2 fail → auto-reject (BU Head-only reversal) (S-114/HRMS-P608, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:307 — **needs CEO decision** — verify: code touched after 2026-08-22
- **P2** Finish: HM final hire decision UI (summary+feedback+AI rec+salary vs budget, Approve/Reject/Hold, Approve disabled until feedback viewed) (S-115/HRMS-P609, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:308
- **P2** Finish: Sub-Vendor Account Creation & Mgmt (S-137/HRMS-P801, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:348 — verify: code touched after 2026-08-22
- **P2** Finish: Recruiter — Send Request to Sub-Vendor (S-139/HRMS-P803, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:350 — verify: possibly done -- `sub_vendor_new_roles` job emails new client roles to approved vendors
- **P2** Finish: Sub-Vendor — View Open Requests (S-140/HRMS-P804, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:351 — verify: code touched after 2026-08-22
- **P2** Finish: Sub-Vendor — Submit Candidate Profile (S-141/HRMS-P805, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:352
- **P2** Finish: Recruiter — Sub-Vendor Submission Review (S-144/HRMS-P808, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:353 — verify: code touched after 2026-08-22
- **P2** Finish: Sub-Vendor Submission Status — Vendor View (S-146/HRMS-P810, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:354
- **P2** Finish: Sub-Vendor Governance Agent (merged) (S-147/HRMS-P811, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:355 — verify: code touched after 2026-08-22
- **P2** Finish: Sub-Vendor Scorecard & Analytics Dashboard (S-148/HRMS-P812, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:356
- **P2** Finish: Sub-Vendor — Request for Clarification (S-150/HRMS-P814, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:357 — verify: code touched after 2026-08-22
- **P2** Build: Auto-Generate Boolean Search per Job (S-155/HRMS-P901, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:363
- **P2** Finish: Skill Synonym Library (S-156/HRMS-P902, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:364 — verify: possibly done -- team synonyms built 2026-11-16 (acf25efd)
- **P2** Build: Boolean Search — Internal DB Search (S-157/HRMS-P903, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:365 — verify: possibly done -- boolean search for jobs and candidates built 2026-11-16 (acf25efd)
- **P2** Build: Recruiter Boolean Search Editor (S-160/HRMS-P906, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:368 — verify: possibly done -- boolean search built 2026-11-16 (acf25efd)
- **P2** Build: Boolean Search Results Dashboard (S-161/HRMS-P907, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:369
- **P2** Build: Work Authorization Filter in Search (S-164/HRMS-P910, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:372
- **P2** Build: Search History & Saved Searches (S-165/HRMS-P911, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:373 — verify: possibly done -- saved searches built 2026-11-16 (acf25efd)
- **P2** Flash chat beyond regex (realistic phrasings, opportunity/staffing decisions) — rapidtechnologiesllc-byte/WROS-Master#405; auto-memory `next_session_autonomy_backlog.md` (2026-11-05) — verify: P2-4 widened routing 2026-10-14
- **P2** Hiring manager validation questions (HM screening): HM email, interview scheduling, Thunder 'try next candidate', escalation and email TODOs — rapidtechnologiesllc-byte/WROS-Master#51; backend/app/services/hiring_manager_validation_service.py:204,433,471,508,552
- **P2** Interview regrouping by job and round with rehire guard — rapidtechnologiesllc-byte/WROS-Master#54 — verify: rehire guard service exists
- **P2** Resume upload UI — rapidtechnologiesllc-byte/WROS-Master#55 — verify: `POST /documents/upload/resume` exists; then close
- **P2** Call transcripts: upload path plus Teams fetch, store, analyse and write learning (SLM Learning screens stay empty) — OPEN_ITEMS.md:122 — **needs CEO decision**
- **P2** Schedule the automatic reply poll for the profile-completion email (candidate-facing job, product call) — OPEN_ITEMS.md:123 — **needs CEO decision**
- **P2** Enable or keep off the candidate rejection email (`REJECTION_EMAIL_ENABLED`) — OPEN_ITEMS.md:91, OPEN_ITEMS.md:188 — **needs CEO decision**
- **P2** Decide whether to ask candidates' current salary — auto-memory `next_session_autonomy_backlog.md` (2026-11-05) — **needs CEO decision**
- **P2** Decide auto-recording of interviews — auto-memory `next_session_autonomy_backlog.md` (2026-11-05) — **needs CEO decision**
- **P2** Confirm the hiring manager and expand the job description on one open job; confirm one candidate's interview outcome — auto-memory `next_session_autonomy_backlog.md` (2026-11-05) — **needs CEO decision** — names in the session notes
- **P2** Confirm new client roles go to every approved sub-vendor (`sub_vendor_new_roles`), a default not stated by the CEO — auto-memory `candidate_merge_and_vendor_roles.md` — **needs CEO decision**
- **P3** Build: Interviewer Quality Scoring — Client Pass Rate (S-377/HRMS-0533, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:33
- **P3** Build: Recruiter Productivity Dashboard (S-330/HRMS-1205, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:170 — verify: possibly done -- Hiring Analytics (recruiter results) built 2026-11-09
- **P3** Build: Source of Hire Analytics (S-333/HRMS-1208, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:173 — verify: possibly done -- Hiring Analytics (source of hire) built 2026-11-09
- **P3** Build: Post Jobs to Free Job Boards (S-338/HRMS-1303, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:176 — **needs CEO decision**
- **P3** Build: Interview Integrity Analysis Engine — analyze consented recording/transcript for rehearsed-answer, outside-assistance, identity-mismatch signals (S-385/HRMS-1501, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:200 — **needs CEO decision** — verify: code touched after 2026-08-22
- **P3** Build: Panel Feedback Cross-Validation & Clarification Routing (S-386/HRMS-1502, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:201 — **needs CEO decision**
- **P3** Build: Duplicate Detection Audit Dashboard (S-092/HRMS-P112, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:241
- **P3** Build: Career Goal Conversation Engine (S-119/HRMS-P301, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:263 — **needs CEO decision**
- **P3** Finish: Personalized Value Messaging Engine (S-120/HRMS-P302, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:264 — **needs CEO decision**
- **P3** Build: Candidate Relationship Score (CRS) (S-121/HRMS-P303, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:265 — **needs CEO decision**
- **P3** Build: Passive Candidate Nurture Campaign (S-122/HRMS-P304, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:266 — **needs CEO decision**
- **P3** Build: Candidate Interest Signal Detection (S-123/HRMS-P305, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:267 — **needs CEO decision**
- **P3** Build: Nurture Campaign Scheduler & Config UI (S-124/HRMS-P306, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:268 — **needs CEO decision** — verify: code touched after 2026-08-22
- **P3** Build: Nurture Campaign Analytics (S-125/HRMS-P307, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:269 — **needs CEO decision**
- **P3** Build: Candidate Re-Engagement on Market Signal (S-126/HRMS-P308, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:270 — **needs CEO decision**
- **P3** Build: Nightly keyword LinkedIn crawl (Playwright) (S-128/HRMS-P401, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:277 — **needs CEO decision**
- **P3** Build: Profile dedup & skeleton creation (S-129/HRMS-P402, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:278 — **needs CEO decision**
- **P3** Build: LinkedIn InMail AI outreach (S-130/HRMS-P403, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:279 — **needs CEO decision**
- **P3** Build: Human recruiter contact queue (S-131/HRMS-P404, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:280 — **needs CEO decision**
- **P3** Build: Profile enrichment pipeline (S-132/HRMS-P405, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:281 — **needs CEO decision**
- **P3** Build: Session & rate-limit management (S-133/HRMS-P406, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:282 — **needs CEO decision**
- **P3** Build: Sourcing analytics dashboard (S-134/HRMS-P407, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:283 — **needs CEO decision**
- **P3** Build: Configurable keywords & filters (S-135/HRMS-P408, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:284 — **needs CEO decision**
- **P3** Build: Profile quality scoring (S-136/HRMS-P409, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:285 — **needs CEO decision**
- **P3** Build: Sub-Vendor Portal Login & Scoped Access (S-138/HRMS-P802, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:349 — **needs CEO decision** — verify: code touched after 2026-08-22
- **P3** Build: Boolean Search — LinkedIn Integration (S-158/HRMS-P904, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:366 — **needs CEO decision**
- **P3** Build: Boolean Search — Job Board Integration (S-159/HRMS-P905, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:367 — **needs CEO decision**
- **P3** Build: Multi-Continent Candidate Pool Architecture (S-163/HRMS-P909, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:371
- **P3** Build: Continent-Aware Salary Benchmarking (S-167/HRMS-P913, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:375
- **P3** Build: Search Effectiveness Analytics (S-168/HRMS-P914, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:376
- **P3** Candidate portal strategy (JobDiva mapping: browse/apply/register interest/progress) — rapidtechnologiesllc-byte/WROS-Master#56 — **needs CEO decision**
- **P3** Careers portal (production grade) — rapidtechnologiesllc-byte/WROS-Master#52, rapidtechnologiesllc-byte/WROS-Master#58 (duplicate) — **needs CEO decision** — parked: careers site out of production scope (decision 2026-10-07)
- **P3** Replace the stub resume parser agent (TODO LLM; skills/experience/education extraction) — backend/app/services/resume_parser_agent.py:33-97 — verify it is still reachable
- **P3** Interview scorecard + corrections table (future scope) — backend/app/services/interview_service.py:165
- **P3** Manual recruiter-entered availability slots — backend/app/models/candidate_availability_slot.py:12
- **P3** Submission violation escalation cascade (3-strike/5-strike compliance review, account suspension) — backend/app/models/submission.py:14-19 — **needs CEO decision**
- **P3** Skills auto-generation from job description (awaiting LLM decision) — backend/app/DEFECTS_LOG.md:620 — **needs CEO decision** — verify
- **P3** Placement-to-work-order (PO/SOW) linkage for revenue not from an opportunity — backend/app/DEFECTS_LOG.md:379 — verify: work orders and staff-aug allocation by client exist
- **P3** Bulk engagement batches as a persisted table/route — backend/app/models/bulk_engagement.py:9
- **P3** Business-model hardcoding: ~181 Guidewire-specific references in backend/app — grep 'guidewire' backend/app; archive/post-go-live-fixes/HARDCODING_AUDIT/01_EXECUTIVE_SUMMARY.md:68 — **needs CEO decision**
- **P3** Email the recruiter on job applications (apply, add, remove) — docs/ACTION_EMAIL_MATRIX.md:113-115
- **P3** Email the requester on rehire review decisions; panel/panel-member deletions; move interview feedback to staff mail — docs/ACTION_EMAIL_MATRIX.md:193-202
- **P3** Email on offer letter edits before generation — docs/ACTION_EMAIL_MATRIX.md:249
- **P3** Email on candidate delete — docs/ACTION_EMAIL_MATRIX.md:361

### Workforce (72)

- **P1** Finish: Internal Manager Timesheet Approval (S-222/HRMS-0903, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:151 — verify: code touched after 2026-08-22
- **P2** Build: Core Eligibility Gate — Performance Gate Workflow (S-352/HRMS-0513, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:16 — verify: code touched after 2026-08-22
- **P2** Build: Welcome Note (Step 1) (S-402/HRMS-ONB-001, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:83 — **needs CEO decision**
- **P2** Build: Email Access Validation (Step 2) (S-403/HRMS-ONB-002, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:84 — **needs CEO decision**
- **P2** Build: Induction / company overview (Step 3) (S-404/HRMS-ONB-003, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:85 — **needs CEO decision**
- **P2** Build: Emergency Information (Step 4) (S-405/HRMS-ONB-004, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:86 — **needs CEO decision**
- **P2** Build: Personal Interests (Step 5) (S-406/HRMS-ONB-005, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:87 — **needs CEO decision**
- **P2** Finish: Personal & Emergency Contact Details Form → Employee record (Step 6) (S-407/HRMS-ONB-006, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:88 — **needs CEO decision**
- **P2** Finish: Bank Account / Payroll Setup (IFSC, PAN) (Step 7) (S-408/HRMS-ONB-007, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:89 — **needs CEO decision**
- **P2** Finish: Government ID & Tax Documents Upload (virus scan + SharePoint) (Step 8) (S-409/HRMS-ONB-008, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:90 — **needs CEO decision**
- **P2** Finish: Offer Letter Digital Acknowledgement (Step 9) (S-410/HRMS-ONB-009, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:91 — **needs CEO decision**
- **P2** Finish: Employment Agreement E-Signature (reuses SignatureModal.js) (Step 10) (S-411/HRMS-ONB-010, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:92 — **needs CEO decision**
- **P2** Build: Company Policies Acknowledgement (Step 11) (S-412/HRMS-ONB-011, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:93 — **needs CEO decision**
- **P2** Build: NDA / Confidentiality E-Signature (Step 12) (S-413/HRMS-ONB-012, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:94 — **needs CEO decision**
- **P2** Build: Background Verification Consent (via ConsentRecord, subject_type='employee') (Step 13) (S-414/HRMS-ONB-013, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:95 — **needs CEO decision**
- **P2** Build: IT Equipment Request (Step 14) (S-415/HRMS-ONB-014, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:96 — **needs CEO decision**
- **P2** Build: SharePoint Access Walkthrough (Step 15) (S-416/HRMS-ONB-015, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:97 — **needs CEO decision**
- **P2** Build: Email & Calendar Setup Walkthrough (Step 16) (S-417/HRMS-ONB-016, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:98 — **needs CEO decision**
- **P2** Build: Org Chart & Company Structure Overview (Step 17) (S-418/HRMS-ONB-017, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:99 — **needs CEO decision**
- **P2** Build: Meet the Leadership (Step 18) (S-419/HRMS-ONB-018, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:100 — **needs CEO decision**
- **P2** Build: Company Culture & Values (Step 19) (S-420/HRMS-ONB-019, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:101 — **needs CEO decision**
- **P2** Build: Benefits Enrollment (Step 20) (S-421/HRMS-ONB-020, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:102 — **needs CEO decision**
- **P2** Build: Dress Code & Office Guidelines (Step 21) (S-422/HRMS-ONB-021, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:103 — **needs CEO decision**
- **P2** Build: First Week Schedule Preview (Step 22) (S-423/HRMS-ONB-022, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:104 — **needs CEO decision**
- **P2** Build: IT Security & Data Protection Training (Step 23) (S-424/HRMS-ONB-023, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:105 — **needs CEO decision**
- **P2** Build: Workplace Conduct / POSH Training Acknowledgement (Step 24) (S-425/HRMS-ONB-024, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:106 — **needs CEO decision**
- **P2** Build: Tools & Software Access Setup checklist (Step 25) (S-426/HRMS-ONB-025, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:107 — **needs CEO decision**
- **P2** Build: Client Confidentiality Agreement (Step 26) (S-427/HRMS-ONB-026, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:108 — **needs CEO decision**
- **P2** Finish: Payroll & Timesheet System Walkthrough (Step 27) (S-428/HRMS-ONB-027, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:109 — **needs CEO decision**
- **P2** Build: Photo & ID Badge Submission (Step 28) (S-429/HRMS-ONB-028, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:110 — **needs CEO decision**
- **P2** Build: Ask Thunder — Onboarding FAQ (Step 29) (S-430/HRMS-ONB-029, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:111 — **needs CEO decision**
- **P2** Finish: Day-1 Logistics Confirmation (Step 30) (S-431/HRMS-ONB-030, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:112 — **needs CEO decision**
- **P2** Finish: Introduction to Reporting Manager (Step 31) (S-432/HRMS-ONB-031, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:113 — **needs CEO decision**
- **P2** Finish: Reporting Manager Introduces Buddy (Step 32) (S-433/HRMS-ONB-032, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:114 — **needs CEO decision**
- **P2** Finish: Convert Candidate to Employee on Joining (S-296/HRMS-0708, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:138 — verify: code touched after 2026-08-22
- **P2** Finish: Timesheet Validation & Submission Lock (S-221/HRMS-0902, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:150 — verify: possibly done -- timesheet lock built (OPEN_ITEMS P2-10)
- **P2** Finish: Employee Utilization Calculation (S-223/HRMS-0904, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:152 — verify: code touched after 2026-08-22
- **P2** Finish: Timesheet Submission Nag Agent — 7-step email/Teams/WhatsApp cascade to employee then RM/RM's-manager/BU-Head, timezone-aware (S-387/HRMS-1601, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:207 — verify: possibly done -- `timesheet_reminders` scheduled job exists
- **P2** Build: Admin Portal — HR Dashboard (S-097/HRMS-P202, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:250
- **P2** Finish: Admin Portal — Resource Management Dashboard (S-098/HRMS-P203, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:251
- **P2** Build: HTD job track configuration (Jobs tagged TRACK=HTD, Java depth required, Guidewire not required) (S-257/HRMS-P501, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:291
- **P2** Build: HTD candidate identification engine (Java 5yr+ scan, HTD_readiness scoring) (S-258/HRMS-P502, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:292
- **P2** Build: HTD internal interview process (L1 Java tech by Tech Lead, L2 learning aptitude by Tech Manager, Director decision, no client involvement) (S-261/HRMS-P505, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:293
- **P2** Finish: HTD deployment readiness checklist (training+assessment+interview+docs+BU Head sign-off → auto readiness report → deployable Guidewire pool) (S-264/HRMS-P508, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:294
- **P2** Build: HTD vs Standard track reporting (cost/hire, time-to-deploy, revenue/head, 12-mo retention) (S-266/HRMS-P510, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:295
- **P2** Build: Timesheet → Client Reporting Manager Notification (S-181/HRMS-P713, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:329
- **P2** Timesheet approved event and employee/approver emails — backend/app/services/timesheet_service.py:9-14 — verify: timesheet jobs and staff mail exist now
- **P2** Performance review recordings auto-fetched from Teams (manual upload is the fallback) — auto-memory `performance_reviews_model.md` — **needs CEO decision** — needs Teams permissions
- **P2** Email the employee on expense decisions (manager approve/reject, receipt check, paid); move approve to staff mail — docs/ACTION_EMAIL_MATRIX.md:168-172
- **P3** Build: Specialty Deployment 90-Day Certification Clock (S-366/HRMS-0522, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:24
- **P3** Build: Escalation Classification Engine — Resource vs Environment (S-367/HRMS-0523, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:25
- **P3** Build: Peer Trust Pulse Survey — Week 6 and Week 12 (S-368/HRMS-0524, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:26
- **P3** Build: Core Certification Scorecard — Full AI Assessment Output (S-369/HRMS-0525, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:27
- **P3** Build: HTD 365-Day Specialty Certification Track (S-370/HRMS-0526, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:28
- **P3** Build: Individual Employee Scorecard — 35 KPI Live View (S-375/HRMS-0531, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:31
- **P3** Build: Specialty Client Release Approval Workflow (S-378/HRMS-0534, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:34 — verify: code touched after 2026-08-22
- **P3** Build: Project Risk Flagging & Delivery Health (S-305/HRMS-0807, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:144 — verify: code touched after 2026-08-22
- **P3** Build: Dynamic Reporting Hierarchy Engine (configurable org-level chain walk) (S-382/HRMS-1404, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:192
- **P3** Build: Admin-editable check-in cadence by org level (S-383/HRMS-1405, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:193
- **P3** Build: Auto-scheduler batch job for recurring check-ins via Outlook Calendar (S-384/HRMS-1406, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:194
- **P3** Task fan-out UX — backend/app/models/task.py:116
- **P3** Core pull Part A (HRMS-1105, S-372) not built — backend/app/services/core_pull_service.py:18
- **P3** Org health snapshot (HRMS-1107) not built — backend/app/services/org_health_service.py:64
- **P3** Decide the learning dashboard APIs (`/learning/dashboard`, `/recommendations`, `/cross-module`, analytics) with no screen — OPEN_ITEMS.md:23
- **P3** Emails for BGV start/verdict/waive/vendor webhook — docs/ACTION_EMAIL_MATRIX.md:43-46
- **P3** Emails for the buddy programme (records, scores, graduate, extend, exit) — docs/ACTION_EMAIL_MATRIX.md:47-51
- **P3** Email when a certification target is assigned — docs/ACTION_EMAIL_MATRIX.md:76-77
- **P3** Emails for the onboarding checklist family — docs/ACTION_EMAIL_MATRIX.md:78-80
- **P3** One digest per manager after employee bulk import — docs/ACTION_EMAIL_MATRIX.md:141
- **P3** Emails on employee organisation, HTD, billable, profile-by-someone-else and remove-from-bench changes — docs/ACTION_EMAIL_MATRIX.md:142-155
- **P3** Emails for employee milestones — docs/ACTION_EMAIL_MATRIX.md:160
- **P3** Emails for the performance review family (review, recording, feedback, notes) — docs/ACTION_EMAIL_MATRIX.md:269-273

### Sales (47)

- **P2** Build: Create Adhoc Demand from Client Request (S-281/HRMS-0601, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:120 — see design -- covered by docs/RECRUITMENT_VS_WORKFORCE_DESIGN.md 2.4 (ad-hoc demand opens a draft requisition); also backend/app/DEFECTS_LOG.md:644 (deferred Aug)
- **P3** Finish: Map Revenue to Role Demand (S-268/HRMS-0302, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:54 — **needs CEO decision**
- **P3** Build: Generate Demand Plan from Revenue Target (S-269/HRMS-0303, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:55 — **needs CEO decision**
- **P3** Build: Forecast 30/60/90 Day Hiring Demand (S-270/HRMS-0304, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:56 — **needs CEO decision**
- **P3** Build: Convert Opportunity Pipeline to Demand (S-271/HRMS-0305, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:57 — **needs CEO decision**
- **P3** Finish: Match Bench vs Demand — Gap Analysis (S-272/HRMS-0306, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:58 — **needs CEO decision**
- **P3** Build: Trigger Sourcing Workflow on Demand Creation (S-273/HRMS-0307, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:59 — **needs CEO decision** — verify: code touched after 2026-08-22
- **P3** Build: Auto Create Job Requisitions from Demand (S-275/HRMS-0309, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:60 — **needs CEO decision** — see design -- covered by docs/RECRUITMENT_VS_WORKFORCE_DESIGN.md (requisition from demand)
- **P3** Build: View Demand Forecast Dashboard (S-276/HRMS-0310, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:61 — **needs CEO decision**
- **P3** Build: AI Revenue to Workforce Conversion Model (S-277/HRMS-0311, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:62 — **needs CEO decision**
- **P3** Build: Plan vs Execution Variance Tracking (S-279/HRMS-0313, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:64 — **needs CEO decision** — verify: code touched after 2026-08-22
- **P3** Build: BU Planning Approval Workflow (S-280/HRMS-0314, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:65 — **needs CEO decision** — verify: code touched after 2026-08-22
- **P3** Build: AI Classify Incoming Request (S-282/HRMS-0602, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:121 — **needs CEO decision**
- **P3** Build: Search Internal Bench First — Instant Match (S-283/HRMS-0603, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:122 — **needs CEO decision** — see design -- bench matches are part of the approved Workforce client-open-roles design
- **P3** Build: AI Suggest Immediate Allocation (S-284/HRMS-0604, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:123 — **needs CEO decision**
- **P3** Build: P1 Emergency Staffing Flow (S-285/HRMS-0605, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:124 — **needs CEO decision** — verify: code touched after 2026-08-22
- **P3** Build: Auto Schedule Client Interviews — Rapid Mode (S-286/HRMS-0606, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:125 — **needs CEO decision**
- **P3** Build: SLA Breach Prediction & Escalation (S-287/HRMS-0607, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:126 — **needs CEO decision**
- **P3** Build: AI Pricing Suggestion for Adhoc Request (S-288/HRMS-0608, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:127 — **needs CEO decision**
- **P3** Build: Admin Portal — Client Services Dashboard (S-099/HRMS-P204, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:252
- **P3** Build: Client User Account Creation & Mgmt (S-169/HRMS-P701, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:317 — **needs CEO decision**
- **P3** Build: Client Portal OTP Login & Scoped Session (S-170/HRMS-P702, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:318 — **needs CEO decision**
- **P3** Build: Client Portal Home Dashboard (S-171/HRMS-P703, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:319 — **needs CEO decision** — verify: code touched after 2026-08-22
- **P3** Build: Resume Submission — Client View List (S-172/HRMS-P704, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:320 — **needs CEO decision**
- **P3** Build: Resume Submission — Candidate Detail (client-safe) (S-173/HRMS-P705, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:321 — **needs CEO decision**
- **P3** Build: BlitzenX Submission Note — Mandatory (S-174/HRMS-P706, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:322 — **needs CEO decision**
- **P3** Build: Submission Status Real-Time Sync (S-175/HRMS-P707, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:323 — **needs CEO decision**
- **P3** Build: Client Action — Request Interview (S-176/HRMS-P708, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:324 — **needs CEO decision**
- **P3** Build: Client Action — Accept Candidate (S-177/HRMS-P709, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:325 — **needs CEO decision**
- **P3** Build: Client Action — Reject w/ Structured Feedback (S-178/HRMS-P710, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:326 — **needs CEO decision**
- **P3** Build: Client Action — Rank Multiple Candidates (S-179/HRMS-P711, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:327 — **needs CEO decision**
- **P3** Build: Client Action — Request Additional Resumes (S-180/HRMS-P712, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:328 — **needs CEO decision**
- **P3** Build: Client Timesheet Approval — Portal View (S-182/HRMS-P714, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:330 — **needs CEO decision**
- **P3** Build: Client Timesheet — Reassign Approver (S-183/HRMS-P715, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:331 — **needs CEO decision**
- **P3** Build: Timesheet Correction/History/SLA (merged) (S-184/HRMS-P716, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:332 — **needs CEO decision**
- **P3** Build: RFP Intake/AI Extraction/Demand Creation (merged) (S-187/HRMS-P719, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:333 — **needs CEO decision**
- **P3** Build: RFP Status Tracking — Client View (S-190/HRMS-P722, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:334 — **needs CEO decision**
- **P3** Build: RFP Clarification Request Flow (S-191/HRMS-P723, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:335 — **needs CEO decision**
- **P3** Build: RFP AI Auto-Sourcing w/ Human Handoff (S-192/HRMS-P724, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:336 — **needs CEO decision**
- **P3** Build: Client Messaging — CS Thread (S-193/HRMS-P725, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:337 — **needs CEO decision**
- **P3** Build: Automated Client Notification Engine (S-194/HRMS-P726, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:338 — **needs CEO decision**
- **P3** Build: Client Communication Archive & Search (S-195/HRMS-P727, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:339 — **needs CEO decision**
- **P3** Build: Client Dashboard — Delivery Health (S-196/HRMS-P728, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:340 — **needs CEO decision**
- **P3** Build: Client Analytics — Submission & Hiring Metrics (S-197/HRMS-P729, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:341 — **needs CEO decision** — verify: code touched after 2026-08-22
- **P3** Build: Client Health Score — Internal View (S-198/HRMS-P730, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:342 — **needs CEO decision**
- **P3** Email on account manager change for a client — docs/ACTION_EMAIL_MATRIX.md:89
- **P3** Emails on opportunity stage transitions — docs/ACTION_EMAIL_MATRIX.md:257

### Finance (30)

- **P1** Finish: Map Timesheet to Project Revenue (S-224/HRMS-0905, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:153 — verify: possibly done -- chain client->job->timesheet->invoice verified end to end 2026-10-07 (bc60293a)
- **P1** Finish: Invoice Generation, Status Tracking & PDF Export (S-226/HRMS-0907, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:154 — note -- PDF export and automatic sending still out of scope (`backend/app/models/invoice.py:5`)
- **P1** Finish: Monthly Invoice Generation Cycle — scheduled trigger on the 2nd of month (S-388/HRMS-1602, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:208 — verify: possibly done -- `auto_invoicing` scheduled job exists
- **P1** Finish: AR Follow-Up Agent — 15/30/45-day escalating reminders, LLM-drafted messages queued for review (S-390/HRMS-1604, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:209 — verify: possibly done -- `ar_follow_up` scheduled job exists
- **P1** Finish: Bank Statement Reconciliation — PDF/Excel upload, LLM extraction, deterministic matching, Finance-confirmed only (S-391/HRMS-1605, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:210 — verify: possibly done -- bank reconciliation screen built 2026-11-09 (CSV/typed credits); PDF/Excel + LLM extraction not
- **P1** Finish: Fully Loaded Cost Engine — locked India/US formulas, ESI cap, 4 flagged placeholder constants (S-393/HRMS-1608, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:211
- **P1** Build: RM Burden Allocation Engine — flat per-hour RM overhead across billable employees (S-394/HRMS-1609, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:212
- **P1** Build: Minimum Bill Rate Engine — (FLC + RM Burden) × multiplier (S-395/HRMS-1610, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:213 — note -- minimum bill rate shown, but pay-per-hour only until cost rates exist
- **P1** Build: BXIN/BXUS Separate P&L Engine — Revenue/Salary/EBITDA/Net Profit per legal entity (S-396/HRMS-1607, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:214 — verify: possibly done -- company P&L built (`revenue_chain_service._company_pnl`, PR #540)
- **P1** Supply cost rates (BU x country statutory % and overhead %): 0 configs, so bench loss and P&L cost read $0 — OPEN_ITEMS.md:41; auto-memory `candidate_merge_and_vendor_roles.md` — **needs CEO decision**
- **P1** Set margin floor values per delivery engine and country and who approves below them (policy table empty, #417) — OPEN_ITEMS.md:54; auto-memory `candidate_merge_and_vendor_roles.md` — **needs CEO decision**
- **P2** Finish: Forecast vs Actual Comparison (S-242/HRMS-0213, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:47 — verify: code touched after 2026-08-22
- **P2** Finish: Revenue Leakage Detection (S-243/HRMS-0214, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:48 — verify: code touched after 2026-08-22
- **P2** Finish: Project Profitability Dashboard (S-331/HRMS-1206, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:171
- **P2** Finish: Bench Cost & Aging Analytics Dashboard (S-332/HRMS-1207, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:172
- **P2** Finish: Reserve Fund Engine — 25% of EBITDA auto-calculated (contribution or drawdown), 12-month buffer check (S-397/HRMS-1612, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:215 — **needs CEO decision**
- **P2** Finish: Hiring Affordability Gate — TWO hard gates (Reserve check + Run-rate check), zero override (S-398/HRMS-1613, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:216 — **needs CEO decision**
- **P2** Build: GST & Statutory Compliance — UAT-gated placeholder scaffold (S-401/HRMS-1615, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:218 — **needs CEO decision**
- **P2** Decide bench (unallocated) vs idle-on-a-project split in the P&L (recommended yes) — OPEN_ITEMS.md:56 — **needs CEO decision**
- **P2** Fixed-price / retainer billing and PM / Program Manager / Delivery Head roles (deferred until Core's revenue share is known) — OPEN_ITEMS.md:58 — **needs CEO decision**
- **P2** Company model Part 2 decisions: intercompany markup, invoicing entity for US clients served from India, per-company letterhead and number series — docs/COMPANY_MODEL_DESIGN.md:55-62; OPEN_ITEMS.md:59, OPEN_ITEMS.md:112 — **needs CEO decision** — BX-Canada question superseded: Poliqs is 1-3; memory says intercompany excluded at org level
- **P2** Record Poliqs loan repayments (loan card shows lent, not owed) — auto-memory `holding_company_model.md` — **needs CEO decision**
- **P2** Confirm 'broken at org level' = kept at org level (SHARED_COST_SPLIT_TO_BUS off) — auto-memory `next_session_autonomy_backlog.md` (2026-11-05) — **needs CEO decision**
- **P2** Invoice PDF export and automatic sending (explicitly out of scope so far) — backend/app/models/invoice.py:5; docs/S316_INVOICE_GENERATION.md:455 — **needs CEO decision**
- **P3** Build: Payroll System Sync (S-343/HRMS-1308, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:181 — **needs CEO decision**
- **P3** Build: Invoice Export to ERP (S-344/HRMS-1309, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:182 — **needs CEO decision**
- **P3** Decide `/invoices/{id}/mark-paid` (replaced by record-payment): remove the API — OPEN_ITEMS.md:23
- **P3** Decide `/agents/cfo/cost-breakdown` (API with no screen): build the screen or remove — OPEN_ITEMS.md:23
- **P3** Emails for the work order family (create, update, end, pause, resume) — docs/ACTION_EMAIL_MATRIX.md:349-353
- **P3** Email on allocation client-billing change — docs/ACTION_EMAIL_MATRIX.md:32

### Leadership (16)

- **P2** Finish: CXO Revenue Dashboard (S-326/HRMS-1201, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:166
- **P2** Build: CXO Workforce Utilization View (S-328/HRMS-1203, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:168
- **P2** Finish: Executive Finance Dashboard — 7-block CEO dashboard, pure aggregation over the 5 engines (S-400/HRMS-1614, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:217
- **P2** Build: Technical Portal — BU Head Oversight View (S-103/HRMS-P208, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:255
- **P2** Decide the org reporting rule: a manager may sit only 1-2 levels above the report; keep or relax? — OPEN_ITEMS.md:53 — **needs CEO decision**
- **P2** Confirm CFO-type chiefs keep their function while L15+ (CEO, Partner, SVP) have none — auto-memory `no_function_above_l15.md`; auto-memory `next_session_autonomy_backlog.md` (2026-11-05) — **needs CEO decision**
- **P3** Build: BU Head ML Dashboard — Workforce Command Centre (S-374/HRMS-0530, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:30
- **P3** Build: Workforce Scenario Planning (S-278/HRMS-0312, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:63 — **needs CEO decision** — verify: code touched after 2026-08-22
- **P3** Build: Daily System Activity Report (S-325/HRMS-1110, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:165 — verify: code touched after 2026-08-22
- **P3** Build: CXO Hiring vs Target Dashboard (S-327/HRMS-1202, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:167 — verify: possibly done -- Hiring Analytics (open positions vs joined) built 2026-11-09
- **P3** Build: CXO Risk Heatmap (S-329/HRMS-1204, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:169
- **P3** Build: Human vs AI Dependency Tracker (S-334/HRMS-1209, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:174
- **P3** Finish: Human dependency measurement dashboard (system-wide AI vs human % per stage, weekly trend, <20% target, alert on wrong-direction) (S-118/HRMS-P612, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:311 — verify: code touched after 2026-08-22
- **P3** Year-over-year goal analytics (historical goals, trends, forecast accuracy) — rapidtechnologiesllc-byte/WROS-Master#57
- **P3** Decide the Spartan forecasting summary and cascade-prediction APIs (no screen): build or remove — OPEN_ITEMS.md:23
- **P3** Partner/BU Head role dashboards + ad-hoc reporting tool; unified CEO executive dashboard (Aug defect log) — backend/app/DEFECTS_LOG.md:20, backend/app/DEFECTS_LOG.md:49 — verify: possibly done -- dashboards rebuilt 2026-10-06/08

### Admin/System (18)

- **P1** Fill each Manage Role's permission set (every role set except Partner grants 0 of 114 resources) and trim the function add-ons that still grant almost everything — OPEN_ITEMS.md:43, OPEN_ITEMS.md:189 — **needs CEO decision** — add-ons Recruitment/HR approved 2026-11-06 (PR #538)
- **P1** Decide HR and Recruitment function rights and assign the add-on to every person in those functions (only two have it) — auto-memory `landing_and_one_stage.md` — **needs CEO decision**
- **P2** Finish: Org Role Mapping to Portal View (S-104/HRMS-P209, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:256
- **P2** Imported employees: create a client-submittable profile automatically? (recommended yes) — OPEN_ITEMS.md:55 — **needs CEO decision**
- **P2** Activation emails on import: batch by business unit? — OPEN_ITEMS.md:57 — **needs CEO decision**
- **P2** Staff notification emails are composed in code and are not in the template catalogue — OPEN_ITEMS.md:27; auto-memory `next_session_autonomy_backlog.md` (2026-11-05)
- **P3** Build: Org authority map config (CEO→BU Head→Director→Tech Manager→Tech Lead→Sr Consultant, escalation paths) (S-117/HRMS-P611, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:310
- **P3** Decide `/ats/*` scores API (no screen): build or remove — OPEN_ITEMS.md:23
- **P3** Decide `/jobs/my-jobs`, `/org/positions`, `/core-certification/eligibility/{id}` (APIs with no screen) — OPEN_ITEMS.md:23
- **P3** Menu resources with no page (hidden but grantable): build the page or drop the resource — HANDOFF.md:198-205; OPEN_ITEMS.md:169 — verify: P2-8 disabled 15; menu clean-up 2026-11-09
- **P3** Admin Settings defect (2026-08-12): HR user & RBAC should be one meaningful screen; HR could not create a job or schedule an interview — backend/app/DEFECTS_LOG.md:4 — verify: possibly done -- access model rebuilt 2026-10-13
- **P3** RBAC screen redesign as module x verb permission grid — backend/app/DEFECTS_LOG.md:274 — verify: possibly superseded by Manage Roles -> Permissions
- **P3** Opportunity owner should default from the client owner — backend/app/DEFECTS_LOG.md:455 — verify: client owner added later
- **P3** Department home_screen needs the matching view right or the person falls back to their profile: check every function — auto-memory `landing_and_one_stage.md`
- **P3** Decide the remaining 'Built, not wired' unused jobs that read empty tables (old no-show, follow-up, reactivation, keep-warm, motivation, campaigns, onboarding touchpoints) — auto-memory `next_session_autonomy_backlog.md` (2026-11-05); OPEN_ITEMS.md:27 — **needs CEO decision**
- **P3** Email the person seated when an org seat, department or role changes — docs/ACTION_EMAIL_MATRIX.md:259-266
- **P3** Emails for the ticket family (create, routing, SLA policy) — docs/ACTION_EMAIL_MATRIX.md:317-319
- **P3** Verify roles-as-data superseded REFACTOR-004 employee roles, then close — rapidtechnologiesllc-byte/WROS-Master#19; OPEN_ITEMS.md:207

### Platform/Infra (57)

- **P1** Verify every registered scheduled job is enabled in production `SCHEDULED_JOBS_ENABLED` (on 2026-10-30 only the Thunder sweep ran; timesheets, AR, invoicing, renewals, reviews were off) — OPEN_ITEMS.md:37 — **needs CEO decision** — memory 2026-11-05 says jobs healthy: confirm the list
- **P1** Set ANTHROPIC_API_KEY (and real Gemini/OpenAI keys if kept) in production; `flash_mission_sweep`, reply reading and facts extraction wait on it — auto-memory `prod_no_ai_keys_rules_first.md`; auto-memory `next_session_autonomy_backlog.md` (2026-11-05); OPEN_ITEMS.md:37 — **needs CEO decision**
- **P1** Monitoring, alerting, APM and error tracking for production (none today) — OPEN_ITEMS.md:176; docs/OPEN_REQUIREMENTS_BACKLOG.md:77 (S-080 AI Recruiter go-live checklist & monitoring) — merged with S-080
- **P1** Document and drill DB backup and restore (pre-deploy dumps exist, restore never tested) — OPEN_ITEMS.md:123, OPEN_ITEMS.md:176
- **P2** Finish: WhatsApp Business API — Enhancement (S-339/HRMS-1304, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:177
- **P2** Finish: Email Outreach Automation & Threading — Enhancement (S-340/HRMS-1305, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:178
- **P2** Finish: Outlook Calendar Integration — Enhancement (S-341/HRMS-1306, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:179 — verify: code touched after 2026-08-22
- **P2** Run the queue worker as a systemd unit instead of the cron watchdog (needs sudo) — OPEN_ITEMS.md:175, HANDOFF.md:130 — **needs CEO decision**
- **P2** Rotate the queue worker and mail-sync logs — OPEN_ITEMS.md:175, HANDOFF.md:131
- **P2** After every merge to main, check the served `main.*.js` contains the change (a shared build folder once rolled production back) — auto-memory `manual_deploys_no_github_actions.md` — process; PR #536 fixed the folder clash
- **P2** Configure WhatsApp/Twilio (THUNDER_WHATSAPP_NUMBER, tested provider); until then Thunder engages by email only and outbound WhatsApp raises ChannelNotConfigured — OPEN_ITEMS.md:49, OPEN_ITEMS.md:102, backend/app/services/whatsapp_webhook_service.py:16 — **needs CEO decision**
- **P2** Grant the Teams application access policy and Graph OnlineMeetings/recording permissions (transcripts, attendance and review recordings still 403) — auto-memory `next_session_autonomy_backlog.md` (2026-11-05); auto-memory `performance_reviews_model.md` — **needs CEO decision**
- **P2** Grant delegated Mail.Send + Mail.ReadWrite and get every staff member connected to Outlook (mail capture) — auto-memory `next_session_autonomy_backlog.md` (2026-11-05); HANDOFF.md:69 — **needs CEO decision** — 2026-11-27: only the CEO may skip Outlook (0fd80260)
- **P3** Build: Integration Health Agent — Self-Heal (S-323/HRMS-1108, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:163 — verify: code touched after 2026-08-22
- **P3** Build: Webhook Engine & Integration Health Dashboard (S-345/HRMS-1310, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:183 — **needs CEO decision** — verify: code touched after 2026-08-22
- **P3** Finish: M365 SSO bridge + embedded tab/dock shell for Outlook/Teams (S-379/HRMS-1401, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:189 — verify: possibly done -- Sign in with Microsoft built 2026-11-27 (0fd80260)
- **P3** Build: Embedded Outlook Mail/Calendar tab, WROS-context deep linking (S-380/HRMS-1402, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:190
- **P3** Build: Teams chat dock + unified notification center (S-381/HRMS-1403, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:191
- **P3** Clean up accumulating `frontend/build-prev-*` and the foreign-owned `build-old` on the server (needs sudo) — OPEN_ITEMS.md:175, HANDOFF.md:132
- **P3** Remove or isolate the stub delivery fallback (`api_keys_service` defaults to provider 'stub', `stub_delivery` always reports sent) — backend/app/services/api_keys_service.py:211, backend/app/services/stub_delivery.py:33 — verify it can never be selected in production
- **P3** Wire or delete the `channel_processors` stubs that fail with 'not yet implemented' (Thunder qualification/outreach, approval workflow, commission ledger, CRM sync, dashboard WebSocket, calendar event, e-signature) — backend/app/workers/channel_processors.py:286-556
- **P3** Remove the `admin_queue` stub router — backend/app/api/v1/endpoints/admin_queue.py:1
- **P3** Implement or remove automatic dependency resolution in the recovery engine — backend/app/services/recovery_engine.py:325
- **P3** Decide on the Celery/Redis path (startup Redis health check) now that the queue is the database `channel_queue_item` — auto-memory `redis_infrastructure_blocker.md` — verify whether anything still needs Redis
- **P3** Remove the stale nested `.git` under backend/ if it still exists — HANDOFF.md:242 — verify
- **P3** `task_service.create_task` commits internally (breaks callers' transactions) — HANDOFF.md:227; backend/app/services/task_service.py:154
- **P3** Retire the stale WROS-deploy clone (2026-11-01) and the pre-consolidation OnboardingModule-* repos from C:\dev, or mark them read-only — C:\dev\WROS-deploy, C:\dev\OnboardingModule-Backend, C:\dev\OnboardingModule-Frontend
- **P3** Triage `backend/scripts/` one-off fixer and migration scripts (keep deploy_backend.sh, code_gate_validator.py) — OPEN_ITEMS.md:180
- **P3** Config-driven opportunity stages (HRMS-0115); stages are the hardcoded default — backend/app/api/v1/endpoints/opportunities.py:10-13
- **P3** On-call Director roster for orchestration routing is not built — backend/app/services/orchestration_router_service.py:292
- **P3** Multi-currency books (INR/CAD) beyond client-currency bill rates — docs/COMPANY_MODEL_DESIGN.md:59 — **needs CEO decision** — client-currency bill rates built 2026-11-11 (bd0987a3)
- **P3** Close: BX-HRMS-DEFECT-005: Backend port configuration mismatch — rapidtechnologiesllc-byte/WROS-Master#44; OPEN_ITEMS.md:202-203 — fixed/obsolete
- **P3** Close: agent_config endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#59; OPEN_ITEMS.md:199 — resolved
- **P3** Close: bi_explorer endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#60; OPEN_ITEMS.md:199 — resolved
- **P3** Close: bu_head_dashboard endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#61; OPEN_ITEMS.md:199 — resolved
- **P3** Close: candidate_ranking endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#62; OPEN_ITEMS.md:199 — resolved
- **P3** Close: candidate_rejection endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#63; OPEN_ITEMS.md:199 — resolved
- **P3** Close: complete_workflow endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#64; OPEN_ITEMS.md:199 — resolved
- **P3** Close: conversions endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#65; OPEN_ITEMS.md:199 — resolved
- **P3** Close: crud endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#66; OPEN_ITEMS.md:199 — resolved
- **P3** Close: doctor_traces_dashboard endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#67; OPEN_ITEMS.md:199 — resolved
- **P3** Close: employee_conversion endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#68; OPEN_ITEMS.md:199 — resolved
- **P3** Close: hiring_manager_validation endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#69; OPEN_ITEMS.md:199 — resolved
- **P3** Close: interview_decision endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#70; OPEN_ITEMS.md:199 — resolved
- **P3** Close: invoices_s316 endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#71; OPEN_ITEMS.md:199 — resolved
- **P3** Close: onboarding_orchestrator endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#73; OPEN_ITEMS.md:199 — resolved
- **P3** Close: onboarding_workflow endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#74; OPEN_ITEMS.md:199 — resolved
- **P3** Close: queue endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#75; OPEN_ITEMS.md:199 — resolved
- **P3** Close: queue_dashboard endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#76; OPEN_ITEMS.md:199 — resolved
- **P3** Close: queues endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#77; OPEN_ITEMS.md:199 — resolved
- **P3** Close: resume_versions endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#78; OPEN_ITEMS.md:199 — resolved
- **P3** Close: revenue_recognition endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#79; OPEN_ITEMS.md:199 — resolved
- **P3** Close: spartan_forecasting endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#80; OPEN_ITEMS.md:199 — resolved
- **P3** Close: spartan_integration endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#81; OPEN_ITEMS.md:199 — resolved
- **P3** Close: strategic_consul endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#82; OPEN_ITEMS.md:199 — resolved
- **P3** Close: system_health endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#83; OPEN_ITEMS.md:199 — resolved
- **P3** Close: training_dashboards endpoint - Not registered (orphaned code) (every orphaned endpoint is now registered or deleted) — rapidtechnologiesllc-byte/WROS-Master#84; OPEN_ITEMS.md:199 — resolved

### Security/Compliance (20)

- **P0** Verify SQL Server port 1433 on the production host is closed and rotate its leaked password — OPEN_ITEMS.md:39, OPEN_ITEMS.md:123 — owner action (server access); last probe (2026-10-19) still got a SQL Server reply
- **P1** Finish: Audit Log Base System (S-208/HRMS-0110, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:40 — note -- audit log is ORM append-only; check coverage of every write
- **P1** Revoke the old Gemini and Azure secrets — OPEN_ITEMS.md:40, OPEN_ITEMS.md:123 — owner action (provider consoles)
- **P1** Build client contact confidentiality step 1: visibility (mask contact email/phone/LinkedIn for non-privileged users on every surface, pickers by contact id, log scrubbing, reading sentinel test) — docs/CLIENT_CONTACT_CONFIDENTIALITY_DESIGN.md:146-148 — CEO rule 2026-11-27/28; design v3 approved
- **P1** Build client contact confidentiality step 2: one `outbound_transport` chokepoint, `guard.decide`, held messages, per-message approval for financial mail, standing approvals, approval task and screen, hold sweep job, egress tests — docs/CLIENT_CONTACT_CONFIDENTIALITY_DESIGN.md:149-150
- **P1** Add `imports/` to .gitignore (employee import files with personal data are untracked but not ignored) — git status (`?? imports/`); auto-memory `next_session_autonomy_backlog.md` (2026-11-05)
- **P1** Remove stray `.env` copies at the C:\dev root (`C:devWROS-Master.env`, `C:devWROS-Masterbackend.env`) or move them into the repo's ignored env files — C:\dev directory listing — contents not read
- **P1** Remove default/test account passwords from CLAUDE.md files and docs (the app now generates or reads ADMIN_PASSWORD, the docs still list fixed ones) — C:\dev\CLAUDE.md, C:\dev\WROS-Master\CLAUDE.md (DB initialization, Login Credentials sections); backend/app/core/db_contract.py:1690
- **P2** Build: Compliance & Audit Reporting Engine (S-335/HRMS-1210, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:175
- **P2** Build: WhatsApp Broadcast Compliance Engine (S-127/HRMS-P309, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:271
- **P2** Build: Interview decision audit log (immutable, exportable, who/when/outcome/panel-split/override) (S-116/HRMS-P610, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:309
- **P2** Purge the old DB password from git history (still the local-dev password) or change the local-dev password — OPEN_ITEMS.md:87, HANDOFF.md:134
- **P2** Wire the API-layer guard for confidential `clients.markup_rate_pct` (never serialised to recruiter-facing responses) — backend/app/models/client.py:135
- **P2** Wire the PAYROLL/ADMIN-only decrypt path for employee bank account numbers (model encrypts, no route decrypts) — backend/app/models/employee.py:152
- **P2** Provision an antivirus scanning vendor: uploads fail closed with `VirusScanUnavailable`, so scanned-document access depends on it — backend/app/services/virus_scan_service.py:1-25 — **needs CEO decision** — verify what production does with unscanned documents
- **P2** Configure the delivery-outcome webhook keys (WEBHOOK_PUBLIC_BASE_URL, SendGrid public key, Mailgun signing key, Twilio auth token); endpoints answer 503 until set — OPEN_ITEMS.md:85 — **needs CEO decision**
- **P2** Replace in-memory rate limiting with a shared store (works with one worker only) — OPEN_ITEMS.md:177
- **P2** Add a WAF or admin IP allowlist — OPEN_ITEMS.md:176 — **needs CEO decision**
- **P2** Decide tenants 2 and 3 (locked out: resources exist only for tenant 1): real tenants get a fix plus cross-tenant smoke test, test data stays locked — OPEN_ITEMS.md:60, OPEN_ITEMS.md:190, docs/ACCESS_MODEL_IMPACT.md:103 — **needs CEO decision**
- **P3** Keep the manual merge gate as process (branch protection off, no GitHub Pro) — OPEN_ITEMS.md:44, OPEN_ITEMS.md:88 — closed by decision; listed for the release checklist

### AI agents (Flash/Thunder) (73)

- **P2** Finish: Intent Detection Engine (S-033/HRMS-0433, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:72 — verify: code touched after 2026-08-22
- **P2** Finish: Human Escalation Detection (S-035/HRMS-0435, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:73 — verify: code touched after 2026-08-22
- **P2** Finish: Automated Outreach Agent (S-319/HRMS-1104, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:160 — verify: code touched after 2026-08-22
- **P2** Fix SLM feedback engine's hardcoded `days_since_last = 3` (query the real last retrain date) — backend/app/services/slm_feedback_engine.py:424
- **P2** `ThunderOutreachHandler.send` returns mock success: delete it or wire it to the real send — backend/app/services/message_handlers/thunder_outreach_handler.py:70-87; backend/app/services/message_handler_registry.py:216 — not registered today
- **P2** Decide `kpi_agent_service.py` and `employee_mental_health_agent_service.py` (no callers): switch on or delete — OPEN_ITEMS.md:61, OPEN_ITEMS.md:170 — **needs CEO decision**
- **P2** Decide the 31 unused service files (~8,200 lines) listed as 'Built, not wired' — OPEN_ITEMS.md:27, OPEN_ITEMS.md:127; auto-memory `next_session_autonomy_backlog.md` (2026-11-05) — **needs CEO decision** — one line per agent group below
- **P3** Build: Reporting Manager Weekly Input Bot (S-355/HRMS-0516, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:17 — verify: code touched after 2026-08-22
- **P3** Build: Core Eligibility AI Assessment — Agentic Bot (S-357/HRMS-0518, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:18 — verify: code touched after 2026-08-22
- **P3** Finish: Curtis Rule — Partner Intent ML Engine (S-371/HRMS-0527, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:29 — verify: code touched after 2026-08-22
- **P3** Build: Predictive Demand ML Engine (S-376/HRMS-0532, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:32
- **P3** Build: Voice Calling Agent Framework (S-068/HRMS-0468, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:75 — **needs CEO decision**
- **P3** Build: Unified Prediction Engine: Talent Signals (S-306/HRMS-1001, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:155 — verify: code touched after 2026-08-22
- **P3** Build: Unified Prediction Engine: Financial Signals (S-309/HRMS-1004, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:156
- **P3** Build: AI Training Recommendation Engine (S-315/HRMS-1010, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:157
- **P3** Finish: System Orchestration Master Agent (S-316/HRMS-1101, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:158 — verify: code touched after 2026-08-22
- **P3** Finish: LinkedIn Sourcing Agent Loop (S-318/HRMS-1103, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:159 — **needs CEO decision** — verify: code touched after 2026-08-22
- **P3** Build: Revenue Monitoring Agent (S-321/HRMS-1106, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:161
- **P3** Build: Project Health Monitoring Agent (S-322/HRMS-1107, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:162 — verify: code touched after 2026-08-22
- **P3** Build: Learning Optimization Agent (S-324/HRMS-1109, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:164 — verify: code touched after 2026-08-22
- **P3** Finish: HR Intelligence Briefing — daily 08:00 digest per recruiter across all their candidates, portal + email, `hr_intelligence_briefings` table (S-350/HRMS-P120, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:224 — **needs CEO decision** — note -- daily digest job exists but is never scheduled
- **P3** Build: AI Search Refinement Suggestions (S-162/HRMS-P908, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:370
- **P3** Build: Boolean Search → AI Recruiter Pipeline (S-166/HRMS-P912, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:374
- **P3** SLM daily improvement: Slack notification, report history, retrain trigger (TODOs) — backend/app/services/slm_daily_improvement.py:342-344
- **P3** `send_thunder_message` has no transport for channels outside the consent map — backend/app/services/thunder_service.py:222
- **P3** Objection handling engine (HRMS-0472) and other NOT_BUILT intent targets — backend/app/services/detect_intent_service.py:28,79
- **P3** Desire profile (EPIC-11) in Thunder context — backend/app/services/thunder_service.py:499
- **P3** Sentiment dashboard (EPIC-12) — backend/app/services/sentiment_analysis_service.py:24
- **P3** Data healer: create recruiter-assignment tasks (TODO) — backend/app/services/data_healer_service.py:177-190
- **P3** Delete the architect auto-fix tooling (agent spawning not implemented) — backend/app/services/architect_auto_fix_hardcoded_roles.py:387-395
- **P3** Conversation audit log: wire the other epics' events — backend/app/models/conversation_audit_log.py:17
- **P3** Switch on or delete: Interview reminder / confirmation / no-show / reschedule agents — OPEN_ITEMS.md:127; rapidtechnologiesllc-byte/WROS-Master#33, rapidtechnologiesllc-byte/WROS-Master#34 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Reactivation campaign and mellow keep-warm — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: No-response detection — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Outreach agent and orchestrator; email-first engagement — OPEN_ITEMS.md:127; rapidtechnologiesllc-byte/WROS-Master#32 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Onboarding agent — OPEN_ITEMS.md:127; rapidtechnologiesllc-byte/WROS-Master#29 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Relation-building agent, tracker and dashboard — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Personal intelligence — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Drop-risk and abandonment scoring — OPEN_ITEMS.md:127; rapidtechnologiesllc-byte/WROS-Master#35 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: KPI / HR / employee mental-health agents — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Supervisor agent — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: HTD pipeline accountability — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Partner success — OPEN_ITEMS.md:127; rapidtechnologiesllc-byte/WROS-Master#27 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Opportunity tracker — OPEN_ITEMS.md:127; rapidtechnologiesllc-byte/WROS-Master#28 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Flash orchestration engine — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: LinkedIn sourcing and recruiter workload — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Timesheet bulk/complete and invoice complete — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Pipeline leakage scan — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Resume search / compare / completeness / SLM parser — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Calendar matching — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Candidate scoring — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Sub-vendor service — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Slack integration — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Ticket SLA and task escalation — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Daily digest (never scheduled; goes to recruiters) — OPEN_ITEMS.md:127; rapidtechnologiesllc-byte/WROS-Master#39; auto-memory `next_session_autonomy_backlog.md` (2026-11-05) — **needs CEO decision** — built, nothing calls it
- **P3** Switch on or delete: Career portal service (careers site out of scope) — OPEN_ITEMS.md:127 — **needs CEO decision** — built, nothing calls it
- **P3** Close: EPIC-FLASH-001: Database Integration for Goals System (COMPLETED) — rapidtechnologiesllc-byte/WROS-Master#45; OPEN_ITEMS.md:201 — labeled completed
- **P3** Close: EPIC-FLASH-002: Frontend API Integration (COMPLETED) — rapidtechnologiesllc-byte/WROS-Master#46; OPEN_ITEMS.md:201 — labeled completed
- **P3** Close: EPIC-FLASH-003: Flash Validation UI Component (COMPLETED) — rapidtechnologiesllc-byte/WROS-Master#47; OPEN_ITEMS.md:201 — labeled completed
- **P3** Close: EPIC-FLASH-004: Role Template Navigation Integration (COMPLETED) — rapidtechnologiesllc-byte/WROS-Master#48; OPEN_ITEMS.md:201 — labeled completed
- **P3** Close: EPIC-FLASH-005: Dark Mode UI Theme (COMPLETED) — rapidtechnologiesllc-byte/WROS-Master#49; OPEN_ITEMS.md:201 — labeled completed
- **P3** Close: EPIC-FLASH-006: End-to-End System Testing (COMPLETED) — rapidtechnologiesllc-byte/WROS-Master#50; OPEN_ITEMS.md:201 — labeled completed
- **P3** Replace THUNDER Phase 3B issue: Phase 3B code deleted, Thunder engagement sweep is live — rapidtechnologiesllc-byte/WROS-Master#53; OPEN_ITEMS.md:208 — close
- **P3** Close: AGENT-001: Resource Management Agent (service implemented) — rapidtechnologiesllc-byte/WROS-Master#23; OPEN_ITEMS.md:200 — verify it is wired
- **P3** Close: AGENT-002: Core-Pull Conflict Agent (service implemented) — rapidtechnologiesllc-byte/WROS-Master#24; OPEN_ITEMS.md:200 — verify it is wired
- **P3** Close: AGENT-003: CFO Agent (service implemented) — rapidtechnologiesllc-byte/WROS-Master#25; OPEN_ITEMS.md:200 — verify it is wired
- **P3** Close: AGENT-004: CEO/FY Progress Agent (service implemented) — rapidtechnologiesllc-byte/WROS-Master#26; OPEN_ITEMS.md:200 — verify it is wired
- **P3** Close: AGENT-008: Buddy Program Agent (service implemented) — rapidtechnologiesllc-byte/WROS-Master#30; OPEN_ITEMS.md:200 — verify it is wired
- **P3** Close: AGENT-009: Employee Milestone Agent (service implemented) — rapidtechnologiesllc-byte/WROS-Master#31; OPEN_ITEMS.md:200 — verify it is wired
- **P3** Close: AGENT-014: Compensation Scoring Agent (service implemented) — rapidtechnologiesllc-byte/WROS-Master#36; OPEN_ITEMS.md:200 — verify it is wired
- **P3** Close: AGENT-015: Desire Intelligence Agent (service implemented) — rapidtechnologiesllc-byte/WROS-Master#37; OPEN_ITEMS.md:200 — verify it is wired
- **P3** Close: AGENT-016: Activity Feed Agent (service implemented) — rapidtechnologiesllc-byte/WROS-Master#38; OPEN_ITEMS.md:200 — verify it is wired
- **P3** Close: AGENT-018: Culture Agent (service implemented) — rapidtechnologiesllc-byte/WROS-Master#40; OPEN_ITEMS.md:200 — verify it is wired

### Data/Migration (12)

- **P1** Finish and release job kinds (delivery PR 1): staged work for #588 (job_kinds model, guards, one-time classification, Admin -> System -> Job Kinds) is uncommitted; dry run on the masked prod copy, then real run — rapidtechnologiesllc-byte/WROS-Master#588; docs/RECRUITMENT_VS_WORKFORCE_DESIGN.md:242-245; git status (staged files) — in progress
- **P1** Recruitment vs Workforce migration: split client demands with external hiring, historical requisitions for past hires, earmarks and allocation links, with ledger, dry-run parity report approved before the real run — docs/RECRUITMENT_VS_WORKFORCE_DESIGN.md:161-221
- **P1** Load clients, projects and allocations from the operating model workbook (employees loaded 2026-11-05) — auto-memory `next_session_autonomy_backlog.md` (2026-11-05)
- **P1** Answer the 23 held employee rows and load the 5 held Corporate rows — auto-memory `next_session_autonomy_backlog.md` (2026-11-05) — **needs CEO decision**
- **P2** Check imported hire dates (roster dates look like FY start) and designations mapped from directory titles — auto-memory `next_session_autonomy_backlog.md` (2026-11-05) — **needs CEO decision**
- **P2** Clear the stale hand-off tasks that predate Thunder acting on replies and find why people still get them — auto-memory `next_session_autonomy_backlog.md` (2026-11-05); OPEN_ITEMS.md:27
- **P2** Delete junk and test candidate records in production (via the UI) — auto-memory `next_session_autonomy_backlog.md` (2026-11-05) — **needs CEO decision**
- **P2** Seat managers in the org chart before importing their reports (imports refuse anyone whose manager has no seat) — OPEN_ITEMS.md:42 — **needs CEO decision** — verify: 55 employees loaded 2026-11-05
- **P3** Build: Import from Greenhouse / Lever (S-342/HRMS-1307, not-done) — docs/OPEN_REQUIREMENTS_BACKLOG.md:180 — **needs CEO decision**
- **P3** Drop the unreferenced `demands` table once Job = Demand has settled — HANDOFF.md:35
- **P3** Reconcile `api_keys_config.created_by/updated_by` varchar vs model — HANDOFF.md:19
- **P3** Read the production Reported Issues list (Admin -> System -> Reported Issues) into this backlog; the old DEFECTS_LOG.md entries were migrated there — commit 5ea6a25d (#585) — production data, not readable from the repo

### Frontend/UX (11)

- **P1** Browser walk-through of screens shipped untested: My Tasks submit feedback / candidate did not join, Add employee with Partner (Function shows All functions), hiring stage and Create Offer, candidate merge, Manage Functions org-level checkbox — auto-memory `next_session_autonomy_backlog.md` (2026-11-05)
- **P2** Finish: Portal Notification Center (S-105/HRMS-P210, partial) — docs/OPEN_REQUIREMENTS_BACKLOG.md:257 — verify: code touched after 2026-08-22
- **P2** Table column customisation and sorting on every list screen — backend/app/DEFECTS_LOG.md:513
- **P3** Finish: Core Navigation & Search Shell (S-209/HRMS-0111, cant-determine) — docs/OPEN_REQUIREMENTS_BACKLOG.md:41 — verify: code touched after 2026-08-22
- **P3** Replace floating toasts with screen-level inline errors (convention adopted, old usages remain) — backend/app/DEFECTS_LOG.md:338
- **P3** Revenue screen / allocations / submissions should never ask for raw UUIDs — backend/app/DEFECTS_LOG.md:77, backend/app/DEFECTS_LOG.md:134; rapidtechnologiesllc-byte/WROS-Master#406 — verify: possibly done -- shared AllocationForm (4043c607)
- **P3** Opportunity pipeline kanban cards should be clickable and drive work — backend/app/DEFECTS_LOG.md:109 — verify
- **P3** Bulk import UX: disabled 'coming soon' types, progress polling, import analytics; job/employee/bank-statement bulk import — C:\dev\defect_log.md:152-202 — verify: employee import and bank reconciliation exist now
- **P3** Close: BX-HRMS-DEFECT-002: Role template auto-created on New button — rapidtechnologiesllc-byte/WROS-Master#41; OPEN_ITEMS.md:202-203 — fixed/obsolete
- **P3** Close: BX-HRMS-DEFECT-003: Administration navigation structure incorrect — rapidtechnologiesllc-byte/WROS-Master#42; OPEN_ITEMS.md:202-203 — fixed/obsolete
- **P3** Close: BX-HRMS-DEFECT-004: Create user form UX issues — rapidtechnologiesllc-byte/WROS-Master#43; OPEN_ITEMS.md:202-203 — fixed/obsolete

### Testing/Quality (242)

- **P1** Frontend has no automated tests and there are no E2E browser tests — OPEN_ITEMS.md:179
- **P2** Load test the critical paths for 1500-HC scale (never executed) — OPEN_ITEMS.md:178; docs/OPEN_REQUIREMENTS_BACKLOG.md:76 (S-079 production load testing) — merged with S-079
- **P2** ESLint pre-commit gate never ran (skipped without global eslint, failed falsely with ESLint 10) — rapidtechnologiesllc-byte/WROS-Master#406 (point 6) — verify
- **P2** Test database role ('root' does not exist) blocks regression runs — rapidtechnologiesllc-byte/WROS-Master#375 — verify: suite now runs on TEST_DATABASE_URL (1816 pass 2026-11-09); then close
- **P3** Close fixed issues: Gate #44 regression suite (#381), rejections not recorded (#382), thunder_memory_update (#383) — rapidtechnologiesllc-byte/WROS-Master#381, rapidtechnologiesllc-byte/WROS-Master#382, rapidtechnologiesllc-byte/WROS-Master#383; OPEN_ITEMS.md:117, OPEN_ITEMS.md:91, OPEN_ITEMS.md:205 — fixed in code
- **P3** Close #373 (vague db.commit error handling) and replace with targeted items — rapidtechnologiesllc-byte/WROS-Master#373; OPEN_ITEMS.md:206
- **P3** Close auto-scan issue for deleted file `add_bu_id_column.py` — rapidtechnologiesllc-byte/WROS-Master#85, rapidtechnologiesllc-byte/WROS-Master#130 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `alembic/versions/b3d5f7a9c1e4_add_users_email_otp.py` — rapidtechnologiesllc-byte/WROS-Master#86, rapidtechnologiesllc-byte/WROS-Master#131 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `alembic/versions/d8f2b4a6c9e1_add_candidate_email_2fa.py` — rapidtechnologiesllc-byte/WROS-Master#87, rapidtechnologiesllc-byte/WROS-Master#132 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/activity_feed.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#88, rapidtechnologiesllc-byte/WROS-Master#133 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/activity_timeline.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#89, rapidtechnologiesllc-byte/WROS-Master#134 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/admin_queue.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#90, rapidtechnologiesllc-byte/WROS-Master#135 — duplicate issues
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/agent_daily_standup.py` — rapidtechnologiesllc-byte/WROS-Master#91, rapidtechnologiesllc-byte/WROS-Master#136 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/agent_kill_switch.py` — rapidtechnologiesllc-byte/WROS-Master#92, rapidtechnologiesllc-byte/WROS-Master#137 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/agent_operations.py` — rapidtechnologiesllc-byte/WROS-Master#93, rapidtechnologiesllc-byte/WROS-Master#138 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/agent_performance_dashboard.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#94, rapidtechnologiesllc-byte/WROS-Master#139 — duplicate issues
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/agent_standups.py` — rapidtechnologiesllc-byte/WROS-Master#95, rapidtechnologiesllc-byte/WROS-Master#140 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/agent_standups_dashboard.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#96, rapidtechnologiesllc-byte/WROS-Master#141 — duplicate issues
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/agent_state_dashboard.py` — rapidtechnologiesllc-byte/WROS-Master#97, rapidtechnologiesllc-byte/WROS-Master#142 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/agents.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#98, rapidtechnologiesllc-byte/WROS-Master#143 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/ai_recruiter_assignment.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#100, rapidtechnologiesllc-byte/WROS-Master#145 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/allocations.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#101, rapidtechnologiesllc-byte/WROS-Master#146 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/auth.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#102, rapidtechnologiesllc-byte/WROS-Master#147 — duplicate issues
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/autonomous_job_management.py` — rapidtechnologiesllc-byte/WROS-Master#103, rapidtechnologiesllc-byte/WROS-Master#148 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/bi_explorer.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#104, rapidtechnologiesllc-byte/WROS-Master#149 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/bu_context.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#105, rapidtechnologiesllc-byte/WROS-Master#150 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/buddy_program.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#106, rapidtechnologiesllc-byte/WROS-Master#151 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/bulk_engagement.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#107, rapidtechnologiesllc-byte/WROS-Master#152 — duplicate issues
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/business_metrics.py` — rapidtechnologiesllc-byte/WROS-Master#108, rapidtechnologiesllc-byte/WROS-Master#153 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/candidate_portal.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#109, rapidtechnologiesllc-byte/WROS-Master#154 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/candidate_rejection.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#110, rapidtechnologiesllc-byte/WROS-Master#155 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/candidate_status.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#111, rapidtechnologiesllc-byte/WROS-Master#156 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/candidates.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#112, rapidtechnologiesllc-byte/WROS-Master#157 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/candidates/crud.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#113, rapidtechnologiesllc-byte/WROS-Master#158 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/checklists.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#115, rapidtechnologiesllc-byte/WROS-Master#160 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/clients.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#116, rapidtechnologiesllc-byte/WROS-Master#161 — duplicate issues
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/complete_workflow.py` — rapidtechnologiesllc-byte/WROS-Master#117, rapidtechnologiesllc-byte/WROS-Master#162 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/conversation_search.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#118, rapidtechnologiesllc-byte/WROS-Master#163 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/core_pull.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#119, rapidtechnologiesllc-byte/WROS-Master#164 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/create_job.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#120, rapidtechnologiesllc-byte/WROS-Master#165 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/defect_reporting.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#121, rapidtechnologiesllc-byte/WROS-Master#166 — duplicate issues
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/demand_confirmation.py` — rapidtechnologiesllc-byte/WROS-Master#122, rapidtechnologiesllc-byte/WROS-Master#167 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/documents.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#124, rapidtechnologiesllc-byte/WROS-Master#169 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/email.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#125, rapidtechnologiesllc-byte/WROS-Master#170 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/employee_conversion.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#126, rapidtechnologiesllc-byte/WROS-Master#171 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/employee_milestones.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#127, rapidtechnologiesllc-byte/WROS-Master#172 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/employee_referrals.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#128, rapidtechnologiesllc-byte/WROS-Master#173 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/employees.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#129, rapidtechnologiesllc-byte/WROS-Master#174 — duplicate issues
- **P3** Re-scan `app/api/v1/endpoints/ai_agent.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#144
- **P3** Re-scan `app/api/v1/endpoints/certifications_admin.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#159
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/doctor_traces_dashboard.py` — rapidtechnologiesllc-byte/WROS-Master#168 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/error_log.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#175
- **P3** Re-scan `app/api/v1/endpoints/executive_signal.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#176
- **P3** Re-scan `app/api/v1/endpoints/expenses.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#177
- **P3** Re-scan `app/api/v1/endpoints/finance_monitoring.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#178
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/finance_operations.py` — rapidtechnologiesllc-byte/WROS-Master#179 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/flash.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#180
- **P3** Re-scan `app/api/v1/endpoints/flash_interview.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#181
- **P3** Re-scan `app/api/v1/endpoints/hiring_manager_validation.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#182
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/hiring_workflow.py` — rapidtechnologiesllc-byte/WROS-Master#183 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/htd_intake_pause.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#184
- **P3** Re-scan `app/api/v1/endpoints/intervention_queue.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#185
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/interview_decision.py` — rapidtechnologiesllc-byte/WROS-Master#186 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/interviews.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#187
- **P3** Re-scan `app/api/v1/endpoints/invoices.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#188
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/invoices_s316.py` — rapidtechnologiesllc-byte/WROS-Master#189 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/message_templates.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#190
- **P3** Re-scan `app/api/v1/endpoints/mfa.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#191
- **P3** Re-scan `app/api/v1/endpoints/msgraph.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#192
- **P3** Re-scan `app/api/v1/endpoints/my_timesheet.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#193
- **P3** Re-scan `app/api/v1/endpoints/newsletter.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#194
- **P3** Re-scan `app/api/v1/endpoints/notifications.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#195
- **P3** Re-scan `app/api/v1/endpoints/offer_letters.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#196
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/onboarding_orchestrator.py` — rapidtechnologiesllc-byte/WROS-Master#197 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/opportunities.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#198
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/opportunity_tracker.py` — rapidtechnologiesllc-byte/WROS-Master#199 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/org_structure.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#200
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/permission_composition.py` — rapidtechnologiesllc-byte/WROS-Master#201 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/portal_messages.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#202
- **P3** Re-scan `app/api/v1/endpoints/preonboarding.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#203
- **P3** Re-scan `app/api/v1/endpoints/projects.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#204
- **P3** Re-scan `app/api/v1/endpoints/public_chat.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#205
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/queue.py` — rapidtechnologiesllc-byte/WROS-Master#206 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/queue_dashboard.py` — rapidtechnologiesllc-byte/WROS-Master#207 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/queues.py` — rapidtechnologiesllc-byte/WROS-Master#208 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/resource_forecast.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#209
- **P3** Re-scan `app/api/v1/endpoints/resource_management.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#210
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/resume_versions.py` — rapidtechnologiesllc-byte/WROS-Master#211 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/revenue.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#212
- **P3** Re-scan `app/api/v1/endpoints/revenue_recognition.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#213
- **P3** Re-scan `app/api/v1/endpoints/risk_dashboard.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#214
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/role_based_dashboard.py` — rapidtechnologiesllc-byte/WROS-Master#215 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/role_template_modules.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#216
- **P3** Re-scan `app/api/v1/endpoints/role_templates.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#217
- **P3** Re-scan `app/api/v1/endpoints/sla_breach.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#218
- **P3** Re-scan `app/api/v1/endpoints/slm_feedback.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#219
- **P3** Re-scan `app/api/v1/endpoints/spartan_forecasting.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#220
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/spartan_integration.py` — rapidtechnologiesllc-byte/WROS-Master#221 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/spartan_phalanx.py` — rapidtechnologiesllc-byte/WROS-Master#222 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `app/api/v1/endpoints/strategic_consul.py` — rapidtechnologiesllc-byte/WROS-Master#223 — file no longer in the repo
- **P3** Re-scan `app/api/v1/endpoints/submissions.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#224
- **P3** Re-scan `app/api/v1/endpoints/system_config.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#225
- **P3** Re-scan `app/api/v1/endpoints/system_health.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#226
- **P3** Re-scan `app/api/v1/endpoints/tasks.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#227
- **P3** Re-scan `app/api/v1/endpoints/tenants.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#228
- **P3** Re-scan `app/api/v1/endpoints/thunder.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#229
- **P3** Re-scan `app/api/v1/endpoints/thunder_analytics.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#230
- **P3** Re-scan `app/api/v1/endpoints/tickets.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#231
- **P3** Re-scan `app/api/v1/endpoints/timesheets.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#232
- **P3** Re-scan `app/api/v1/endpoints/training_dashboards.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#233
- **P3** Re-scan `app/api/v1/endpoints/users.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#234
- **P3** Re-scan `app/api/v1/endpoints/users_access_control.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#235
- **P3** Re-scan `app/api/v1/endpoints/whatsapp_webhook.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#236
- **P3** Re-scan `app/api/v1/endpoints/work_orders.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#237
- **P3** Re-scan `app/api/v1/routes.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#238
- **P3** Close auto-scan issue for deleted file `app/api/v1/routes_master.py` — rapidtechnologiesllc-byte/WROS-Master#239 — file no longer in the repo
- **P3** Re-scan `app/core/dependencies.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#240
- **P3** Re-scan `app/core/graph_auth.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#241
- **P3** Close auto-scan issue for deleted file `app/core/permission_decorators.py` — rapidtechnologiesllc-byte/WROS-Master#242 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `app/core/permission_enforcement.py` — rapidtechnologiesllc-byte/WROS-Master#243 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `app/core/pytest_no_silent_failures.py` — rapidtechnologiesllc-byte/WROS-Master#244 — file no longer in the repo
- **P3** Re-scan `app/middleware/auth_middleware.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#245
- **P3** Re-scan `app/models/newsletter.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#246
- **P3** Close auto-scan issue for deleted file `app/routes/api_v1_invoices.py` — rapidtechnologiesllc-byte/WROS-Master#247 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `app/routes/api_v1_pnl.py` — rapidtechnologiesllc-byte/WROS-Master#248 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `app/routes/api_v1_revenue.py` — rapidtechnologiesllc-byte/WROS-Master#249 — file no longer in the repo
- **P3** Re-scan `app/seeds/init_resources.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#250
- **P3** Re-scan `app/services/abandonment_scoring_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#251
- **P3** Close auto-scan issue for deleted file `app/services/agent_event_service.py` — rapidtechnologiesllc-byte/WROS-Master#252 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `app/services/agent_kill_switch_service.py` — rapidtechnologiesllc-byte/WROS-Master#253 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `app/services/agent_shield_service.py` — rapidtechnologiesllc-byte/WROS-Master#254 — file no longer in the repo
- **P3** Re-scan `app/services/ai_conversation_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#255
- **P3** Re-scan `app/services/autonomous_job_closure_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#256
- **P3** Re-scan `app/services/bulk_engagement_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#257
- **P3** Re-scan `app/services/calendar_matching_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#258
- **P3** Re-scan `app/services/candidate_rejection_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#259
- **P3** Re-scan `app/services/candidate_scoring_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#260
- **P3** Re-scan `app/services/cfo_agent_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#261
- **P3** Re-scan `app/services/channel_processors.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#262
- **P3** Re-scan `app/services/compensation_scoring_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#263
- **P3** Re-scan `app/services/core_pull_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#264
- **P3** Re-scan `app/services/daily_digest_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#265
- **P3** Re-scan `app/services/desire_profile_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#266
- **P3** Re-scan `app/services/desire_signal_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#267
- **P3** Re-scan `app/services/document_collection_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#268
- **P3** Re-scan `app/services/document_task_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#269
- **P3** Re-scan `app/services/drop_risk_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#270
- **P3** Re-scan `app/services/email_first_engagement_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#271
- **P3** Re-scan `app/services/employee_conversion_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#272
- **P3** Re-scan `app/services/employee_mental_health_agent_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#273
- **P3** Re-scan `app/services/employee_referral_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#274
- **P3** Re-scan `app/services/engagement_metrics_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#275
- **P3** Re-scan `app/services/expense_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#276
- **P3** Re-scan `app/services/facts_extraction_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#277
- **P3** Re-scan `app/services/finance_agent.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#278
- **P3** Re-scan `app/services/flash_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#279
- **P3** Re-scan `app/services/follow_up_scheduler_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#280
- **P3** Re-scan `app/services/ghosting_detection_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#281
- **P3** Re-scan `app/services/hiring_manager_validation_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#282
- **P3** Close auto-scan issue for deleted file `app/services/hiring_workflow_service.py` — rapidtechnologiesllc-byte/WROS-Master#283 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `app/services/hm_validation_service.py` — rapidtechnologiesllc-byte/WROS-Master#284 — file no longer in the repo
- **P3** Re-scan `app/services/hr_agent_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#285
- **P3** Re-scan `app/services/intervention_queue_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#286
- **P3** Re-scan `app/services/interview_confirmation_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#287
- **P3** Close auto-scan issue for deleted file `app/services/interview_decision_service.py` — rapidtechnologiesllc-byte/WROS-Master#288 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `app/services/interview_feedback_notification_service.py` — rapidtechnologiesllc-byte/WROS-Master#289 — file no longer in the repo
- **P3** Re-scan `app/services/interview_feedback_task_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#290
- **P3** Re-scan `app/services/interview_no_show_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#291
- **P3** Re-scan `app/services/interview_reminder_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#292
- **P3** Re-scan `app/services/interview_reschedule_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#293
- **P3** Re-scan `app/services/interview_sequencing_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#294
- **P3** Re-scan `app/services/job_approval_workflow_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#295
- **P3** Re-scan `app/services/joining_readiness_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#296
- **P3** Re-scan `app/services/lifecycle_communication_linking_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#297
- **P3** Re-scan `app/services/linkedin_sourcing_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#298
- **P3** Re-scan `app/services/mellow_keepwarm_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#299
- **P3** Re-scan `app/services/motivation_engine_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#300
- **P3** Re-scan `app/services/newsletter_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#301
- **P3** Re-scan `app/services/no_response_detection_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#302
- **P3** Re-scan `app/services/notification_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#303
- **P3** Close auto-scan issue for deleted file `app/services/offer_decision_service.py` — rapidtechnologiesllc-byte/WROS-Master#304 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `app/services/offer_faq_service.py` — rapidtechnologiesllc-byte/WROS-Master#305 — file no longer in the repo
- **P3** Re-scan `app/services/offer_readiness_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#306
- **P3** Re-scan `app/services/offer_release_notification_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#307
- **P3** Re-scan `app/services/onboarding_agent_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#308
- **P3** Close auto-scan issue for deleted file `app/services/onboarding_workflow_service.py` — rapidtechnologiesllc-byte/WROS-Master#309 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `app/services/operational_accountability_agents.py` — rapidtechnologiesllc-byte/WROS-Master#310 — file no longer in the repo
- **P3** Re-scan `app/services/org_hierarchy_validator.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#311
- **P3** Re-scan `app/services/outreach_campaign_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#312
- **P3** Re-scan `app/services/partner_incentive_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#313
- **P3** Re-scan `app/services/partner_success_agent_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#314
- **P3** Re-scan `app/services/permission_helper.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#315
- **P3** Close auto-scan issue for deleted file `app/services/personal_goal_agents.py` — rapidtechnologiesllc-byte/WROS-Master#316 — file no longer in the repo
- **P3** Re-scan `app/services/personal_intelligence_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#317
- **P3** Re-scan `app/services/portal_message_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#318
- **P3** Re-scan `app/services/reactivation_campaign_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#319
- **P3** Re-scan `app/services/referral_access_control.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#320
- **P3** Re-scan `app/services/relation_building_agent_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#321
- **P3** Re-scan `app/services/resource_forecast_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#322
- **P3** Re-scan `app/services/resource_management_agent_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#323
- **P3** Re-scan `app/services/response_parser_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#324
- **P3** Re-scan `app/services/resume_completeness_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#325
- **P3** Re-scan `app/services/resume_parser_agent.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#326
- **P3** Close auto-scan issue for deleted file `app/services/resume_parsing_service.py` — rapidtechnologiesllc-byte/WROS-Master#327 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `app/services/role_template_seed.py` — rapidtechnologiesllc-byte/WROS-Master#328 — file no longer in the repo
- **P3** Re-scan `app/services/task_assignment_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#329
- **P3** Re-scan `app/services/task_escalation_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#330
- **P3** Close auto-scan issue for deleted file `app/services/thunder_autonomous_loop.py` — rapidtechnologiesllc-byte/WROS-Master#331 — file no longer in the repo
- **P3** Re-scan `app/services/thunder_explanation_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#332
- **P3** Re-scan `app/services/thunder_pause_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#333
- **P3** Re-scan `app/services/timesheet_nag_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#334
- **P3** Re-scan `app/services/timesheet_service.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#335
- **P3** Re-scan `app/tasks/__init__.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#336
- **P3** Re-scan `app/utils/agent_logger.py` with code_gate_validator, fix real findings, close the auto-scan issue — rapidtechnologiesllc-byte/WROS-Master#337
- **P3** Close auto-scan issue for deleted file `apply_phase2_migration.py` — rapidtechnologiesllc-byte/WROS-Master#338 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `assign_bu_to_partner.py` — rapidtechnologiesllc-byte/WROS-Master#339 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `bootstrap_superuser_only.py` — rapidtechnologiesllc-byte/WROS-Master#340 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `cleanup_bad_permissions.py` — rapidtechnologiesllc-byte/WROS-Master#341 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `cleanup_old_users_resource.py` — rapidtechnologiesllc-byte/WROS-Master#342 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `cleanup_resources.py` — rapidtechnologiesllc-byte/WROS-Master#343 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `consolidate_to_single_tenant.py` — rapidtechnologiesllc-byte/WROS-Master#344 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `create_recruiter_template.py` — rapidtechnologiesllc-byte/WROS-Master#345 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `create_standup_test_data.py` — rapidtechnologiesllc-byte/WROS-Master#346 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `debug_nav.py` — rapidtechnologiesllc-byte/WROS-Master#347 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `finalize_multitenant_setup.py` — rapidtechnologiesllc-byte/WROS-Master#348 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `fix_all_permissions.py` — rapidtechnologiesllc-byte/WROS-Master#349 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `fix_data_final.py` — rapidtechnologiesllc-byte/WROS-Master#350 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `fix_data_issues.py` — rapidtechnologiesllc-byte/WROS-Master#351 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `fix_permissions_comprehensive.py` — rapidtechnologiesllc-byte/WROS-Master#352 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `fix_superuser_tenant.py` — rapidtechnologiesllc-byte/WROS-Master#353 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `init_org_hierarchy.py` — rapidtechnologiesllc-byte/WROS-Master#354 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `init_resources_all_tenants.py` — rapidtechnologiesllc-byte/WROS-Master#355 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `init_role_permissions_proper.py` — rapidtechnologiesllc-byte/WROS-Master#356 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `init_roles.py` — rapidtechnologiesllc-byte/WROS-Master#357 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `init_wros_db.py` — rapidtechnologiesllc-byte/WROS-Master#358 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `migrations/seed_agent_performance_data.py` — rapidtechnologiesllc-byte/WROS-Master#359 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `migrations/seed_agent_state_data.py` — rapidtechnologiesllc-byte/WROS-Master#360 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `migrations/seed_real_business_data.py` — rapidtechnologiesllc-byte/WROS-Master#361 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `migrations/seed_realistic_business_data.py` — rapidtechnologiesllc-byte/WROS-Master#362 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `migrations/seed_scenario_data.py` — rapidtechnologiesllc-byte/WROS-Master#363 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `phase1_final.py` — rapidtechnologiesllc-byte/WROS-Master#364 — file no longer in the repo
- **P3** Close auto-scan issue for deleted file `phase1_reseed.py` — rapidtechnologiesllc-byte/WROS-Master#365 — file no longer in the repo

### Docs (7)

- **P2** Rewrite C:\dev\WROS-Master\CLAUDE.md: remove the DEPRECATED sections (90-second cycle, Spartan formation, LinkedIn/flash session logs), fix the deploy rule (Actions deploys again), drop credentials — C:\dev\WROS-Master\CLAUDE.md; auto-memory `manual_deploys_no_github_actions.md`
- **P2** Update or archive C:\dev\CLAUDE.md (2026-08-23 state, 50 issues, BUG-001/002) — C:\dev\CLAUDE.md
- **P2** Refresh HANDOFF.md (2026-10-08; says deploys are manual only and lists items fixed since) — HANDOFF.md:86
- **P3** Refresh the 'Signal today' column of OPEN_REQUIREMENTS_BACKLOG.md (story ids no longer in code) — OPEN_ITEMS.md:12; docs/OPEN_REQUIREMENTS_BACKLOG.md:6
- **P3** Mark docs/INDEX.md, ROUTES_QUICK_REFERENCE.md, API_ROUTES_INTEGRATION_GUIDE.md, MASTER_ROUTES_IMPLEMENTATION_EXAMPLE.md (2026-08 'production ready' route docs) historical or regenerate from the route table — docs/INDEX.md:1-5
- **P3** Architecture decision records and OpenAPI completeness (gate criteria 51-52) — C:\dev\WROS-Master\CLAUDE.md (Section 1 H)
- **P3** Incident runbooks per handler (gate criterion 34); only the queue processor runbook exists — backend/docs/QUEUE_PROCESSOR_RUNBOOK.md; CLAUDE.md Section 1 E
