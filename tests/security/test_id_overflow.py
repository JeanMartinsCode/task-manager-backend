"""Security regression tests for oversized IDs (pentest finding #2, MÉDIO).

Root cause: SQLite's INTEGER storage class is a signed 64-bit value
(-2**63 .. 2**63-1). Python ints are unbounded, and none of the `int` path
params, query params, or Pydantic body fields for IDs had an upper bound —
so a value like 999999999999999999999999 sailed past validation and hit
`sqlite3`'s parameter binding, which raises an uncaught `OverflowError`
that bubbled up as a generic, unhandled 500.

The fix has two independent layers, both covered here:
1. `constants.MAX_SQLITE_INTEGER` bounds every ID field (`le=...`), so
   oversized IDs are rejected with 422 before ever reaching the database.
2. A global exception handler in `main.py` catches anything unexpected
   that still gets through and returns a generic message + `error_id`,
   never a stack trace — defense in depth for *any* unforeseen exception,
   not just this one.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.task_manager.database import Base, SessionLocal, engine
from src.task_manager.main import app

try:
    from task_manager.models import PriorityEnum, Task, TaskStatusEnum, User
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from src.task_manager.models import PriorityEnum, Task, TaskStatusEnum, User

TEST_API_KEY = "test-api-key-for-pytest-only"

# Comfortably outside SQLite's signed 64-bit INTEGER range (max is
# 9_223_372_036_854_775_807); this is the exact class of value the pentest
# report used to trigger the OverflowError.
OVERFLOWING_ID = 999999999999999999999999


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Create and drop tables for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """Create a test client, pre-authenticated with the API key."""
    test_client = TestClient(app)
    test_client.headers.update({"X-API-Key": TEST_API_KEY})
    return test_client


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


def make_user(db_session, email="overflow@example.com"):
    user = User(name="Overflow Fixture", email=email)
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


def test_get_task_with_overflowing_id_returns_422_not_500(client):
    """GET /api/tasks/{huge_id} is rejected by validation, never reaches the DB."""
    response = client.get(f"/api/tasks/{OVERFLOWING_ID}")

    assert response.status_code == 422


def test_update_task_with_overflowing_id_returns_422(client):
    """PUT /api/tasks/{huge_id} is rejected by validation."""
    response = client.put(f"/api/tasks/{OVERFLOWING_ID}", json={"title": "x"})

    assert response.status_code == 422


def test_delete_task_with_overflowing_id_returns_422(client):
    """DELETE /api/tasks/{huge_id} is rejected by validation."""
    response = client.delete(f"/api/tasks/{OVERFLOWING_ID}")

    assert response.status_code == 422


def test_get_user_with_overflowing_id_returns_422(client):
    """GET /api/users/{huge_id} is rejected by validation."""
    response = client.get(f"/api/users/{OVERFLOWING_ID}")

    assert response.status_code == 422


def test_create_task_with_overflowing_assigned_to_id_returns_422(client, db_session):
    """POST /api/tasks with an oversized assigned_to_id body field is rejected."""
    future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()

    response = client.post(
        "/api/tasks",
        json={
            "title": "Task",
            "deadline": future_date,
            "assigned_to_id": OVERFLOWING_ID,
        },
    )

    assert response.status_code == 422


def test_get_all_tasks_with_overflowing_assigned_to_id_query_returns_422(client):
    """GET /api/tasks?assigned_to_id=<huge> is rejected by validation."""
    response = client.get("/api/tasks", params={"assigned_to_id": OVERFLOWING_ID})

    assert response.status_code == 422


def test_get_notifications_with_overflowing_task_id_query_returns_422(client):
    """GET /api/notifications?task_id=<huge> is rejected by validation."""
    response = client.get("/api/notifications", params={"task_id": OVERFLOWING_ID})

    assert response.status_code == 422


def test_get_notifications_with_overflowing_user_id_query_returns_422(client):
    """GET /api/notifications?user_id=<huge> is rejected by validation."""
    response = client.get("/api/notifications", params={"user_id": OVERFLOWING_ID})

    assert response.status_code == 422


def test_unexpected_exception_returns_generic_500_with_error_id_no_internals(monkeypatch):
    """Any exception the routes don't anticipate is masked by the global handler.

    Uses `raise_server_exceptions=False` because Starlette's TestClient
    re-raises unhandled exceptions by default (so pytest can show a
    traceback) instead of returning the response an ASGI server would
    actually send in production; we need the real HTTP response here.

    Patches `src.task_manager.services.TaskService` specifically (matching
    how `app` itself is imported above) rather than the compatibility
    `task_manager.services` alias: whichever import path resolves first
    process-wide during the full test run can cache the two as distinct
    module objects, and only the `src`-prefixed one is guaranteed to be
    the class the running `app`'s routes actually call.
    """
    from src.task_manager.services import TaskService

    def boom(*args, **kwargs):
        raise RuntimeError("credentials=supersecret db_path=/etc/prod.db")

    monkeypatch.setattr(TaskService, "get_task", boom)

    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update({"X-API-Key": TEST_API_KEY})

    response = client.get("/api/tasks/1")

    assert response.status_code == 500
    body = response.json()
    assert set(body.keys()) == {"detail", "error_id"}
    assert body["detail"] == "Internal server error"
    assert "supersecret" not in response.text
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text
    # error_id must be present and usable for log correlation.
    assert len(body["error_id"]) > 0
