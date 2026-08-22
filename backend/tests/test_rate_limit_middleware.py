"""
Proves Phase 1 B4's acceptance test: "exceed the configured rate limit
from a single source; confirm throttling engages before the request
reaches business logic."

Uses a tiny standalone app (not the real app.main:app -- keeps this
fast and independent of the real database) with a handler that
increments a counter, so "reaches business logic" is directly
observable rather than inferred from a status code alone.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.auth_middleware import RateLimitMiddleware

handler_call_count = {"n": 0}

def _build_app(max_requests=3, window_seconds=60):
    handler_call_count["n"] = 0
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, max_requests=max_requests, window_seconds=window_seconds)

    @app.get("/ping")
    def ping():
        handler_call_count["n"] += 1
        return {"pong": True}

    return app

def test_requests_under_the_limit_reach_business_logic():
    client = TestClient(_build_app(max_requests=3, window_seconds=60))
    for _ in range(3):
        resp = client.get("/ping")
        assert resp.status_code == 200
    assert handler_call_count["n"] == 3

def test_exceeding_the_limit_is_throttled_before_business_logic():
    client = TestClient(_build_app(max_requests=3, window_seconds=60))
    for _ in range(3):
        client.get("/ping")

    resp = client.get("/ping")  # 4th request, over the limit
    assert resp.status_code == 429
    # The core assertion: the handler itself was never invoked for the
    # throttled request -- business logic was never reached.
    assert handler_call_count["n"] == 3

def test_throttled_response_does_not_leak_internal_details():
    client = TestClient(_build_app(max_requests=1, window_seconds=60))
    client.get("/ping")
    resp = client.get("/ping")
    assert resp.status_code == 429
    assert "Rate limit exceeded" in resp.json()["detail"]

def test_different_ips_are_tracked_independently():
    """
    TestClient sends every request from the same client IP by default,
    so this test exercises the per-IP bucket logic directly rather than
    relying on TestClient's transport internals.
    """
    mw = RateLimitMiddleware(app=lambda scope, receive, send: None, max_requests=2, window_seconds=60)
    now = 1000.0

    assert mw._is_rate_limited("1.1.1.1", now) is False
    mw._record_request("1.1.1.1", now)
    mw._record_request("1.1.1.1", now)
    assert mw._is_rate_limited("1.1.1.1", now) is True

    # A different IP has its own independent bucket, unaffected by 1.1.1.1's usage.
    assert mw._is_rate_limited("2.2.2.2", now) is False

def test_window_expiry_allows_requests_again():
    mw = RateLimitMiddleware(app=lambda scope, receive, send: None, max_requests=1, window_seconds=10)
    mw._record_request("3.3.3.3", 1000.0)
    assert mw._is_rate_limited("3.3.3.3", 1000.0) is True

    # Well past the 10s window -- old entry should be pruned by _clean_old_entries.
    mw._clean_old_entries("3.3.3.3", 1020.0)
    assert mw._is_rate_limited("3.3.3.3", 1020.0) is False
