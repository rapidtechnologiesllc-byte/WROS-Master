# Recruitment vs Workforce: hiring requisitions and client demands

**Status:** APPROVED by the CEO 2026-11-27 (v3, decisions D1-D8 as recommended in section 9). Ruthless Architect:
review #1 BLOCK, review #2 APPROVE WITH CHANGES, all applied (section 10). Delivery follows section 8.
Related: client contact confidentiality, `docs/CLIENT_CONTACT_CONFIDENTIALITY_DESIGN.md` (CEO 2026-11-27).
**Date:** 2026-11-27 · **Issue:** #579

## 1. The problem (CEO 2026-11-27)

> "Recruitment is external candidate to employee, we shouldn't show client demand here. If there is an ad-hoc
> client demand we need to still create an internal pipeline to then submit in workforce and show client open
> roles in workforce. The problem with this would be we will never be able to track end to end."

What the code does today (evidence):

| Fact | Where |
|---|---|
| One `jobs` row is both a hiring job and a client demand ("synonyms") | `models/user.py` `Jobs`; `Demand` is the same class |
| An opportunity opens a client job at once and recruiting starts on a **prospect** role | `opportunity_service`, `upcoming_role_service`, `opportunities.py:147,312,384` (`start_recruiting`) |
| Flash missions start on jobs **with** a client and hire external people onto them (L1, sourcing, offer) | `flash_mission_service.py:243, 650-692, 164-183` |
| Thunder role outreach and sub-vendor broadcasts run from client jobs | `role_outreach_service.py:178-230`, `sub_vendor_roles_service.py:90` |
| Candidate page **Submit to Job** lists every job and posts a client submission; the API then refuses (not a bench employee) | `CandidateAssignJobModal.js`, `submission_service.check_market_profile_rule` |
| "Internal vs client" is inferred from `client_id`, which a company-name edit can silently change | `create_job.py:738-740`, `job_creation_service.resolve_job_client:26-40` |
| `confirmation_status` is POTENTIAL for every job; nothing writes CONFIRMED | `models/user.py:199` |

## 2. The model

Two kinds of job record, two owners, stored links between them. End-to-end tracking comes from the stored links
and from the person (candidate → employee keeps `candidate_id`). It never comes from sharing one record.

```
 Opportunity (Sales)                             Partner / BU head
      │ needs a role                                  │ anticipated scope
      ▼                                               ▼
 CLIENT DEMAND (Workforce) ◄── requisition_demands ── HIRING REQUISITION (Recruitment)
 filled only by employees                             filled only by external candidates
      ▲   ▲                                           │ screen → L1 → L2 → offer → onboarding → BGV
      │   └── employee_earmarks ◄──── hire ◄──────────┘   (offer_letters.job_id = the requisition)
      │ submission (employee → demand)                    → EMPLOYEE (candidate_id kept) → BENCH
      ▼
 client rounds (submission_client_rounds) → client selection → client onboarding
      → ALLOCATION (allocation_submissions) → timesheet → invoice → revenue
```

### 2.1 The kind is stored, never inferred (review C1)
- New table **`job_kinds`**: `job_id` (PK, FK jobs), `tenant_id` NOT NULL, `kind` (`REQUISITION` | `CLIENT_DEMAND`),
  `classified_by` (user or `migration`), `classified_at`, `evidence` (text). Written once, by the one creation
  path for each kind. Reads go through one helper, `job_kind(db, job)`, which **fails fast** when a job has no row. Jobs on the manual
  review list get the kind `UNCLASSIFIED`: they can be read, and every write to them is refused until an
  administrator classifies them. A job row is inserted in exactly two places, and each writes `job_kinds` in the
  same transaction: `demand_service.create_demand` (demand_service.py:22) and `JobCreationFlashHandler`
  (job_creation_flash_handler.py:131).
- A `REQUISITION` also requires `business_unit_id`: employee conversion takes the BU from it
  (employee_conversion_service.py:172), and so does the hiring manager default (`head_for_client`, bu_leadership.py:119).
- Invariants enforced in the creation paths and in every update endpoint:
  - `CLIENT_DEMAND` requires `client_id`.
  - `REQUISITION` requires `client_id`, `opportunity_id` and `project_id` all to be NULL.
  - Once a job has children (applications, panels, offers, submissions, allocations), the API refuses any change
    to `client_id`. A company-name edit no longer re-matches the client on such a job.
  - An unmatched company name on a client demand is an error ("client not found"), never a silent internal hire
    (`resolve_job_client` fails fast).
- **Prospect vs Confirmed** comes from the demand's opportunity stage (`WON_STAGES`), or "Confirmed" for an ad-hoc
  demand whose client is active. It is never read from `confirmation_status`.
- Code that uses "has a client_id" to mean "is a demand" moves to `job_kind`: `kpi_service.py:232`,
  `allocations.py:246`, `flash_mission_service.py:243`, `demand_service.py:65`. The POTENTIAL filter at
  `flash_mission_service.py:245` is replaced by the opportunity-stage rule above.

### 2.2 Hiring requisition (Recruitment)
- BlitzenX hiring external people **as employees**, e.g. "Guidewire Developer × 3, BU Guidewire India".
- Raised by a Partner or BU head for anticipated scope, or opened as a draft from a client demand (2.4). Approved
  per D1.
- **Its own status path** (review H4): `DRAFT → APPROVED → OPEN → FILLED | CANCELLED`. It doesn't need a client
  to open. Stored in `jobs.demand_status`, with the allowed transitions chosen by `job_kind`
  (`ALLOWED_REQUISITION_TRANSITIONS` beside `ALLOWED_DEMAND_TRANSITIONS`, demand.py:42-49). `_job_closed` and
  `record_placement` use the same rule. **Sourcing gate:** sourcing (Thunder, sub-vendors, Flash) runs only on an OPEN requisition that is
  either linked to a demand whose `bench_first_checked` is true, or approved as anticipated scope.
- Candidates are added to it ("Add to requisition"). Screening calls and L1/L2 belong to it, or to no job (a
  market candidate screened for the talent pool; their rounds travel with them, 2.6).
- **Requisition → employee is stored** (end-to-end gap 1): the hire is attributed to the accepted offer's
  `job_id`. `offer_letters.job_id` is required for a requisition offer. `hiring_pipelines.job_id` is set from the
  accepted offer, not from "first job seen" (`link_job`).
- It never receives a client submission (API guard).

### 2.3 Client demand (Workforce)
- A client's open role, from an opportunity (prospect or confirmed) or an ad-hoc client request.
- Shown in **Workforce → Client open roles**: Prospect/Confirmed, rate, start date, headcount, bench matches,
  earmarked employees, linked requisitions and their progress (Fulfilment panel).
- Filled only by bench employees: submission → client rounds → client selection → client onboarding → allocation.
  The current submission gates stay (bench-first, 5-year floor, employment type, Direct certification, buddy
  graduated).
- It never receives applications or hiring rounds (API guard: "this is a client role: add the candidate to its
  requisition").
- **Client rounds are kept apart** (review H2): a client's interview of a submitted employee is recorded in a new
  table, `submission_client_rounds(panel_id, submission_id, tenant_id)`. The hiring pipeline (`_walk`) and the
  rehire guard (`has_failed_round`) skip those panels, so a client's "no" never changes a hiring stage or blocks
  a rehire.

### 2.4 Links (review M1, gaps 2-3)
| Table | Columns | Rule |
|---|---|---|
| `requisition_demands` | `tenant_id`, `requisition_job_id`, `demand_job_id`, `headcount`, `linked_by`, `linked_at` | unique (requisition, demand); both jobs in the link's tenant; the headcounts a requisition gives its demands add up to at most its own |
| `employee_earmarks` | `tenant_id`, `employee_id`, `demand_job_id`, `requisition_job_id`, `status` (ACTIVE/RELEASED/USED), `created_at` | written when a demand-backed requisition's hire reaches the bench |
| `allocation_submissions` | `tenant_id`, `allocation_id`, `submission_id` | an allocation onto a CLIENT_DEMAND needs a PLACED submission, checked inside `allocate_employee_to_project`, so it applies at every entry point (`allocations.py:312`, `resource_management_agent_service.py:473`, `employee_import_service.py:839`, `core_pull_service`). The one exception is `existing_placement=True` for imports: logged, and listed in the Step 4 report |
| `submission_interview_rounds` | (built) hiring rounds attached to a submission as a snapshot | see 2.6 |
| `submission_client_rounds` | `tenant_id`, `panel_id`, `submission_id` | client rounds, kept out of hiring |

- **Ad-hoc client demand with no bench fit:** the existing bench-first check runs. When no bench employee fits,
  the system opens a **draft linked requisition** prefilled from the demand. Approving it is the one human step
  (D1). This is technical; the old D4 is closed.
- **Opportunity → Add role** creates the client demand only. Hiring starts when a requisition is approved for it.
  `start_recruiting` (`opportunities.py`) opens or links a requisition instead of sourcing on the demand.
- **BU lock** (review H1): `submission_bu_id` is set when the employee is **submitted**, never when a candidate is
  added to a requisition (`candidate_assignment_service.py:30-31` changes). An India requisition can back a US
  demand; a cross-company placement follows the existing intercompany rules.

### 2.5 End-to-end tracking: every hop is a stored link
| Hop | Link | Status |
|---|---|---|
| Opportunity → demand | `jobs.opportunity_id` | exists |
| Demand → requisition | `requisition_demands` | new |
| Requisition → candidate → hire | panels/applications `job_id`; accepted `offer_letters.job_id`; `hiring_pipelines.job_id` | tightened (2.2) |
| Candidate → employee | `employees.candidate_id` | exists |
| Hire → demand (earmark) | `employee_earmarks` | new |
| Employee → demand | `submissions.demand_id` | exists |
| Submission → allocation | `allocation_submissions` | new (allocations can hold `demand_id = NULL`, `employee_allocation_service.py:401`) |
| Allocation → timesheet | `timesheets.allocation_id` | exists, nullable for task and work-item time; client-billable time must carry it (guard) |
| Timesheet → invoice line → revenue | `invoice.py:109`, `revenue.py:39` | exist |

On the demand, **Fulfilment** reads these links and shows: requisitions → candidates by stage → hired (earmarked)
→ submitted → client response → placed. Time-to-fill is counted from the day the demand opened.

### 2.6 Screening calls and rounds
- **Screening call:** a first conversation with a market candidate, with or without a requisition. It moves a new
  candidate to Screening only (never back from a later stage). The 5-year and employment-type gates run.
- **Hiring rounds (L1/L2):** on the requisition, or with no job (talent pool).
- **Client rounds:** `submission_client_rounds` (2.3).
- **Attached to the submission:** when a bench employee is submitted, their hiring rounds (requisition and
  job-less) are attached as a snapshot (`submission_interview_rounds`; built and tested on branch
  `feat/screening-calls-and-submission-rounds`, held for this design).

## 3. Flash and Thunder in the Phalanx (review C2, H3)

| | Demand mission (Workforce) | Requisition mission (Recruitment) |
|---|---|---|
| **Phalanx position** | Position 1, Flash: owns the client demand end to end | Position 1, Flash: orchestrates the requisition. Watches Thunder (Position 2, sourcing yield) and Interview/Offer (Position 3, conversion) |
| **Work** | bench-first → earmark proposals → submission → client rounds → placement | sourcing → screening → L1/L2 → offer → joined |
| **Filled when** | placed (`record_placement`) | headcount joined |
| **Neighbour health watched** | each linked requisition: candidates per stage vs the demand's start date; earmarked hires' bench readiness; submission → client response time | the demand's start date and the bench supply it still needs; offer acceptance rate |
| **Cascade predicted 15 min ahead** | a linked requisition can't produce a joiner before the demand's start date (pipeline velocity × days left) | sourcing yield below what's needed to fill the headcount by the date |
| **Escalates when** | formation health < 70%: no bench fit and no requisition approved within the SLA, or requisition velocity below need → BU head, then Partner | no qualified candidates after the sourcing window, or the offer is declined → BU head |

- Missions start from `job_kind`, never from `client_id IS NOT NULL` (`flash_mission_service.py:243`) or
  `confirmation_status` (:245). **Backlog on deploy:** missions for demands and requisitions that are already open
  start rate-limited (at most `FLASH_AUTO_MISSION_BATCH` per sweep, oldest start date first), not all at once.
- `_fill` schedules hiring L1 only on a requisition mission; a demand mission never schedules hiring rounds.
- `candidate_joined` fills the requisition, then proposes the earmarked submission to the demand mission.
- **Thunder role outreach, UpcomingRole and sub-vendor broadcasts** are re-keyed to the requisition, carrying the
  demand's `client_description` (the client is never named). Their cadences already in flight are **paused** for
  the migration and resumed on the requisition afterwards.

## 4. Migration (review C3, H5, M2): table by table, ledgered, reversible

**Preconditions (the migration fails fast and changes nothing otherwise):**
- No job with NULL `tenant_id`.
- Run first as a dry run on the masked production copy. The dry-run report (section 5) has been read and approved.
- Thunder and Flash paused for the tenant during the run.

**Step 1. Classify** every job into `job_kinds` using every signal, never one:
`client_id` set; `opportunity_id`; `project_id`; `source_type`; an UpcomingRole row; submissions or allocations on
the job; whether `client_id` came only from a company-name match; the client's tenant.
- All signals agree → classified, with the evidence recorded.
- Signals disagree (e.g. a client matched by name only with hiring applications and no submissions, or a
  client from another tenant) → **manual review list**, never guessed. Those jobs are not migrated until an
  administrator classifies them on a review screen.

**Step 2. Split each client demand with external hiring on it.** "External hiring" means applications, hiring
panels, offers, or employees still PRE_JOINING (review M2). One linked requisition is created per demand, and
each row below is moved or kept as shown. Every change is written to the **`migration_moves` ledger**
(`run_id`, `seq`, `tenant_id`, `op` UPDATE/INSERT/DELETE, `table`, `pk`, `column`, `old_value`, `new_value`,
`row_before` JSONB = the whole row for DELETE, `row_after` for INSERT).

| Table (column) | Action |
|---|---|
| `candidate_job_applications.job_id` | move |
| `interview_panels.job_id` | **client round** (stays on the demand, recorded in `submission_client_rounds`): the candidate was already an employee when the panel was created (`employees.joining_date` <= `panel.created_at`) **and** a submission to this demand existed by then. **Hiring round** (moves): every other panel on the demand. A panel that fits neither rule clearly goes to the manual review list |
| `interview_verdicts.job_id`, `interview_rehire_reviews.job_id` | move with their panel |
| `offers.job_id`, `offer_letters.job_id` | move |
| `candidates.job_id` | move (`pay_from_offer` reads offers by it: employee cost stays known) |
| `hiring_pipelines.job_id` | move |
| `candidate_rejections.job_id`, `candidate_job_scores`, `candidate_job_flags`, `hiring_manager_validations` | move |
| `demand_interview_panels` | move hiring entries; keep client ones |
| `upcoming_roles` (PK job_id), `role_outreach`, `outreach`, `sourcing_alerts`, `demand_gap_scores`, `sub_vendor_requests` | re-key to the requisition. Where the requisition already has a row (unique key), the old row is ledgered and removed |
| `flash_missions` (UNIQUE job_id) | demand keeps a demand mission; a new requisition mission is created; the old mission state is ledgered |
| `slm_job_metadata` (UNIQUE), `job_search` (PK) | copied for the requisition (new key), demand keeps its own |
| `submissions.demand_id`, `employee_allocations.demand_id`, invoices, timesheets | **stay** on the demand |
| `thunder_emails.job_id`, `referrals.job_id`, `candidate_history.job_id`, `mailbox_intake.job_id`, `slm_learning_metrics.job_id` | move when they concern a hiring candidate of the moved panels/applications; else stay |
| `ats` scores (`ats.py:31`), `candidate_opportunity_watch.matched_job_id` | move (hiring) |
| `client_onboarding.demand_id`, `core_pull_events.core_demand_id`, `work_orders`, `bench_allocation_recommendations`, `pipeline_leakage`, `demand_history` | stay (delivery) |
| `candidates.submission_bu_id` | cleared (ledgered) for candidates with **no** submission: the lock now comes at submission time (H1) |
| FlashMission / ThunderEmail / Referral / SLM JSON metadata that holds a job id | rewritten through the ledger |

**Step 3. Past hires (H5):** a client demand whose hires all completed gets a **closed historical
requisition**. Its panels and offers move there, so time-to-hire and recruiter metrics keep them.

**Step 4. Earmarks and allocation links:** `employee_earmarks` for employees hired through the demand and still on
the bench; `allocation_submissions` backfilled from submission + employee + demand where exactly one match
exists, otherwise listed in the report.

**Reverse:** replay the ledger in descending `seq`: re-insert deleted rows from `row_before`, delete inserted rows,
restore updated values. The dry run proves it restores the affected tables byte for byte (section 5).

## 5. Dry-run and parity report (must be approved before the real run)
- Per tenant, per table: row counts before and after, and the job ids moved.
- The manual review list, with the reason for each job.
- Each candidate's hiring stage before and after `evaluate`, with the verdict per level.
- Every employee's cost resolution (`pay_from_offer` is not None before and after).
- Every Flash mission and Thunder cadence state, before and after.
- Every unique-key collision and how it was resolved.
- `submission_bu_id` unchanged for every candidate who has a submission; the cleared ones listed.
- The reverse replay restores a byte-for-byte equal dump of the affected tables.

## 6. Rules enforced at every entry point
| Rule | API | Pickers | Flash / Thunder | Importers |
|---|---|---|---|---|
| Only bench employees are submitted to a client demand | `submission_service` (exists) | Workforce shows bench only | demand mission | — |
| A client demand never takes applications or hiring rounds | applications, panels, scheduling, offers | Recruitment lists requisitions only | requisition mission only | candidate import |
| A requisition never takes a submission | `submission_service` | — | demand mission only | — |
| Kind is fixed once children exist (`client_id` locked) | job update endpoints | — | — | job import |
| No second submission path | `career_portal_service.py:131` (creates a Submission, skips every gate, no endpoint calls it) is **deleted** (M3) | | | |

## 7. Screens
| Area | Shows | Removed |
|---|---|---|
| Recruitment → Jobs | requisitions: status path, headcount, BU, linked demands as chips, pipeline by stage | client demands |
| Recruitment → Hiring pipeline | candidates by stage per requisition (+ talent pool) | client submissions |
| Candidate page | "Add to requisition", "Schedule screening call" | "Submit to Job" to client roles |
| Workforce → Client open roles (new) | demands, Prospect/Confirmed, bench matches, earmarks, **Raise requisition**, Fulfilment | — |
| Workforce → Submissions | employee → demand submissions (moved from /pipeline), client rounds | — |
| Opportunity → Add role | creates the demand; "Raise hiring requisition" | instant hiring job |
| Admin → Job classification review | the migration's manual review list | — |

## 8. Delivery plan (after approval)
1. `job_kinds` + guards + `resolve_job_client` fail-fast + the `client_id` lock + both creation paths, **and**
   migration Step 1 (classify) on its own: dry run on the masked prod copy, then the real run, so every existing job
   has a kind before any reader needs it. No rows move yet.
2. Link tables + requisition status path + sourcing gate + Flash/Thunder split.
3. Migration with ledger, dry run on the masked prod copy, report review, then the real run.
4. Screens: Workforce → Client open roles, Submissions move, Recruitment requisitions, candidate page, opportunity
   role flow.

Each PR: architect review, full test suite in the gate, browser check of the affected screens locally and on the
masked prod copy, and a statement of what was not seen on production.

## 9. Decisions (CEO approved 2026-11-27: every recommendation below)
- **D1. Who approves a requisition?** The BU head of its BU. The Partner too when it's above a headcount threshold
  or has no confirmed demand behind it (pure anticipated scope).
- **D2. Hire for a prospect demand before the contract?** Yes, but only through a requisition the Partner
  approved as anticipated scope. Never automatically.
- **D3. Earmark = reservation or suggestion?** A suggestion. The earmarked employee is proposed first; another
  demand may take them with the BU head's OK. (Stored in `employee_earmarks` either way.)
- **D5. Sub-vendor candidates:** hired as W2 employees through a requisition (bench-first holds), or not used
  for client roles at all? Recommended: through a requisition, so every rule applies.
- **D6. Opportunity marked LOST:** demand cancelled. Its requisitions are asked to continue (anticipated scope,
  Partner decides) or cancel. Candidates in flight stay in the talent pool. Earmarks are released.
- **D7. One requisition backs several demands: who decides which demand a hire goes to?** The demand mission
  proposes by start date and fit; the BU head confirms.
- **D8. Do Recruitment KPIs count requisitions with no demand behind them?** Yes, reported separately
  ("anticipated scope") from demand-backed ones.
- ~~D4~~ technical: ad-hoc demand with no bench fit always opens a draft requisition (2.4).

## 10. Review #2 changes applied
| Finding | Where |
|---|---|
| N1 classify ships with `job_kinds` (PR 1); `UNCLASSIFIED` is readable, write-refused; the two job-insert paths named | 2.1, 8 |
| N2 ledger records op + whole rows; reverse replays in descending order | 4 |
| N3 rule for old client rounds vs hiring rounds; unclear panels go to manual review | 4, step 2 table |
| N4 allocation onto a demand needs a PLACED submission at every entry point; import exception logged | 2.4 |
| M-a POTENTIAL filter replaced; rate-limited backlog on deploy | 2.1, 3 |
| M-b both missions are Flash (Position 1) watching Thunder (2) and Interview/Offer (3) | 3 |
| M-c requisition status in `demand_status` with a transition map chosen by kind | 2.2 |
| M-d `submission_bu_id` cleared (ledgered) where there's no submission; check reworded | 4, 5 |
| M-e migration table completed (MOVE/STAY for every listed table) | 4 |
| M-f same-tenant links; REQUISITION requires `business_unit_id` | 2.1, 2.4 |
