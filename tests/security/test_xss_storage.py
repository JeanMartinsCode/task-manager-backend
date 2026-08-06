"""Characterization tests for stored-XSS handling (pentest finding #4, BAIXO).

This is a *documented design decision*, not a code fix: `name`, `title`,
and `description` are intentionally stored and returned verbatim, with no
HTML/script sanitization. See API.md "Considerações de Segurança" for the
full rationale — in short, output encoding at render time is the correct
XSS defense, not input filtering at rest, and blocklisting tags here would
destroy legitimate data (e.g. a task titled "fix the <script> tag in
header.html") while giving a false sense of security.

These tests lock that decision in place: if someone later adds
sanitization here without updating the docs, this is the test that should
fail and prompt a conscious decision, not a silent behavior change.
"""

from datetime import datetime, timedelta

import pytest

from task_manager.database import Base, SessionLocal, engine
from task_manager.models import User

XSS_PAYLOAD = "<script>alert(1)</script>"


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Create and drop tables for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Provide a database session for setup."""
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


def make_user(db_session, email="xss@example.com"):
    user = User(name="XSS Fixture", email=email)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_user_name_with_script_tag_is_stored_and_returned_verbatim(client):
    """POST /api/users accepts an HTML/script payload in `name`, unmodified."""
    response = client.post(
        "/api/users", json={"name": XSS_PAYLOAD, "email": "payload-user@example.com"}
    )

    assert response.status_code == 201
    assert response.json()["name"] == XSS_PAYLOAD


def test_task_title_and_description_with_script_tag_round_trip_verbatim(client, db_session):
    """POST /api/tasks + GET returns `title`/`description` byte-for-byte, unescaped."""
    user = make_user(db_session)
    future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()

    created = client.post(
        "/api/tasks",
        json={
            "title": XSS_PAYLOAD,
            "description": f"Body: {XSS_PAYLOAD}",
            "deadline": future_date,
            "assigned_to_id": user.id,
        },
    )
    assert created.status_code == 201
    task_id = created.json()["id"]

    fetched = client.get(f"/api/tasks/{task_id}")

    assert fetched.status_code == 200
    body = fetched.json()
    assert body["title"] == XSS_PAYLOAD
    assert body["description"] == f"Body: {XSS_PAYLOAD}"
