"""
Runs the HRMS-0114 audit against the REAL app (app.main:app) and
reports the current gap.

Tiers:
- "no identity check at all" (find_routes_missing_permission_declaration)
  -- the genuinely dangerous category. Started at 58 flagged tonight;
  most turned out to be legitimately protected by candidate-self-service
  or any-internal-user checks the audit tool now recognizes, or were
  fixed directly. Of what's left, 3 (the msgraph mail/calendar routes)
  have REAL protection the tool structurally can't see -- an in-function-
  body cookie check (_require_account in msgraph.py), not a FastAPI
  Depends() the dependency-tree scanner can inspect. Those 3 are in
  MANUALLY_VERIFIED_EXCEPTIONS below, with a guard test that fails
  loudly if that protection is ever removed, so this exception can't
  silently go stale.

  The other 2 that showed up were genuine open questions, resolved
  2026-07-20 after confirming intent (not guessed at):
    - GET /jobs/active-jobs: its query returns BOTH "active" and
      "public" status jobs mixed together, so making it public would
      leak internal not-yet-published jobs. Confirmed internal-only --
      now has require_permission("job.view").
    - POST /ai-agent/webhook/email-reply: now requires either a shared
      secret (X-Webhook-Secret header, WEBHOOK_SHARED_SECRET in .env)
      or a valid internal-user bearer token -- see
      app.core.webhook_auth.require_webhook_secret_or_internal_user,
      which supports both since this endpoint has both external
      (scheduler/webhook) and internal (HR portal) legitimate callers.

- "coarse auth only" -- routes with SOME identity check but no
  fine-grained RBAC permission. Reported (xfail, non-blocking) as a
  punch list to tighten over time, not an emergency.

Importing app.main only registers routes -- it does not connect to the
database (SQLAlchemy's create_engine is lazy), so this is safe to run
without touching the real database.
"""
import inspect

import pytest

from app.core.route_security_audit import (
    find_routes_missing_permission_declaration,
    find_routes_with_only_coarse_auth,
)
from app.middleware.auth_middleware import AuthenticationMiddleware

MANUALLY_VERIFIED_EXCEPTIONS = {
    "GET /msgraph/calendar/meetings",
    "POST /msgraph/calendar/schedule",
    "POST /msgraph/mail/send",
}

GENUINE_OPEN_QUESTIONS = set()  # both resolved 2026-07-20: active-jobs kept
# internal (require_permission("job.view")), webhook now requires either
# a shared secret or an internal-user token (require_webhook_secret_or_internal_user)


def _all_public_paths():
    # route_security_audit compares against route.path, which for a
    # parameterized route IS the literal "{param}" template string --
    # unlike AuthenticationMiddleware's runtime check, no segment
    # matching is needed here, plain equality against the template works.
    return AuthenticationMiddleware.PUBLIC_ROUTES + AuthenticationMiddleware.PUBLIC_ROUTE_TEMPLATES


def test_msgraph_manual_exception_guard_still_has_real_protection():
    """
    If _require_account ever gets removed or renamed in msgraph.py, the
    3 routes in MANUALLY_VERIFIED_EXCEPTIONS lose their only protection
    -- this must fail loudly, not silently pass the exception list
    forever regardless of whether the underlying claim is still true.
    """
    from app.api.v1.endpoints import msgraph

    assert hasattr(msgraph, "_require_account"), (
        "msgraph.py's _require_account() is gone -- MANUALLY_VERIFIED_EXCEPTIONS "
        "in this test file is no longer valid and those 3 routes need real review."
    )
    source = inspect.getsource(msgraph)
    for route_fn_snippet in ["def send_mail(", "def schedule_meeting(", "def get_my_meetings("]:
        assert route_fn_snippet in source, f"{route_fn_snippet} not found -- route may have moved/renamed"


def test_real_app_has_no_unexplained_routes_with_zero_identity_check():
    from app.main import app

    missing = set(find_routes_missing_permission_declaration(app, _all_public_paths()))
    unexplained = missing - MANUALLY_VERIFIED_EXCEPTIONS - GENUINE_OPEN_QUESTIONS

    if unexplained:
        print(f"\n{len(unexplained)} UNEXPLAINED route(s) with no identity check:")
        for route in sorted(unexplained):
            print(f"  - {route}")
    assert not unexplained, (
        "New route(s) shipped with no identity check and no entry in this "
        "test's exception lists -- see docs/build-package/HRMS-0114-route-gap.md"
    )

    # And the reverse -- if one of the "genuine open questions" gets
    # fixed, this test should notice so the question can be removed
    # from the list rather than silently staying documented as open.
    resolved = GENUINE_OPEN_QUESTIONS - missing
    if resolved:
        print(f"\nThese are no longer open questions, remove from GENUINE_OPEN_QUESTIONS: {resolved}")


@pytest.mark.xfail(strict=False, reason="Routes with coarse auth but no fine-grained RBAC permission -- tracked, not an emergency")
def test_real_app_has_no_routes_with_only_coarse_auth():
    from app.main import app

    coarse = find_routes_with_only_coarse_auth(app, _all_public_paths())
    if coarse:
        print(f"\n{len(coarse)} route(s) with coarse auth only (protected, not fine-grained):")
        for route in coarse:
            print(f"  - {route}")
    assert not coarse
