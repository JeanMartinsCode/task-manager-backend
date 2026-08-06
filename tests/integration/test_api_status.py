"""Integration tests for the status endpoint (Task 6.1)."""

from datetime import datetime, timedelta

import pytest

from task_manager.database import Base, SessionLocal, engine

try:
    from task_manager.api import status as status_module
    from task_manager.models import PriorityEnum, Task, TaskStatusEnum, User
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from task_manager.api import status as status_module
    from task_manager.models import PriorityEnum, Task, TaskStatusEnum, User


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Create and drop tables for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def stub_last_run_info(monkeypatch):
    """Isolate the endpoint from the real scheduler state by default."""
    monkeypatch.setattr(
        status_module, "get_last_run_info", lambda: {"timestamp": None, "escalated_count": 0}
    )


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


def make_user(db_session, email):
    user = User(name="Status User", email=email)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def make_task(db_session, user, *, status, priority):
    task = Task(
        title="Task",
        deadline=datetime.utcnow() + timedelta(days=1),
        priority=priority,
        status=status,
        assigned_to=user.id,
    )
    db_session.add(task)
    db_session.commit()
    return task


def test_status_reflects_task_counts_by_status_and_priority(client, db_session):
    """GET /api/status aggregates tasks by status and priority correctly."""
    user = make_user(db_session, "status-a@example.com")
    make_task(db_session, user, status=TaskStatusEnum.PENDING, priority=PriorityEnum.LOW)
    make_task(db_session, user, status=TaskStatusEnum.PENDING, priority=PriorityEnum.HIGH)
    make_task(db_session, user, status=TaskStatusEnum.COMPLETED, priority=PriorityEnum.HIGH)

    response = client.get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["db_connected"] is True
    assert body["tasks_count"] == 3
    assert body["tasks_by_status"] == {"PENDING": 2, "IN_PROGRESS": 0, "COMPLETED": 1}
    assert body["tasks_by_priority"] == {"HIGH": 2, "MEDIUM": 0, "LOW": 1}


def test_status_with_empty_database_returns_zero_counts(client):
    """GET /api/status returns all-zero counts when there are no tasks."""
    response = client.get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["tasks_count"] == 0
    assert all(count == 0 for count in body["tasks_by_status"].values())
    assert all(count == 0 for count in body["tasks_by_priority"].values())


def test_status_before_any_escalation_run_shows_null_and_zero(client):
    """Before the escalation job has ever run, last-run fields are null/0."""
    response = client.get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["last_escalation_time"] is None
    assert body["last_escalation_count"] == 0


def test_status_reflects_last_escalation_run_info(client, monkeypatch):
    """GET /api/status surfaces whatever the scheduler reports as the last run."""
    fixed_timestamp = "2026-07-25T12:00:00+00:00"
    monkeypatch.setattr(
        status_module,
        "get_last_run_info",
        lambda: {"timestamp": fixed_timestamp, "escalated_count": 3},
    )

    response = client.get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["last_escalation_time"] == fixed_timestamp
    assert body["last_escalation_count"] == 3
