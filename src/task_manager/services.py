"""Service layer for user-related and task-related operations."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from task_manager.models import (
    Notification,
    NotificationTypeEnum,
    PriorityEnum,
    Task,
    TaskStatusEnum,
    User,
)


class UserService:
    """Simple service for creating and querying users."""

    @staticmethod
    def create_user(db: Session, name: str, email: str) -> User:
        """Create a new user. Raises ValueError if email already exists."""
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise ValueError("email already exists")

        user = User(name=name, email=email)
        db.add(user)
        try:
            db.commit()
        except IntegrityError as exc:
            # The check above is not atomic with the insert: under
            # concurrent requests for the same email, more than one can
            # pass the check before either commits. The database's real
            # unique constraint is the actual source of truth here, and
            # correctly rejects every insert after the first -- convert
            # that into the same error the non-concurrent path raises,
            # instead of letting it fall through to a 500.
            db.rollback()
            raise ValueError("email already exists") from exc
        db.refresh(user)
        return user

    @staticmethod
    def get_user(db: Session, user_id: int) -> Optional[User]:
        """Retrieve a user by id or return None if not found."""
        return db.get(User, user_id)

    @staticmethod
    def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
        """Return a list of users with pagination."""
        return db.query(User).offset(skip).limit(limit).all()  # type: ignore[no-any-return]


class TaskService:
    """Service for task CRUD operations with filtering and pagination."""

    @staticmethod
    def create_task(
        db: Session,
        title: str,
        deadline: datetime,
        assigned_to_id: int,
        description: Optional[str] = None,
        priority: PriorityEnum = PriorityEnum.MEDIUM,
    ) -> Task:
        """Create a new task. Raises ValueError if assigned_to_id is invalid."""
        user = db.get(User, assigned_to_id)
        if not user:
            raise ValueError(f"assigned_to_id {assigned_to_id} does not exist")

        task = Task(
            title=title,
            description=description,
            deadline=deadline,
            priority=priority,
            status=TaskStatusEnum.PENDING,
            assigned_to=assigned_to_id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    def get_task(db: Session, task_id: int) -> Optional[Task]:
        """Retrieve a task by id or return None if not found."""
        return db.get(Task, task_id)

    @staticmethod
    def get_all_tasks(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Task]:
        """Return a list of tasks with pagination and optional filters.

        Filters can include:
        - status: TaskStatusEnum
        - priority: PriorityEnum
        - assigned_to_id: int
        """
        query = db.query(Task).order_by(Task.id)

        if filters:
            if "status" in filters:
                query = query.filter(Task.status == filters["status"])
            if "priority" in filters:
                query = query.filter(Task.priority == filters["priority"])
            if "assigned_to_id" in filters:
                query = query.filter(Task.assigned_to == filters["assigned_to_id"])

        return query.offset(skip).limit(limit).all()  # type: ignore[no-any-return]

    @staticmethod
    def count_tasks(
        db: Session,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Return the total number of tasks matching the provided filters."""
        query = db.query(Task)

        if filters:
            if "status" in filters:
                query = query.filter(Task.status == filters["status"])
            if "priority" in filters:
                query = query.filter(Task.priority == filters["priority"])
            if "assigned_to_id" in filters:
                query = query.filter(Task.assigned_to == filters["assigned_to_id"])

        return query.count()  # type: ignore[no-any-return]

    @staticmethod
    def update_task(
        db: Session, task_id: int, updates: Dict[str, Any]
    ) -> Task:
        """Update a task with provided fields. Raises ValueError if task not found.

        Only provided fields are updated. None values are ignored to avoid clearing fields.
        """
        task = db.get(Task, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        for key, value in updates.items():
            if value is not None and hasattr(task, key):
                setattr(task, key, value)

        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    def delete_task(db: Session, task_id: int) -> None:
        """Delete a task. Raises ValueError if task not found."""
        task = db.get(Task, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        db.delete(task)
        db.commit()


class EscalationService:
    """Service that auto-escalates task priority as deadlines approach."""

    ESCALATION_WINDOW_HOURS = 24

    @staticmethod
    def escalate_urgent_tasks(db: Session) -> int:
        """Escalate incomplete tasks with a deadline within 24h to HIGH priority.

        For each task that is not COMPLETED, has a deadline set, that deadline
        is within ESCALATION_WINDOW_HOURS from now, and priority is not
        already HIGH: set priority to HIGH and record an ESCALATION
        notification. Tasks already at HIGH priority are excluded, so
        repeated calls do not re-escalate or create duplicate notifications.

        Returns the number of tasks escalated in this run.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        threshold = now + timedelta(hours=EscalationService.ESCALATION_WINDOW_HOURS)

        candidates = (
            db.query(Task)
            .filter(Task.status != TaskStatusEnum.COMPLETED)
            .filter(Task.priority != PriorityEnum.HIGH)
            .filter(Task.deadline.isnot(None))
            .filter(Task.deadline <= threshold)
            .all()
        )

        for task in candidates:
            hours_remaining = max((task.deadline - now).total_seconds() / 3600, 0)
            task.priority = PriorityEnum.HIGH
            db.add(
                Notification(
                    task_id=task.id,
                    notification_type=NotificationTypeEnum.ESCALATION,
                    message=f"Deadline in ~{hours_remaining:.0f}h, escalated to HIGH",
                )
            )

        db.commit()
        return len(candidates)


class NotificationService:
    """Service for querying notifications with pagination."""

    @staticmethod
    def get_notifications(db: Session, skip: int = 0, limit: int = 100) -> List[Notification]:
        """Return the most recent notifications, paginated."""
        return (  # type: ignore[no-any-return]
            db.query(Notification)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_notifications_by_task(
        db: Session, task_id: int, skip: int = 0, limit: int = 100
    ) -> List[Notification]:
        """Return notifications for a specific task, most recent first."""
        return (  # type: ignore[no-any-return]
            db.query(Notification)
            .filter(Notification.task_id == task_id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_notifications_by_user(
        db: Session, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[Notification]:
        """Return notifications for all tasks assigned to a user, most recent first."""
        return (  # type: ignore[no-any-return]
            db.query(Notification)
            .join(Task, Notification.task_id == Task.id)
            .filter(Task.assigned_to == user_id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
