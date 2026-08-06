"""Integration tests for User API endpoints (Task 2.3)."""

import pytest

from task_manager.database import Base, SessionLocal, engine
from task_manager.models import User


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Setup and teardown database for each test."""
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


def test_create_user(client):
    """POST /api/users creates a new user and returns 201."""
    payload = {"name": "John Doe", "email": "john@example.com"}
    response = client.post("/api/users", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "John Doe"
    assert data["email"] == "john@example.com"
    assert "id" in data
    assert "created_at" in data


def test_create_user_duplicate_email_returns_400(client, db_session):
    """POST /api/users returns 400 for duplicate email."""
    # Create first user in database
    user1 = User(name="John", email="john@example.com")
    db_session.add(user1)
    db_session.commit()

    # Try to create second user with same email
    payload = {"name": "Jane", "email": "john@example.com"}
    response = client.post("/api/users", json=payload)

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_get_user(client, db_session):
    """GET /api/users/{user_id} returns 200 with user data."""
    user = User(name="John Doe", email="john@example.com")
    db_session.add(user)
    db_session.commit()
    user_id = user.id

    response = client.get(f"/api/users/{user_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["name"] == "John Doe"
    assert data["email"] == "john@example.com"


def test_get_user_not_found(client):
    """GET /api/users/{user_id} returns 404 if user doesn't exist."""
    response = client.get("/api/users/999")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_all_users(client, db_session):
    """GET /api/users returns 200 with list of users."""
    users_data = [
        User(name="User 1", email="user1@example.com"),
        User(name="User 2", email="user2@example.com"),
        User(name="User 3", email="user3@example.com"),
    ]
    for user in users_data:
        db_session.add(user)
    db_session.commit()

    response = client.get("/api/users")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["name"] == "User 1"
    assert data[1]["name"] == "User 2"
    assert data[2]["name"] == "User 3"


def test_get_all_users_with_pagination(client, db_session):
    """GET /api/users with skip/limit returns paginated results."""
    for i in range(5):
        user = User(name=f"User {i+1}", email=f"user{i+1}@example.com")
        db_session.add(user)
    db_session.commit()

    response = client.get("/api/users?skip=1&limit=2")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "User 2"
    assert data[1]["name"] == "User 3"
