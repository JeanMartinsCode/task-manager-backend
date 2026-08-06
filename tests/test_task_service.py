"""Unit tests for `TaskService` (Task 3.2)."""

from datetime import datetime, timedelta

import pytest

from task_manager.database import SessionLocal

try:
    from task_manager.models import PriorityEnum, Task, TaskStatusEnum, User
    from task_manager.services import TaskService
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from task_manager.models import PriorityEnum, Task, TaskStatusEnum, User
    from task_manager.services import TaskService


@pytest.fixture
def db_session():
    """Provide a database session for testing."""
    db = SessionLocal()
    try:
        # Clean tables before each test
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
    user = User(name="Test User", email="test@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestTaskServiceCreate:
    """Tests for TaskService.create_task."""

    def test_create_task_valid(self, db_session, test_user):
        """Create a task with valid data."""
        future_date = datetime.utcnow() + timedelta(days=1)
        task = TaskService.create_task(
            db_session,
            title="Fix bug",
            description="Critical bug in auth",
            deadline=future_date,
            priority=PriorityEnum.HIGH,
            assigned_to_id=test_user.id,
        )

        assert task.id is not None
        assert task.title == "Fix bug"
        assert task.description == "Critical bug in auth"
        assert task.priority == PriorityEnum.HIGH
        assert task.status == TaskStatusEnum.PENDING
        assert task.assigned_to == test_user.id

    def test_create_task_defaults_priority_to_medium(self, db_session, test_user):
        """Create task defaults priority to MEDIUM."""
        future_date = datetime.utcnow() + timedelta(days=1)
        task = TaskService.create_task(
            db_session,
            title="Task 1",
            description="Description",
            deadline=future_date,
            assigned_to_id=test_user.id,
        )

        assert task.priority == PriorityEnum.MEDIUM

    def test_create_task_defaults_status_to_pending(self, db_session, test_user):
        """Create task defaults status to PENDING."""
        future_date = datetime.utcnow() + timedelta(days=1)
        task = TaskService.create_task(
            db_session,
            title="Task 1",
            description="Description",
            deadline=future_date,
            assigned_to_id=test_user.id,
        )

        assert task.status == TaskStatusEnum.PENDING

    def test_create_task_invalid_assigned_to_id(self, db_session):
        """Create task raises error for non-existent user."""
        future_date = datetime.utcnow() + timedelta(days=1)
        with pytest.raises(ValueError, match="assigned_to_id"):
            TaskService.create_task(
                db_session,
                title="Task",
                description="Description",
                deadline=future_date,
                assigned_to_id=999,
            )

    def test_create_task_description_optional(self, db_session, test_user):
        """Create task works with description as None."""
        future_date = datetime.utcnow() + timedelta(days=1)
        task = TaskService.create_task(
            db_session,
            title="Task 1",
            deadline=future_date,
            assigned_to_id=test_user.id,
        )

        assert task.description is None


class TestTaskServiceRead:
    """Tests for TaskService.get_task."""

    def test_get_task_by_id(self, db_session, test_user):
        """Retrieve task by ID."""
        future_date = datetime.utcnow() + timedelta(days=1)
        created = TaskService.create_task(
            db_session,
            title="Task 1",
            deadline=future_date,
            assigned_to_id=test_user.id,
        )

        retrieved = TaskService.get_task(db_session, created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == "Task 1"

    def test_get_task_not_found(self, db_session):
        """Get task returns None if not found."""
        result = TaskService.get_task(db_session, 999)
        assert result is None


class TestTaskServiceGetAll:
    """Tests for TaskService.get_all_tasks."""

    def test_get_all_tasks_empty(self, db_session):
        """Get all tasks returns empty list when no tasks."""
        tasks = TaskService.get_all_tasks(db_session)
        assert tasks == []

    def test_get_all_tasks_pagination_skip_limit(self, db_session, test_user):
        """Get all tasks respects skip and limit."""
        future_date = datetime.utcnow() + timedelta(days=1)
        for i in range(5):
            TaskService.create_task(
                db_session,
                title=f"Task {i+1}",
                deadline=future_date,
                assigned_to_id=test_user.id,
            )

        # Get first 2 tasks
        tasks = TaskService.get_all_tasks(db_session, skip=0, limit=2)
        assert len(tasks) == 2

        # Get next 2 tasks
        tasks = TaskService.get_all_tasks(db_session, skip=2, limit=2)
        assert len(tasks) == 2

        # Get remaining 1 task
        tasks = TaskService.get_all_tasks(db_session, skip=4, limit=2)
        assert len(tasks) == 1

    def test_get_all_tasks_filter_by_status(self, db_session, test_user):
        """Get all tasks filtered by status."""
        future_date = datetime.utcnow() + timedelta(days=1)
        task1 = TaskService.create_task(
            db_session,
            title="Task 1",
            deadline=future_date,
            assigned_to_id=test_user.id,
        )
        task2 = TaskService.create_task(
            db_session,
            title="Task 2",
            deadline=future_date,
            assigned_to_id=test_user.id,
        )

        # Update one task to IN_PROGRESS
        TaskService.update_task(
            db_session, task2.id, {"status": TaskStatusEnum.IN_PROGRESS}
        )

        # Filter by PENDING
        pending = TaskService.get_all_tasks(
            db_session, filters={"status": TaskStatusEnum.PENDING}
        )
        assert len(pending) == 1
        assert pending[0].id == task1.id

        # Filter by IN_PROGRESS
        in_progress = TaskService.get_all_tasks(
            db_session, filters={"status": TaskStatusEnum.IN_PROGRESS}
        )
        assert len(in_progress) == 1
        assert in_progress[0].id == task2.id

    def test_get_all_tasks_filter_by_priority(self, db_session, test_user):
        """Get all tasks filtered by priority."""
        future_date = datetime.utcnow() + timedelta(days=1)
        TaskService.create_task(
            db_session,
            title="Task 1",
            deadline=future_date,
            priority=PriorityEnum.HIGH,
            assigned_to_id=test_user.id,
        )
        TaskService.create_task(
            db_session,
            title="Task 2",
            deadline=future_date,
            priority=PriorityEnum.LOW,
            assigned_to_id=test_user.id,
        )

        high_priority = TaskService.get_all_tasks(
            db_session, filters={"priority": PriorityEnum.HIGH}
        )
        assert len(high_priority) == 1
        assert high_priority[0].priority == PriorityEnum.HIGH

    def test_get_all_tasks_filter_by_assigned_to(self, db_session, test_user):
        """Get all tasks filtered by assigned_to_id."""
        user2 = User(name="User 2", email="user2@example.com")
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user2)

        future_date = datetime.utcnow() + timedelta(days=1)
        TaskService.create_task(
            db_session,
            title="Task 1",
            deadline=future_date,
            assigned_to_id=test_user.id,
        )
        TaskService.create_task(
            db_session,
            title="Task 2",
            deadline=future_date,
            assigned_to_id=user2.id,
        )

        assigned_to_user1 = TaskService.get_all_tasks(
            db_session, filters={"assigned_to_id": test_user.id}
        )
        assert len(assigned_to_user1) == 1
        assert assigned_to_user1[0].assigned_to == test_user.id

    def test_get_all_tasks_combine_filters(self, db_session, test_user):
        """Get all tasks with combined filters."""
        future_date = datetime.utcnow() + timedelta(days=1)
        task1 = TaskService.create_task(
            db_session,
            title="Task 1",
            deadline=future_date,
            priority=PriorityEnum.HIGH,
            assigned_to_id=test_user.id,
        )
        TaskService.create_task(
            db_session,
            title="Task 2",
            deadline=future_date,
            priority=PriorityEnum.LOW,
            assigned_to_id=test_user.id,
        )

        # Filter by priority AND status
        filtered = TaskService.get_all_tasks(
            db_session,
            filters={
                "priority": PriorityEnum.HIGH,
                "status": TaskStatusEnum.PENDING,
            },
        )
        assert len(filtered) == 1
        assert filtered[0].id == task1.id


class TestTaskServiceUpdate:
    """Tests for TaskService.update_task."""

    def test_update_task_partial(self, db_session, test_user):
        """Update task with partial fields."""
        future_date = datetime.utcnow() + timedelta(days=1)
        task = TaskService.create_task(
            db_session,
            title="Original Title",
            deadline=future_date,
            priority=PriorityEnum.LOW,
            assigned_to_id=test_user.id,
        )

        # Update only title and priority
        updated = TaskService.update_task(
            db_session,
            task.id,
            {"title": "New Title", "priority": PriorityEnum.HIGH},
        )

        assert updated.title == "New Title"
        assert updated.priority == PriorityEnum.HIGH
        assert updated.status == TaskStatusEnum.PENDING  # unchanged

    def test_update_task_full(self, db_session, test_user):
        """Update task with all fields."""
        future_date = datetime.utcnow() + timedelta(days=1)
        later_date = datetime.utcnow() + timedelta(days=2)
        task = TaskService.create_task(
            db_session,
            title="Task",
            description="Desc",
            deadline=future_date,
            priority=PriorityEnum.LOW,
            assigned_to_id=test_user.id,
        )

        updated = TaskService.update_task(
            db_session,
            task.id,
            {
                "title": "Updated",
                "description": "Updated desc",
                "deadline": later_date,
                "priority": PriorityEnum.HIGH,
                "status": TaskStatusEnum.COMPLETED,
            },
        )

        assert updated.title == "Updated"
        assert updated.description == "Updated desc"
        assert updated.deadline == later_date
        assert updated.priority == PriorityEnum.HIGH
        assert updated.status == TaskStatusEnum.COMPLETED

    def test_update_task_not_found(self, db_session):
        """Update task raises ValueError if task not found."""
        with pytest.raises(ValueError, match="not found"):
            TaskService.update_task(db_session, 999, {"title": "New"})

    def test_update_task_ignores_none_values(self, db_session, test_user):
        """Update task ignores None values (doesn't clear fields)."""
        future_date = datetime.utcnow() + timedelta(days=1)
        task = TaskService.create_task(
            db_session,
            title="Original",
            description="Original description",
            deadline=future_date,
            assigned_to_id=test_user.id,
        )

        # Update with None values for description - should be ignored
        updated = TaskService.update_task(
            db_session,
            task.id,
            {"title": "New", "description": None},
        )

        assert updated.title == "New"
        assert updated.description == "Original description"  # unchanged


class TestTaskServiceDelete:
    """Tests for TaskService.delete_task."""

    def test_delete_task(self, db_session, test_user):
        """Delete a task."""
        future_date = datetime.utcnow() + timedelta(days=1)
        task = TaskService.create_task(
            db_session,
            title="Task",
            deadline=future_date,
            assigned_to_id=test_user.id,
        )
        task_id = task.id

        TaskService.delete_task(db_session, task_id)

        # Verify task is deleted
        result = TaskService.get_task(db_session, task_id)
        assert result is None

    def test_delete_task_not_found(self, db_session):
        """Delete task raises ValueError if task not found."""
        with pytest.raises(ValueError, match="not found"):
            TaskService.delete_task(db_session, 999)

    def test_delete_task_removes_from_db(self, db_session, test_user):
        """Delete task removes from database."""
        future_date = datetime.utcnow() + timedelta(days=1)
        TaskService.create_task(
            db_session,
            title="Task 1",
            deadline=future_date,
            assigned_to_id=test_user.id,
        )
        task2 = TaskService.create_task(
            db_session,
            title="Task 2",
            deadline=future_date,
            assigned_to_id=test_user.id,
        )

        all_tasks = TaskService.get_all_tasks(db_session)
        assert len(all_tasks) == 2

        TaskService.delete_task(db_session, task2.id)

        all_tasks = TaskService.get_all_tasks(db_session)
        assert len(all_tasks) == 1
