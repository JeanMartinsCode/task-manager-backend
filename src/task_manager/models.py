"""
SQLAlchemy models for Task Management system.

Defines User, Task, and Notification models with relationships.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

try:
    from task_manager.database import Base
except ModuleNotFoundError:  # pragma: no cover - compatibility for Alembic imports
    from src.task_manager.database import Base


class PriorityEnum(str, Enum):
    """Task priority levels."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TaskStatusEnum(str, Enum):
    """Task status values."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class NotificationTypeEnum(str, Enum):
    """Notification type values."""

    DEADLINE_APPROACHING = "DEADLINE_APPROACHING"
    TASK_ASSIGNED = "TASK_ASSIGNED"
    TASK_COMPLETED = "TASK_COMPLETED"
    ESCALATION = "ESCALATION"


class User(Base):
    """User model representing a person in the system."""

    __tablename__ = "users"

    id: int
    name: str
    email: str
    created_at: datetime

    # Columns
    # The plain annotations above give mypy the runtime attribute type;
    # SQLAlchemy's legacy Column() (no Mapped[]) conflicts with them statically.
    id = Column(Integer, primary_key=True, index=True)  # type: ignore[assignment]
    name = Column(String(255), nullable=False)  # type: ignore[assignment]
    email = Column(String(255), nullable=False, unique=True, index=True)  # type: ignore[assignment]
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # type: ignore[assignment]

    # Relationships
    tasks = relationship("Task", back_populates="assigned_user")

    def __repr__(self) -> str:
        """Return a debug-friendly representation."""
        return f"<User(id={self.id}, name={self.name!r}, email={self.email!r})>"


class Task(Base):
    """Task model representing a work item."""

    __tablename__ = "tasks"

    id: int
    title: str
    description: str | None
    priority: PriorityEnum
    status: TaskStatusEnum
    deadline: datetime | None
    assigned_to: int
    created_at: datetime
    updated_at: datetime

    # Columns
    # The plain annotations above give mypy the runtime attribute type;
    # SQLAlchemy's legacy Column() (no Mapped[]) conflicts with them statically.
    id = Column(Integer, primary_key=True, index=True)  # type: ignore[assignment]
    title = Column(String(255), nullable=False)  # type: ignore[assignment]
    description = Column(Text, nullable=True)  # type: ignore[assignment]
    priority = Column(  # type: ignore[assignment]
        SQLEnum(PriorityEnum, native_enum=False),
        default=PriorityEnum.MEDIUM,
        nullable=False,
    )
    status = Column(  # type: ignore[assignment]
        SQLEnum(TaskStatusEnum, native_enum=False),
        default=TaskStatusEnum.PENDING,
        nullable=False,
    )
    deadline = Column(DateTime, nullable=True)  # type: ignore[assignment]
    assigned_to = Column(  # type: ignore[assignment]
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # type: ignore[assignment]
    updated_at = Column(  # type: ignore[assignment]
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    assigned_user = relationship("User", back_populates="tasks")
    notifications = relationship(
        "Notification", back_populates="task", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """Return a debug-friendly representation."""
        return (
            f"<Task(id={self.id}, title={self.title!r}, "
            f"status={self.status}, priority={self.priority})>"
        )


class Notification(Base):
    """Notification model for task-related alerts."""

    __tablename__ = "notifications"

    id: int
    task_id: int
    notification_type: NotificationTypeEnum
    message: str
    created_at: datetime

    # Columns
    # The plain annotations above give mypy the runtime attribute type;
    # SQLAlchemy's legacy Column() (no Mapped[]) conflicts with them statically.
    id = Column(Integer, primary_key=True, index=True)  # type: ignore[assignment]
    task_id = Column(  # type: ignore[assignment]
        Integer, ForeignKey("tasks.id"), nullable=False, index=True
    )
    notification_type = Column(  # type: ignore[assignment]
        SQLEnum(NotificationTypeEnum, native_enum=False),
        nullable=False,
    )
    message = Column(String(512), nullable=False)  # type: ignore[assignment]
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # type: ignore[assignment]

    # Relationships
    task = relationship("Task", back_populates="notifications")

    def __repr__(self) -> str:
        """Return a debug-friendly representation."""
        return (
            f"<Notification(id={self.id}, task_id={self.task_id}, "
            f"type={self.notification_type!r})>"
        )
