"""Integration tests for Notification API endpoints (Task 5.3)."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.task_manager.database import Base, SessionLocal, engine
from src.task_manager.main import app

try:
    from task_manager.models import (
        Notification,
        NotificationTypeEnum,
        PriorityEnum,
        Task,
        TaskStatusEnum,
        User,
    )
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from src.task_manager.models import (
        Notification,
        NotificationTypeEnum,
        PriorityEnum,
        Task,
        TaskStatusEnum,
        User,
    )


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Create and drop tables for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


TEST_API_KEY = "test-api-key-for-pytest-only"


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


def make_user(db_session, email):
    user = User(name="Test User", email=email)
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


def make_notification(db_session, task, *, created_at):
    notification = Notification(
        task_id=task.id,
        notification_type=NotificationTypeEnum.ESCALATION,
        message="msg",
        created_at=created_at,
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)
    return notification


def test_get_notifications_returns_most_recent_first_with_pagination(client, db_session):
    """GET /api/notifications returns items newest-first, respecting skip/limit."""
    user = make_user(db_session, "notif-a@example.com")
    task = make_task(db_session, user)
    base = datetime.utcnow()
    notification_ids = [
        make_notification(db_session, task, created_at=base - timedelta(minutes=i)).id
        for i in range(3)
    ]

    response = client.get("/api/notifications", params={"skip": 1, "limit": 1})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == notification_ids[1]


def test_get_notifications_filtered_by_task_id(client, db_session):
    """GET /api/notifications?task_id=X returns only that task's notifications."""
    user = make_user(db_session, "notif-b@example.com")
    task_1 = make_task(db_session, user)
    task_2 = make_task(db_session, user)
    make_notification(db_session, task_2, created_at=datetime.utcnow())
    expected_id = make_notification(db_session, task_1, created_at=datetime.utcnow()).id
    task_1_id = task_1.id

    response = client.get("/api/notifications", params={"task_id": task_1_id})

    assert response.status_code == 200
    body = response.json()
    assert [n["id"] for n in body] == [expected_id]


def test_get_notifications_filtered_by_task_id_no_match_returns_empty_list(client, db_session):
    """A task_id with no notifications returns 200 and an empty list, not 404."""
    user = make_user(db_session, "notif-c@example.com")
    task = make_task(db_session, user)

    response = client.get("/api/notifications", params={"task_id": task.id})

    assert response.status_code == 200
    assert response.json() == []


def test_get_notifications_filtered_by_user_id(client, db_session):
    """GET /api/notifications?user_id=Y returns notifications across that user's tasks."""
    user_a = make_user(db_session, "notif-d@example.com")
    user_b = make_user(db_session, "notif-e@example.com")
    task_a = make_task(db_session, user_a)
    task_b = make_task(db_session, user_b)
    make_notification(db_session, task_b, created_at=datetime.utcnow())
    expected_id = make_notification(db_session, task_a, created_at=datetime.utcnow()).id
    user_a_id = user_a.id

    response = client.get("/api/notifications", params={"user_id": user_a_id})

    assert response.status_code == 200
    body = response.json()
    assert [n["id"] for n in body] == [expected_id]


def test_get_notifications_filtered_by_user_id_no_match_returns_empty_list(client, db_session):
    """A user_id with no notifications returns 200 and an empty list, not 404."""
    user = make_user(db_session, "notif-f@example.com")

    response = client.get("/api/notifications", params={"user_id": user.id})

    assert response.status_code == 200
    assert response.json() == []


def test_get_notifications_task_id_takes_precedence_over_user_id(client, db_session):
    """When both filters are given, task_id wins."""
    user_a = make_user(db_session, "notif-g@example.com")
    user_b = make_user(db_session, "notif-h@example.com")
    task_a = make_task(db_session, user_a)
    task_b = make_task(db_session, user_b)
    expected_id = make_notification(db_session, task_a, created_at=datetime.utcnow()).id
    make_notification(db_session, task_b, created_at=datetime.utcnow())
    task_a_id = task_a.id
    user_b_id = user_b.id

    response = client.get(
        "/api/notifications", params={"task_id": task_a_id, "user_id": user_b_id}
    )

    assert response.status_code == 200
    body = response.json()
    assert [n["id"] for n in body] == [expected_id]


@pytest.mark.parametrize(
    "params",
    [
        {"skip": -1},
        {"limit": 0},
        {"limit": 101},
        {"task_id": 0},
        {"user_id": 0},
    ],
)
def test_get_notifications_invalid_query_params_return_422(client, params):
    """Out-of-range query params are rejected with 422."""
    response = client.get("/api/notifications", params=params)

    assert response.status_code == 422
