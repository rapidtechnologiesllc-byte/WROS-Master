# Addendum: Two Gaps Closed Before Claude Code Starts

Both found by cross-checking against the CFO's Build 27 financial model and the Talent Engine's 35-KPI framework respectively. Neither is cosmetic — one is a missing financial guardrail, the other is ambiguity that would otherwise get resolved inconsistently by whoever builds S-364 first.

---

## Gap 1 — Minimum Bill Rate is missing entirely

**⚠ CORRECTED per the authoritative BlitzenX Operating Model reference (v1.0, locked):** the formula below was wrong in the original version of this document. The correct, locked formula is:

```
Min Bill Rate = (Fully Loaded Cost $/hr + RM Burden $/hr) × Multiplier
```

**RM Burden is a distinct cost component this document originally omitted entirely** — total annual RM cost divided by billable headcount divided by billable hours per year (worked example: ₹35,00,000 ÷ 45 ÷ 1,680 = $0.541/hr), spread evenly across every billable employee. Omitting it understates the true delivery cost floor on every rate decision built on top of it.

This is now fully specified and built as three stories in EPIC-16: **HRMS-1608 (Fully Loaded Cost Engine)**, **HRMS-1609 (RM Burden Allocation Engine)**, and **HRMS-1610 (Minimum Bill Rate Engine)** — see those story documents for the complete, correct implementation. The multiplier itself (1.25 as stated, vs. 1.19 needed to match the CFO's own reference sheet's $14.30 figure) remains an open, placeholder constant pending Avinash's confirmation, per Section 16 of the Operating Model reference.

Nothing in any WROS story checks a demand's or opportunity's bill rate against this floor yet at the enforcement points (R-11) — that wiring is specified in HRMS-1610's story doc and still needs to be built into S-236/S-239/S-301.

**New table (add to Phase 2's Data Model, Domain 3 — Employee section):**
```
employee_cost_structure (id, employee_id, pay_structure_type, fully_loaded_cost_usd_cents,
                          min_bill_rate_usd_cents, calculated_at, calculation_inputs_json)
```
`min_bill_rate_usd_cents` is always `fully_loaded_cost_usd_cents × 1.25`, recalculated whenever the underlying cost inputs change (salary change, benefits change, currency/FX update) — same "recalculate on change, don't let it go stale" discipline already used elsewhere in this backlog (e.g., S-211's revenue potential recalculation).

**Where this plugs into stories that already exist:**
- **S-236 Create Opportunity / S-239 Create Role Demand:** when a bill rate is entered, check it against the relevant employee's (or, pre-staffing, the role's typical) `min_bill_rate_usd_cents`. Below-floor is not a silent allow — surface a warning at minimum, and per the CFO's own margin discipline, treat it the same way R-04's bench-first override works: allowed only with a logged justification from whoever has pricing authority (BU Head, per Section 12's access model), not blocked outright, since there may be legitimate strategic-pricing reasons — but it must never be silent.
- **S-304 Project Revenue Estimate & Margin Indicator:** the "rough margin indicator" this story already computes should explicitly flag when a project's assigned resources are billed below their individual min bill rates, not just show an aggregate healthy/tight/at-risk badge.
- **S-343 Payroll System Sync:** this is where `fully_loaded_cost_usd_cents` actually gets its real inputs (compensation, benefits) — the cost-structure calculation should be triggered from the same data this story already syncs, not a separately-maintained figure.

**New business rule (add to R-01–R-10 reference as a platform-level rule, call it R-11 for continuity):**

| Rule | Requirement | Enforcement point |
|---|---|---|
| R-11 | Bill rate below an employee's fully-loaded-cost × 1.25 floor requires logged BU Head justification, never silent | Checked at S-236/S-239 bill rate entry, re-checked at S-301 allocation creation |

---

## Gap 2 — The 35-KPI framework: which are system-calculated, which are manual, who sees what

S-364 (30-Day Buddy Program) specifies the 35 KPIs and their three owners (HR/Buddy/RM) but doesn't classify each one as auto-calculated vs. requiring a human's subjective input, and doesn't specify view scoping beyond "never visible to employee." Here's the classification, resolved so Claude Code builds each KPI the right way the first time instead of guessing:

### HR-owned (12) — mostly system-calculated, one exception

| # | KPI | Type | Data source if auto |
|---|---|---|---|
| 1 | Timesheet submission punctuality | **Auto** | Timestamp diff, timesheet submission vs. due time |
| 2 | Response time to HR emails | **Auto** | Email/ticket timestamp diff (requires the embedded Outlook integration, Phase 3-adjacent S-380, to read timestamps) |
| 3 | Onboarding task completion rate | **Auto** | Checklist completion %, from the onboarding checklist system |
| 4 | IT/equipment setup compliance | **Auto** | Days-to-complete from asset provisioning record |
| 5 | Benefits enrollment completion | **Auto** | Boolean/date from HR system |
| 6 | Policy acknowledgement sign-offs | **Auto** | % signed, from e-signature/acknowledgment log |
| 7 | Background check responsiveness | **Auto** | Days-to-submit from document collection timestamps |
| 8 | NDA and contract execution speed | **Auto** | Hours from send to sign, DocuSign timestamp diff |
| 9 | Training module completion | **Auto** | % complete from training system |
| 10 | Meeting attendance rate | **Auto** | % attended vs. invited, from calendar integration (S-380) |
| 11 | Calendar responsiveness | **Auto** | Hours to accept/decline, from calendar integration |
| 12 | Communication tone in written comms | **Manual** | HR qualitative rating 1-5 — this is the one HR KPI requiring genuine human judgment, not inferable from a timestamp |

### Buddy-owned (15) — almost entirely manual, by design

These are subjective technical/professional judgment calls a system cannot compute — building any of these as "auto-calculated" would be a design error, not a shortcut:

| # | KPI | Type |
|---|---|---|
| 13-26 | Technical knowledge depth, requirements understanding, adhoc problem-solving, learning speed, code/config quality, documentation discipline, question quality, mistake ownership, initiative, team integration, communication clarity, escalation judgement, pressure attitude, peer interaction | **Manual**, all — buddy-entered 1-5 ratings via the weekly scoring flow |
| 24 | Deadline reliability | **Auto** | The one exception in this group — did they hit every buddy-set task deadline is a real date comparison, not a judgment call, if buddy-assigned tasks are tracked with due dates in the system |

### RM-owned (8) — mixed, lean auto

| # | KPI | Type | Data source if auto |
|---|---|---|---|
| 28 | Timesheet accuracy | **Auto** | Hours logged vs. hours expected from allocation percentage |
| 29 | Daily standup quality | **Manual** | RM judgment — "meaningful vs. filler" isn't computable |
| 30 | Proactive communication | **Manual** | RM judgment |
| 31 | Sprint/task velocity | **Auto** | Stories/tasks completed vs. committed, from project milestone tracking (S-302) |
| 32 | Responsiveness to RM check-ins | **Auto** | Hours to respond, same pattern as HR KPI #2 |
| 33 | Interview participation | **Auto** | Did they take an assigned interview — boolean from interview panel assignment |
| 34 | Interview quality score | **Auto** | Already built as its own story — S-377 Interviewer Quality Scoring, feeds this KPI directly rather than being computed twice |
| 35 | Bench responsibility behaviour | **Manual** | RM judgment — "productive vs. passive on bench" isn't computable from bench-duration data alone |

### Visibility rule, resolved

- **Never visible to the employee themselves** — this was already explicit in S-364/S-354 and doesn't change.
- **Write access is scoped to the owning role for manual KPIs** — HR can only enter KPI #12, Buddy can only enter KPIs #13-23/25-27, RM can only enter KPIs #29/30/35. A role should not be able to write a KPI it doesn't own, even though all three (plus BU Head) can *view* the composite scorecard.
- **Auto-calculated KPIs have no write path for any human role at all** — they're computed, full stop. If a reviewer ever sees a UI that lets someone manually override an auto-calculated KPI like "Timesheet submission punctuality," that's a defect against this classification, not a feature.
- **BU Head sees the full composite scorecard** (all 35, both manual and auto) for their Day-30 gate decision (S-365) — this is the one role with full visibility by design, since they're the one making the graduate/extend/exit call.

**Add this table to Phase 2's Data Model, Domain 3:**
```
buddy_program_kpi_definitions (id, kpi_number [1-35], owner_role [HR/BUDDY/RM],
                                calculation_type [AUTO/MANUAL], data_source_description)
```
Seed this table with all 35 rows from the classification above at migration time — this becomes the single source of truth Claude Code checks before building each KPI's scoring UI or calculation job, so the auto-vs-manual decision is never re-litigated per-KPI during the build.
