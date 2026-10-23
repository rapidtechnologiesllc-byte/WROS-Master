# WROS delivery-management gap research: Program and Project Manager view (Managed Services and Staff Augmentation)

**Repo:** `/home/user/WROS-Master`, `main` at `47108888` (2026-10-23). Read-only research; nothing was edited.
**Method:** I read the models, services, endpoints, scheduled-job registry, nav catalog (`backend/app/seeds/init_resources.py` RESOURCE_ROUTES) and frontend routes and screens. I also cross-checked OPEN_ITEMS.md, docs/OPEN_REQUIREMENTS_BACKLOG.md and docs/COMPANY_MODEL_DESIGN.md.
**Status key:** BUILT = reachable from the nav and works end to end in code. PARTIAL = exists but is broken, unwired, missing UI or missing data. MISSING = nothing found.
**Verification limits:** status comes from reading code only. Nothing was run against a database, and production config was not inspected. Items marked *(unverified)* depend on runtime or production state.

---

## 1. Verdict

WROS handles the **staff-augmentation cash chain** well. That chain runs from job to submission to client start date, then allocation (with bill rate), weekly timesheet, internal approval, and an invoice generated only from fully APPROVED timesheets. It continues through Finance approval, email, payment record and an earned-revenue P&L. The P&L uses loaded cost and bench cost and breaks down by partner, BU, company, client and line.

WROS is **not yet a delivery-management system**:
- **Projects are thin.** A project has no Project Manager, budget, start/end dates (no writer), SOW value, change requests, RAID, status/RAG, health score or client acceptance.
- **Fixed-price billing cannot work.** `FIXED_BID` exists as an enum, but milestones carry no amount, invoices are built only from timesheet hours, and the UI cannot select fixed bid.
- **Staff aug is missing its renewal and compliance layer:**
  - no rate card or margin floor at placement
  - no allocation edit/extend
  - no extension pipeline beyond a read-only 30/60/90 roll-off list
  - no client-side timesheet approval
  - no PO on invoices
  - no visa or work-authorization expiry
  - no replacement SLA
  - no consultant client-feedback loop
  - no leave or holiday calendars
- **Several money jobs may be switched off in production.** `auto_invoicing`, `ar_follow_up`, `timesheet_reminders` and `timesheet_draft_creation` are registered. The last recorded production setting (2026-10-13) enables only `thunder_engagement_sweep` *(unverified today)*.
- **No dashboards for these roles.** There is no Program Manager, Project Manager or Delivery Head dashboard. Home dashboards exist only for CEO, CFO, Partner and BU Head.

Net: a BU Head can see revenue and bench, but a PM cannot run a project or an account from WROS today.

---

## 2. Capability tables

### 2a. Program Manager: Managed Services (Core) lens

| Capability | Status | Evidence | Business impact |
|---|---|---|---|
| Program/account entity grouping projects | MISSING | No program model. `Project.client_id` is the only grouping (`models/project.py:66`); `client_partner` is free text (`project.py:110`). | Cannot roll up a multi-project Guidewire program (e.g. PolicyCenter + BillingCenter for one carrier) for steering reporting. |
| SOW / contract with value, dates, milestones | PARTIAL | Client-level MSA fields only: `Client.contract_start_date/end_date/contract_url` (`models/client.py:117-119`). `WorkOrder.sow_reference` is a free string (`models/work_order.py:42`). No SOW value. | No contracted-value baseline, so no burn %, no over-run alert and no revenue-at-risk for SOW expiry. |
| Billing models FP / T&M / retainer | PARTIAL | `BILLING_TYPES = ("TIME_AND_MATERIALS","FIXED_BID")` (`project.py:35`); no RETAINER. Create form never offers billing type (`frontend/src/screens/ProjectsScreen.js`, only `BUSINESS_TYPES`), so every project is T&M. Invoicing is timesheet-only (`services/invoice_service.py:110-196`). | Fixed-price and retainer (AMS/support) contracts cannot be invoiced from WROS; Finance invoices them by hand outside the P&L chain. |
| Budget vs actual burn (hours and $) | MISSING | No budget field on Project (grep "budget" in models finds only recruiting budgets). `_calculate_burn_rate_pct` (`services/client_revenue_dashboard_service.py:39`) needs FIXED_BID plus start/end dates, which no code path ever sets. | Over-runs on fixed bids are found at invoice time or never. One 20% over-run on a $500K FP project is $100K of margin. |
| EAC/ETC forecasting | MISSING | Only `calculate_project_expected_revenue` (`services/project_service.py:181`), labelled "Estimate only". It uses raw `base_salary_usd_cents` (line ~219), not the loaded cost the P&L uses. | No forward view of margin at completion; the estimate overstates margin (excludes statutory and overhead). |
| Change requests | MISSING | No model or endpoint (grep "change.?request" = 0 files). | Scope creep is delivered free; CR revenue is not tracked. |
| RAID log | MISSING | 0 files for raid/risk_log/issue log at project level. | Risks and dependencies (client environment access, Guidewire upgrade windows) live in spreadsheets; no escalation trail. |
| SLA/KPI tracking and client reporting packs | MISSING | `models/sla_breach.py` is candidate-engagement SLA (S-020), not client delivery SLA. Ticket SLA is the internal helpdesk (`models/ticket.py:88`). | Managed-services credits/penalties cannot be evidenced; no monthly service report. |
| Status reports (RAG) | MISSING | 0 files for status_report / rag_status. | Leadership has no weekly delivery truth; problems surface as escalations. |
| Governance cadence (SteerCo, QBR) | MISSING | 0 files for steering / QBR. | Renewals and upsell conversations are not scheduled or minuted. |
| Deliverable acceptance | PARTIAL | `ProjectMilestone` with due date, `is_complete`, `completion_date` (`project.py:126-146`); UI on Projects screen. No client sign-off, no acceptance date, no amount. | Milestone payments cannot be triggered; disputes over "done" have no record. |
| Project health scoring | MISSING | Model docstring says HRMS-1107/0807 not built (`project.py:11-16`). Backlog S-305, S-322. | No early warning across projects. |
| Profitability per project / per client | PARTIAL | Backend: `GET /revenue-chain/summary?group_by=project` (`api/v1/endpoints/revenue_chain.py:61-72`, groups in `services/revenue_chain_service.py:57`). UI: P&L shows by partner/BU/company/client and line level (`PnlScreen.js:186-221`) but **not by project**. | Loss-making projects hide inside a profitable client. Backlog S-331 (PARTIAL). |
| Program Manager / Delivery Head dashboard | MISSING | Home dashboards: ceo/cfo/partner/bu_head only (`frontend/src/routes/Approutes.jsx:96-113`, `core/authority.py:209`). Everyone else gets the recruiting Dashboard. | The people who run delivery have no landing view. |

### 2b. Project Manager: Managed Services (Core) lens

| Capability | Status | Evidence | Business impact |
|---|---|---|---|
| Create project, status lifecycle | BUILT | `POST /projects`, `POST /projects/{id}/status` (`api/v1/endpoints/projects.py:116,233`); Projects screen in nav (`init_resources.py` "projects"). | Works. |
| Project owner / PM field | MISSING | No PM/owner column on `Project` (`project.py:60-124`). | Cannot route tasks, alerts or approvals to the person accountable. |
| Project dates / edit project | PARTIAL | `start_date/end_date` exist (`project.py:116-117`) but `create_project` takes neither (`services/project_service.py:86-105`) and there is no update endpoint. | Burn %, roll-off and duration analytics are all blind. |
| Milestones | BUILT (basic) | `POST/GET /projects/{id}/milestones`, `/complete` (`projects.py:267-365`); delay_days derived. | Usable as a checklist; no payment or acceptance link. |
| Resource plan vs demand per project | PARTIAL | `GET /projects/{id}/unfilled-roles` (`projects.py:366`, `project_service.py:143`): open headcount per linked job vs ACTIVE allocations. No time-phased plan (FTE by week or month). | PM sees today's gaps, not next month's ramp-up. |
| Allocate people to the project | BUILT | `AllocationForm` on Projects screen; `POST /allocations` (`allocations.py:137`); bill rate and utilization_pct on allocation (`employee_allocation.py:68-75`). | Works. |
| Shadow / backup resources | PARTIAL | Non-billable allocation possible (`EmployeeAllocation.billable`, `employee_allocation.py:78`). No "shadow of X" link or backup designation. HTD `SHADOW_DELIVERY` is a training phase (`employee.py:54`). | Key-person risk on single-threaded Guidewire integrations is invisible. |
| Knowledge transfer / transition plans | MISSING | 0 files. | Transition-in and transition-out (common in managed services) are untracked; client churn risk at handover. |
| Time capture against project / tasks | BUILT | Timesheet per allocation, BILLABLE / NON_BILLABLE / LEAVE / HOLIDAY entries (`models/timesheet.py:33-34,56-57`); My Timesheet in nav. | Works for actual hours. Without budget there is no actual-vs-plan comparison. |
| Forecast vs actual at project level | MISSING | Forecast vs Actual is org/client revenue (`services/forecast_variance_service.py`, `GET /forecast-vs-actual`). | No project-level variance. |
| Client escalations at project level | MISSING | Escalations exist only against an employee (`models/employee_escalation.py`; `employees.py:519-560`; Employees screen). | Client complaints about a project (not a person) have no home. |

### 2c. Program Manager: Staff Augmentation ("SPECIALITY") lens

| Capability | Status | Evidence | Business impact |
|---|---|---|---|
| Rate cards (role x level x location x client) | MISSING | 0 files for rate card. Bill rate typed per job or allocation (`employee_allocation.py:75`, `Employee.billing_rate_usd_cents` `employee.py:134`). | Inconsistent pricing across recruiters and accounts; under-pricing is not caught. Backlog S-288 (AI pricing) NOT-DONE. |
| Margin per placement (bill vs loaded cost) | PARTIAL | Line-level margin per timesheet-week in P&L (`PnlScreen.js:165-176`, loaded cost via `CostBook` `revenue_chain_service.py:61`). **No margin check when a placement is created** (`employee_allocation_service.py:54+`, no cost or margin reference). Hiring affordability is a BU-level gate only (`hiring_affordability_service.py`). | A placement at $55/hr for a consultant who costs $58/hr loaded is accepted silently and loses money every hour. |
| Contract start/end per placement | BUILT (data) | `EmployeeAllocation.start_date/end_date` (`employee_allocation.py:69-70`); `WorkOrder.start_date/end_date` (`work_order.py:55-56`). | Data exists. |
| Extension / renewal pipeline ahead of roll-off | PARTIAL | Read-only roll-off list `GET /resource-forecast/expiring` 30/60/90 (`resource_forecast.py:45`, `resource_forecast_service.py:43`) on the Demand vs Bench screen. **No allocation edit/extend endpoint** (allocations.py has create/list/end only). No renewal status or owner. No alert task. | Each missed extension is unplanned bench. At ~$90/hr that is ~$15.6K/month of revenue lost per consultant, plus loaded bench cost. |
| PO / contract tracking per placement | PARTIAL | `WorkOrder` (PO number, bill/pay rate, dates) with `POST/GET /work-orders` only (`work_orders.py:73,125`); service has update/end/pause but no routes. **No frontend.** Not linked to invoices (no `po_number` anywhere outside work_order). No PO value or hours cap, no PO-expiry alert. | Client AP (especially VMS/MSP clients) rejects or delays invoices without a valid PO. Hours past PO expiry may be unbillable. |
| Client timesheet approval (client-side approver) | PARTIAL | Columns exist but nothing reads or writes them from UI: `EmployeeAllocation.timesheet_approver_email` (`employee_allocation.py:74`), `Timesheet.client_approver_email` (`timesheet.py:74`); `ClientContact.role_type` TIMESHEET_APPROVER (`client.py:51`). Approval routes only to internal managers (`services/timesheet_approval_service.py:1-25,65`). Backlog S-182/183/184 NOT-DONE. | Invoices go out on internally approved hours. A client dispute later forces credit notes and stretches DSO. |
| Consultant performance and client feedback | MISSING | `Submission.client_feedback` is pre-hire only (`submission.py:89`). Performance store exists (`models/performance_store.py`) but has no client-feedback events. Backlog S-355 (manager weekly input) NOT-DONE. | Early warnings of a consultant being released are missed; there is no evidence for rate increases. |
| Replacement SLA (time to replace) | MISSING | Only `SpecialtyPoolReplacementPlan` (internal Core pull, `models/core_pull.py:57`). | Client asks for a replacement in 10 days; nobody is timing it, and the seat (revenue) is lost to a competitor. |
| Bench-to-billable conversion | PARTIAL | Bench screen: bench days, loss vs earnings (`frontend/src/screens/BenchScreen.js`, `services/bench_service.py:152`). Bench matching (`resource_management.py` endpoints `/scan`, `/recommendations`, `/demands/{id}/matching-bench-resources`). No conversion-rate or time-to-deploy KPI. Backlog S-332 PARTIAL. | Bench is visible (good) but not managed to a target. |
| Visa / work authorization and compliance expiry | MISSING | `Employee.visa_status` free text, no expiry (`employee.py:144`); `EmployeeDocument` type VISA with no expiry date (`employee.py:220-226`); BGV is pre-joining only (`models/background_verification.py`). Backlog S-164 (work-auth filter) NOT-DONE. | H-1B/LCA worksite or expiry lapses mean an unlawful billing exposure in the US, and I-9 penalties per form. India BGV re-checks demanded by insurer clients are untracked. |
| Utilization targets per person/role | PARTIAL | Single constant `LOW_UTILIZATION_THRESHOLD_PCT = 50` (`services/resource_management_service.py:40`). Snapshots are written only by a manual `POST /employees/{id}/record-utilization`, where the user types an employee ID (`employees.py:433`, `UtilizationDashboardScreen.js:26`). No scheduled computation. | Utilization dashboard is empty or stale unless someone keys IDs in; no target by role. |

### 2d. Project Manager: Staff Augmentation lens (account or delivery manager for placed consultants)

| Capability | Status | Evidence | Business impact |
|---|---|---|---|
| Submission to client, client decision, start date | BUILT | Submissions (`models/submission.py`), Pipeline & Submissions screen (nav "submissions"); `ClientOnboarding` and `POST /client-onboarding/{id}/confirm-start` (`client_onboarding.py:47`); `client_start_date` job creates the allocation (`core/scheduled_jobs.py`). | Works (job must be enabled, see section 4). |
| Consultant onboarding at client (access, laptop, badge) | PARTIAL | `ClientOnboarding` tracks status and start date only (`models/client_onboarding.py`). Checklists are **candidate**-scoped only (`models/checklist.py:69-111`). Backlog S-426 (tools access checklist) NOT-DONE. | Day-1 no-access delays are unbillable days. |
| Weekly timesheet, reminders, internal approval | BUILT | My Timesheet, Timesheet Approvals (`timesheet_approvals.py`), reject-with-reason and resubmit-diff (`timesheet_approval_service.py`); nag job (`timesheet_nag_service.py`); anomalies and disputes (`timesheets.py:451-577`). | Strong. Nag escalates only to the reporting manager (S-387 PARTIAL). Jobs must be enabled. |
| Allocation history | BUILT | ENDED allocations kept (`employee_allocation.py:47`); Employees > Allocations tab (`Approutes.jsx:551` redirect); `EmployeeOrgHistory` for BU/company moves. | Works. |
| Employee escalations blocking deployment | BUILT | `employee_escalations`; an open escalation blocks submission and deployment (`models/employee_escalation.py:1-3`); Employees screen. | Works. |
| Roll-off / exit / offboarding checklist | MISSING | No offboarding model (0 files). `end_allocation` benches the employee (`employee_allocation_service.py:165`), but there are no access-revocation, asset-return or KT tasks. | Client access left open after roll-off is a security and audit finding with insurer clients. |

### 2e. Shared (both lenses)

| Capability | Status | Evidence | Business impact |
|---|---|---|---|
| Opportunities to demand to hiring | BUILT | Opportunity pipeline screen; stage CONTRACT creates a project (OPEN_ITEMS P0-2 fixed); `POST /opportunities/{id}/role-demand` creates a job and starts recruiting (`opportunities.py:263-290`). | Works post-win. |
| Capacity planning vs sales pipeline (pre-win) | PARTIAL | Weighted revenue forecast exists (`opportunity_service.calculate_weighted_forecast`); roll-off plus skill-gap vs open jobs (`resource_forecast_service.py:88`). Opportunity has no headcount, skill or start month (`models/opportunity.py:52-97`). Backlog S-268, S-270, S-276 NOT-DONE/PARTIAL. | Hiring starts only after signature, so Guidewire start dates slip by the 4-8 week hiring lead time. |
| Skills matrix and certifications | PARTIAL | `Employee.current_skills` JSON list without proficiency (`employee.py:129`); Guidewire cert current/target (`employee.py:166-167`, `PUT /employees/{id}/certifications`). `EmployeeCertification` (with expiry, `certification.py:43`) has **no writer anywhere**, yet training dashboards read it (`training_certification_service.py`). | Cannot answer "who has ClaimCenter 10 Ace cert, expiring in Q1"; certification-based rate premiums are unprovable. |
| Leave / holiday calendars per location | MISSING | Only timesheet entry types LEAVE / HOLIDAY (`timesheet.py:34`) and employee status ON_LEAVE. No leave requests, balances or holiday calendar (grep = 0). P2-8: "leave" resource has no page. | Capacity overstated (India festivals, US holidays); timesheet nags and utilization ignore approved leave; billing on client holidays is not prevented. |
| Onboarding / offboarding checklists | PARTIAL | Candidate pre-joining checklists (`ChecklistTemplatesScreen.js`, `models/checklist.py`); no employee or offboarding scope. | See 2d. |
| Forecast vs actual | PARTIAL | Org/client revenue only (`forecast_variance_service.py`). Actuals by `Invoice.created_at` month (line ~33), while P&L uses earned-by-week. | Two different "actual revenue" numbers for the same month. |
| Invoicing from approved time | BUILT | `generate_invoice` blocks on any unapproved or disputed timesheet, no double billing, splits weeks across months (`invoice_service.py:110-196`); auto job (`invoice_automation_service.py:217`); Finance approval (`invoice_service.py:198`); Invoices screen. | Strong. Gaps: no PO, no tax/GST, invoice number = UUID prefix (`send_invoice_email_handler.py:66`), USD-only (`invoice_service.py:180-183`). |
| AR / collections per project | PARTIAL | Invoices filterable by project and client (`invoices.py:299`); `record-payment` with bank match (`invoices.py:272`). AR job uses fixed 30-day grace from `sent_at`, ignoring `Client.payment_terms_days` (`ar_followup_service.py:25-47`). No aging screen (no frontend caller). Backlog S-390 PARTIAL. | Net-45/60 clients chased early, net-15 clients late. No DSO by project or client. |
| Escalation management | PARTIAL | Employee escalations BUILT; internal helpdesk tickets with SLA (`models/ticket.py`); no client or project escalation. Backlog S-367 NOT-DONE. | See 2b. |
| Multi-company (BX-US, BX-IN) billing and intercompany | PARTIAL | Company P&L live (`PnlScreen.js:186`, `revenue_chain_service._company_pnl`). Invoice issuer derived at email time from `Client.contracting_company_id` (`send_invoice_email_handler.py:43-51`), not stored. Intercompany is a manual ledger with free-text entity names matched by name (`intercompany_ledger.py:24-25`, `revenue_chain_service.py:496-497`). Automatic intercompany is in design, waiting on 4 CEO decisions (`docs/COMPANY_MODEL_DESIGN.md`). Backlog S-396. | BX-IN cost of India staff on BX-US clients is not recharged unless typed by hand, so BX-US margin is overstated and BX-IN shows a loss. Transfer-pricing exposure in India. |
| Dashboards per role | PARTIAL | CEO, CFO, Partner, BU Head homes (`Approutes.jsx:96-113`); Workforce Overview, Bench, P&L. No PgM, PM or Delivery Head home. Backlog S-099, S-103, S-196, S-198 NOT-DONE. | See 2a. |
| Notifications / approvals | BUILT | Task + My Tasks + Flash chips; approvals for timesheets, invoices (Finance Senior Manager+), expenses, jobs, Core cert. Email depended on the Azure app being configured (OPEN_ITEMS decision 3) *(unverified today)*. | Works in-app. |

---

## 3. Top 15 gaps, ranked by money and risk

**1. Extension / renewal pipeline and allocation edit (Staff Aug)** — Effort **M**
- **What's missing:** an extend/edit action on allocations and work orders (new end date, new rate, history kept); a renewal status (Not started / In discussion / Extended / Rolling off) and an owner; alert tasks at 60/30/15 days.
- **Why it matters:** 100 SPECIALITY consultants on 6-month terms means ~17 roll-offs a month. Missing even 2 a month at ~$90/hr is about $31K/month revenue gone, plus loaded bench cost. Today the 30/60/90 list is read-only, and nobody owns or acts on it.
- **Smallest viable build:**
  - `PATCH /allocations/{id}` (end_date, rate) writing allocation history
  - renewal fields on the allocation
  - a daily job creating a Task for the client's account manager at 60 days
  - a "Renewals" tab on Demand vs Bench
- **Dependencies:** decision on the renewal owner (section 5).
- **Backlog:** not covered.

**2. Enable the money jobs in production** — Effort **S** (config)
- **What's missing:** confirmation that `auto_invoicing`, `ar_follow_up`, `timesheet_draft_creation`, `timesheet_reminders` and `client_start_date` are in `SCHEDULED_JOBS_ENABLED`.
- **Why it matters:** the last recorded production value (OPEN_ITEMS line 43) runs only `thunder_engagement_sweep`. If that still holds, drafts, reminders, monthly invoice drafts and AR tasks never run. Invoices then slip a month and DSO grows. *(unverified today)*
- **Smallest viable build:** set the environment variable; `backlog_guard`s already exist.
- **Dependencies:** none. The AR job is internal only (Task + notify). Auto-invoicing emails the client only after Finance approval.
- **Backlog:** not covered.

**3. Client timesheet approval and PO on invoice (Staff Aug)** — Effort **M**
- **What's missing:**
  - routing approval to the client approver on the allocation (already a column)
  - an emailed tokenized approve/reject link, or upload of the client's VMS-approved timesheet as evidence
  - the PO number from the work order printed on the invoice
- **Why it matters:** insurers on VMS (Fieldglass/Beeline) pay only against client-approved hours and a valid PO. Invoices without these bounce, adding 30-60 days of DSO.
- **Smallest viable build:**
  - approval step 2 "client" when `timesheet_approver_email` is set
  - signed-link approval page
  - `WorkOrder` link on the allocation; PO on the invoice line or header
- **Dependencies:** Azure mail live; decision on client-approval mode.
- **Backlog:** S-182/183/184 NOT-DONE.

**4. Margin guard and rate card at placement (Staff Aug)** — Effort **S/M**
- **What's missing:** a rate card (role/level/location, with floor bill rate) and a margin check at allocation create or edit using `CostBook` loaded cost, with an approval below the floor.
- **Why it matters:** a single under-priced placement at -$3/hr runs for a year: -$6K, plus the margin that should have been earned (~$20K). Placements are accepted with any bill rate today.
- **Smallest viable build:**
  - `rate_cards` table and admin page
  - `employee_allocation_service.allocate_employee_to_project` computes margin % (the loaded hourly figure already exists in `CostBook.hourly`)
  - below the floor creates an approval Task for the BU Head
- **Dependencies:** margin-floor decision.
- **Backlog:** S-288 NOT-DONE (AI pricing; a plain rate card is simpler).

**5. Work-authorization and compliance expiry (US and India)** — Effort **M**
- **What's missing:** typed work-auth record (H-1B/L-1/GC/Citizen/EAD/OPT), expiry and worksite (LCA) per employee, document expiry dates, alerts at 120/90/30 days, and a block on allocation or extension past expiry.
- **Why it matters:** billing an H-1B consultant at an unlisted worksite or after expiry exposes BX-US to DOL/USCIS penalties and the client to compliance findings. Insurer clients audit this.
- **Smallest viable build:**
  - `work_authorizations` table plus `expires_at` on `EmployeeDocument`
  - daily alert job
  - a check in allocate/extend
- **Dependencies:** decision on system of record (section 5).
- **Backlog:** S-164 (search filter) only; expiry tracking not in backlog.

**6. Fixed-price and milestone billing (Managed Services)** — Effort **L**
- **What's missing:** a billing type selectable in the UI; FIXED_BID / RETAINER; milestone amount and client acceptance; invoice-from-milestone path; retainer monthly invoice; revenue recognition rule.
- **Why it matters:** every Core fixed-bid or AMS retainer is invoiced outside WROS today. P&L revenue for those projects is zero while their people show as delivery cost, so Core margin looks negative and the P&L is wrong.
- **Smallest viable build:**
  - `amount_usd_cents`, `accepted_at`, `accepted_by_contact_id` on `ProjectMilestone`
  - `generate_milestone_invoice`
  - retainer as a monthly fixed line
  - P&L lines for non-timesheet revenue
- **Dependencies:** revenue-recognition decision; gap 8 (budget) for burn.
- **Backlog:** not covered (S-331 touches profitability only).

**7. Project budget, burn and EAC (Managed Services)** — Effort **M**
- **What's missing:** budget hours and budget $ per project (and per role); editable start/end dates; actual from approved timesheets and loaded cost; burn %; EAC = actual + remaining plan.
- **Why it matters:** a 4,000-hour Guidewire upgrade at 120% burn by week 10 is a ~$150K overrun found too late. `_calculate_burn_rate_pct` exists but can never fire.
- **Smallest viable build:**
  - `PATCH /projects/{id}` (dates, budget, PM)
  - `project_budget_lines`
  - burn and EAC computed from `revenue_chain.chain_lines` filtered by project
  - a project detail panel
- **Dependencies:** PM field (gap 9).
- **Backlog:** S-331 PARTIAL.

**8. Per-project and per-client profitability in the UI** — Effort **S**
- **What's missing:** a "By project" table on P&L and project-level margin trend; replace the unloaded-salary estimate in `calculate_project_expected_revenue` with `CostBook`.
- **Why it matters:** loss-making projects hide inside a profitable client. The current project estimate overstates margin by statutory plus overhead (often 20-35% of salary).
- **Smallest viable build:** the backend already supports `group_by=project` (`revenue_chain.py:61`). Add one card in `PnlScreen.js` and swap the cost source in `project_service.py:~219`.
- **Dependencies:** none.
- **Backlog:** S-331.

**9. PM ownership, status / RAG, RAID and project health** — Effort **M**
- **What's missing:** `Project.manager_user_id` (and program owner); weekly status report (RAG schedule/scope/budget/people, narrative); RAID items with owner and due date; a health score derived from burn, milestone delay, open RAID HIGH, unfilled roles and timesheet anomalies.
- **Why it matters:** without a weekly RAG, leadership learns of a failing carrier implementation from the client's CIO. A lost Core account is $1-3M/year.
- **Smallest viable build:**
  - three tables (`project_status_reports`, `project_raid_items`) plus manager FK
  - a status/RAID tab on the project panel
  - health = rule-based score shown on Projects list
- **Dependencies:** gap 7 for burn input.
- **Backlog:** S-305, S-322 NOT-DONE.

**10. Leave and holiday calendars per location** — Effort **M**
- **What's missing:** holiday calendar per company/location (BX-US, BX-IN, client calendar optional); leave requests, approval and balances; feed into timesheet prefill/validation, utilization denominator, nag suppression and capacity.
- **Why it matters:** India's ~12-15 public holidays plus US holidays are not in capacity. Nags hit people on approved leave. Utilization is understated or overstated. Billing on a client holiday is not checked.
- **Smallest viable build:** `holiday_calendars`, `leave_requests` (approval via Task), with timesheet LEAVE/HOLIDAY entries auto-filled.
- **Dependencies:** leave-policy decision per company.
- **Backlog:** "leave" resource listed as pageless (P2-8); no story found.

**11. Utilization engine with targets** — Effort **S**
- **What's missing:** a scheduled weekly snapshot (reuse `record_weekly_utilization_metric`) for all employees; targets per role/level (template data, not names); drop the manual typed-ID form.
- **Why it matters:** a 5-point utilization gap on 500 billable people at $90/hr x 160 h is about $360K/month. It cannot be managed if the dashboard is manual.
- **Smallest viable build:**
  - add a job to `core/scheduled_jobs.py`
  - `utilization_target_pct` on the role template or level
  - compare in `utilization_summary`
- **Dependencies:** gap 10 for a correct denominator (can ship before it).
- **Backlog:** S-223 PARTIAL, S-328 NOT-DONE.

**12. Invoice compliance and AR by terms** — Effort **M**
- **What's missing:** a stored sequential invoice number per issuing company; stored `issuing_company_id` and `due_date`; PO; tax (GST for BX-IN); a PDF attachment *(PDF unverified)*; AR aging by `due_date` using `Client.payment_terms_days`; an AR aging screen by client and project.
- **Why it matters:** UUID-prefix invoice numbers fail Indian GST sequential-numbering rules and many US AP systems. The fixed 30-day AR cadence chases net-60 clients prematurely and net-15 clients late.
- **Smallest viable build:** columns on `Invoice`, a number sequence per company, and a change of `scan_overdue_invoices` to use `due_date`.
- **Dependencies:** COMPANY_MODEL_DESIGN decisions 2 and 4.
- **Backlog:** S-390 PARTIAL; company design Part 2.

**13. Capacity planning from the pre-win pipeline** — Effort **M**
- **What's missing:** on opportunities, expected roles (skill, level, qty, start month), weighted by probability; a monthly demand curve vs bench plus roll-offs plus in-flight hires, by skill.
- **Why it matters:** Guidewire hiring lead time is 4-8 weeks. Hiring only after signature delays starts, and each week of delay on a 10-person ramp at $90/hr is ~$36K deferred or lost.
- **Smallest viable build:**
  - `opportunity_role_lines`
  - forecast service summing probability x qty per skill per month
  - a "Pipeline demand" view on Demand vs Bench
- **Dependencies:** none.
- **Backlog:** S-268 PARTIAL, S-270 and S-276 NOT-DONE.

**14. Replacement SLA and consultant client feedback** — Effort **M**
- **What's missing:** a "replacement request" (client, seat, reason, requested_at, SLA target, filled_at) that spawns a job flagged REPLACEMENT; a monthly or quarterly client feedback pulse per consultant (score + comment) feeding the performance store.
- **Why it matters:** a seat not replaced within the client's tolerance is usually lost to another vendor, which is a permanent loss of ~$180K/year per seat. Feedback gives early warning of a release and evidence for rate increases.
- **Smallest viable build:** two small tables and a client feedback form (internal entry first, client link later).
- **Dependencies:** SLA-commitment decision.
- **Backlog:** not covered.

**15. Automatic intercompany and multi-currency** — Effort **M-L**
- **What's missing:** a monthly cost-plus recharge BX-IN to BX-US (design Part 2); company FK on intercompany entries instead of free-text names; INR and CAD books.
- **Why it matters:** without a recharge, BX-IN shows losses and BX-US overstated profit. That creates Indian transfer-pricing exposure and misleading company P&Ls.
- **Smallest viable build:** as designed in `docs/COMPANY_MODEL_DESIGN.md` Part 2 (monthly job writing ledger entries).
- **Dependencies:** 4 CEO decisions in that doc.
- **Backlog:** yes (design doc; S-396).

Not ranked but expected by a PMO lead (all MISSING): change requests, SLA/KPI client reporting packs, governance cadence (SteerCo/QBR), KT/transition plans, offboarding checklist, client/project escalations, PM/PgM/Delivery Head dashboards, program entity.

---

## 4. Exists but broken or unwired (fastest wins)

| # | Item | Evidence | Fix size |
|---|---|---|---|
| 1 | Money jobs probably off in prod: only `thunder_engagement_sweep` was enabled at last record. | `OPEN_ITEMS.md:43`; registry `core/scheduled_jobs.py:28-48` *(unverified today)* | S (env var) |
| 2 | Project start/end dates can never be set; no project edit endpoint. So client burn rate is always None, and FIXED_BID can't be chosen in the UI. | `project_service.py:86-105`; `schemas/project.py:15-34`; `client_revenue_dashboard_service.py:39-64`; `ProjectsScreen.js` (no billing-type control) | S |
| 3 | Project expected-margin uses unloaded `base_salary_usd_cents`; P&L uses loaded `CostBook`. Two margins disagree. | `project_service.py:181-235` vs `revenue_chain_service.py:61-157` | S |
| 4 | Utilization dashboard only shows weeks someone recorded by typing an employee ID. | `employees.py:433-450`; `UtilizationDashboardScreen.js:26` | S (add job) |
| 5 | Client revenue dashboard needs a typed client ID. | `RevenueScreen.js:212` | S (picker) |
| 6 | Client timesheet approver captured nowhere in the UI and read by nothing. | `employee_allocation.py:74`, `timesheet.py:74`; no frontend references | S to wire capture; M for the approval flow |
| 7 | Work orders (PO) are API-only, with update/end/pause in the service but no routes and no UI; never linked to invoices. | `work_orders.py:73,125`; `work_order_service.py:129-259` | S/M |
| 8 | `EmployeeCertification` (with expiry) has no writer, so training/cert dashboards read an empty table. | `certification.py:43`; only reader `training_certification_service.py` | S |
| 9 | Per-project P&L exists in the API but not on screen. | `revenue_chain.py:61-72` (`group_by=project`); `PnlScreen.js` has no project card | S |
| 10 | Three definitions of monthly revenue: P&L = earned by timesheet week; Forecast vs Actual and BU Head MTD = invoices by `created_at`. | `revenue_chain_service.py:1-27`; `forecast_variance_service.py:~33`; `bu_head_dashboard_service.py:1-10` | S (point both at revenue-chain) |
| 11 | AR follow-up ignores client payment terms (fixed 30 days from `sent_at`); due date in the invoice email is computed from `approved_at`, not sent date, and not stored. | `ar_followup_service.py:25-47`; `send_invoice_email_handler.py:65` | S |
| 12 | Invoice number is the first UUID segment. | `send_invoice_email_handler.py:66` | S (with a company sequence, gap 12) |
| 13 | Intercompany entries are free-text entity names matched to companies by name; a typo silently lands in "Group". | `intercompany_ledger.py:24-25`; `revenue_chain_service.py:496-497` | S (FK to company) |
| 14 | `ResourceDemand` model has no writer (only read by `kpi_service`): dead demand table beside Jobs. | `models/resource_demand.py`; grep | S (delete or wire) |
| 15 | Timesheet nag escalates only to the reporting manager, not BU Head; no timezone awareness. | `timesheet_nag_service.py`; backlog S-387 | S |

---

## 5. Business decisions the CEO must make before building

1. **Billing models in WROS:** support fixed-price milestone and monthly retainer (AMS) alongside T&M? Revenue recognition for fixed price: on milestone acceptance, or percentage of completion on burn? *Recommend:* milestone acceptance first (simple, auditable), with POC later for the P&L view.
2. **Margin floor per placement:** minimum gross margin % by line (SPECIALITY vs CORE) and by delivery location (US onsite vs India offshore), and who may approve below it. *Recommend:* BU Head approves below the floor and Partner approves below a lower hard floor. Authority comes from role-template level, not names.
3. **Client timesheet approval mode:** emailed approve link to the client approver, or accept the client's VMS-approved export as evidence, or both? Is client approval required before invoicing for all clients or only those flagged? *Recommend:* per-client flag; link plus evidence upload.
4. **Renewal ownership and lead time:** who owns an extension (account manager vs BU Head vs delivery manager), and at how many days before end does it become an alert? *Recommend:* account manager, alerts at 60/30/15.
5. **Immigration and compliance system of record:** is WROS the system of record for H-1B/LCA worksite, I-9/E-Verify and BGV re-checks, or does it mirror an immigration counsel system? What blocks allocation or extension (expired authorization, worksite not on LCA)?
6. **Replacement SLA commitment:** what BlitzenX promises clients (e.g. a replacement profile in 5 business days and a start in 15), and whether a free-replacement guarantee period applies.
7. **Leave and holiday policy per company:** BX-US PTO vs BX-IN statutory leave. Does leave approval live in WROS? Whose holiday calendar governs billing: ours, or the client's?
8. **Company model Part 2 (already pending):**
   - intercompany markup (proposed 10% cost-plus)
   - the issuing entity for US clients served from India (recommend BX-US)
   - BX-Canada and multi-currency timing
   - per-company letterhead and number series

   Source: `docs/COMPANY_MODEL_DESIGN.md`.
9. **Delivery roles:** create Program Manager, Project Manager and Delivery Head as role templates (level, specialization, permissions), each with its own Home dashboard. Decide what each may see (own projects / BU / org).
10. **Governance standard:** mandatory weekly status (RAG) for every Core project, a monthly SteerCo and a QBR for accounts above a revenue threshold. This defines what WROS must template and chase.
11. **Turn on the money jobs:** confirm production should run auto-invoicing (Finance still approves before the client email), AR follow-up (internal tasks), timesheet drafts and reminders, and client start-date placement. *Recommend:* yes, now.

---

## Backlog cross-reference

- **Already in the backlog:**
  - S-305 / S-322: project health
  - S-331: project profitability (PARTIAL)
  - S-332: bench analytics (PARTIAL)
  - S-182 / 183 / 184: client timesheet approval (NOT-DONE)
  - S-387: timesheet nag (PARTIAL)
  - S-390: AR follow-up (PARTIAL)
  - S-396: entity P&L (now partly live)
  - S-164: work-auth filter
  - S-268 / 270 / 276: demand forecast
  - S-223 / 328: utilization
  - S-099 / 103 / 196 / 198: client and delivery dashboards
  - S-288: pricing suggestion
  - S-367: escalation classification
  - S-426: tools access checklist
  - S-242: forecast vs actual (PARTIAL)
  - Company design Part 2: intercompany, issuing company
- **Not in any backlog I found:**
  - SOW entity and value
  - change requests
  - RAID
  - status reports / RAG
  - governance cadence
  - budget / burn / EAC
  - fixed-price milestone and retainer invoicing
  - rate cards and margin floor at placement
  - allocation extend/edit and renewal pipeline
  - PO on invoice
  - visa or compliance expiry
  - replacement SLA
  - consultant client feedback
  - leave and holiday calendars
  - offboarding
  - KT / transition
  - PM / PgM / Delivery Head dashboards and the PM field on Project
