# HRMS-0109 — tenant scoping: what's done, what's left

## Done tonight, proven on real live routes (not just the helper in isolation)

- `app.core.tenant_context.get_tenant_scoped_query()` — the one sanctioned
  way to scope a query to the caller's tenant, fails closed on no
  tenant assigned.
- Migration `d6e7f8a9b0c1` backfills every existing NULL-tenant_id row
  (users, candidates, jobs) to a single seeded "BlitzenX" tenant —
  **must run before any of the routes below reach production**, or
  every existing account gets 403'd by the fail-closed check.
- 6 real, live routes wired to it, each a genuine list/search endpoint
  (the highest-risk shape — returns many rows, not one by ID):
  - `GET /onboarding/hr/get_all_candidates`
  - `GET /hr/users/all`, `GET /hr/users/search`
  - `GET /jobs/all`, `GET /jobs/filter`
  - `GET /candidate-status/all`
  - `GET /candidate-pool/`
- `tests/test_tenant_scoping_real_routes.py` proves it end-to-end: two
  tenants, two recruiters, one recruiter's candidate list never
  contains the other tenant's candidate, on the actual HTTP route.

## What's left — ~180 more `db.query(Candidate|Users|Jobs)` call sites

Full inventory (`grep -rn "db\.query(Candidate)\|db\.query(Users)\|db\.query(Jobs)" app/api/v1/endpoints/`)
found 186 sites total; 6 are fixed above. The rest split into two very
different risk categories:

**Lower priority — single-record lookup by primary key** (the vast
majority, e.g. `db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()`).
Risk shape is IDOR (Insecure Direct Object Reference): someone would
need to already know or guess a specific ID belonging to another
tenant to exploit it — not a bulk-enumeration leak. Still worth fixing,
lower urgency than the list/search endpoints above.

**Same risk category as what's already fixed — found but not yet fixed**:
- `onboarding.py:516` — BU-pool candidate listing, more complex
  (joins `CandidateOwnership`, filters by business_unit rather than
  directly by tenant) — needs someone who understands the BU-pool
  semantics to get the scoping right, not a copy-paste of the pattern
  used elsewhere.

## The scalable long-term fix — recommended, not implemented tonight

Manually editing 180 more call sites, one at a time, is real, mechanical,
and error-prone (one missed site defeats the whole guarantee). The
architecturally correct fix at this scale is SQLAlchemy's
`with_loader_criteria()` — a session-level event listener
(`do_orm_execute`) that automatically injects `tenant_id == current_tenant`
into every query against a tenant-scoped model, without touching each
call site. This would retroactively secure all ~180 remaining sites
(and any future ones) at once.

This was deliberately NOT implemented tonight: it requires a
request-scoped "current tenant" context variable populated from the
authenticated user, and the right hook point to set it — this
codebase's auth happens per-route via `Depends()`, not global
middleware, so getting the timing right (context var set before the
first query in a request, cleared after) needs careful integration
testing against the real app before enabling, not a rushed guess. A
mistake here (a stale context value leaking between requests) would be
worse than today's status quo (no observable leak, since there is
currently exactly one tenant in production).

**Recommended next step**: build `with_loader_criteria`-based global
scoping as its own focused piece of work, with thorough concurrent-
request testing, before extending manual site-by-site fixes further.
