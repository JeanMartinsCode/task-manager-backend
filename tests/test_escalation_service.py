"""Unit tests for `EscalationService` (Task 4.1)."""

from datetime import datetime, timedelta

import pytest

from src.task_manager.database import SessionLocal

try:
    from task_manager.models import (
        Notification,
        NotificationTypeEnum,
        PriorityEnum,
        Task,
        TaskStatusEnum,
        User,
    )
    from task_manager.services import EscalationService
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from src.task_manager.models import (
        Notification,
        NotificationTypeEnum,
        PriorityEnum,
        Task,
        TaskStatusEnum,
        User,
    )
    from src.task_manager.services import EscalationService


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
def test_user(db_session):
    """Create a test user for task assignments."""
    user = User(name="Test User", email="escalation@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def make_task(
    db_session,
    test_user,
    *,
    hours_to_deadline,
    priority,
    status=TaskStatusEnum.PENDING,
    has_deadline=True,
):
    """Create a task with a deadline offset (in hours) from now."""
    task = Task(
        title="Task",
        description="desc",
        deadline=(datetime.utcnow() + timedelta(hours=hours_to_deadline)) if has_deadline else None,
        priority=priority,
        status=status,
        assigned_to=test_user.id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


class TestEscalateUrgentTasks:
    """Tests for EscalationService.escalate_urgent_tasks."""

    def test_escalates_task_within_24h_and_not_high(self, db_session, test_user):
        task = make_task(db_session, test_user, hours_to_deadline=12, priority=PriorityEnum.MEDIUM)

        escalated = EscalationService.escalate_urgent_tasks(db_session)

        db_session.refresh(task)
        assert task.priority == PriorityEnum.HIGH
        assert escalated == 1

    def test_escalates_overdue_task(self, db_session, test_user):
        task = make_task(db_session, test_user, hours_to_deadline=-5, priority=PriorityEnum.LOW)

        EscalationService.escalate_urgent_tasks(db_session)

        db_session.refresh(task)
        assert task.priority == PriorityEnum.HIGH

    def test_does_not_escalate_task_beyond_24h(self, db_session, test_user):
        task = make_task(db_session, test_user, hours_to_deadline=48, priority=PriorityEnum.LOW)

        EscalationService.escalate_urgent_tasks(db_session)

        db_session.refresh(task)
        assert task.priority == PriorityEnum.LOW

    def test_does_not_escalate_task_without_deadline(self, db_session, test_user):
        task = make_task(
            db_session,
            test_user,
            hours_to_deadline=0,
            priority=PriorityEnum.LOW,
            has_deadline=False,
        )

        EscalationService.escalate_urgent_tasks(db_session)

        db_session.refresh(task)
        assert task.priority == PriorityEnum.LOW

    def test_does_not_escalate_completed_task(self, db_session, test_user):
        task = make_task(
            db_session,
            test_user,
            hours_to_deadline=1,
            priority=PriorityEnum.LOW,
            status=TaskStatusEnum.COMPLETED,
        )

        EscalationService.escalate_urgent_tasks(db_session)

        db_session.refresh(task)
        assert task.priority == PriorityEnum.LOW

    def test_does_not_reescalate_already_high_priority_task(self, db_session, test_user):
        make_task(db_session, test_user, hours_to_deadline=1, priority=PriorityEnum.HIGH)

        escalated = EscalationService.escalate_urgent_tasks(db_session)

        assert escalated == 0

    def test_creates_notification_on_escalation(self, db_session, test_user):
        task = make_task(db_session, test_user, hours_to_deadline=6, priority=PriorityEnum.LOW)

        EscalationService.escalate_urgent_tasks(db_session)

        notifications = (
            db_session.query(Notification).filter(Notification.task_id == task.id).all()
        )
        assert len(notifications) == 1
        assert notifications[0].notification_type == NotificationTypeEnum.ESCALATION
        assert "HIGH" in notifications[0].message

    def test_idempotent_on_repeated_runs(self, db_session, test_user):
        task = make_task(db_session, test_user, hours_to_deadline=10, priority=PriorityEnum.MEDIUM)

        first_run_count = EscalationService.escalate_urgent_tasks(db_session)
        second_run_count = EscalationService.escalate_urgent_tasks(db_session)

        notifications = (
            db_session.query(Notification).filter(Notification.task_id == task.id).all()
        )
        assert first_run_count == 1
        assert second_run_count == 0
        assert len(notifications) == 1

    def test_escalates_multiple_eligible_tasks_independently(self, db_session, test_user):
        eligible = make_task(db_session, test_user, hours_to_deadline=2, priority=PriorityEnum.LOW)
        not_eligible = make_task(
            db_session, test_user, hours_to_deadline=100, priority=PriorityEnum.LOW
        )

        escalated = EscalationService.escalate_urgent_tasks(db_session)

        db_session.refresh(eligible)
        db_session.refresh(not_eligible)
        assert escalated == 1
        assert eligible.priority == PriorityEnum.HIGH
        assert not_eligible.priority == PriorityEnum.LOW
