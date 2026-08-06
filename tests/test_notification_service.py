"""Unit tests for `NotificationService` (Task 5.2)."""

from datetime import datetime, timedelta

import pytest

from task_manager.database import SessionLocal
from task_manager.models import (
    Notification,
    NotificationTypeEnum,
    PriorityEnum,
    Task,
    TaskStatusEnum,
    User,
)
from task_manager.services import NotificationService


@pytest.fixture
def db_session():
    """Provide a database session for testing."""
    db = SessionLocal()
    try:
        # Clean tables before each test (respect FK order)
        db.query(Notification).delete()
        db.query(Task).delete()
        db.query(User).delete()
        db.commit()
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def two_users(db_session):
    """Create two users to distinguish task ownership in tests."""
    user_a = User(name="User A", email="notif-user-a@example.com")
    user_b = User(name="User B", email="notif-user-b@example.com")
    db_session.add_all([user_a, user_b])
    db_session.commit()
    db_session.refresh(user_a)
    db_session.refresh(user_b)
    return user_a, user_b


def make_task(db_session, user):
    """Create a task assigned to the given user."""
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


def make_notification(
    db_session, task, *, created_at, notification_type=NotificationTypeEnum.ESCALATION
):
    """Create a notification tied to the given task with an explicit timestamp."""
    notification = Notification(
        task_id=task.id,
        notification_type=notification_type,
        message="msg",
        created_at=created_at,
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)
    return notification


class TestGetNotifications:
    """Tests for NotificationService.get_notifications."""

    def test_returns_most_recent_first(self, db_session, two_users):
        user_a, _ = two_users
        task = make_task(db_session, user_a)
        base = datetime.utcnow()
        older = make_notification(db_session, task, created_at=base - timedelta(hours=2))
        newer = make_notification(db_session, task, created_at=base)

        results = NotificationService.get_notifications(db_session)

        assert [n.id for n in results] == [newer.id, older.id]

    def test_pagination_skip_and_limit(self, db_session, two_users):
        user_a, _ = two_users
        task = make_task(db_session, user_a)
        base = datetime.utcnow()
        notifications = [
            make_notification(db_session, task, created_at=base - timedelta(minutes=i))
            for i in range(5)
        ]

        page = NotificationService.get_notifications(db_session, skip=1, limit=2)

        assert [n.id for n in page] == [notifications[1].id, notifications[2].id]


class TestGetNotificationsByTask:
    """Tests for NotificationService.get_notifications_by_task."""

    def test_returns_only_notifications_for_the_given_task(self, db_session, two_users):
        user_a, _ = two_users
        task_1 = make_task(db_session, user_a)
        task_2 = make_task(db_session, user_a)
        make_notification(db_session, task_2, created_at=datetime.utcnow())
        expected = make_notification(db_session, task_1, created_at=datetime.utcnow())

        results = NotificationService.get_notifications_by_task(db_session, task_1.id)

        assert [n.id for n in results] == [expected.id]

    def test_returns_empty_list_for_task_without_notifications(self, db_session, two_users):
        user_a, _ = two_users
        task = make_task(db_session, user_a)

        results = NotificationService.get_notifications_by_task(db_session, task.id)

        assert results == []


class TestGetNotificationsByUser:
    """Tests for NotificationService.get_notifications_by_user."""

    def test_returns_notifications_across_all_tasks_assigned_to_user(
        self, db_session, two_users
    ):
        user_a, _ = two_users
        task_1 = make_task(db_session, user_a)
        task_2 = make_task(db_session, user_a)
        base = datetime.utcnow()
        notif_1 = make_notification(db_session, task_1, created_at=base - timedelta(minutes=1))
        notif_2 = make_notification(db_session, task_2, created_at=base)

        results = NotificationService.get_notifications_by_user(db_session, user_a.id)

        assert {n.id for n in results} == {notif_1.id, notif_2.id}

    def test_excludes_notifications_from_other_users_tasks(self, db_session, two_users):
        user_a, user_b = two_users
        task_a = make_task(db_session, user_a)
        task_b = make_task(db_session, user_b)
        make_notification(db_session, task_b, created_at=datetime.utcnow())
        expected = make_notification(db_session, task_a, created_at=datetime.utcnow())

        results = NotificationService.get_notifications_by_user(db_session, user_a.id)

        assert [n.id for n in results] == [expected.id]
