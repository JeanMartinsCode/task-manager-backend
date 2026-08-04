"""Security regression tests for missing rate limiting (pentest finding #5, BAIXO).

Root cause: no request throttling existed anywhere — the pentest fired 30
consecutive requests in ~180ms and all were accepted. `rate_limit.py`
adds an application-level limiter (slowapi) on write endpoints
(POST/PUT/DELETE), configurable via the `RATE_LIMIT_WRITE` env var.

This is explicitly defense in depth, not a replacement for infra-level
throttling: see ARCHITECTURE.md for why a real production deployment
should also rate-limit at the gateway/reverse-proxy layer.

The test suite pins `RATE_LIMIT_WRITE=5/minute` (see tests/conftest.py) so
this test is fast and deterministic; production defaults to a higher
value (20/minute) via the same env var. `conftest.py`'s autouse
`_reset_rate_limiter` fixture resets the shared limiter state before
every test so this test's writes don't leak into (or get starved by)
other tests sharing the same in-process app/limiter singleton.
"""

import pytest

from src.task_manager.database import Base, engine


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Create and drop tables for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_create_user_is_throttled_after_configured_limit(client):
    """POST /api/users returns 429 once the per-IP write limit is exceeded.

    The test env pins RATE_LIMIT_WRITE=5/minute, so the 6th rapid request
    in the same minute must be rejected.
    """
    responses = [
        client.post("/api/users", json={"name": f"User {i}", "email": f"rl{i}@example.com"})
        for i in range(6)
    ]

    statuses = [r.status_code for r in responses]
    assert statuses[:5] == [201, 201, 201, 201, 201]
    assert statuses[5] == 429


def test_rate_limited_response_does_not_create_a_resource(client):
    """A 429 response must not have side effects: no user is created."""
    for i in range(5):
        client.post("/api/users", json={"name": f"Filler {i}", "email": f"fill{i}@example.com"})

    blocked = client.post(
        "/api/users", json={"name": "Blocked", "email": "blocked@example.com"}
    )
    assert blocked.status_code == 429

    listing = client.get("/api/users")
    emails = [u["email"] for u in listing.json()]
    assert "blocked@example.com" not in emails


def test_get_requests_are_not_rate_limited(client):
    """Read-only GET endpoints are unaffected — only writes are throttled."""
    responses = [client.get("/api/users") for _ in range(10)]

    assert all(r.status_code == 200 for r in responses)
