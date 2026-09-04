# Phase 1 acceptance gate — final status, 2026-07-20

Checklist copied verbatim from `01-SECURITY-FOUNDATION.md`. Honest
status against each — this phase is NOT 100% closed; four items are
structurally blocked without things only a human (with VPS/production
access, or product/design authority) can provide.

- [x] **HRMS-0114** — the application fails to start if any route lacks
  a permission declaration. Wired into `app.main`, 0 unexplained gaps,
  tested end-to-end (`tests/test_app_startup_enforcement.py`).

- [x] **HRMS-0117** — no raw console logging anywhere, CI-enforced.
  AST-based test (not text-grep) fails the build on any future
  `print()` call. Secret redaction wired into every log handler.

- [x] **B3 (half)** — a forged/expired session token is rejected.
  Tested directly against the real `create_access_token`/
  `decode_access_token` functions.

- [x] **B4** — a rate-limit-exceeding burst is throttled before reaching
  business logic. Enabled and tested. Known limitation documented in
  code: in-memory state means production's multi-worker gunicorn config
  gives each worker an independent counter — correct fix needs Redis,
  not implemented (not otherwise in this stack).

- [x] **B5** — an embedded prompt-injection attempt has zero effect.
  Pattern built, tested, AND retrofitted into both real Gemini call
  sites in `ai_conversation_service.py` — found and fixed the actual
  vulnerable f-string-concatenation pattern the doc warned about.

- [x] **B6** — `consent_records` exists and is queryable. Done, tested.

- [ ] **HRMS-0109 (partial)** — cross-tenant read/write fails "on every
  tested endpoint." True for 6 real, high-risk list/search routes
  (proven end-to-end). NOT true yet for ~180 remaining single-record
  lookup call sites (lower-urgency IDOR-shaped risk, documented in
  `HRMS-0109-tenant-scoping-gap.md`) or for one more complex BU-pool
  query needing domain review. Recommended scalable fix
  (`with_loader_criteria` global scoping) documented, not implemented
  — needs careful integration testing against real concurrent requests.

- [ ] **HRMS-0110 (partial)** — `audit_log` is append-only, "tested
  against the Admin role specifically." True at the ORM level (tested).
  NOT true yet at the database-grant level (the actual requirement —
  a raw SQL client should be blocked too) — the `DENY UPDATE, DELETE`
  SQL is written into the migration but has never been run against any
  real database, and needs the real SQL Server login name confirmed
  first (currently assumes `hrms_app`, a placeholder). **Blocked: needs
  someone with access to the actual database.**

- [ ] **B1 (partial)** — "no secret value appears in code, committed
  config, or logs." True GOING FORWARD (`.env` untracked, `.gitignore`
  fixed, log redaction wired in, full-history grep performed and every
  found secret already rotated or flagged for rotation). NOT true
  retroactively — the secrets still exist in this repo's git history
  and always will unless someone deliberately rewrites history (BFG/
  `git filter-repo`). That's a destructive, force-push-requiring
  operation on a shared repo — **deliberately not done without explicit
  sign-off**, since it rewrites every commit hash after the earliest
  affected commit and would break any existing clones/forks.

- [ ] **B3 (other half) — MFA for Admin/Director.** Fully built and
  tested (enrollment, TOTP verification, backup codes, the pending-
  token isolation that makes the gate not-decorative). Enforcement is
  behind `MFA_ENFORCEMENT_ENABLED`, **off by default, on purpose** —
  turning it on requires a frontend screen to show a QR code and accept
  a code, which doesn't exist yet. Also: the role mapping
  (`Super User`, `BU Head` standing in for the doc's "Admin and
  Director") is this session's best-guess analog, not a confirmed
  decision — **needs sign-off from whoever owns the role taxonomy**.

- [ ] **B2 — encryption at rest and in transit.** Not attempted.
  Structurally needs VPS/cloud access neither this session nor the
  intern has — verifying/configuring TLS certs and database-level
  encryption happens on infrastructure this session cannot reach.

## What "done" actually requires from here

Four things, none of them more code from a session like this one:
1. Someone with real database access: run the 5 migrations (in order),
   confirm the SQL Server login name for the `audit_log` DENY grants,
   apply them.
2. Someone with VPS/cloud access: verify TLS 1.2+ and at-rest
   encryption (B2).
3. A product/design decision + a small frontend build: the MFA QR/code
   entry screen, then flip `MFA_ENFORCEMENT_ENABLED` on and confirm the
   Super-User/BU-Head role mapping is actually right.
4. A decision on git history: rotate-and-move-on (current state, safe)
   vs. a deliberate, sign-off'd history rewrite to scrub the old
   secrets retroactively (destructive, disruptive to any existing
   clones).

Everything else on the original checklist is done and tested.
