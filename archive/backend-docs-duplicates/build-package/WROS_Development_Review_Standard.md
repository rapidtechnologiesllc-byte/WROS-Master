# WROS Development & Review Standard
**For use with Claude Code builds, human review, and pre-prod sign-off — applies to every story, every epic, not just Onboarding.**

---

## Why this exists

The Onboarding Module review found the same failure pattern four times: a hard rule from the spec (R-01, R-05, HRMS-0118's scan gate) either never made it into code, or made it in as a *schema field that implies the rule* without the actual enforcement logic behind it — `is_virus_scanned` defaulting to `False` and never being set is the clearest example. A generic "review the PR, does this look reasonable" pass doesn't reliably catch this, because the gap isn't a bug in visible logic — it's an absence. You can't see something that isn't there unless you're checking for it by name.

This document is that checklist, generalized to every hard rule and every cross-cutting pattern in WROS, so it travels with every future build instead of being reconstructed per epic.

---

## Part 1 — The Hard Rule Compliance Checklist (R-01 to R-10)

For each rule: what it requires, and — based directly on how it failed to survive in the Onboarding code — the specific way to verify it's *actually* enforced, not just present as a field or a UI constraint.

| Rule | Requirement | How it silently fails | How to actually verify |
|---|---|---|---|
| **R-01** | 5-year experience gate, no exceptions without logged BU Head override | Experience is *scored* (contributes to a ranking) but never *gates* (blocks creation/submission) | Search for the check at the point of creation/submission, not just in a scoring function. Test: submit a candidate with 2 years experience — must be rejected, not just scored lower |
| **R-02** | No market profile without recruiter + CS sign-off | Both roles can independently approve, or one role's approval silently satisfies the requirement | Test with only one sign-off present — action must still be blocked |
| **R-03** | W2/full-time only, no override authority | Enforced only in the UI dropdown, bypassable via direct API call | Test via direct API call with a non-compliant value, bypassing the UI entirely |
| **R-04** | Bench-first — external sourcing blocked until confirmed insufficient | Bench check runs but result is logged, not actually gating the next step | Force bench-sufficient result, confirm external sourcing genuinely does not fire |
| **R-05** | L1 must pass before L2 can be scheduled | No sequencing check on panel/round creation — this is exactly what the Onboarding review found | Test: create an L2 (or any round 2+) panel with zero prior rounds logged — must be rejected |
| **R-06** | Human dependency below 20% by Month 6 | N/A at individual-story level — tracked at platform level via HRMS-P612 | Confirm story doesn't silently increase manual steps in a workflow HRMS-P612 is tracking |
| **R-07** | createCandidateSafe() is the only creation path, dedup runs first | A duplicate check exists but only matches one field (e.g., email), missing phone/LinkedIn — this is exactly what the Onboarding review found | Test with a duplicate on each identifying field independently — email match, phone match, LinkedIn match — all three must catch it |
| **R-08** | Thunder locked when recruiter owns conversation | Lock checked at send time but not re-checked if a race condition lets two sends queue near-simultaneously | Test two near-simultaneous send attempts, confirm only one honors the lock correctly |
| **R-09** | USD cents storage, display-only conversion | A second currency field gets written somewhere convenient "just for this one report" | Grep the codebase for any monetary column that isn't BIGINT USD cents — there should be zero |
| **R-10** | Unapproved timesheet blocks invoice generation | Check exists but is a warning, not a hard block, or is only enforced in the UI | Attempt invoice generation via direct API call with an unapproved timesheet in the period — must fail server-side |

**The single pattern underneath all ten:** if a rule can be described as "the system checks X," always ask *checks X and then what?* A check that's logged but doesn't block, or that's UI-only and not re-validated server-side, is not the same thing as the rule being enforced. This is the exact shape of all four Onboarding gaps.

---

## Part 2 — Cross-Cutting Checks (apply regardless of which story you're building)

These come from the platform architecture itself (Core Platform & Multi-Tenant Foundation batch), not from R-01–R-10, but fail the same way if unchecked:

- **Tenant/BU scoping is server-side, not trusted from client state.** Test: send a request with a forged or absent tenant/BU identifier — the server must resolve it from the session, never accept it from the caller (per HRMS-0109's BR-0109-01).
- **Every hard-rule override writes an audit_log row in the same transaction as the override itself** — not a separate, best-effort logging call that can silently fail while the override succeeds (per HRMS-0110's BR-0110-02).
- **Fail-open vs. fail-closed is a deliberate choice per action, and the choice is documented, not accidental.** Compliance/security gates (dedup, R-01, virus scan) fail closed — block the action if the check can't be confirmed. Non-critical agent conflict-detection (HRMS-1101) fails open with an alert — an agent shouldn't halt entirely because one router is down. If a story doesn't say which one it is, that's a gap in the build, not a detail to guess at.
- **LLM outputs are advisory for anything irreversible; only explicitly-designated actions (e.g., Core-Pull) are fully autonomous.** If a story's agentic AI section says an LLM call informs a decision, confirm the code path actually stops for human confirmation rather than auto-executing on the LLM's output.
- **File uploads are not accessible until they pass whatever security gate the story specifies** — scan, verification, etc. The Onboarding review's sharpest finding: a schema field that *implies* this (`is_virus_scanned`) is not the same as the gate existing. Grep for where the field is actually *set*, not just where it's *declared*.

---

## Part 3 — Claude Code Build Brief Template

Use this per story (or per small group of tightly related stories) instead of pointing Claude Code at a whole epic at once. Small, verifiable units — same reasoning as building the requirements docs in batches rather than all 378 at once.

```
STORY: [S-number, WROS ID, title]

CURRENT STATE (if extending existing code):
- File(s): [exact paths]
- What exists today: [functions, endpoints, schema]
- What's missing: [specific gap, cite the rule it violates]

REQUIRED BEHAVIOR:
- [Exact business rule text from the story's Business Rules section]
- [Which existing pattern in the codebase to extend/reuse rather than reimplement —
   e.g., "use the same require_permission() dependency pattern already used in interviews.py"]

ACCEPTANCE TEST (write this FIRST, it's the definition of done):
- [ ] Positive case: [expected behavior when compliant]
- [ ] Negative case: [attempt the violation directly via API, bypassing any UI constraint —
       must be rejected server-side]
- [ ] Edge case: [race condition / concurrent access / service failure behavior,
       per the story's fail-open/fail-closed specification]

OUT OF SCOPE (from the story's "Not In Scope" section):
- [explicit list, so Claude Code doesn't over-build]
```

---

## Part 4 — Review Workflow

1. **Build brief written before code starts** (Part 3 template), scoped to one story or a tightly coupled small group.
2. **Claude Code implements against the brief**, including the negative-case tests — tests are part of the deliverable, not an afterthought.
3. **Review checks against Part 1 + Part 2, by name, not by impression.** The reviewer isn't asking "does this look right" — they're going down the specific checklist item(s) relevant to this story and confirming each one has a passing negative-case test, not just a positive-case demo.
4. **A story doesn't move to prod-ready until its specific hard-rule tests are green**, not just its happy-path demo. The Onboarding module's four features all demoed successfully — that's precisely why the gaps weren't caught first time.
5. **Regression protection**: hard-rule tests stay in the suite permanently. A future refactor that reopens a gap (e.g., someone "simplifies" the dedup check back down to email-only) should fail CI, not wait for the next manual review to notice.

---

## Applying this now

The Onboarding review found 4 concrete gaps (R-01 gate, R-05 gate, R-07 dedup breadth, HRMS-0118 scan gate) — those become the first 4 build briefs under this standard, each with its own negative-case test, each independently reviewable and shippable rather than one large "fix onboarding" PR.

Going forward, every batch we've already built (Core Platform, Sub-Vendor Portal, Client Portal, Revenue Visibility Engine, HTD/Time Tracking/Project & Delivery) already has its Business Rules and Acceptance Criteria sections written in a form that maps directly onto Part 3's template — the brief-writing step is largely just extracting what's already in each `.docx`, not drafting from scratch.
