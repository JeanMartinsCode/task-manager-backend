"""Security regression tests for unbounded request body size (pentest round 2, #3, MÉDIO).

Root cause: `max_length` in schemas.py only rejects a field *after*
Pydantic has already parsed the full JSON body into Python objects --
the raw bytes are read into memory and parsed regardless of size. A
48MB body was fully read and parsed (process RSS jumped ~150MB in a
single request, ~1.7s) before being rejected with 422.

`body_limit.py` adds an ASGI middleware that inspects the
`Content-Length` header before Starlette reads a single byte of the
body, rejecting oversized requests with 413 -- cheaply, before any
parsing happens.
"""

from datetime import datetime, timedelta

import pytest

from task_manager.database import Base, engine

try:
    from task_manager.body_limit import MAX_BODY_BYTES
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from task_manager.body_limit import MAX_BODY_BYTES


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Create and drop tables for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_oversized_body_rejected_with_413_before_parsing(client):
    """A body exceeding MAX_BODY_BYTES is rejected at the middleware layer (413).

    Pre-fix, this exact payload would be fully parsed and only then
    rejected by Pydantic's `max_length` validator (422) -- the body still
    gets read and parsed in full first. Post-fix it never reaches parsing.
    """
    huge_description = "A" * (MAX_BODY_BYTES + 1024)
    future = (datetime.utcnow() + timedelta(days=1)).isoformat()

    response = client.post(
        "/api/tasks",
        json={
            "title": "Task",
            "description": huge_description,
            "deadline": future,
            "assigned_to_id": 1,
        },
    )

    assert response.status_code == 413


def test_oversized_body_does_not_create_a_resource(client):
    """A body rejected for size never reaches the database."""
    huge_name = "A" * (MAX_BODY_BYTES + 1024)

    response = client.post(
        "/api/users", json={"name": huge_name, "email": "huge-body@example.com"}
    )

    assert response.status_code == 413

    listing = client.get("/api/users")
    emails = [u["email"] for u in listing.json()]
    assert "huge-body@example.com" not in emails


def test_normal_sized_request_is_unaffected_by_the_size_cap(client):
    """A legitimately-sized request is never rejected by this middleware."""
    response = client.post(
        "/api/users", json={"name": "Normal", "email": "normal-size@example.com"}
    )

    assert response.status_code != 413
    assert response.status_code == 201
