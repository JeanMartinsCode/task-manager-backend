"""Unit tests for Task Pydantic schemas (Task 3.1)."""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from task_manager.models import PriorityEnum, TaskStatusEnum
from task_manager.schemas import TaskCreate, TaskRead, TaskUpdate


class TestTaskCreate:
    """Tests for TaskCreate schema."""

    def test_task_create_valid(self):
        """TaskCreate accepts valid data."""
        future_date = datetime.utcnow() + timedelta(days=1)
        data = {
            "title": "Fix bug",
            "description": "Fix critical bug in auth",
            "deadline": future_date,
            "priority": PriorityEnum.HIGH,
            "assigned_to_id": 1,
        }
        task = TaskCreate(**data)
        assert task.title == "Fix bug"
        assert task.description == "Fix critical bug in auth"
        assert task.assigned_to_id == 1

    def test_task_create_title_required(self):
        """TaskCreate requires title."""
        future_date = datetime.utcnow() + timedelta(days=1)
        data = {
            "description": "Fix bug",
            "deadline": future_date,
            "priority": PriorityEnum.HIGH,
            "assigned_to_id": 1,
        }
        with pytest.raises(ValidationError) as exc_info:
            TaskCreate(**data)
        assert "title" in str(exc_info.value)

    def test_task_create_title_min_length(self):
        """TaskCreate validates title minimum length."""
        future_date = datetime.utcnow() + timedelta(days=1)
        data = {
            "title": "",
            "deadline": future_date,
            "priority": PriorityEnum.HIGH,
            "assigned_to_id": 1,
        }
        with pytest.raises(ValidationError):
            TaskCreate(**data)

    def test_task_create_deadline_required(self):
        """TaskCreate requires deadline."""
        data = {
            "title": "Fix bug",
            "priority": PriorityEnum.HIGH,
            "assigned_to_id": 1,
        }
        with pytest.raises(ValidationError) as exc_info:
            TaskCreate(**data)
        assert "deadline" in str(exc_info.value)

    def test_task_create_deadline_must_be_future(self):
        """TaskCreate validates deadline is in future."""
        past_date = datetime.utcnow() - timedelta(days=1)
        data = {
            "title": "Fix bug",
            "deadline": past_date,
            "priority": PriorityEnum.HIGH,
            "assigned_to_id": 1,
        }
        with pytest.raises(ValidationError) as exc_info:
            TaskCreate(**data)
        assert "deadline" in str(exc_info.value).lower()

    def test_task_create_assigned_to_id_required(self):
        """TaskCreate requires assigned_to_id."""
        future_date = datetime.utcnow() + timedelta(days=1)
        data = {
            "title": "Fix bug",
            "deadline": future_date,
            "priority": PriorityEnum.HIGH,
        }
        with pytest.raises(ValidationError) as exc_info:
            TaskCreate(**data)
        assert "assigned_to_id" in str(exc_info.value)

    def test_task_create_assigned_to_id_must_be_positive(self):
        """TaskCreate validates assigned_to_id is positive."""
        future_date = datetime.utcnow() + timedelta(days=1)
        data = {
            "title": "Fix bug",
            "deadline": future_date,
            "priority": PriorityEnum.HIGH,
            "assigned_to_id": 0,
        }
        with pytest.raises(ValidationError):
            TaskCreate(**data)

    def test_task_create_priority_defaults_to_medium(self):
        """TaskCreate defaults priority to MEDIUM."""
        future_date = datetime.utcnow() + timedelta(days=1)
        data = {
            "title": "Fix bug",
            "deadline": future_date,
            "assigned_to_id": 1,
        }
        task = TaskCreate(**data)
        assert task.priority == PriorityEnum.MEDIUM

    def test_task_create_priority_accepts_all_enums(self):
        """TaskCreate accepts all priority enum values."""
        future_date = datetime.utcnow() + timedelta(days=1)
        for priority in [PriorityEnum.HIGH, PriorityEnum.MEDIUM, PriorityEnum.LOW]:
            data = {
                "title": "Fix bug",
                "deadline": future_date,
                "priority": priority,
                "assigned_to_id": 1,
            }
            task = TaskCreate(**data)
            assert task.priority == priority

    def test_task_create_description_optional(self):
        """TaskCreate allows description to be optional."""
        future_date = datetime.utcnow() + timedelta(days=1)
        data = {
            "title": "Fix bug",
            "deadline": future_date,
            "priority": PriorityEnum.HIGH,
            "assigned_to_id": 1,
        }
        task = TaskCreate(**data)
        assert task.description is None


class TestTaskUpdate:
    """Tests for TaskUpdate schema."""

    def test_task_update_all_fields_optional(self):
        """TaskUpdate accepts empty data (all fields optional)."""
        update = TaskUpdate()
        assert update.title is None
        assert update.description is None
        assert update.deadline is None
        assert update.priority is None
        assert update.status is None

    def test_task_update_partial_update(self):
        """TaskUpdate allows partial updates."""
        data = {"title": "New title", "priority": PriorityEnum.HIGH}
        update = TaskUpdate(**data)
        assert update.title == "New title"
        assert update.priority == PriorityEnum.HIGH
        assert update.status is None
        assert update.deadline is None

    def test_task_update_title_min_length(self):
        """TaskUpdate validates title minimum length if provided."""
        data = {"title": ""}
        with pytest.raises(ValidationError):
            TaskUpdate(**data)

    def test_task_update_deadline_must_be_future(self):
        """TaskUpdate validates deadline is in future if provided."""
        past_date = datetime.utcnow() - timedelta(days=1)
        data = {"deadline": past_date}
        with pytest.raises(ValidationError) as exc_info:
            TaskUpdate(**data)
        assert "deadline" in str(exc_info.value).lower()

    def test_task_update_deadline_future_accepted(self):
        """TaskUpdate accepts future deadline."""
        future_date = datetime.utcnow() + timedelta(days=1)
        data = {"deadline": future_date}
        update = TaskUpdate(**data)
        assert update.deadline == future_date

    def test_task_update_status_accepts_all_enums(self):
        """TaskUpdate accepts all status enum values."""
        for status in [
            TaskStatusEnum.PENDING,
            TaskStatusEnum.IN_PROGRESS,
            TaskStatusEnum.COMPLETED,
        ]:
            data = {"status": status}
            update = TaskUpdate(**data)
            assert update.status == status

    def test_task_update_priority_accepts_all_enums(self):
        """TaskUpdate accepts all priority enum values."""
        for priority in [
            PriorityEnum.HIGH,
            PriorityEnum.MEDIUM,
            PriorityEnum.LOW,
        ]:
            data = {"priority": priority}
            update = TaskUpdate(**data)
            assert update.priority == priority


class TestTaskRead:
    """Tests for TaskRead schema."""

    def test_task_read_instantiation(self):
        """TaskRead accepts required fields."""
        future_date = datetime.utcnow() + timedelta(days=1)
        data = {
            "id": 1,
            "title": "Fix bug",
            "description": "Critical bug",
            "priority": PriorityEnum.HIGH,
            "status": TaskStatusEnum.IN_PROGRESS,
            "deadline": future_date,
            "assigned_to": 5,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        task = TaskRead(**data)
        assert task.id == 1
        assert task.title == "Fix bug"
        assert task.assigned_to == 5

    def test_task_read_all_fields_present(self):
        """TaskRead schema includes all required fields."""
        now = datetime.utcnow()
        data = {
            "id": 1,
            "title": "Task 1",
            "description": "Description",
            "priority": PriorityEnum.MEDIUM,
            "status": TaskStatusEnum.PENDING,
            "deadline": now + timedelta(days=1),
            "assigned_to": 1,
            "created_at": now,
            "updated_at": now,
        }
        task = TaskRead(**data)
        assert hasattr(task, "id")
        assert hasattr(task, "title")
        assert hasattr(task, "description")
        assert hasattr(task, "priority")
        assert hasattr(task, "status")
        assert hasattr(task, "deadline")
        assert hasattr(task, "assigned_to")
        assert hasattr(task, "created_at")
        assert hasattr(task, "updated_at")

    def test_task_read_description_optional(self):
        """TaskRead allows description to be None."""
        now = datetime.utcnow()
        data = {
            "id": 1,
            "title": "Task 1",
            "description": None,
            "priority": PriorityEnum.MEDIUM,
            "status": TaskStatusEnum.PENDING,
            "deadline": now + timedelta(days=1),
            "assigned_to": 1,
            "created_at": now,
            "updated_at": now,
        }
        task = TaskRead(**data)
        assert task.description is None

    def test_task_read_deadline_optional(self):
        """TaskRead allows deadline to be None."""
        now = datetime.utcnow()
        data = {
            "id": 1,
            "title": "Task 1",
            "description": "Description",
            "priority": PriorityEnum.MEDIUM,
            "status": TaskStatusEnum.PENDING,
            "deadline": None,
            "assigned_to": 1,
            "created_at": now,
            "updated_at": now,
        }
        task = TaskRead(**data)
        assert task.deadline is None

    def test_task_read_serialization_types(self):
        """TaskRead fields have correct types."""
        now = datetime.utcnow()
        data = {
            "id": 1,
            "title": "Task 1",
            "description": "Description",
            "priority": PriorityEnum.HIGH,
            "status": TaskStatusEnum.COMPLETED,
            "deadline": now + timedelta(days=1),
            "assigned_to": 42,
            "created_at": now,
            "updated_at": now,
        }
        task = TaskRead(**data)
        assert isinstance(task.id, int)
        assert isinstance(task.title, str)
        assert isinstance(task.priority, PriorityEnum)
        assert isinstance(task.status, TaskStatusEnum)
        assert isinstance(task.assigned_to, int)
        assert isinstance(task.created_at, datetime)
        assert isinstance(task.updated_at, datetime)
