# Phase 4: Resource Management

**Build this fourth — unlocked in parallel with Phase 3's other three workstreams, but detailed separately here given its scope and its direct dependency on the Core-Pull policy, which is one of this platform's two genuinely non-negotiable rules (alongside R-01 through R-10).**

---

## Why this gets its own phase document

Resource management is where three things this platform cares most about collide in the normal course of business: a bench employee's actual availability, the Core-Pull policy's zero-debate mandate, and the 40-person minimum Specialty pool floor. Getting any one of these slightly wrong doesn't fail loudly — it fails as a BU Head discovering weeks later that Specialty silently dropped below its staffing floor, or a Core-certified employee getting pulled without the required replacement plan ever being logged. This phase exists to make sure that can't happen quietly.

---

## Part A — Already-specified stories (build first, in this order)

1. **HRMS-1105 Resource Management Agent** (full doc exists). Runs every 30 minutes against the bench pool. Two distinct behaviors that must never be blurred together:
   - **Core-vs-Speciality simultaneous eligibility detection** — when a bench employee matches both a CORE and a SPECIALITY demand at once, this agent *detects the situation and calls* HRMS-0312's existing Core-Pull engine. It does **not** contain its own copy of the Core-wins decision logic. If you find yourself writing an `if delivery_engine == CORE: win()` conditional inside this agent, stop — that logic already exists in HRMS-0312 and duplicating it is exactly the kind of drift this platform has already been burned by once (the LinkedIn-sourcing triplication).
   - **Non-conflicting allocation ranking** — for bench employees who only match one engine's demand, an LLM-based ranking (advisory only) surfaces a best-fit recommendation to the RM. This never auto-creates an `employee_allocations` row. Only an explicit RM-approval action does that.

2. **S-373 Specialty Pool Minimum 40 Core-Certified Guard** (full doc exists). Called by *every* Core-move path — HRMS-1105's Core-Pull trigger, S-372's Confirmed/Potential Demand Workflow, any manual transfer — before the move completes. If the count after the move would drop below 40, the move blocks and the BU Head must log a replacement plan (100+ character strategy plus expected replacement date, both required) before it's allowed to proceed. The alert fires at 41 too — one move from breach — not only after the breach happens.

3. **S-353 Core-Pull Conflict Rule Engine** (full doc exists). Core wins, same-day, no debate — Section 4.3's policy exactly as written. Publishes `risk_tier=MEDIUM` to the Orchestration Router (Phase 3, Part A) before executing, since a Core-Pull affects live project staffing. Specialty's RM is notified before any client is told anything — the client always finds out last, never first, so a disruption doesn't happen for nothing if a downstream confirmation later falls through.

4. **S-372 Confirmed vs Potential Demand Workflow** (full doc exists). The two genuinely different paths — Confirmed (SOW signed, same-day alignment call, notify Specialty client with a replacement plan) versus Potential (interview-first, Specialty client notified only after SOW is actually in hand). Getting these two paths crossed is a relationship-damaging mistake with a real client, not just a data-quality issue — build the branching explicitly, don't try to unify them into one flow with conditionals sprinkled through it.

---

## Part B — The 11-story gap: Resource & Bench Management basics

No requirements doc exists yet for this cluster, but it's foundational to everything in Part A — HRMS-1105 can't rank or detect anything without a real bench pool to query. Minimum viable schema and behavior to unblock Part A:

```
bench_pool (id, tenant_id, employee_id, available_from, skill_tags, bench_duration_days, bench_cost_usd_cents)
employee_utilization_metrics (id, employee_id, period, utilization_pct, billable_hours, bench_hours)
allocation_conflict_log (id, employee_id, conflicting_allocation_ids_json, resolution, resolved_at)
```

Core behaviors needed, in priority order:
1. **Mark Employee as Bench** — a status transition on the `employees` table (not a separate entity), triggered when an allocation ends with no immediate next allocation. This is what populates `bench_pool` and is what HRMS-1105 actually queries every 30 minutes.
2. **Bench Duration & Aging** — how long someone's been on the bench, feeding both HRMS-1105's ranking urgency and cost-visibility reporting.
3. **Allocate Employee to Project** — the write path that actually creates an `employee_allocations` row. This is the *only* thing that can move someone off the bench pool — HRMS-1105 recommends, this action executes, and it's always a distinct human (RM) decision, never automatic, matching the advisory-only design already established for HRMS-1105 itself.
4. **Allocation Conflict Detection** — checking that a new allocation doesn't push an employee's total overlapping percentage above 100%, the same check S-301 (Project & Delivery, already built) calls before saving any assignment. Build this once, here, and have S-301 call it — don't duplicate the conflict check in two places.
5. **Staffing Eligibility Engine** — confirms an employee is actually eligible for a given engine's demand before they can even appear in HRMS-1105's ranking — respects `buddy_program_status=GRADUATED` (per S-365) and `core_certified` status (per S-352) as hard gates, not just ranking inputs.

---

## The one rule that governs this entire phase

**Core-Pull decision logic exists in exactly one place: HRMS-0312.** Every story in this phase — HRMS-1105's detection, S-353's execution, S-373's guard, and any of the 11 gap stories that might touch allocation — calls it or checks its output. None of them contain an independent copy of "Core wins" as a conditional. If a code review in this phase finds Core-wins logic anywhere other than HRMS-0312 itself, that's a defect, not a stylistic preference, and it should block merge the same way a missing R-01 gate would.

---

## Acceptance gate for this phase

- [ ] A bench employee matching both a CORE and SPECIALITY demand triggers HRMS-0312 within one HRMS-1105 scan cycle, verified by inspecting that the trigger is a function call, not a local conditional
- [ ] No `employee_allocations` row is ever created directly by HRMS-1105 — only via explicit RM approval, verified by code review and integration test
- [ ] A Core-move that would drop the Specialty pool below 40 is blocked until a replacement plan (100+ chars, expected date) is logged — verified by attempting the move without one
- [ ] The Specialty client in a Confirmed-demand scenario is notified only after the alignment call and replacement plan exist; in a Potential-demand scenario, only after SOW is in hand — both paths tested independently, not as variations of one shared code path
- [ ] Allocation Conflict Detection is called from exactly one shared location, confirmed by checking that S-301 (Project & Delivery) and this phase's own allocation-creation flow both call the same function, not two independently-implemented checks
