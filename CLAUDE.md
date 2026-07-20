# CLAUDE.md — WROS Project Context

This file is read automatically at the start of every Claude Code session in this repo. If you are reading this, you are working on WROS (Workforce Revenue Operating System) for BlitzenX, a Guidewire specialist staffing firm.

## Read this, in this order, before writing any code

1. `/docs/build-package/00-MASTER-INDEX.md` — the build order and what already exists
2. `/docs/build-package/01-SECURITY-FOUNDATION.md` through `04-RESOURCE-MANAGEMENT.md` — the four sequenced phases
3. `/docs/build-package/WROS_Development_Review_Standard.md` — the hard-rule compliance checklist and build-brief template every story build must follow
4. The specific story's `.docx` in `/docs/requirements/` for whatever you're currently building — its Business Rules and Acceptance Criteria sections are the authoritative behavior spec, this file and the phase docs give you architecture and sequencing only

## The one-sentence version of every rule that matters

Ten hard business rules (R-01 through R-10) plus one financial rule (R-11) are absolute and enforced in code, not policy — see the Development & Review Standard for the full checklist and the specific "how it silently fails" pattern to test against for each. If you are ever unsure whether something you're building touches one of these, assume it does and check.

## Non-negotiables, regardless of which story you're building

- **`createCandidateSafe()` is the only path to create a candidate.** No direct inserts, anywhere, ever.
- **`sendThunderMessage()` is the only path to send a candidate message.** No raw WhatsApp/email/LinkedIn API calls from any story.
- **`sendNotification()` (HRMS-0113) is the only path to send any internal notification.** It handles business-hours gating, tenant scoping, and channel fallback — do not reimplement any of that in an individual story.
- **Core-Pull decision logic lives in exactly one place: HRMS-0312.** Every story that touches Core-vs-Speciality staffing calls it or checks its output. None reimplement it.
- **Every table has `tenant_id`, NOT NULL, indexed. No exceptions.** Middleware resolves it from session, never from client input.
- **Every monetary value is `BIGINT`, USD cents, named `*_usd_cents`.** No second-currency column, anywhere, in any story, for any reason.
- **LLM output is advisory for anything irreversible.** An agent proposing an action and a human confirming it are two different code paths — do not collapse them because it seems more efficient.

## What already exists — check before building anything that sounds new

- **256 of 386 original canonical backlog stories** have complete, audited requirements docs. Organized by epic in `/docs/requirements/`.
- **15 EPIC-16 Finance & Accounting stories** (S-387 onward) — timesheet nag cascade, invoice cycle, AR follow-up, bank reconciliation, cost/rate engines. Some still pending (P&L Engine, Reserve Fund, Hiring Affordability, Partner Incentive Calculator, Executive Dashboard, GST placeholder) — check `/docs/build-package/00-MASTER-INDEX.md` for current status before assuming a story exists.
- **One existing partial codebase**, `OnboardingModule-Backend` / `OnboardingModule-Frontend`, already implements rough versions of Add Candidate, Schedule Interview, Start Pre-Onboarding, Collect Document. It has real gaps against R-01, R-05, R-07, and the virus-scan requirement — extend this code per the Development & Review Standard's build-brief template, do not discard and rewrite it from scratch.
- **94 stories have no written requirements yet.** If you're asked to build something in Client Portal legacy screens, Resource & Bench Management basics, Boolean Search, Interview Decision Engine, LinkedIn Sourcing, Talent Engine ATS, Analytics, or Nurture Engine — check whether a full requirements doc exists first. If not, flag it rather than inventing scope, unless a `[GAP-SPEC]` minimum-viable stub is given in the relevant phase document.

## Build order

Phase 1 (Security) → Phase 2 (Data Model) → Phase 3 (Thunder + Agentic Layer, Part A single-threaded then Part B's four parallel workstreams) → Phase 4 (Resource Management, in parallel with Phase 3's other workstreams). EPIC-16 (Finance) can build in parallel with Phase 3/4 once Phase 1 and Phase 2 are complete, since it depends on Payroll Sync (Phase 2/Integration Hub) and the Notification Engine (Phase 1) but not on Thunder or Resource Management directly.

Do not skip ahead. A phase assumes the prior phase's acceptance gate has actually passed, not just that the code exists.

## When something is ambiguous

Check the specific story's requirements doc first. If the story doesn't exist yet, check the phase document for a `[GAP-SPEC]` stub. If neither exists, stop and ask — do not invent a plausible-sounding design for a hard-rule-adjacent story (anything touching R-01 through R-11, tenant isolation, or Core-Pull) without confirmation. For lower-stakes ambiguity (a UI label, a non-critical config default), make a reasonable choice and note the assumption in your PR description.
