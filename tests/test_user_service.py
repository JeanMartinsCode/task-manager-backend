"""Unit tests for `UserService` (Task 2.2)."""

import pytest

from task_manager.database import SessionLocal
from task_manager.models import User
from task_manager.services import UserService


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        # clean users table before each test
        db.query(User).delete()
        db.commit()
        yield db
    finally:
        db.rollback()
        db.close()


def test_create_and_get_user(db_session):
    svc = UserService()
    user = svc.create_user(db_session, name="Alice", email="alice@example.com")

    assert user.id is not None
    assert user.name == "Alice"

    fetched = svc.get_user(db_session, user.id)
    assert fetched is not None
    assert fetched.email == "alice@example.com"


def test_create_user_duplicate_email_raises(db_session):
    svc = UserService()
    svc.create_user(db_session, name="Bob", email="bob@example.com")

    with pytest.raises(ValueError):
        svc.create_user(db_session, name="Bobby", email="bob@example.com")


def test_get_all_users_pagination(db_session):
    svc = UserService()
    # create 3 users
    svc.create_user(db_session, name="U1", email="u1@example.com")
    svc.create_user(db_session, name="U2", email="u2@example.com")
    svc.create_user(db_session, name="U3", email="u3@example.com")

    all_users = svc.get_all_users(db_session, skip=0, limit=10)
    assert len(all_users) >= 3

    first_two = svc.get_all_users(db_session, skip=0, limit=2)
    assert len(first_two) == 2
