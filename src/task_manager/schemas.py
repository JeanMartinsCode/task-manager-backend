"""Pydantic schemas for API request/response validation."""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

try:
    from task_manager.models import NotificationTypeEnum, PriorityEnum, TaskStatusEnum
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from src.task_manager.models import NotificationTypeEnum, PriorityEnum, TaskStatusEnum


class UserCreate(BaseModel):
    """Schema for creating a new user."""

    name: str = Field(..., min_length=1)
    email: str = Field(...)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        """Validate email format using regex."""
        pattern = r"[^@]+@[^@]+\.[^@]+"
        if not isinstance(v, str) or not re.match(pattern, v):
            raise ValueError("invalid email format")
        return v


class UserRead(BaseModel):
    """Schema for returning user data."""

    id: int
    name: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    """Schema for creating a new task."""

    title: str = Field(..., min_length=1, description="Task title")
    description: Optional[str] = Field(None, description="Task description")
    deadline: datetime = Field(..., description="Task deadline (must be in future)")
    priority: PriorityEnum = Field(
        default=PriorityEnum.MEDIUM, description="Task priority level"
    )
    assigned_to_id: int = Field(..., gt=0, description="User ID to assign task to")

    @field_validator("deadline")
    @classmethod
    def _validate_deadline(cls, v: datetime) -> datetime:
        """Validate that deadline is in the future."""
        if v <= datetime.utcnow():
            raise ValueError("deadline must be in the future")
        return v


class TaskUpdate(BaseModel):
    """Schema for updating a task."""

    title: Optional[str] = Field(None, min_length=1, description="Task title")
    description: Optional[str] = Field(None, description="Task description")
    deadline: Optional[datetime] = Field(None, description="Task deadline")
    priority: Optional[PriorityEnum] = Field(None, description="Task priority level")
    status: Optional[TaskStatusEnum] = Field(None, description="Task status")

    @field_validator("deadline")
    @classmethod
    def _validate_deadline(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate that deadline is in the future if provided."""
        if v is not None and v <= datetime.utcnow():
            raise ValueError("deadline must be in the future")
        return v


class TaskRead(BaseModel):
    """Schema for returning task data."""

    id: int
    title: str
    description: Optional[str]
    priority: PriorityEnum
    status: TaskStatusEnum
    deadline: Optional[datetime]
    assigned_to: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedTaskResponse(BaseModel):
    """Schema for returning paginated task results with total count."""

    items: list[TaskRead]
    total: int


class NotificationRead(BaseModel):
    """Schema for returning notification data."""

    id: int
    task_id: int
    notification_type: NotificationTypeEnum
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}

