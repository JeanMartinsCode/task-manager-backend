"""Security regression tests for unbounded free-text fields (pentest finding #3, MÉDIO).

Root cause: `UserCreate.name`, `UserCreate.email`, `TaskCreate.title`,
`TaskCreate.description`, and their `TaskUpdate` counterparts had no
`max_length` — a 500KB payload in any of them was accepted and persisted,
a payload-amplification DoS vector (storage, memory, and bandwidth cost
per request with no upper bound).

Chosen limits (see schemas.py for the same rationale inline):
- `name`: 200 chars — far beyond any real name, headroom under the
  `String(255)` DB column.
- `email`: 254 chars — RFC 5321's practical maximum mailbox length.
- `title`: 200 chars — titles are short identifiers, not documents;
  headroom under the `String(255)` DB column.
- `description`: 2000 chars — roughly 300-400 words, enough for a
  genuinely detailed task description while bounding worst-case payload
  amplification to a few KB instead of hundreds.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.task_manager.database import Base, SessionLocal, engine
from src.task_manager.main import app

try:
    from task_manager.models import User
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from src.task_manager.models import User

TEST_API_KEY = "test-api-key-for-pytest-only"
OVERSIZED_PAYLOAD = "A" * (500 * 1024)  # 500KB, matching the pentest's payload size


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


def make_user(db_session, email="lengths@example.com"):
    user = User(name="Length Fixture", email=email)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_create_user_rejects_oversized_name(client):
    """POST /api/users rejects a 500KB `name` with 422, not 201."""
    response = client.post(
        "/api/users", json={"name": OVERSIZED_PAYLOAD, "email": "big-name@example.com"}
    )

    assert response.status_code == 422


def test_create_user_rejects_oversized_email(client):
    """POST /api/users rejects an absurdly long `email` with 422."""
    huge_email = "a" * 500 * 1024 + "@example.com"

    response = client.post("/api/users", json={"name": "Normal Name", "email": huge_email})

    assert response.status_code == 422


def test_create_user_accepts_name_at_boundary(client):
    """A 200-char name (the chosen limit) is still accepted."""
    response = client.post(
        "/api/users", json={"name": "A" * 200, "email": "boundary@example.com"}
    )

    assert response.status_code == 201


def test_create_user_rejects_name_one_over_boundary(client):
    """A 201-char name (one over the chosen limit) is rejected."""
    response = client.post(
        "/api/users", json={"name": "A" * 201, "email": "over-boundary@example.com"}
    )

    assert response.status_code == 422


def test_create_task_rejects_oversized_title(client, db_session):
    """POST /api/tasks rejects a 500KB `title` with 422, not 201."""
    user = make_user(db_session)
    future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()

    response = client.post(
        "/api/tasks",
        json={
            "title": OVERSIZED_PAYLOAD,
            "deadline": future_date,
            "assigned_to_id": user.id,
        },
    )

    assert response.status_code == 422


def test_create_task_rejects_oversized_description(client, db_session):
    """POST /api/tasks rejects a 500KB `description` with 422, not 201."""
    user = make_user(db_session)
    future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()

    response = client.post(
        "/api/tasks",
        json={
            "title": "Normal title",
            "description": OVERSIZED_PAYLOAD,
            "deadline": future_date,
            "assigned_to_id": user.id,
        },
    )

    assert response.status_code == 422


def test_create_task_accepts_description_at_boundary(client, db_session):
    """A 2000-char description (the chosen limit) is still accepted."""
    user = make_user(db_session)
    future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()

    response = client.post(
        "/api/tasks",
        json={
            "title": "Normal title",
            "description": "D" * 2000,
            "deadline": future_date,
            "assigned_to_id": user.id,
        },
    )

    assert response.status_code == 201


def test_update_task_rejects_oversized_title(client, db_session):
    """PUT /api/tasks/{id} rejects a 500KB `title` with 422."""
    user = make_user(db_session)
    future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
    created = client.post(
        "/api/tasks",
        json={"title": "Original", "deadline": future_date, "assigned_to_id": user.id},
    )
    task_id = created.json()["id"]

    response = client.put(f"/api/tasks/{task_id}", json={"title": OVERSIZED_PAYLOAD})

    assert response.status_code == 422


def test_update_task_rejects_oversized_description(client, db_session):
    """PUT /api/tasks/{id} rejects a 500KB `description` with 422."""
    user = make_user(db_session)
    future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
    created = client.post(
        "/api/tasks",
        json={"title": "Original", "deadline": future_date, "assigned_to_id": user.id},
    )
    task_id = created.json()["id"]

    response = client.put(f"/api/tasks/{task_id}", json={"description": OVERSIZED_PAYLOAD})

    assert response.status_code == 422
