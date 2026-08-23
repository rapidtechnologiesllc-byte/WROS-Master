# Requirements folder catalog — 357 docs mapped to epics and phases

Source: `C:\Users\AvinashMukund\Documents\Claude\Requirements\` (357 `.docx`
files — some S-numbers appear twice, pointing at two different HRMS-IDs;
that's a historical renumbering artifact, not a duplicate story. Per
CLAUDE.md, S-numbers carry no build-priority meaning; the HRMS-ID is
the stable identifier).

Built by extracting the title + epic line from every file (not
sampling/guessing) and cross-referencing against `00-MASTER-INDEX.md`
through `07-FINANCE-ACCOUNTING.md`. **No code was built from any of
these tonight** — Phase 2 (the full data model) hasn't started yet, and
per this project's own build order, none of these should be built
before Phase 2's acceptance gate passes.

## Epic → phase mapping

| HRMS-ID range | Count | Epic | Which WROS phase |
|---|---|---|---|
| 04xx | 80 | EPIC-04 — Candidate Engagement & AI Recruiter Platform ("Thunder") | **Phase 3, Part A** — shared core, build first, single-threaded |
| 11xx | 11 | EPIC-11 — Recruit/Interview/Onboarding/Resource-Mgmt agentic workstreams | **Phase 3, Part B** — the 4 parallel workstreams, unlocked after Part A |
| P4xx | 9 | EPIC-P4 — LinkedIn Sourcing | **Phase 3, Workstream 1 (Recruit)** |
| P9xx | 14 | EPIC-P9 — Boolean Search & Advanced Matching | **Phase 3, Workstream 1 (Recruit)** — cross-check against EPIC-11's existing Boolean logic before building, per Phase 2 doc's explicit warning |
| P6xx | 12 | EPIC-P6 — Interview Rules Engine | **Phase 3, Workstream 2 (Interview)** — this is where R-05's sequencing gate lives |
| 05xx | 34 | EPIC-05 — Resource Management (includes NEW-RM S-351–378) | **Phase 4** — richest-detailed domain in the whole backlog per Phase 2 doc |
| P5xx | 9 | HTD Track & Non-Traditional Hiring | **Phase 3/4 boundary** — feeds both Onboarding (Workstream 3) and Resource Mgmt (Phase 4) |
| P1xx | 20 | EPIC-P1 — Candidate Portal & Universal Identity Engine | Not yet phase-mapped in 00–07 — likely part of the 94-gap-story set or a later phase doc not yet written |
| P2xx | 10 | EPIC-P2 — Employee Portal (Admin & Technical Split) | Not yet phase-mapped |
| P3xx | 9 | EPIC-P3 — Candidate Nurture & Relationship Management | Matches Phase 2's `[GAP-SPEC]` "Proactive Nurture Engine" — **but this range already has full docs**, meaning that gap may already be closed and the Phase 2 doc's gap list is stale |
| P7xx | 26 | EPIC-P7 — Client Portal | Not yet phase-mapped |
| P8xx | 15 | EPIC-P8 — Sub-Vendor Portal | **Phase 2, Domain 5** (full detail already in `02-DATA-MODEL.md`) |
| 01xx (+ part of 07xx) | 5 (+ some of 16) | EPIC-01 — Core Platform | **Phase 1/2 foundation** — HRMS-0109/0110/0113/0114/0117 etc. live here; some 07xx stories (e.g. Interview Panel Assignment) are also tagged EPIC-01, so this epic isn't a clean contiguous ID block |
| 02xx | 10 | EPIC-02 — Revenue Visibility (client-side foundation: entity mgmt, contacts) | **Phase 2, Domain 4** |
| 03xx | 21 | Workforce Planning (revenue targets feeding hiring decisions) | Likely feeds **Phase 2, Domain 4** — not explicitly named as its own epic in 00–07 |
| 06xx | 19 | EPIC-02 — Revenue Visibility (continued — recognition model, etc.) | **Phase 2, Domain 4** — same epic as 02xx, non-contiguous numbering |
| 07xx | 16 | Mixed — some Core Platform (EPIC-01), rest likely Client-facing ops | Needs per-file check, not cleanly one epic |
| 08xx | 6 | EPIC-08 — Project & Delivery | **Phase 2, Domain 4** (`S-299, 301–305` named explicitly) |
| 09xx | 9 | EPIC-09 — Time Tracking | **Phase 2, Domain 4** (`S-225, 226, 228, 229` named explicitly) |
| 10xx | 3 | AI Intelligence Layer (Unified Prediction Engine, Model Drift Monitor) | Not yet phase-mapped — likely feeds Phase 3's agentic layer generally, not one workstream |
| 12xx | 13 | Analytics Data Warehouse / Executive Dashboards | Phase 2 doc listed "Analytics" as a 7-story `[GAP-SPEC]` — **13 fully-detailed docs already exist**, meaning this gap is likely already closed and the Phase 2 doc is stale here |
| 13xx | 6 | Integration Hub (job board posting, payroll sync, etc.) | **Phase 2, Domain 4** (`S-338, 342–344` named explicitly) |

**EPIC-16 Finance & Accounting** (15 stories, S-387–401 / HRMS-1601–1615)
is not in the Requirements folder — it's the separately-delivered
package already described in full in `07-FINANCE-ACCOUNTING.md`.

## What this means practically

- **Phase 3 Part A (Thunder core) is the single biggest, most fully-detailed
  block** — 80 stories, all with complete docs, ready to build the moment
  Phase 1 + Phase 2 pass.
- **Two of the Phase 2 doc's `[GAP-SPEC]` items (Nurture Engine, Analytics)
  may already be closed** — P3xx and 12xx both have full requirement docs
  now, where the phase doc describes them as "no doc yet." Worth
  confirming before treating them as gaps requiring a `[GAP-SPEC]` stub.
- **Several large ranges (P1xx, P2xx, P7xx, 03xx, 10xx — ~90 stories
  combined) aren't named in any phase doc (00–07) at all.** They're not
  missing — they have full docs — they're just not yet sequenced into
  the phase plan. Whoever plans Phase 3/4's detailed schedule should
  fold these in explicitly rather than build them ad hoc when they come up.
- Story numbering (S-xxx) has real historical renumbering churn (several
  S-numbers point at two different HRMS-IDs) — always build against the
  HRMS-ID and the doc's own content, never assume the S-number implies
  anything about order or which of two same-numbered files is current.
