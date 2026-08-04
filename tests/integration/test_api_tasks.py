"""Integration tests for Task API endpoints (Task 3.3)."""

from datetime import datetime, timedelta

import pytest

from src.task_manager.database import Base, SessionLocal, engine

try:
    from task_manager.models import PriorityEnum, Task, TaskStatusEnum, User
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from src.task_manager.models import PriorityEnum, Task, TaskStatusEnum, User


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


def test_create_task(client, db_session):
    """POST /api/tasks creates a task and returns 201."""
    user = User(name="Jane Doe", email="jane@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    future_date = datetime.utcnow() + timedelta(days=1)
    response = client.post(
        "/api/tasks",
        json={
            "title": "Fix auth bug",
            "description": "Investigate login issue",
            "deadline": future_date.isoformat(),
            "priority": "HIGH",
            "assigned_to_id": user.id,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Fix auth bug"
    assert data["priority"] == "HIGH"
    assert data["assigned_to"] == user.id
    assert data["status"] == "PENDING"


def test_get_task(client, db_session):
    """GET /api/tasks/{task_id} returns 200 for existing task."""
    user = User(name="Jane Doe", email="jane@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    task = Task(
        title="Write docs",
        description="Update API docs",
        deadline=datetime.utcnow() + timedelta(days=2),
        priority=PriorityEnum.MEDIUM,
        status=TaskStatusEnum.PENDING,
        assigned_to=user.id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    response = client.get(f"/api/tasks/{task.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == task.id
    assert data["title"] == "Write docs"


def test_get_task_not_found(client):
    """GET /api/tasks/{task_id} returns 404 when absent."""
    response = client.get("/api/tasks/999")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_all_tasks_with_filters_and_pagination(client, db_session):
    """GET /api/tasks returns paginated items with total count."""
    user = User(name="Jane Doe", email="jane@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    for index in range(3):
        task = Task(
            title=f"Task {index}",
            deadline=datetime.utcnow() + timedelta(days=index + 1),
            priority=PriorityEnum.HIGH if index % 2 == 0 else PriorityEnum.LOW,
            status=TaskStatusEnum.IN_PROGRESS if index == 1 else TaskStatusEnum.PENDING,
            assigned_to=user.id,
        )
        db_session.add(task)
    db_session.commit()

    response = client.get("/api/tasks?skip=1&limit=1&status=PENDING&priority=HIGH")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Task 2"


def test_update_task(client, db_session):
    """PUT /api/tasks/{task_id} updates a task."""
    user = User(name="Jane Doe", email="jane@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    task = Task(
        title="Old title",
        deadline=datetime.utcnow() + timedelta(days=3),
        priority=PriorityEnum.LOW,
        status=TaskStatusEnum.PENDING,
        assigned_to=user.id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    response = client.put(
        f"/api/tasks/{task.id}",
        json={"title": "New title", "status": "IN_PROGRESS"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New title"
    assert data["status"] == "IN_PROGRESS"


def test_delete_task(client, db_session):
    """DELETE /api/tasks/{task_id} removes a task."""
    user = User(name="Jane Doe", email="jane@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    task = Task(
        title="Delete me",
        deadline=datetime.utcnow() + timedelta(days=1),
        priority=PriorityEnum.MEDIUM,
        status=TaskStatusEnum.PENDING,
        assigned_to=user.id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    response = client.delete(f"/api/tasks/{task.id}")

    assert response.status_code == 204
    assert client.get(f"/api/tasks/{task.id}").status_code == 404
