# Phase 3: Thunder Master Agent & Agentic Layer

**Build this third, after Phase 1 and Phase 2 acceptance gates both pass.** This phase has two parts: a small shared core that must be built first and by one team/session, and four parallel workstreams that fan out from it and can genuinely build simultaneously once the core exists.

---

## Part A — Shared Core (build first, single-threaded, do not parallelize this part)

Every one of the four workstreams below depends on these two pieces existing and being trustworthy. Building them in parallel with the workstreams risks four teams each hitting bugs in a foundation that's still being written underneath them.

### A1. Thunder Conversation Core

This is the actual AI recruiter engine — full-conversation AI on WhatsApp, defined across EPIC-04 (80 stories, not yet fully re-audited in this package but referenced consistently throughout everything already built). Two functions everything else in this platform calls instead of reimplementing:

- **`buildCandidateContext()`** — called before Thunder generates any response. Reads full cross-channel history (WhatsApp, any prior recruiter notes, desire profile). No response is ever generated without this being called first — this is not a performance optimization to skip when convenient, it's why Thunder doesn't ask a candidate a question already answered three messages ago.
- **`sendThunderMessage()`** — the only send path. Enforces, every time, with no bypass:
  - R-08: if a recruiter sent the most recent message, Thunder is locked and the send is rejected
  - Consent: `candidates.consent_given` must be true
  - Duplicate-send prevention within a debounce window
  - Every other story in this platform that sends a candidate message — HRMS-1104's Outreach Agent, HRMS-0516's Reporting Manager bot (employee-facing, but same underlying send-governance pattern), any future story — calls this function. **No story anywhere in this codebase implements its own message-send logic outside this function.** This is the single most important rule in this entire phase.

### A2. Orchestration Router (HRMS-1101 — full doc exists, build exactly as specified)

The deterministic conflict-detection layer every agent in the four workstreams below publishes an `agent.action.intent` event to before acting. It is explicitly **not** an LLM-based arbitration layer — six seeded conflict rules (Outreach-vs-Core-Pull collision, Thunder conversation ownership override, and four others per the story doc), plus a narrow LLM classification step for genuinely novel conflict patterns that only ever escalates severity, never auto-resolves.

**Build order within Part A: A1 before A2** — the Router's seeded conflict rules reference Thunder's send path (BR-1101-02, "Thunder conversation ownership overrides all agents"), so Thunder's ownership-lock behavior needs to exist and be testable before the Router can meaningfully enforce a rule referencing it.

### A3. Notification and Audit Wiring Check

Before declaring Part A complete, confirm every agent action in every workstream below routes its human-facing alerts through Phase 1's `notifications` table (via HRMS-0113, already specified) and every hard-rule-adjacent decision writes to `audit_log` — this is a checkpoint, not new work, since both already exist from Phase 1.

**Part A acceptance gate — do not fan out to the four workstreams until:**
- [ ] `sendThunderMessage()` correctly rejects a send when R-08's ownership condition is active, verified by test
- [ ] `buildCandidateContext()` is confirmed as a mandatory pre-call in Thunder's response generation path — no code path generates a response without it
- [ ] HRMS-1101's six seeded conflict rules are live and each independently testable
- [ ] A test conflict between two of the four workstreams below (simulated) is correctly caught by the Router before either agent's action executes

---

## Part B — Four Parallel Workstreams

Once Part A passes its gate, these four can be assigned to four separate Claude Code sessions (or four separate engineers directing Claude Code) and built simultaneously — each workstream's agents are independent of the other three except through the shared Router, which already exists.

### Workstream 1 — Recruit

**Agents to build (all fully specified, EPIC-11):**
- HRMS-1102 Workforce Demand Monitoring Agent — 15-minute scan, gap-severity classification, auto-creates sourcing alerts once R-04 bench-first confirms insufficiency
- HRMS-1103 LinkedIn Sourcing Agent Loop — Boolean query generation, dedup via `createCandidateSafe()`'s dedup sub-function only, stages candidates for review, never creates a candidate record directly
- HRMS-1104 / S-319 Automated Outreach Agent — composes and sends first-touch messages via `sendThunderMessage()` exclusively, 3-touch cap, R-08-aware (does not auto-switch channel on an ownership-lock rejection)
- HRMS-0527 Curtis Rule — Partner Intent ML Engine — nightly batch, infers partner demand patterns to minimize qualification questions

**`[GAP-SPEC]` areas this workstream also closes** (LinkedIn Autonomous Sourcing's 7 undocumented stories, Boolean Search's 11): treat these as refinements/extensions of HRMS-1103's existing agent — check for overlap before writing new sourcing code, per the duplication lesson already learned once in this project (LinkedIn sourcing was independently specified three separate times before being caught).

**Hard rule this workstream must never violate:** R-04 (bench-first, checked before every external sourcing action, no exceptions) and R-07 (dedup via the one sanctioned path).

### Workstream 2 — Interview

**Agents/logic to build:**
- R-05 sequencing gate (L1-before-L2) — **this is the single highest-priority item in this workstream**, since the existing Onboarding Module code has zero enforcement of it today
- HRMS-1501 Interview Integrity Analysis Engine — full doc exists; consent-gated, produces assessment only, invisible until released
- HRMS-1502 Panel Feedback Cross-Validation & Clarification Routing — full doc exists; **never overrides a panel decision, enforced in code, not policy**

**`[GAP-SPEC]` Interview Decision Engine & Compliance Rules (10 undocumented stories):** this is where R-05's gate physically lives in the schema (`interview_panels`, `interview_scorecards` from Phase 2). Build the gate first, then layer the remaining decision-engine logic on top.

**Existing code to extend, not replace:** `OnboardingModule-Backend`'s `interviews.py` panel-creation endpoint. Add the R-05 sequencing check as a precondition on panel creation — do not rewrite the endpoint from scratch, extend it per the Development & Review Standard's build-brief template.

**Hard rule this workstream must never violate:** R-05 (absolute, no override authority anywhere).

### Workstream 3 — Onboarding

**Stories to build (NEW-RM, fully specified):**
- S-364 30-Day Buddy Program — 35-KPI framework (HR 12 / Buddy 15 / RM 8), weekly scoring
- S-365 Buddy Program Graduation Gate — BU Head approval, Graduate/Extend/Exit
- S-351 Delivery Engine Assignment — every new hire enters SPECIALITY at the code level, no exceptions, DB constraint blocks CORE without `core_certified=TRUE`
- S-360 (HTD-specific) 4-Phase Gate Structure — if this hire is on the HTD track

**Existing code to extend, not replace:** `OnboardingModule-Backend`'s candidate-creation and document-collection endpoints. Two specific fixes required here, both already identified:
1. Add the R-01 5-year experience gate at creation time (today it's scored, not gated — see the Development & Review Standard for the exact test)
2. Wire the virus-scanning service to actually run before `is_virus_scanned` is ever set true (today the field exists and defaults false but nothing ever sets it — this is Phase 1's file-upload security work, B2/B5, applied to this specific endpoint)

**Hard rule this workstream must never violate:** R-01 (experience gate) and R-03 (full-time only, already partially enforced in this codebase per the earlier review — confirm it's server-side, not just the UI dropdown).

### Workstream 4 — Resource Management

Detailed fully in `04-RESOURCE-MANAGEMENT.md` — summarized here for sequencing purposes only:
- HRMS-1105 Resource Management Agent (full doc exists) — detects Core-vs-Speciality simultaneous eligibility, **calls** HRMS-0312's existing Core-Pull engine rather than reimplementing Section 4.3's Core-wins logic, advisory-only bench allocation ranking
- S-373 Specialty Pool Minimum 40 Core-Certified Guard — blocks a Core-Pull move that would breach the 40-minimum, requires a logged replacement plan
- S-353 Core-Pull Conflict Rule Engine — Core wins, same-day, MEDIUM risk_tier published to the Router (Part A)

**Hard rule this workstream must never violate:** Section 4.3's Core-Pull policy (no debate, no committee, BU Head logged override only) — and specifically, **this workstream detects and calls, it never reimplements the Core-wins decision logic**, which lives in exactly one place (HRMS-0312).

---

## Why these four, and why they can genuinely run in parallel

Each workstream touches a distinct slice of the schema (Recruit: `candidates`/`sourcing_*`/`outreach_sequences`; Interview: `interview_*`; Onboarding: `employees`/`employee_engine_history`/`buddy_program_kpi_scores`; Resource Management: `employee_allocations`/`bench_*`/`core_pull_events`) and the only place they'd naturally collide — an outreach agent and a resource-management agent both wanting to act on the same employee at the same time — is exactly the scenario HRMS-1101's Router (Part A, already built) exists to catch. That's the whole reason Part A had to come first: it's what makes "4X simultaneously" actually safe instead of just fast.

---

## Acceptance gate for the entire phase

- [ ] Part A's gate (above) passed before any workstream started
- [ ] Every one of the four workstreams' agents publishes `agent.action.intent` to the Router before acting, verified per workstream
- [ ] A simulated real conflict between Workstream 1 (Outreach) and Workstream 4 (Resource Management/Core-Pull) on the same employee is caught and resolved per HRMS-1101's BR-1101-01, not by chance
- [ ] R-05's gate (Workstream 2) is live and blocks a test L2-before-L1 attempt via direct API call, bypassing any UI
- [ ] R-01's gate (Workstream 3) is live and blocks a test sub-5-year-experience candidate via direct API call
- [ ] The existing Onboarding Module's four demoed features (Add Candidate, Schedule Interview, Start Pre-Onboarding, Collect Document) all pass the specific negative-case tests identified in the original code review
