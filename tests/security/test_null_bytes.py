"""Security regression tests for null bytes in free-text fields (pentest finding #6, INFORMATIVO).

Root cause: neither Pydantic nor SQLite reject `\\x00` in a string — it was
accepted and persisted as-is. Not directly exploitable through this API,
but a latent landmine for anything downstream that treats these strings as
C-strings (truncation) or writes them to logs/CSV exports (corruption,
parsing failures).
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


def make_user(db_session, email="nullbyte@example.com"):
    user = User(name="Null Byte Fixture", email=email)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_create_user_rejects_null_byte_in_name(client):
    """POST /api/users rejects a `name` containing a null byte with 422."""
    response = client.post(
        "/api/users", json={"name": "Evil\x00Name", "email": "nullbyte-user@example.com"}
    )

    assert response.status_code == 422


def test_create_task_rejects_null_byte_in_title(client, db_session):
    """POST /api/tasks rejects a `title` containing a null byte with 422."""
    user = make_user(db_session)
    future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()

    response = client.post(
        "/api/tasks",
        json={
            "title": "Task\x00Title",
            "deadline": future_date,
            "assigned_to_id": user.id,
        },
    )

    assert response.status_code == 422


def test_create_task_rejects_null_byte_in_description(client, db_session):
    """POST /api/tasks rejects a `description` containing a null byte with 422."""
    user = make_user(db_session)
    future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()

    response = client.post(
        "/api/tasks",
        json={
            "title": "Normal title",
            "description": "Some\x00Body",
            "deadline": future_date,
            "assigned_to_id": user.id,
        },
    )

    assert response.status_code == 422


def test_update_task_rejects_null_byte_in_title(client, db_session):
    """PUT /api/tasks/{id} rejects a `title` containing a null byte with 422."""
    user = make_user(db_session)
    future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
    created = client.post(
        "/api/tasks",
        json={"title": "Original", "deadline": future_date, "assigned_to_id": user.id},
    )
    task_id = created.json()["id"]

    response = client.put(f"/api/tasks/{task_id}", json={"title": "New\x00Title"})

    assert response.status_code == 422


def test_create_user_accepts_ordinary_name_without_null_bytes(client):
    """Ordinary names are unaffected by the null-byte check."""
    response = client.post(
        "/api/users", json={"name": "Ana Silva", "email": "ana-ok@example.com"}
    )

    assert response.status_code == 201
