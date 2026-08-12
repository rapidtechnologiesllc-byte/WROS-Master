# Defect Reports - Production


## [DEFECT-2026-08-12T02191132] CRITICAL - Admin Settings

**Reporter:** Admin (local dev) (Admin@blitzenx.com)
**Timestamp:** 2026-08-12T02:19:11.326476
**Severity:** CRITICAL
**Blocking Production Function:** Yes
**Screen:** Admin Settings

**Description:**
Hr USer & RBAC  should be merged and more meaning full right now HR is unable to create job, schedule interview

**Status:** OPEN
**Resolution:** Pending review

---

## [FEATURE-2026-08-12] Partner/BU Head Role Dashboards + Ad-Hoc Reporting Tool

**Requested by:** Avinash
**Timestamp:** 2026-08-12
**Type:** Feature request (backlog, not yet scheduled)
**Severity:** N/A (backlog)

**Description:**

Role-based dashboards for Partner and BU Head users:

1. Training & certification dashboard
   - Who is in the Buddy Program
   - Who is certified, and at what level
   - What the next steps are per person

2. Partner Dashboard
   - Current Demand
   - Pre-Onboarding Pipeline
   - Certifications
   - Buddy Program
   - Core Certified

Separately: install Power BI (or an equivalent ad-hoc reporting tool) inside WROS so Troy can freely select any table/any column for reporting, without needing a purpose-built screen per question.

**Status:** OPEN — backlog, not yet scoped or started.

---

## [FEATURE-2026-08-12T2] Unified CEO/Super User Executive Dashboard

**Requested by:** Avinash
**Timestamp:** 2026-08-12
**Type:** Feature request (backlog, not yet scheduled)
**Severity:** N/A (backlog)

**Description:**

When a CEO/Super User logs in, the landing screen should be a single unified
executive dashboard, not the current experience of navigating across
separate screens (CEO FY Progress, Jobs, etc. as distinct sidebar items).

Should combine on one screen:
- Jobs (open positions overview)
- New Hires
- In Onboarding (pipeline status)
- Full view of the entire org

Framed as replacing/superseding the standalone "CEO FY Progress" nav item
shown in the screenshot with one consolidated landing view. Related to the
already-known gap in CLAUDE.md history: "Implement role-based default
dashboards ... Currently all roles see same dashboard."

**Status:** OPEN — backlog, not yet scoped or started.

---

## [DEFECT-2026-08-12T3] Revenue screen requires manual project UUID entry — not autonomous

**Reporter:** Avinash
**Timestamp:** 2026-08-12
**Severity:** MEDIUM (not blocking — screen loads, underlying API calls return 200 — but unusable as designed)
**Screen:** /revenue (Revenue Leakage Detection, Timesheet-to-Revenue Reconciliation)

**Description:**

The Revenue Leakage Detection card (and the Timesheet-to-Revenue Reconciliation
card below it) requires the user to manually type a raw Project UUID plus a
period start/end before it will scan for anything. In practice nobody has
project UUIDs memorized, so this is effectively unusable — it always just
shows "No active leakage flags" because nobody can realistically trigger a
scan. There's no project picker/search, and no proactive scanning.

Should be autonomous instead: the system should run leakage/reconciliation
scans across all active projects on a schedule (or on relevant triggers, e.g.
invoice generation) and surface only the projects with real flags — the
manual per-project form should be a secondary "re-scan this one" action, not
the only way in. Same pattern as several other screens found this session
(Core-Pull scan, bench scan) that default to manual-trigger instead of
proactive detection.

Confirmed via direct testing: `/revenue/leakage` and
`/revenue/reconciliation/alerts` both return 200 OK — this is a design/UX gap,
not a backend crash.

**Status:** OPEN — backlog, not yet scoped or started.

---

## [DEFECT-2026-08-12T4] Opportunity Pipeline Kanban cards are static — not clickable/sortable, not driving work

**Reporter:** Avinash
**Timestamp:** 2026-08-12
**Severity:** MEDIUM
**Screen:** /opportunities (Opportunity Pipeline — Kanban view)

**Description:**

The Kanban stage cards (QUALIFICATION, PROSPECT, PROPOSAL, NEGOTIATION,
CONTRACT, ACTIVE, LOST) are static — not clickable to open/edit the
opportunity, not drag-and-drop sortable between stages. All stages currently
show $0 / "No opportunities," so the board isn't reflecting real pipeline
data or actually generating downstream work (tasks, follow-ups) from stage
changes. Bad UX as a Kanban board that can't be interacted with the way a
Kanban board normally works.

Related to [DEFECT-2026-08-12T3] (Revenue screen) and [FEATURE-2026-08-12]/
[FEATURE-2026-08-12T2] (dashboards) — part of the same pass of screens found
non-functional or non-agentic this session.

**Status:** OPEN — backlog, not yet scoped or started.

---

## [DEFECT-2026-08-12T5] Employee Allocations screen — same raw-UUID anti-pattern, real reference exists

**Reporter:** Avinash
**Timestamp:** 2026-08-12
**Severity:** MEDIUM
**Screen:** /allocations (Employee Allocations)

**Description:**

Same broken pattern as [DEFECT-2026-08-12T3] (Revenue) and Stage 1's Demand
Confirmation screen: `AllocationsScreen.js` requires typing raw Employee ID /
Demand ID / Project ID UUIDs into text boxes, one allocation at a time, with
no picker and no real list view — "No allocations yet" no matter what's
actually allocated, because nobody can realistically use raw UUID entry.

Avinash provided the actual bar to hit: an external reference system
(JobDiva-style — matches the "real JobDiva client record shown as reference"
convention already used elsewhere in this codebase, e.g. ClientManagementScreen.js)
showing what a real assignment/placement list needs: a filterable, sortable,
paginated table with columns including Billing Company, Spread, Bill Rate,
Pay Rate, Job Title, Working State, Assignment Division, Bill Start/End, Pay
Start/End, Assignment Status, Client Contact, Primary Recruiter, Primary
Sales, Start Entered, Optional Ref#, Net Bill Rate — plus optional
candidate/employee-profile columns (DOB, Educational Qualification, Notice
Period, Employee Status, Vaccine Status, etc.) toggleable via a column editor.

This is a genuine redesign, not a small patch: `AllocationsScreen.js` needs
to become a real list/table screen (Excel export, column customization,
bulk actions matching the reference) with the single-allocation form as a
secondary "add one" action, not the whole screen.

**Status:** OPEN — backlog, not yet scoped or started.

---

## [DEFECT-2026-08-12T6] Log Expense — no mandatory receipt, no manager approval step, no per-user assignment

**Reporter:** Avinash
**Timestamp:** 2026-08-12
**Severity:** MEDIUM
**Screen:** /my-expenses (My Expenses — Log Expense)

**Description:**

Real backend machinery exists here (not building from zero): `expense_service.py`
has `approve_expense()` (sets `payment_status=APPROVED`, notifies finance),
and a real state-machine guard blocking `REIMBURSED` before `APPROVED`.
`FinanceOperationsScreen.js` has a working "Expense Review" panel with a
real Approve button. Confirmed genuine gaps on top of that real foundation:

1. **Receipt not mandatory** — `receipt_ref` is `Optional[str]` end to end
   (backend model + form UI). Nothing blocks submitting an expense with no
   receipt reference at all.
2. **No autonomous receipt validation** — nothing checks whether a
   submitted receipt is plausible/valid (amount matches, not a duplicate,
   legible, etc.) before it enters the approval queue.
3. **No reporting-manager approval step** — the only approval found is
   Finance's own review queue. There's no gate where the employee's direct
   manager signs off before it reaches Finance — it goes straight from
   "employee logs it" to "sits in Finance's shared pool."
4. **Partially wrong when first logged, corrected here:** the *initial*
   "please review/approve" step is a shared, unassigned Finance Operations
   queue — but `expense_service._create_mark_paid_task()` **does** already
   auto-create a real Task assigned to a specific finance user
   (`_finance_assignee()`) once an expense is approved, prompting them to
   mark it paid. So the Task-routing pattern is already used here for the
   *post-approval* step — just not for the initial review/approval step
   itself, which is still a shared pool. Real infrastructure either way;
   the gap is narrower than first described.
5. **Payment status validation** — partially real (the APPROVED-before-
   REIMBURSED guard exists server-side), but no UI action to actually mark
   an approved expense as paid/reimbursed was found in this pass — worth
   confirming whether that's missing entirely or just not yet located.

**Separate open question, also raised by Avinash in the same pass:** "My
Expenses" is deliberately a standalone nav item, not grouped under Finance
— per `navItems.js`'s own comment, this was Avinash's own prior call
("logged by employee, same posture as My Tasks/My Timesheet"). That now
conflicts with today's separate rule ("anything monetary stays in
finance") from the Sales-section nav discussion. Needs Avinash's call on
which wins — personal self-service framing, or monetary-stays-in-Finance.

**Status:** OPEN — backlog, not yet scoped or started.

---

## [DEFECT-2026-08-12T7] Timesheet approval has no notification/reminder — RM never knows one is waiting

**Reporter:** Avinash (traced from a live repro on /my-timesheet)
**Timestamp:** 2026-08-12
**Severity:** MEDIUM
**Screen:** Reporting Manager's approval flow (backend: timesheet_service.py)

**Description:**

`approve_timesheet()` is real and correctly RBAC-gated (HRMS-0902 BR-01:
only RM/Admin may approve). But per the module's own header comment,
`TimesheetApprovalReminderJob` (Monday 6 AM per spec) is "NOT wired to
work, not built here," and `timesheet.approved` event publish + employee/
approver email notifications are also not built. The approval gate exists;
nothing tells a reporting manager a timesheet is waiting for them. They'd
have to know to go looking.

**For contrast, confirmed solid in the same pass:** Finance validation
before invoicing is a real, hard-enforced rule (R-10) — `invoice_service.py`
raises `UnapprovedTimesheetBlocksInvoice` if any timesheet in the billing
period isn't APPROVED, "no partial." That half of the pipeline is correct
as built.

**Root prerequisite, not a separate fix:** timesheets can't even be created
today because [DEFECT-2026-08-12T5] (Employee Allocations screen) has no
way to actually assign an employee to a project — `get_my_active_allocations()`
requires a real `EmployeeAllocation` row that nothing in the UI can create.
Fix that first; this notification gap is the next thing blocking the same
pipeline stage after it.

**Status:** OPEN — backlog, not yet scoped or started.

---

## [DEFECT-2026-08-12T02191132] RESOLVED — HR / RBAC — job.view / job.create missing for HR roles

**Resolved by:** Claude (2026-08-12 session)

Root cause: `ROLE_PERMISSIONS_SEED` in `app/services/rbac_service.py` never
granted `job.view`/`job.create` to `HR Manager`, `HR Operations`, or `HRBP`
— `interview.manage` was present, but the schedule-interview flow's own
`handleScheduleInterview()` looks up the candidate's job application first,
which needs `job.view`, so it broke one step before reaching the interview
call. Fixed: `job.create`+`job.view` added to HR Manager (matches its "Full
HR control within BU" description), `job.view` added to HR Operations/HRBP
(narrower roles, not extended to job creation without being asked). Verified
directly against the local DB after a clean backend restart — RBAC seed
(`RBACService.seed_roles_and_permissions`) picked up the change and all
three roles now carry the correct grants.

**Status:** RESOLVED.

---

## [FEATURE-2026-08-12T3] RBAC / HR screen redesign — HubSpot-style module x verb permission model

**Requested by:** Avinash
**Timestamp:** 2026-08-12
**Type:** Feature request (backlog, scoped but not yet built)
**Severity:** N/A (backlog) — but blocks a clean access model as more roles/modules get added

**Description:**

Avinash's direct spec (with HubSpot's Users/Permissions screen as the
reference UX — screenshots provided: Users list with Seat/Access columns,
a permissions-editor with per-module View/Create/Edit/Delete/Merge toggles,
and a "Manage user access" wizard with Manual/Super Admin/Template/From-
scratch entry points):

**New role-access spec to implement** (supersedes/refines the current
`ROLE_ATTRIBUTES_SEED`/`ROLE_PERMISSIONS_SEED` in `rbac_service.py`):
- HR, Recruiter, Recruitment Manager, Hiring Manager, BU Head, Partner, CEO
  (i.e. every role except Employee, Consultant, Candidate, Finance) can:
  open a job, submit a candidate, schedule an interview.
- Hiring Manager: additionally provides the hiring decision.
- BU Head: final approval on budget + candidate prior to Hire.
- HR: can initiate onboarding, add employee.
- Partner: everything, but scoped to their own BU only (not org-wide) —
  note this is a change from the current seed, where Partner has
  `global_access: True` (org-wide). Needs explicit reconciliation.
- Super User: full org-wide read/edit access to everything, no exceptions.

**Redesign asks:**
1. Convert "seat assignment" framing to role assignment — this codebase
   has no real "seat" concept today (that's purely HubSpot's own licensing
   construct), so this is really "make Role the single, clear access unit
   in the UI," matching what the backend already does structurally.
2. Left-hand module list (Candidates, Jobs, Interviews, Offers, Employees,
   Documents, Invoices, Timesheets, Expenses, Projects, Revenue,
   Opportunities, Demand, Clients, RBAC/Admin, Reports, ...) each with
   View/Create/Edit/Delete/Merge toggles where applicable per module —
   replacing the current `RbacSettingsScreen.js`, which is a flat set of
   raw ID-keyed dropdown forms (Assign Role, Assign BU, Role Permission
   Mapping as two independent ID selects, etc.) — the same raw-ID-picker
   anti-pattern already flagged on Allocations/Revenue/Demand screens this
   session, now confirmed on the RBAC screen itself too.
3. A "Manage user access" flow per HubSpot's own pattern (manually assign /
   copy a template role / start from scratch), rather than the current
   screen's disconnected micro-forms.

**Not started — scoping notes for next session:**
- Current permission set (28 permissions, see `PERMISSIONS_SEED`) is far
  coarser than "per-module x per-verb" — e.g. there's one `offer.manage`
  covering create/edit/approve/reject, not separable verbs. Building the
  HubSpot-style grid needs the permission model itself expanded to real
  view/create/edit/delete/merge granularity, not built anywhere in the
  current schema.
- Partner's BU-scoping change is a real behavior change to an existing
  attribute (`global_access`) — flagged per CLAUDE.md's own rule that
  tenant/access-model changes touching existing behavior should be
  confirmed before building, even under the "requirements docs don't gate
  development" rule.

**Status:** OPEN — scoped, not yet built. Sizeable (permission-model
expansion + full screen rebuild), recommended as its own dedicated session.

---

## [FEATURE-2026-08-12T4] Toast/alert popups should be screen-level inline errors, not floating toasts

**Requested by:** Avinash
**Timestamp:** 2026-08-12
**Type:** Standing convention change (backlog — partially started)
**Severity:** N/A (UX consistency)

**Description:**

Avinash: remove toast-style error/warning popups; errors and warnings
should render at screen level (inline banner within the screen itself),
not as a floating toast. Going forward this is the standard for any screen
being touched; existing toast usages get converted as they're found/worked
on, not as one mass rewrite.

**Scope found this session:** `react-toastify` (`toast.success()`/
`toast.error()`/etc.) is used in **50 files** across
`OnboardingModule-Frontend-main/src`. Several screens already do the
correct pattern locally (a component-level `error`/`notice` state rendered
as an inline banner — e.g. `RbacSettingsScreen.js`, `OpportunityPipelineScreen.js`)
but *also* call `toast.*` in places, inconsistently, rather than committing
to one pattern.

**Done this session** (screens already being edited for other fixes):
- `OpportunityPipelineScreen.js`: `OpportunityCard`'s `handleMove()` used a
  native `alert()` on a failed stage transition — converted to an inline
  error banner on the card itself (`moveError` state).

**Not done — full 50-file conversion is its own task**, next session:
1. Add a shared `<InlineAlert>`/banner component to `components/ui` (formalize
   the ad hoc pattern already used in a few screens) so every screen doesn't
   hand-roll its own error/notice `div`.
2. Sweep all 50 `toast.*` call sites, converting each to the shared
   component's local `error`/`notice` state pattern.
3. Remove the `react-toastify` dependency once the last usage is converted.

**Status:** OPEN — convention adopted going forward; full existing-usage
sweep deferred to next session (50 files, mechanical but real effort).

---

## [FEATURE-2026-08-12T5] No linkage from Job/Candidate placement to a revenue-generating Work Order (PO/SOW) — Opportunity is not the only real-world source of revenue

**Reported by:** Avinash, with a real signed example document (Guidewire
Software SOW/PO for Rapid Consulting Services, PO "New PO", effective
2026-07-27, term through 2026-11-22, Testing Consultant role, 680 est.
hours @ $35/hr = $23,800 total, resource named in Appendix A, invoices to
Guidewire AP referencing the PO number)
**Timestamp:** 2026-08-12
**Severity:** HIGH — real revenue-recognition gap, adjacent to R-11 (financial
hard rule) per CLAUDE.md's own flagging convention
**Screens/flow:** Job creation → candidate sourcing/submission → placement,
and the entire revenue/Project layer

**Description:**

Avinash's exact framing: *"in reality this came in as an Adhoc requirement
and not as an opportunity -- We sourced a resume and submitted then it got
to placement. now from the job to this revenue where is the linkage and I
don't see you thinking it through."*

Investigated the actual data model to confirm the gap is real, not just a
UI gap:

- `Demand.source_type` (`app/models/demand.py`) already has exactly two
  values: `DIRECT` and `OPPORTUNITY` (`DEMAND_SOURCE_TYPES`). So a job/demand
  created directly for a client need -- the real-world case in the example
  SOW above, not sourced from a tracked sales Opportunity -- is already a
  valid, modeled path. Good foundation, but it dead-ends:
- Automatic Project creation (the thing that puts an engagement on the
  revenue/forecast radar) **only fires from one place**:
  `opportunity_service.transition_stage()` calling
  `create_project_from_won_opportunity()` when an Opportunity moves to WON.
- The generic `create_project()` in `project_service.py` exists and is real,
  but has exactly **one caller** -- the manual `POST /projects` endpoint in
  `app/api/v1/endpoints/projects.py`. Nothing calls it automatically when a
  `DIRECT`-sourced job's candidate gets placed/hired. A human has to already
  know a Project needs creating and manually re-enter client/rate/dates that
  live nowhere else in the system.
- **No PO/SOW/Work Order model exists anywhere in `app/models`** (confirmed
  via search: no `WorkOrder`, `work_order`, `po_number`, `sow_document`, or
  `contract_document` in any model file). The actual authoritative document
  that sets billing terms -- PO number, rate, term dates, named resource,
  invoicing contact, per the real example above -- has nowhere to live.
  `Opportunity`/`Demand` capture a revenue *estimate*; nothing captures the
  signed *authority* to bill, or links it to the specific candidate placed
  against the specific job.

**Net effect:** for a `DIRECT`-sourced job (arguably the more common
real-world case per this example, not the exception), there is currently
**no automatic path** from "candidate hired into this job" to "this
generates a Project/revenue record," and no way to attach the actual signed
PO/SOW as the system of record for billing terms. The only automatic
revenue linkage in the whole codebase is Opportunity-sourced.

**Not started -- this needs Avinash's confirmation before building**, per
CLAUDE.md's own rule that anything touching a financial hard rule (R-11)
stays high-blast-radius enough to confirm the approach first, even under
the "requirements docs don't gate development" rule. Recommended shape to
discuss next session:
1. A `WorkOrder`/engagement record (PO number, client, rate, term
   start/end, named resource, invoicing contact) linkable to a
   `Demand`/`Job` and to the `Candidate`/`Employee` placed against it.
2. Auto-create (or prompt to create) this record at the point a candidate
   is converted to Employee against a `DIRECT`-sourced job -- the same
   "no manual re-entry" principle `create_project_from_won_opportunity()`
   already uses for the Opportunity path, applied to the other real path.
3. Whether `create_project()` should fire from that same event for
   `DIRECT` demands, so both sourcing paths land on the same downstream
   revenue/Project machinery instead of two divergent ones.

**Status:** OPEN -- confirmed real via code investigation, not yet scoped
into a build plan. Flagged as financial-hard-rule-adjacent, needs Avinash's
explicit go-ahead on the shape before implementation starts.

---

## [DEFECT-2026-08-12T6] Opportunity Owner doesn't default from Client Owner — because "Client Owner" doesn't exist as real data anywhere

**Reported by:** Avinash — "if existing client for example I select BlitzenX
it is not defaulting based on the client management - client owner"; also
"owner field is still not populating, I'm super user, at least my name
should show up"
**Timestamp:** 2026-08-12
**Severity:** MEDIUM (workflow gap) / confirms a pre-existing known gap
**Screen:** Opportunity Pipeline create form; Client Management

**Description — two separate causes, both investigated and one fixed live:**

1. **"My name doesn't show up" — FIXED this session.** The Owner dropdown
   ([FEATURE-2026-08-12] Owner-scoping fix above) is correctly scoped to
   `employees` joined to `users`/`revenue.view`, but this local dev DB's
   `employees` table had **zero rows** — not even for the Super User/Admin
   accounts. Root cause: `Opportunity.owner_employee_id` is a hard FK to
   `employees.id`, and Super User/Partner/BU Head-style accounts (seeded
   directly into `users`, never run through candidate→employee conversion)
   never get an `employees` row at all under normal flows. Backfilled a
   minimal `Employee` row (linked via `wros_user_id`) for each of the 7
   seeded local-dev `Users` accounts so real named people (including
   Avinash's CEO account and the Admin account) now appear — verified live,
   both show up in the dropdown now. This is a **local dev data backfill
   only** — the underlying architectural question stands: should Opportunity
   ownership really require a full Employee record (a staffed, billable
   resource concept), when the people who actually own sales relationships
   (Super User/Partner/BU Head) may never have one? Worth revisiting
   together with [FEATURE-2026-08-12T5]'s WorkOrder design — same root
   tension between "billable staffed resource" and "person who owns a
   business relationship."

2. **"Should default from Client Owner" — NOT fixed, no data to default
   from.** Confirmed via search: there is **no `client_owner` field
   anywhere in the backend** — not on the `Client` model, not in any
   endpoint/schema. The only place "Client Owner" exists at all is
   `CandidateAssignJobModal.js` reading `selectedJob?.client_owner_name` —
   a frontend field with no backend source, matching this session's own
   CLAUDE.md note from the earlier Submit Job Modal work: *"Test jobs don't
   have hiring_manager_name, client_owner_name, department fields
   populated"* — i.e. this was already a known-unpopulated field before
   today, not something broken by this session's changes.

**Not started — needs real schema work, not wiring:**
1. Add an actual `owner_employee_id` (or similar) column to `Client`,
   surfaced and editable in Client Management.
2. Once real, wire the Opportunity create form: selecting a Client
   auto-populates (not locks) the Owner field from that Client's owner.
3. Decide, alongside item 1 above, whether Client/Opportunity "owner" should
   reference `employees` or `users` — the same tension the Super User gap
   exposed.

**Status:** OPEN. Owner-dropdown emptiness fixed live (dev data backfill);
Client→Owner auto-default needs a real Client.owner field built first —
flagged for next session, not rushed before this push.

---

## [FEATURE-2026-08-12T7] Table Column Customization & Sorting — Missing from ALL screens

**Reported by:** Avinash (2026-08-12)
**Timestamp:** 2026-08-12
**Type:** Feature request (architectural gap, Day 2)
**Severity:** HIGH — blocks autonomous data exploration
**Screens affected:** Clients, Candidates, Opportunities, Employees, Projects, Jobs, Allocations, Demands, Invoices, Expenses, and 10+ more

**Description:**

*"for example what if i want to add additional columns, or sort by something — none of them are available. you need to do this in almost all screens. might be a day 2 item but something very important is missed by you."*

Confirmed: No table in the system supports:
1. **Column visibility toggle** — newly exposed fields (business_unit_name, account_manager_name, line_type on Clients; probability_pct on Opportunities; department, bu_id on Employees) render in API responses but have no UI toggle to show/hide them in the list view.
2. **Sorting** — every table is hard-wired to a single sort order (e.g. `order_by(Client.company_name)`, `order_by(Opportunity.created_at.desc())`), no way for a user to click a column header to sort.
3. **Filtering** — limited to fixed filter controls on individual screens (Client status filter in ClientManagementScreen, Opportunity stage filter in OpportunityPipelineScreen), not a generalized filterable-column pattern.

**Impact:**
- Users can't customize views to their workflow — violates autonomy principle
- Data discovery is constrained to whatever the UI builder decided to show
- Each new field exposed at the API (business_unit_name, Client Owner, line_type, etc.) requires the field to be hard-coded into a row template — no way for a user to opt-in dynamically
- Blocks real-world usability: users need to filter by BU, sort by Client status/tier/owner, add/remove columns per task

**Architectural shape for Day 2:**
1. Create a shared `<DataTable>` component that accepts:
   - `columns`: Array of {key, label, sortable?, filterable?, visible?, type}
   - `rows`: Data array
   - `onColumnToggle`, `onSort`, `onFilter` callbacks
   - Persistence: Save user's column preferences to localStorage per screen
2. Migrate all existing hardcoded tables (Client list, Candidate list, Opportunity pipeline list view, Employees, Projects, etc.) to use this component.
3. Wire column names from API response schemas — a field in the API response can be surfaced as a column toggle without code changes (no "add customer_id, add tier, add bu_id" code commits — it's metadata-driven).
4. Extend to Kanban (Opportunity Pipeline stage columns should be sortable, filterable, draggable).

**Status:** OPEN — scoped as Day 2/architectural work. Blocks autonomous workflows until implemented.

---
