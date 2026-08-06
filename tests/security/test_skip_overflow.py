"""Security regression tests for unbounded `skip` pagination param (pentest round 2, #2, MÉDIO).

Root cause: `skip: int = Query(0, ge=0)` in tasks.py, users.py, and
notifications.py has no upper bound. A value like
999999999999999999999 sails past validation and hits sqlite3's
parameter binding for the SQL `OFFSET` clause, which raises an
uncaught `OverflowError`, surfacing as a generic 500 instead of a 422
-- the exact same class of bug already fixed for resource IDs
(`le=MAX_SQLITE_INTEGER`), just not applied to `skip`.
"""

import pytest

from src.task_manager.database import Base, engine

try:
    from task_manager.constants import MAX_SQLITE_INTEGER
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from src.task_manager.constants import MAX_SQLITE_INTEGER

OVERFLOWING_SKIP = MAX_SQLITE_INTEGER + 1


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Create and drop tables for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_get_all_tasks_with_overflowing_skip_returns_422(client):
    """GET /api/tasks?skip=<huge> is rejected by validation, never reaches the DB."""
    response = client.get("/api/tasks", params={"skip": OVERFLOWING_SKIP})

    assert response.status_code == 422


def test_get_all_users_with_overflowing_skip_returns_422(client):
    """GET /api/users?skip=<huge> is rejected by validation, never reaches the DB."""
    response = client.get("/api/users", params={"skip": OVERFLOWING_SKIP})

    assert response.status_code == 422


def test_get_notifications_with_overflowing_skip_returns_422(client):
    """GET /api/notifications?skip=<huge> is rejected by validation, never reaches the DB."""
    response = client.get("/api/notifications", params={"skip": OVERFLOWING_SKIP})

    assert response.status_code == 422


def test_get_all_tasks_with_skip_at_boundary_is_accepted(client):
    """skip=MAX_SQLITE_INTEGER (the boundary itself) is still valid, just yields no rows."""
    response = client.get("/api/tasks", params={"skip": MAX_SQLITE_INTEGER})

    assert response.status_code == 200
