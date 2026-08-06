"""Security regression tests for naive/aware datetime comparison (pentest round 2, #1, ALTO).

Root cause: `TaskCreate`/`TaskUpdate`'s `_validate_deadline` compared the
incoming `deadline` directly against `datetime.utcnow()` (naive). If the
client sends an ISO-8601 deadline with an explicit timezone — a "Z" suffix
or an explicit offset like "+03:00", which is exactly what
`Date.toISOString()` produces in JS — Pydantic parses it into a
timezone-aware `datetime`, and comparing that against the naive
`datetime.utcnow()` raises an uncaught
`TypeError: can't compare offset-naive and offset-aware datetimes`,
surfacing as a generic 500 instead of either accepting a valid future
deadline or rejecting a past one with 422.
"""

from datetime import datetime, timedelta, timezone

import pytest

from task_manager.database import Base, SessionLocal, engine
from task_manager.models import PriorityEnum, Task, TaskStatusEnum, User


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


def make_user(db_session, email="tz@example.com"):
    user = User(name="TZ Fixture", email=email)
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


def _z_suffixed(dt: datetime) -> str:
    """Format like JS `Date.toISOString()`: naive-UTC wall clock + literal 'Z'."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def _offset_suffixed(dt_utc: datetime) -> str:
    """Format the same instant with an explicit +03:00 offset instead of Z."""
    local = dt_utc.astimezone(timezone(timedelta(hours=3)))
    return local.strftime("%Y-%m-%dT%H:%M:%S") + "+03:00"


FUTURE_UTC = datetime.now(timezone.utc) + timedelta(days=365)
PAST_UTC = datetime.now(timezone.utc) - timedelta(days=1)


@pytest.mark.parametrize(
    "deadline_str",
    [_z_suffixed(FUTURE_UTC), _offset_suffixed(FUTURE_UTC)],
    ids=["Z-suffix", "explicit-offset"],
)
def test_create_task_accepts_future_aware_deadline(client, db_session, deadline_str):
    """POST /api/tasks with a future tz-aware deadline succeeds (never 500)."""
    user = make_user(db_session)

    response = client.post(
        "/api/tasks",
        json={"title": "Task", "deadline": deadline_str, "assigned_to_id": user.id},
    )

    assert response.status_code == 201


@pytest.mark.parametrize(
    "deadline_str",
    [_z_suffixed(PAST_UTC), _offset_suffixed(PAST_UTC)],
    ids=["Z-suffix", "explicit-offset"],
)
def test_create_task_rejects_past_aware_deadline_with_422(client, db_session, deadline_str):
    """POST /api/tasks with a past tz-aware deadline returns 422, never 500."""
    user = make_user(db_session)

    response = client.post(
        "/api/tasks",
        json={"title": "Task", "deadline": deadline_str, "assigned_to_id": user.id},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "deadline_str",
    [_z_suffixed(FUTURE_UTC), _offset_suffixed(FUTURE_UTC)],
    ids=["Z-suffix", "explicit-offset"],
)
def test_update_task_accepts_future_aware_deadline(client, db_session, deadline_str):
    """PUT /api/tasks/{id} with a future tz-aware deadline succeeds (never 500)."""
    user = make_user(db_session)
    task = make_task(db_session, user)

    response = client.put(f"/api/tasks/{task.id}", json={"deadline": deadline_str})

    assert response.status_code == 200


@pytest.mark.parametrize(
    "deadline_str",
    [_z_suffixed(PAST_UTC), _offset_suffixed(PAST_UTC)],
    ids=["Z-suffix", "explicit-offset"],
)
def test_update_task_rejects_past_aware_deadline_with_422(client, db_session, deadline_str):
    """PUT /api/tasks/{id} with a past tz-aware deadline returns 422, never 500."""
    user = make_user(db_session)
    task = make_task(db_session, user)

    response = client.put(f"/api/tasks/{task.id}", json={"deadline": deadline_str})

    assert response.status_code == 422
