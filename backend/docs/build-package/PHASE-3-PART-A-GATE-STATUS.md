# Phase 3 Part A acceptance gate — status, 2026-07-22

Checklist copied verbatim from `03-THUNDER-AGENTIC-LAYER.md`. Three of
four items are genuinely done and tested; the fourth is not
satisfiable yet, honestly, not glossed over.

- [x] **`sendThunderMessage()` correctly rejects a send when R-08's
  ownership condition is active, verified by test.** Built as
  `app.services.thunder_service.send_thunder_message()`, wrapping the
  pre-existing, already-tested R-08 gate in
  `whatsapp_routing_service.send_whatsapp_message()` (not
  reimplemented) and adding the two guarantees the doc calls for that
  gate didn't cover: consent (via the real `consent_records` table —
  `candidates.consent_given` doesn't exist in this codebase, same
  doc-vs-reality gap pattern flagged elsewhere) and duplicate-send
  debounce. 13 dedicated tests
  (`tests/test_thunder_conversation_core.py`), plus the pre-existing
  30 whatsapp-routing/conversation-inactivity tests, all passing after
  retrofitting the one call site that previously bypassed it
  (`conversation_inactivity_service.py`'s reclaim/nudge).

- [ ] **`buildCandidateContext()` confirmed as a mandatory pre-call in
  Thunder's response generation path — no code path generates a
  response without it.** **Not satisfiable yet, not a gap in this
  function.** `build_candidate_context()` is built and tested
  (unifies email + WhatsApp history for the first time, since both
  already write to `conversation_events` but nothing previously read
  them back as one ordered timeline) — but there is no Thunder
  response-generation path in this codebase to enforce it on.
  `ai_conversation_service.py` is one-shot missing-field email parsing,
  not conversational reply generation. This checkbox can only turn
  green once Workstream 1's outreach/response agents (HRMS-1104 and
  friends) exist and are built to call `build_candidate_context()`
  first — tracked as a build requirement on those agents, not
  re-opened as separate work here.

- [x] **HRMS-1101's six seeded conflict rules are live and each
  independently testable.** Correction, not a gap:
  `03-THUNDER-AGENTIC-LAYER.md`'s own summary says "six seeded conflict
  rules"; the actual story doc (`S-270_HRMS-1101.docx`) specifies
  exactly two concrete rule rows in its Business Rules section
  (BR-1101-01 outreach-vs-Core-Pull, BR-1101-02 Thunder ownership
  lock) — BR-1101-03 through -06 are platform behaviors (novel
  patterns escalate-only, HIGH pages within 5 min, Admin-only rule
  edits, fail-open), not additional rows. Both real rows are seeded
  (`seed_default_conflict_rules()`) and independently tested, and all
  four behavioral BRs are implemented and tested too. Flagged here
  rather than inventing four more rule rows to match a rounded-off
  phase-doc summary.

- [x] **A test conflict between two of the four workstreams (simulated)
  is correctly caught by the Router before either agent's action
  executes.** `test_outreach_blocked_by_prior_corepull_flag_same_entity`
  simulates exactly this: Workstream 1's HRMS-1104 (outreach) colliding
  with Workstream 4's HRMS-1105 (Core-pull) on the same candidate —
  `ActionBlocked` is raised before any send would occur.

## What's real vs. what's deferred, precisely

Built and tested this round:
- `app/services/thunder_service.py` — `send_thunder_message()`,
  `build_candidate_context()`, `has_active_consent()`. 13 tests.
- `app/models/orchestration.py` — `conflict_rules`, `orchestration_events`.
- `app/services/orchestration_router_service.py` — rule CRUD
  (Admin-gated), `evaluate_action_intent()` (BLOCK/DELAY/ESCALATE_ONLY,
  novel-pattern LLM-classifier hook with MEDIUM-on-failure default,
  fail-open on internal error). 27 tests.
- Retrofit: `conversation_inactivity_service.py` now calls
  `send_thunder_message()` instead of `send_whatsapp_message()`
  directly — no remaining bypass of the one sanctioned send path.

Deferred, and why it's not silently dropped:
- **HRMS-1102 through HRMS-1108 (the nine agents) do not exist.** Part
  A is infrastructure for agents that are Part B's job — this is
  correct sequencing per the doc, not a shortfall.
- **No event bus.** `evaluate_action_intent()` is a direct function
  call, the synchronous equivalent of publishing to
  `agent.action.intent` and waiting for a response. A future agent
  calls it before acting, same "idempotent function exists, wiring is
  follow-up" posture as every cron-shaped story already in this
  codebase.
- **No on-call Director roster.** Escalation delivery
  (`send_notification`, P0/WhatsApp) is real and tested when a
  `director` is supplied by the caller; resolving *who* that is isn't
  built. Same posture HRMS-0113 itself had before this session wired
  real call sites into it.
- **Concurrency**: two agents proposing near-simultaneous intents on
  the same `entity_id` could both read the collision window before
  either commits its own event, and miss each other. Documented in
  `orchestration_router_service.py`'s module docstring rather than
  silently assumed away — closing it needs a DB-level lock strategy
  tied to a production-database decision, same class of gap as Phase
  1's multi-worker rate-limiter note.

377/377 tests passing (1 xfailed) after this round.
