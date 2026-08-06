"""Security regression tests for API key authentication (pentest finding #1, ALTO).

Root cause: no router had any identity check wired in — every endpoint
depended only on `Depends(get_db)`, so any HTTP request could read or
mutate any resource. `security.require_api_key` closes that gap; these
tests lock the fix in place.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from task_manager.database import Base, SessionLocal, engine
from task_manager.main import app

try:
    from task_manager.models import PriorityEnum, Task, TaskStatusEnum, User
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from task_manager.models import PriorityEnum, Task, TaskStatusEnum, User

TEST_API_KEY = "test-api-key-for-pytest-only"
WRONG_API_KEY = "definitely-not-the-right-key"


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Create and drop tables for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def unauthenticated_client():
    """A client that sends no credentials at all."""
    return TestClient(app)


@pytest.fixture
def wrong_key_client():
    """A client that sends a well-formed but incorrect API key."""
    client = TestClient(app)
    client.headers.update({"X-API-Key": WRONG_API_KEY})
    return client


@pytest.fixture
def authenticated_client():
    """A client that sends the correct API key."""
    client = TestClient(app)
    client.headers.update({"X-API-Key": TEST_API_KEY})
    return client


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


def make_user(db_session, email="auth-fixture@example.com"):
    user = User(name="Auth Fixture", email=email)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def make_task(db_session, user):
    task = Task(
        title="Task",
        deadline=datetime.utcnow() + timedelta(days=1),
        priority=PriorityEnum.MEDIUM,
        status=TaskStatusEnum.PENDING,
        assigned_to=user.id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


# (method, path_template, json_body) — path_template is filled in per-test since
# some routes need a real id created via db_session first.
PROTECTED_GET_ROUTES = [
    "/api/users",
    "/api/tasks",
    "/api/notifications",
    "/api/status",
]


@pytest.mark.parametrize("path", PROTECTED_GET_ROUTES)
def test_protected_get_routes_reject_missing_api_key(unauthenticated_client, path):
    """Every protected GET endpoint returns 401 with no X-API-Key header."""
    response = unauthenticated_client.get(path)

    assert response.status_code == 401
    assert "api key" in response.json()["detail"].lower()


@pytest.mark.parametrize("path", PROTECTED_GET_ROUTES)
def test_protected_get_routes_reject_wrong_api_key(wrong_key_client, path):
    """Every protected GET endpoint returns 401 with an incorrect X-API-Key."""
    response = wrong_key_client.get(path)

    assert response.status_code == 401


@pytest.mark.parametrize("path", PROTECTED_GET_ROUTES)
def test_protected_get_routes_accept_correct_api_key(authenticated_client, path):
    """Every protected GET endpoint returns 200 with the correct X-API-Key."""
    response = authenticated_client.get(path)

    assert response.status_code == 200


def test_create_user_rejected_without_api_key(unauthenticated_client):
    """POST /api/users (write) is blocked without a key."""
    response = unauthenticated_client.post(
        "/api/users", json={"name": "Eve", "email": "eve@example.com"}
    )

    assert response.status_code == 401


def test_create_user_allowed_with_api_key(authenticated_client):
    """POST /api/users succeeds once authenticated (behavior unchanged for legit callers)."""
    response = authenticated_client.post(
        "/api/users", json={"name": "Eve", "email": "eve@example.com"}
    )

    assert response.status_code == 201


def test_get_single_user_rejected_without_api_key(unauthenticated_client, db_session):
    """GET /api/users/{id} is blocked without a key, even for a real id."""
    user = make_user(db_session)

    response = unauthenticated_client.get(f"/api/users/{user.id}")

    assert response.status_code == 401


def test_update_and_delete_task_rejected_without_api_key(unauthenticated_client, db_session):
    """PUT and DELETE on tasks are blocked without a key."""
    user = make_user(db_session)
    task = make_task(db_session, user)

    put_response = unauthenticated_client.put(
        f"/api/tasks/{task.id}", json={"title": "Hijacked"}
    )
    delete_response = unauthenticated_client.delete(f"/api/tasks/{task.id}")

    assert put_response.status_code == 401
    assert delete_response.status_code == 401
    # Prove the attempted mutation never happened.
    survivor = db_session.get(Task, task.id)
    assert survivor is not None
    assert survivor.title == "Task"


def test_health_check_remains_public(unauthenticated_client):
    """/health is intentionally exempt (infra liveness probes carry no credentials)."""
    response = unauthenticated_client.get("/health")

    assert response.status_code == 200


def test_server_without_api_key_configured_fails_closed(unauthenticated_client, monkeypatch):
    """If API_KEY is unset on the server, requests are rejected (500), never silently allowed."""
    monkeypatch.delenv("API_KEY", raising=False)

    response = unauthenticated_client.get("/api/users")

    assert response.status_code == 500
