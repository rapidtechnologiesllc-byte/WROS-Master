# WROS Claude Code Build Package — Master Index

**Read this file first, in every new Claude Code session on this project.** It tells you what exists, what order to build in, and where to find the detail for whatever phase you're currently working on.

---

## Build Order — Non-Negotiable

```
PHASE 1: Ultra-High Security Foundation        (see 01-SECURITY-FOUNDATION.md)
              ↓
PHASE 2: Complete Data Model                    (see 02-DATA-MODEL.md)
              ↓
PHASE 3: Thunder + Agentic Layer                (see 03-THUNDER-AGENTIC-LAYER.md)
    → unlocks 4 parallel workstreams:
      Recruit | Interview | Onboarding | Resource Management
              ↓
PHASE 4: Resource Management                    (see 04-RESOURCE-MANAGEMENT.md)
    (also unlocked in parallel by Phase 3, detailed separately given its scope)
              ↓
EPIC-16: Finance & Accounting Operations         (see 07-FINANCE-ACCOUNTING.md)
    (builds in parallel with Phase 3/4 once Phase 1+2 pass — depends on
     Payroll Sync and the Notification Engine, not on Thunder or Resource Mgmt)
```

**Why this order, specifically:** Phase 1 has to exist before a single line of business logic is written, because every other phase assumes tenant isolation, permission middleware, and audit logging are already bulletproof — retrofitting security into 350 stories' worth of code is far more expensive than building on a secure foundation from row one. Phase 2 has to exist before Phase 3 because every agent in the Thunder layer reads and writes real tables — building agent logic against a schema that's still shifting underneath it produces exactly the kind of integration debt this package exists to prevent. Phase 3 unlocks parallelization: once Thunder's core conversation engine and its sub-agent pattern exist, the four workstreams (Recruit, Interview, Onboarding, Resource Management) can build simultaneously because each is a distinct sub-agent or consumer of the same shell, not a shared bottleneck.

---

## What already exists — read before writing anything new

**256 of 386 canonical backlog stories have complete, audited requirements documents** (Why/What/Agentic AI/Before/Steps/UI Fields/Business Rules/Integrations/Data Mapping/Acceptance Criteria/Test Cases/Not In Scope/Demo — all 12 sections, all verified S-number/WROS-ID/title-consistent). These are organized by epic, not by ticket number — ticket numbers are historical Jira artifacts and carry no build-order meaning going forward.

**94 stories still have no written requirements** — concentrated in Client Portal legacy screens, Resource & Bench Management basics, Boolean Search, Interview Decision Engine, LinkedIn Sourcing, Talent Engine ATS, Analytics, and Nurture Engine. Where Phase 3 or Phase 4 touches one of these gaps, that gap gets closed just-in-time as part of this package (see each phase doc for which gaps it resolves) rather than blocking on a separate 94-story documentation effort.

**One existing partial codebase** (`OnboardingModule-Backend` / `OnboardingModule-Frontend`) already implements a rough version of 4 features: Add Candidate, Schedule Interview, Start Pre-Onboarding, Collect Document. It has real gaps against the hard rules (no R-01 experience gate, no R-05 interview-sequencing gate, single-field-only dedup, and a virus-scan field that's declared but never actually invoked). Phase 1 and Phase 3 both touch this code — don't discard it, extend it against the standard below.

**Companion document:** `WROS_Development_Review_Standard.md` (already delivered separately) — the hard-rule compliance checklist (R-01 to R-10), the cross-cutting architectural checks, and the build-brief/test-first template. Every phase in this package assumes that standard is being applied; it is not repeated in full here.

---

## The Ten Hard Rules — quick reference (full detail in the Development & Review Standard)

| # | Rule | One-line enforcement point |
|---|---|---|
| R-01 | 5-year experience floor, no exceptions without logged BU Head override | Blocks at candidate creation, not just scored |
| R-02 | No market profile without recruiter + CS sign-off | Both roles required, independently |
| R-03 | W2/full-time only | Enforced server-side, not just UI dropdown |
| R-04 | Bench-first before external sourcing | Hard gate, checked before every sourcing action |
| R-05 | L1 must pass before L2 scheduled | No exceptions, checked at panel-creation time |
| R-06 | Human dependency < 20% by Month 6 | Platform-level tracking, not a per-story gate |
| R-07 | createCandidateSafe() is the only creation path | Multi-field dedup (email + phone + LinkedIn), not single-field |
| R-08 | Thunder locked when recruiter owns conversation | Checked at send time, race-condition safe |
| R-09 | USD cents storage, display-only conversion | No second currency column, anywhere, ever |
| R-10 | Unapproved timesheet blocks invoice | Server-side block, not a UI warning |

---

## How to use this package day to day

1. Open the phase file for what you're currently building. Don't skip ahead — a phase file assumes the prior phase's guarantees already hold.
2. For any story referenced by S-number, the full 12-section requirements doc is the source of truth for that story's Business Rules and Acceptance Criteria — this package gives you architecture and sequencing, the story doc gives you the specific behavior to build and test against.
3. Write the negative-case test before the code, per the Development & Review Standard's Part 3 template.
4. If a phase file references a story that's one of the 94 gaps, that gap's minimum viable spec is given inline in the phase file — treat it as authoritative for that story, since a full 12-section doc doesn't exist yet.
