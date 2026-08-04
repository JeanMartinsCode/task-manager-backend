"""Pydantic schemas for API request/response validation."""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

try:
    from task_manager.constants import MAX_SQLITE_INTEGER
    from task_manager.models import NotificationTypeEnum, PriorityEnum, TaskStatusEnum
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from src.task_manager.constants import MAX_SQLITE_INTEGER
    from src.task_manager.models import NotificationTypeEnum, PriorityEnum, TaskStatusEnum

# Upper bounds on free-text fields, to close a payload-amplification DoS
# (a client could otherwise send e.g. a 500KB `name` and it would be
# accepted and persisted as-is). Chosen generously above any realistic
# legitimate value, with headroom under the matching DB column:
NAME_MAX_LENGTH = 200  # models.User.name is String(255); no real name is close to 200 chars
EMAIL_MAX_LENGTH = 254  # RFC 5321's practical maximum mailbox length
TITLE_MAX_LENGTH = 200  # models.Task.title is String(255); a title is a label, not a document
DESCRIPTION_MAX_LENGTH = 2000  # ~300-400 words: room for real detail, bounded worst case


def _reject_null_bytes(v: Optional[str]) -> Optional[str]:
    """Reject NUL bytes in free-text input.

    Not exploitable through this API today, but SQLite happily stores
    `\\x00` mid-string, which is a landmine for anything downstream that
    treats the value as a C-string (silent truncation) or writes it to
    logs/CSV exports (corruption, parsing failures).
    """
    if v is not None and "\x00" in v:
        raise ValueError("must not contain null bytes")
    return v


class UserCreate(BaseModel):
    """Schema for creating a new user."""

    name: str = Field(..., min_length=1, max_length=NAME_MAX_LENGTH)
    email: str = Field(..., max_length=EMAIL_MAX_LENGTH)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        """Reject null bytes in name."""
        _reject_null_bytes(v)
        return v

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        """Validate email format using regex and reject null bytes."""
        _reject_null_bytes(v)
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

    title: str = Field(..., min_length=1, max_length=TITLE_MAX_LENGTH, description="Task title")
    description: Optional[str] = Field(
        None, max_length=DESCRIPTION_MAX_LENGTH, description="Task description"
    )
    deadline: datetime = Field(..., description="Task deadline (must be in future)")
    priority: PriorityEnum = Field(
        default=PriorityEnum.MEDIUM, description="Task priority level"
    )
    assigned_to_id: int = Field(
        ..., gt=0, le=MAX_SQLITE_INTEGER, description="User ID to assign task to"
    )

    @field_validator("title", "description")
    @classmethod
    def _validate_no_null_bytes(cls, v: Optional[str]) -> Optional[str]:
        """Reject null bytes in title/description."""
        return _reject_null_bytes(v)

    @field_validator("deadline")
    @classmethod
    def _validate_deadline(cls, v: datetime) -> datetime:
        """Validate that deadline is in the future."""
        if v <= datetime.utcnow():
            raise ValueError("deadline must be in the future")
        return v


class TaskUpdate(BaseModel):
    """Schema for updating a task."""

    title: Optional[str] = Field(
        None, min_length=1, max_length=TITLE_MAX_LENGTH, description="Task title"
    )
    description: Optional[str] = Field(
        None, max_length=DESCRIPTION_MAX_LENGTH, description="Task description"
    )
    deadline: Optional[datetime] = Field(None, description="Task deadline")
    priority: Optional[PriorityEnum] = Field(None, description="Task priority level")
    status: Optional[TaskStatusEnum] = Field(None, description="Task status")

    @field_validator("title", "description")
    @classmethod
    def _validate_no_null_bytes(cls, v: Optional[str]) -> Optional[str]:
        """Reject null bytes in title/description."""
        return _reject_null_bytes(v)

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

