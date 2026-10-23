# WROS End-to-End Hire Pipeline — Priority Backlog

**Ordering principle, per Avinash's 2026-08-12 directive:** work is prioritized by position in the real business pipeline, not by when a bug was found. The pipeline:

```
Create Demand (Partner/BU/RM/HR/Recruiter) → Create Job → Add Candidate / AI auto-identifies
→ Auto interview scheduling → Panel feedback → Hiring manager check → BU final approval
→ Auto document request → HR document validation → Generate offer → Add as employee
→ Assign to BU & Client & Project → Send timesheet login/URL/details → Submit timesheet
```

**Confidence key** — how deeply each stage was actually verified, not just observed:
- 🟢 **VERIFIED** — traced end-to-end this session, live-tested (created real records, checked DB/API responses), same rigor as the tenant_id fix
- 🟡 **SPOT-CHECKED** — confirmed the relevant screen/endpoint/service exists and read its code, but not live-tested end-to-end
- 🔴 **GAP FOUND** — confirmed, by reading the actual code, that the step doesn't exist or doesn't do what's needed
- ⚪ **NOT YET LOOKED AT** — pipeline stage not investigated yet this pass

Don't treat a 🟡 as "working" — it means "looks plausible, unverified." Only 🟢 has been actually proven.

---

## Stage 1 — Create Demand (Partner / BU / Resource Manager / HR / Recruiter) — 🔴 GAP FOUND, DESIGN CLARIFIED

**Most important finding in this pass.** There is no UI, and no API endpoint, that lets any of the named roles manually create a demand record. `app/services/demand_service.py:create_demand()` exists and works, but its **only** caller in the entire codebase is `opportunity_service.py` — it fires automatically when a sales Opportunity closes (`source_type=OPPORTUNITY`).

**`DemandConfirmationScreen.js` is not a creation screen — confirmed by reading it in full.** It requires a `demandId` and `employeeId` typed in as raw UUIDs, with no picker or lookup anywhere (the screen's own top comment admits this: *"No Demand/Employee browse screen exists yet in this app... a separate, later story in the 205-story queue"* — that later story never landed). "Schedule alignment call" doesn't call anyone — it creates an `AlignmentCall` tracking record; the real call happens over some untracked external channel, and a human comes back afterward to manually mark "Employee: fit / not a fit" and "BU Head: fit / not a fit." This screen is a **post-hoc sign-off tracker for a call that already happened**, not a scheduler and not a creation flow.

**Corrected process, per Avinash directly (2026-08-12):** "A demand is coming from a partner, sales or resource manager which has to go to BU assigned as a task to review and provide direction."

**Design path — real infrastructure already exists for this:** `app/models/task.py`'s `Task` model is a genuine, already-built org-wide task system — `assigned_to_user_id`, `department_id`-based round-robin routing, `status` (NEW/IN_PROGRESS/ON_HOLD/COMPLETED/CANCELLED), priority, and an existing Org-wide Task Dashboard per the model's own docstring. Stage 1 doesn't need a task-routing system built from scratch:

1. New `POST /demand` endpoint + Create Demand form, gated to **CEO, Partners, Sales, and BU Head** — confirmed by Avinash 2026-08-12: "sales is done by CEO, partners, sales and BU Head." HR/Recruiter are downstream consumers of demand, not creators.
2. On creation, auto-generate a `Task` (`task_type=GENERAL`) assigned to the relevant BU Head via the department routing that already exists.
3. BU Head reviews and directs it from their existing task queue — no new "demand inbox" UI needed, reuse what's there.
4. `DemandConfirmationScreen.js`'s existing SOW-confirmation / alignment-call-tracking / fit-sign-off functionality stays as a *later* stage in the flow (once BU has directed it and a Specialty placement is being pursued) — not the entry point.

**Status: not yet built. Awaiting Avinash's go-ahead before implementation, given the RBAC-role question above still needs confirming.**

---

## Stage 2 — Create Job — 🟢 VERIFIED (with caveats already fixed this session)

`POST /jobs/create_job`, `JobCreate.js`. Actually created real jobs this session. Fixed today: validation no longer blocks on invisible fields (Skills/HR), End Date removed, Role Type simplified to auto-derive from client. **Still open, not yet fixed:** the AI-assisted "Generate Overview + Roles" flow (`/jobs/generate-with-agent`, `/jobs/generate-complete`) is not deployed to production (separate from this local-dev finding — see the prod deploy gap from earlier in this session).

---

## Stage 3 — Add Candidate / AI Auto-Identifies Candidate — 🟢 VERIFIED, JUST FIXED

`POST /onboarding/create_candidate` → `run_auto_assign_ai_agent_in_background()`. This was the tenant_id bug fixed this session — confirmed working end-to-end: candidate creation now reliably triggers real Thunder assignment, first-touch WhatsApp/email attempt, and visible activity feed entries. The "AI auto-identifies candidate" half (Thunder proactively sourcing/matching candidates against open demand, rather than only reacting to a manually-added candidate) — **not verified this session, likely 🟡 at best** — `ready_for_opportunity_service.py` exists and is triggered on job publish, worth checking next.

---

## Stage 4 — Auto Interview Scheduling — 🟡 SPOT-CHECKED, LIKELY NOT AUTONOMOUS

`InterviewSchedule.js` + `app/services/interview_service.py`, `calendar_matching_service.py`, `interview_availability_service.py` all exist. But the screen name and the CLAUDE.md history ("Added 'Schedule Interview' button... opens full Schedule Interview modal") both describe a **manual, HR-triggered** flow — someone clicks a button and fills a modal. No evidence found this pass of Thunder autonomously proposing/booking interview slots without a human initiating it. Given the pattern found today (Core-Pull scan, Bench scan, Revenue Leakage — all manual-trigger where they could be proactive), I'd bet this is the same shape until proven otherwise.

---

## Stage 5 — Panel Feedback — 🟡 SPOT-CHECKED, LOOKS REAL

`InterviewFeedbackScreen.js` — per recent commit history (`a386d27 Implement Interview Feedback Screen with Flash-Panel comparison & coaching emails`), this was purpose-built recently and sounds substantive (Flash-vs-panel comparison, coaching emails). Not live-tested this session.

---

## Stage 6 — Hiring Manager Check — ⚪ NOT YET LOOKED AT

No dedicated "hiring manager sign-off" step distinct from panel feedback found in this pass. May be folded into panel feedback, may not exist as its own gate. Needs a real look.

---

## Stage 7 — BU Final Approval — 🟡 SPOT-CHECKED

`hiring_workflow_service.py` exists and is named plausibly. Job creation already has a real BU Head approval gate (`create_job.py`'s `_can_auto_approve_job` / pending_approval flow, confirmed reading the code earlier this session) — but that's approval of the **job posting**, not of a **specific candidate** reaching BU for final hire sign-off. Whether a distinct "BU approves this candidate for hire" gate exists wasn't confirmed.

---

## Stage 8 — Auto Document Request — 🟡 SPOT-CHECKED, ORDERING CONFLICT WITH YOUR SPEC

`document_collection_service.start_document_collection(db, candidate, conversation, offer, tenant_id)` exists — **but its signature requires an already-generated `OfferLetter`**. Your stated pipeline order is `BU approval → document request → HR validation → generate offer`; the code's actual order is `offer generated → THEN document collection starts`. Either your intended process order differs from what's built, or this needs re-sequencing — worth confirming which is correct before treating this as a bug.

---

## Stage 9 — HR Document Validation — ⚪ NOT YET LOOKED AT

`Documents.js` screen exists. Verification logic not checked this pass.

---

## Stage 10 — Generate Offer — 🟡 SPOT-CHECKED

`OfferLettersScreen.js`, `OfferScreen.js`, `OfferListing.js`, `offer_letters.py` endpoint all exist — a real, apparently substantial feature (matches EPIC-16/offer-approval-workflow history referenced in CLAUDE.md). Not live-tested this session.

---

## Stage 11 — Add as Employee — 🟢 LIKELY VERIFIED (by prior session, per CLAUDE.md history)

Per this repo's own CLAUDE.md history: `"Fix: Candidate-to-Employee conversion endpoint"` (commit `6e50e5f`) — a real, already-fixed bug in a prior session. Not re-verified live this session, but this is the one stage with documented prior confirmation rather than a cold guess.

---

## Stage 12 — Assign to BU & Client & Project — 🔴 CONFIRMED BROKEN (live-reproduced 2026-08-12)

Was 🟡, now fully confirmed live. `AllocationsScreen.js` ([DEFECT-2026-08-12T5]) is the only UI for this and requires typing raw Employee/Demand/Project UUIDs — nobody can realistically use it. Traced the real consequence: `employee_self_service.get_my_active_allocations()` requires a real `EmployeeAllocation` row to exist before a timesheet can even start. With no usable way to create that row, **no employee can ever get a timesheet** — confirmed by reproducing "Could not load your project allocations" / "no timesheet to fill yet" on `/my-timesheet` directly. This is the actual root blocker for Stage 14, not a parallel issue.

---

## Stage 13 — Send Timesheet Login, URL, Details — 🟡 SPOT-CHECKED

`onboarding_agent_service.py` and `email_service.py` both reference onboarding/welcome communications. Whether it specifically sends timesheet login credentials/URL as its own step, separate from general welcome email, not confirmed.

---

## Stage 14 — Create/Submit Timesheet — 🟡 SUBMIT PATH SOLID, ROUTING HALF-BUILT (verified 2026-08-12)

`timesheet_service.py` is genuinely mature. Two real findings from live tracing:
- **Blocked entirely by Stage 12** (see above) — no allocation, no timesheet, confirmed live.
- **Finance validation before invoicing is real and hard-enforced** — R-10: `invoice_service.py` raises `UnapprovedTimesheetBlocksInvoice` if any timesheet in the billing period isn't APPROVED, no partial invoicing. This part is correct as built.
- **Reporting Manager approval is real but silent** — `approve_timesheet()` works and is RBAC-gated correctly, but `TimesheetApprovalReminderJob` and the approval notification/email are explicitly "not built" per the module's own comment ([DEFECT-2026-08-12T7]). An RM has no way to know a timesheet is waiting unless they go looking manually.

---

## Navigation — Sales section (Avinash, 2026-08-12)

Opportunity Pipeline currently sits in the **Finance** nav group; Client Management and Demand Confirmation sit in **Workforce** — three pieces of one sequential sales flow (Opportunity → Demand → Contract → Client), split across two unrelated groups, with no Contract screen at all (though `Client.contract_start_date/end_date/url` columns already exist).

Data-layer good news: `Opportunity.client_id` and `Demand.client_id` are both real required FKs — the "opportunity/demand can reference an existing or new client" linkage already exists structurally. `CreateOpportunityForm` already has working "select existing client OR + New prospect inline" UI (blocked only by the unrelated `getAllUsers()` crash being fixed in this same session).

**Plan:** new "Sales" nav group — Opportunity Pipeline, Demand (once Stage 1 above is built), Contract (net-new screen + likely net-new backend entity, since Client's contract fields today have no dedicated creation/negotiation workflow), Client Management (relocated from Workforce). **Confirmed by Avinash 2026-08-12: "anything monetary stays in finance"** — Executive Revenue, Partner ROI, CEO FY Progress, and CFO Agent all stay in Finance. Sales only gets the four screens above.

**Status:** design confirmed, not yet built. Depends on Stage 1 (Demand creation) landing first, since "Demand" as a nav item needs something real to point at.

---

## Immediate priority order (my recommendation)

1. **Stage 1 (Create Demand)** — nothing else in the pipeline has a real front door without this. Highest leverage fix in the whole list.
2. **Stage 12 (Employee→Project assignment)** — documented as still-broken from a prior session; blocks Stage 14 even if everything before it works.
3. **Stages 4, 6, 7, 8, 9, 13** — need the ⚪/🟡 items actually verified with the same rigor as Stages 1–3, before trusting any "looks like it exists" assessment.
4. The already-logged defects in `DEFECTS_LOG.md` (CRITICAL HR/RBAC blocker, `/admin/ai-config`, Revenue screen autonomy, Opportunity Pipeline interactivity) slot in as follows: HR/RBAC blocks Stage 2 directly (HR literally can't create jobs) — that one jumps ahead of even Stage 1 in true urgency since it's an active, confirmed, blocking defect on a stage otherwise marked working.

**Corrected true top priority given all of the above: the CRITICAL HR/RBAC defect (blocks Stage 2, already confirmed blocking) — then Stage 1 (Create Demand, confirmed missing) — then Stage 12 (Employee/Project assignment, documented broken) — then verify the remaining 🟡/⚪ stages in pipeline order.**
