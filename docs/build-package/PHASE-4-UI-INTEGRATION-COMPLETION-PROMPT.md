# Phase 4 UI + Integration Completion — Continuation Prompt

**Use this prompt to resume this work in a new session, or as the working checklist for the current one.** Read `CLAUDE.md` first for full project context and conventions — this file is the specific, scoped task list for finishing what Phase 4 left incomplete.

---

## The correction this prompt exists to enforce

Earlier this build round, four Phase 4 stories were marked `Done` in `WROS_Canonical_Backlog_S001-401.xlsx` after only their backend (models, services, migrations, tests) was built — no REST API, no UI, nothing a person could actually click through. Avinash caught this directly:

> "A story is not complete till all requirements in it are done, the UI, Integration, Business rules and all corresponding test cases. Just building backend is not going to be of help for either of us as we can't track them in future on what all are pending."

This is now the standing **Definition of Done** (see the top of `C:\Users\AvinashMukund\Documents\Claude\CLAUDE.md`): a story is Done only when its **UI, its API/integration layer, its business rules, and its tests are all complete.** Backend-only is `In Progress`, never `Done`. All four stories below were reverted from `Done` to `In Progress` in the canonical sheet.

## The instruction for this pass: top-down, one story complete at a time

Do **not** build all four backends, then all four APIs, then all four screens (that's the mistake that already happened once, just shifted up a layer). For each story below, in order:

1. Build/verify the API endpoints wired to the already-built service layer.
2. Build the frontend screen(s)/panel(s) that use those endpoints.
3. **Verify it actually works in the browser** — real click-through with the preview tools, not just "the code compiles." Screenshot or describe what you saw.
4. Write/extend tests: API-level tests (FastAPI `TestClient`, same pattern as `tests/test_thunder_test_chat_api.py`) in addition to the existing service-level tests.
5. Run the full backend suite, confirm green.
6. Commit and push (backend + frontend separately, both directly to `main`, per standing instruction).
7. **Only then** mark that story `Done` in `WROS_Canonical_Backlog_S001-401.xlsx` (with a `Change Log` entry) and move to the next story.

Do not start story 2's API until story 1 has a working, tested screen. Vertical slices, not horizontal layers.

## Order to work in

Avinash's own framing: the Resource Management Agent is "the most important bread and butter for BlitzenX." Suggested order (confirm with him if picking up in a fresh session and this hasn't been explicitly reconfirmed):

1. **HRMS-1105 Resource Management Agent (canonical S-320)** — highest business priority.
2. **S-353 Core-Pull Engine + S-373 Specialty Pool Guard** — built together originally, natural to surface together (S-373's guard is directly visible inside the Core-Pull flow).
3. **S-372 Confirmed vs Potential Demand Workflow**.

---

## Story 1: HRMS-1105 Resource Management Agent (canonical S-320)

**Backend already built** — `app/models/resource_agent.py` (`BenchAllocationRecommendation`, now with `PENDING_RM_REVIEW` → `IN_PROGRESS` → `APPROVED`/`REJECTED`), `app/services/resource_management_agent_service.py`. Key functions to wire up:
- `run_bench_scan(db, tenant_id, bu_head)` — triggers the scan (Core-Pull detection + LLM ranking).
- `get_recommendation_queue(db, tenant_id)` — the RM's review queue, confidence-sorted.
- `start_pursuing_recommendation(db, recommendation, actor_user_id)` — the exclusivity gate; raises `EmployeeAlreadyActivelyEngaged` if the employee is already `IN_PROGRESS` elsewhere. **The UI must surface this block clearly** — this is the exact business rule Avinash asked to be architected cautiously (an employee already in interview stage at one client can't be pushed to a second).
- `approve_bench_recommendation(db, recommendation, actor_user_id)` — creates the real allocation.
- `reject_bench_recommendation(db, recommendation, actor_user_id)`.
- `is_employee_actively_engaged(db, employee_id)` — useful for showing "why is this blocked" in the UI.

**API to build**: new `app/api/v1/endpoints/resource_management.py` (or similar), registered in `app/api/v1/routes.py`. Suggested routes:
- `POST /resource-management/scan` — trigger `run_bench_scan()` (admin/RM-triggered manual run, since no scheduler exists yet — that's a known, separate deferred piece, not blocking this).
- `GET /resource-management/recommendations` — the queue.
- `POST /resource-management/recommendations/{id}/pursue` — `start_pursuing_recommendation()`.
- `POST /resource-management/recommendations/{id}/approve` — `approve_bench_recommendation()`.
- `POST /resource-management/recommendations/{id}/reject` — `reject_bench_recommendation()`.
- Auth: same pattern as Thunder's `get_current_hr_or_admin` unless a narrower RM-specific permission already exists — check `app/core/dependencies.py`'s `require_permission()` options first.

**UI to build**: a screen (RM/Partner-facing) showing the recommendation queue — employee, matched demand, confidence, rationale, current status. Actions: Pursue / Approve / Reject. When Pursue is blocked, show the clear error from `EmployeeAlreadyActivelyEngaged`, not a generic failure.

**Test the actual scenario Avinash described**: search for a Guidewire developer, have them pursued for Client A, confirm the UI blocks pursuing them for Client B until A resolves.

---

## Story 2: S-353 Core-Pull Engine + S-373 Specialty Pool Guard

**Backend already built** — `app/models/core_pull.py` (`CorePullEvent`, `SpecialtyPoolReplacementPlan`), `app/services/core_pull_service.py`. Key functions:
- `detect_core_pull_conflict(db, employee, core_demand)`, `execute_core_pull(db, event, ...)`, `override_core_pull(db, event, actor_role, actor_user_id, justification, ...)`.
- `check_specialty_pool_guard(db, employee)`, `log_replacement_plan(db, employee_being_moved, replacement_strategy, expected_replacement_date, logged_by)`.

**API to build**: endpoints for viewing pending `CorePullEvent`s, the current Specialty pool count/guard status, executing a detected event, the BU Head override action (100-char justification), and the replacement-plan submission form.

**UI to build**: an admin/BU-Head-facing panel — Specialty pool count (flag when at 41, the one-move-from-breach warning per AC-6), list of pending Core-Pull events, execute/override actions, replacement-plan form when blocked.

---

## Story 3: S-372 Confirmed vs Potential Demand Workflow

**Backend already built** — `app/models/demand_confirmation.py` (`DemandAlignmentCall`), `Demand.confirmation_status`/`sow_reference`/`sow_received_date`, `app/services/demand_confirmation_service.py`. Key functions:
- `confirm_demand_with_sow(db, demand, sow_reference, sow_received_date)`.
- `schedule_alignment_call(db, demand, employee, curtis_user_id, bu_head_user_id, scheduler)`.
- `confirm_fit(db, call, participant, confirmed, notes)` — `participant` is `"EMPLOYEE"` or `"BU_HEAD"`; each can only confirm once, cannot be overridden by the other.
- `trigger_specialty_client_release(db, call, demand, speciality_rm, tenant_id)` — the hard gate: `confirmation_status == "CONFIRMED"` AND both fit confirmations `True`.

**API to build**: SOW confirmation form submission, alignment call scheduling trigger, fit-confirmation endpoints (one for the employee's own portal view, one for the BU Head), the release-trigger action.

**UI to build**: likely two surfaces — an RM/BU-Head admin view (SOW entry, scheduling, BU Head fit confirmation, release trigger) and an employee-facing fit-confirmation view (their own honest yes/no, which the BR says can never be overridden — make sure the UI doesn't imply anyone else can answer for them).

---

## Cross-cutting reminders (apply to all three stories)

- **Read the real requirement docs before building UI copy/flows**, not just the backend code — `Requirements/S-274_HRMS-1105.docx`, `Requirements/S-353_HRMS-0514.docx`, `Requirements/S-373_HRMS-0529.docx`, `Requirements/S-372_HRMS-0528.docx`. The UI Fields sections in each doc (even if sparse) are the closest thing to a UI spec.
- **Full backend test suite before every commit** — currently 616/616 passing (1 xfailed); don't regress it.
- **Verify the frontend in an actual browser** using the preview tools — don't claim a UI works without having clicked through it. `start-dev.cmd` must stay on disk permanently in the frontend repo (gitignored) — do not delete it after testing, that's what caused the "localhost won't come up" issue earlier.
- **Commit and push directly to `main`** for both repos, no branches/PRs, per Avinash's standing instruction — small logical units, not one giant commit per story.
- **Only mark a row `Done` in the canonical sheet once all four layers are verified working**, with a `Change Log` entry.
- **Ask before guessing** on genuinely ambiguous UI/UX calls (e.g., exact wording, exact placement) rather than inventing silently — Avinash has been consistent about wanting judgment calls surfaced, not guessed.
