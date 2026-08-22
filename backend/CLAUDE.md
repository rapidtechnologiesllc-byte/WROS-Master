# CLAUDE.md — WROS Project Context

## 🟢 CURRENT STATUS (2026-08-21 Session - CAREER SITE END-TO-END WORKING)

**Career Portal:** ✅ COMPLETE - Relationship-building conversation flow implemented, database-backed, Thunder AI integration ready
**Backend:** ✅ PRODUCTION READY - JWT token fixes integrated (2026-08-19 session)
**Frontend:** ✅ PRODUCTION READY - Portfolio: WROS + Career Site  
**Database:** ✅ POSTGRESQL 18 - Career tables created with full indexes

### Session Work (2026-08-21 - Career Portal Completion):

**Career Site - End-to-End Flow COMPLETE**
- ✅ Relationship-building conversation stage (5 Q&A)
- ✅ All conversation responses persisted to `career_conversations` table
- ✅ Job listings synced from `career_jobs` database table
- ✅ Resume upload stage with Thunder AI analysis readiness
- ✅ Clarifications Q&A stage framework
- ✅ Application submission with full data persistence
- ✅ Welcome-back feature for returning candidates
- ✅ Database schema: 5 career tables with proper indexes

**JWT Token Claims Fix (2026-08-19 Integration):**
- ✅ Integrated remote JWT standardization ("sub": UserID, "type": "user")
- ✅ All authentication endpoints using correct token format
- ✅ Auth middleware updated with career site public routes

This file is read automatically at the start of every Claude Code session in this repo. If you are reading this, you are working on WROS (Workforce Revenue Operating System) for BlitzenX, a Guidewire specialist staffing firm.

## Read this, in this order, before writing any code

1. `/docs/build-package/00-MASTER-INDEX.md` — the build order and what already exists
2. `/docs/build-package/01-SECURITY-FOUNDATION.md` through `04-RESOURCE-MANAGEMENT.md` — the four sequenced phases
3. `/docs/build-package/WROS_Development_Review_Standard.md` — the hard-rule compliance checklist and build-brief template every story build must follow
4. The specific story's requirements file in `Requirements/` for whatever you're currently building — its Business Rules and Acceptance Criteria sections are the authoritative behavior spec, this file and the phase docs give you architecture and sequencing only. **Format, changed 2026-08-02**: S-001 through S-048 are `.docx` (original format, already built or already researched — no need to reconvert); **S-049 onward, every requirements file is Markdown (`.md`)**, converted at Avinash's request because `.docx` needed a python-docx extraction step before every read and Markdown doesn't. Same filename convention either way (`S-0NN_HRMS-0NNN.md`), same folder, same content — just read the file directly now instead of extracting it first.

## Definition of Done — corrected 2026-07-22, read this before marking anything Done

**A story is not Done until its UI, its API/integration layer, its business rules, AND its test cases are all complete.** Backend-only (models + services + migrations + tests, no REST endpoint, no screen) is **In Progress**, never Done — this was gotten wrong for four Phase 4 stories (S-353, S-373, S-320, S-372) this session: real, tested backend logic marked Done in the canonical sheet while none of them had an endpoint or a UI a person could actually use. Corrected, and this is now the standing bar. Why it matters beyond correctness: an inaccurate Done marking is actively worse than an honest "still open" — it's the exact same silent-tracking-drift problem already found once in this project's own history (`CLAUDE.md`'s own "Still open in Phase 3" bullet went stale for ~9 commits earlier this session). Don't repeat that mistake in the canonical sheet, which now exists specifically to prevent it.

When scoping a story, plan all four layers up front — backend, API, UI, tests — not backend-first-and-hope-to-circle-back. If only backend is built in a given round because of a genuine sequencing reason, say so explicitly and mark the row `In Progress`, not `Done`.

## The one-sentence version of every rule that matters

Ten hard business rules (R-01 through R-10) plus one financial rule (R-11) are absolute and enforced in code, not policy — see the Development & Review Standard for the full checklist and the specific "how it silently fails" pattern to test against for each. If you are ever unsure whether something you're building touches one of these, assume it does and check.

## Non-negotiables, regardless of which story you're building

- **`createCandidateSafe()` is the only path to create a candidate.** No direct inserts, anywhere, ever.
- **`sendThunderMessage()` is the only path to send a candidate message.** No raw WhatsApp/email/LinkedIn API calls from any story.
- **`sendNotification()` (HRMS-0113) is the only path to send any internal notification.** It handles business-hours gating, tenant scoping, and channel fallback — do not reimplement any of that in an individual story.
- **Core-Pull decision logic lives in exactly one place: HRMS-0514 (S-353, "Core-Pull Conflict Rule Engine — Core Wins Policy").** Every story that touches Core-vs-Speciality staffing calls it or checks its output. None reimplement it. (Corrected 2026-07-22: this file and `04-RESOURCE-MANAGEMENT.md` both previously cited "HRMS-0312" — that ID actually belongs to an unrelated story, Workforce Scenario Planning, per `WROS_Canonical_Backlog_S001-401.xlsx`. Flagging the drift rather than trusting either doc's ID cross-references at face value going forward.)
- **Every table has `tenant_id`, NOT NULL, indexed. No exceptions.** Middleware resolves it from session, never from client input.
- **Every monetary value is `BIGINT`, USD cents, named `*_usd_cents`.** No second-currency column, anywhere, in any story, for any reason.
- **LLM output is advisory for anything irreversible.** An agent proposing an action and a human confirming it are two different code paths — do not collapse them because it seems more efficient.

## What already exists — check before building anything that sounds new

- **256 of 386 original canonical backlog stories** have complete, audited requirements docs, in `Requirements/` (`.docx` for S-001–048, `.md` from S-049 onward — see the format note above).
- **15 EPIC-16 Finance & Accounting stories** (S-387 onward) — timesheet nag cascade, invoice cycle, AR follow-up, bank reconciliation, cost/rate engines. Some still pending (P&L Engine, Reserve Fund, Hiring Affordability, Partner Incentive Calculator, Executive Dashboard, GST placeholder) — check `/docs/build-package/00-MASTER-INDEX.md` for current status before assuming a story exists.
- **One existing partial codebase**, `OnboardingModule-Backend` / `OnboardingModule-Frontend`, already implements rough versions of Add Candidate, Schedule Interview, Start Pre-Onboarding, Collect Document. It has real gaps against R-01, R-05, R-07, and the virus-scan requirement — extend this code per the Development & Review Standard's build-brief template, do not discard and rewrite it from scratch.
- **94 stories have no written requirements yet.** If you're asked to build something in Client Portal legacy screens, Resource & Bench Management basics, Boolean Search, Interview Decision Engine, LinkedIn Sourcing, Talent Engine ATS, Analytics, or Nurture Engine, that's fine — per the 2026-08-11 update under "When something is ambiguous" below, a missing requirements doc no longer blocks the build. Use the live app, direct instruction, and judgment instead, and say what you assumed.

## Progress tracking — the canonical backlog sheet

`WROS_Canonical_Backlog_S001-401.xlsx` (this folder) is Avinash's canonical 401-story backlog — Story ID, WROS ID (the authoritative HRMS-ID, not always what an older `.docx` filename or a past commit message says), Epic, Phase, and Status. It's the source of truth for "what's the real HRMS-ID for this story" when the requirements corpus and old build history disagree (which happens — see the Core-Pull correction above).

**Known, real drift**: requirements filenames/content in `Requirements/` (`.docx` for S-001–048, `.md` for S-049 onward — see the format note above) and this spreadsheet's WROS ID column don't always agree — some stories were renumbered (often with a `-REV` suffix on the reused ID) after the original 357-doc corpus was written. When they conflict, trust the spreadsheet's WROS ID column, not the requirements filename, and don't force-match by ID string alone — verify by content (Summary/Description) since a numeric coincidence can be a false match.

**Standing convention, starting 2026-07-22**: update the row's `Status` column using the correct canonical Story ID/WROS ID (verify by content if the ID looks off, per the drift note above), and log the change in the sheet's `Change Log` tab (date + one line) — but only mark `Done` when the **Definition of Done above is actually met** (UI + API/integration + business rules + tests, all four). Backend-only work is `In Progress`. Avinash's explicit call: don't do a full historical reconciliation of all 401 rows up front — update only what you complete going forward, and run one regression pass over the remaining `Planned`/`Ready for Build`/`In Progress` rows at the end of the build to catch anything missed along the way, rather than reconciling continuously.

## Build order

Phase 1 (Security) → Phase 2 (Data Model) → Phase 3 (Thunder + Agentic Layer, Part A single-threaded then Part B's four parallel workstreams) → Phase 4 (Resource Management, in parallel with Phase 3's other workstreams). EPIC-16 (Finance) can build in parallel with Phase 3/4 once Phase 1 and Phase 2 are complete, since it depends on Payroll Sync (Phase 2/Integration Hub) and the Notification Engine (Phase 1) but not on Thunder or Resource Management directly.

Do not skip ahead. A phase assumes the prior phase's acceptance gate has actually passed, not just that the code exists.

## When something is ambiguous

**Superseded 2026-08-11, Avinash's explicit call: requirements docs no longer gate development.** The old rule (check `Requirements/`, then the phase doc's `[GAP-SPEC]` stub, then stop and ask) is retired — the requirements corpus isn't being kept current against how the project is actually running now, and stopping work to hunt for a doc that may not reflect reality anymore does more harm than a reasonable, stated assumption does. Do not block a build on a requirements doc existing.

**What to use instead, in order:** the live app itself (what's actually on screen, what the code actually does today) > a direct instruction from Avinash in the current conversation > a requirements doc, if one happens to exist and still looks current > your own best judgment. When you make a judgment call, say what you assumed and why, in a sentence, rather than going silent about it.

**The one thing that still stops you**: a design that touches a hard rule (R-01 through R-11), tenant isolation, or Core-Pull. Those stay high-blast-radius enough that a wrong guess is worse than a pause — for those specifically, still confirm the approach with Avinash directly before building, even under this looser rule. Everything else: build it.
