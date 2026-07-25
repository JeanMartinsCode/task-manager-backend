"""Unit tests for Notification Pydantic schemas (Task 5.1)."""

from datetime import datetime

import pytest
from pydantic import ValidationError

try:
    from task_manager.models import NotificationTypeEnum
    from task_manager.schemas import NotificationRead
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from src.task_manager.models import NotificationTypeEnum
    from src.task_manager.schemas import NotificationRead


class TestNotificationRead:
    """Tests for NotificationRead schema."""

    def test_notification_read_valid(self):
        """NotificationRead accepts valid data."""
        now = datetime.utcnow()
        data = {
            "id": 1,
            "task_id": 10,
            "notification_type": NotificationTypeEnum.ESCALATION,
            "message": "Deadline in ~12h, escalated to HIGH",
            "created_at": now,
        }
        notification = NotificationRead(**data)
        assert notification.id == 1
        assert notification.task_id == 10
        assert notification.notification_type == NotificationTypeEnum.ESCALATION
        assert notification.message == "Deadline in ~12h, escalated to HIGH"
        assert notification.created_at == now

    @pytest.mark.parametrize(
        "notification_type",
        [
            NotificationTypeEnum.ESCALATION,
            NotificationTypeEnum.DEADLINE_APPROACHING,
            NotificationTypeEnum.TASK_ASSIGNED,
            NotificationTypeEnum.TASK_COMPLETED,
        ],
    )
    def test_notification_read_accepts_all_enum_values(self, notification_type):
        """NotificationRead accepts every NotificationTypeEnum value."""
        data = {
            "id": 1,
            "task_id": 10,
            "notification_type": notification_type,
            "message": "msg",
            "created_at": datetime.utcnow(),
        }
        notification = NotificationRead(**data)
        assert notification.notification_type == notification_type

    def test_notification_read_from_attributes(self):
        """NotificationRead can be built from an ORM-like object."""

        class FakeNotification:
            id = 1
            task_id = 10
            notification_type = NotificationTypeEnum.TASK_ASSIGNED
            message = "You were assigned a task"
            created_at = datetime.utcnow()

        notification = NotificationRead.model_validate(FakeNotification())
        assert notification.id == 1
        assert notification.notification_type == NotificationTypeEnum.TASK_ASSIGNED

    def test_notification_read_task_id_required(self):
        """NotificationRead requires task_id."""
        data = {
            "id": 1,
            "notification_type": NotificationTypeEnum.ESCALATION,
            "message": "msg",
            "created_at": datetime.utcnow(),
        }
        with pytest.raises(ValidationError) as exc_info:
            NotificationRead(**data)
        assert "task_id" in str(exc_info.value)

    def test_notification_read_notification_type_required(self):
        """NotificationRead requires notification_type."""
        data = {
            "id": 1,
            "task_id": 10,
            "message": "msg",
            "created_at": datetime.utcnow(),
        }
        with pytest.raises(ValidationError) as exc_info:
            NotificationRead(**data)
        assert "notification_type" in str(exc_info.value)

    def test_notification_read_message_required(self):
        """NotificationRead requires message."""
        data = {
            "id": 1,
            "task_id": 10,
            "notification_type": NotificationTypeEnum.ESCALATION,
            "created_at": datetime.utcnow(),
        }
        with pytest.raises(ValidationError) as exc_info:
            NotificationRead(**data)
        assert "message" in str(exc_info.value)

    def test_notification_read_serialization_types(self):
        """NotificationRead serializes fields to expected types."""
        now = datetime.utcnow()
        notification = NotificationRead(
            id=1,
            task_id=10,
            notification_type=NotificationTypeEnum.ESCALATION,
            message="msg",
            created_at=now,
        )
        dumped = notification.model_dump()
        assert isinstance(dumped["created_at"], datetime)
        assert dumped["notification_type"] == NotificationTypeEnum.ESCALATION
