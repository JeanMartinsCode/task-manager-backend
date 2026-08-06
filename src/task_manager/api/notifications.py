"""API endpoints for notifications."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

try:
    from task_manager.constants import MAX_SQLITE_INTEGER
    from task_manager.database import get_db
    from task_manager.schemas import NotificationRead
    from task_manager.security import require_api_key
    from task_manager.services import NotificationService
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from src.task_manager.constants import MAX_SQLITE_INTEGER
    from src.task_manager.database import get_db
    from src.task_manager.schemas import NotificationRead
    from src.task_manager.security import require_api_key
    from src.task_manager.services import NotificationService

router = APIRouter(
    prefix="/api/notifications",
    tags=["notifications"],
    dependencies=[Depends(require_api_key)],
)


@router.get("", response_model=list[NotificationRead])
def get_notifications(
    skip: int = Query(0, ge=0, le=MAX_SQLITE_INTEGER),
    limit: int = Query(100, ge=1, le=100),
    task_id: Optional[int] = Query(None, ge=1, le=MAX_SQLITE_INTEGER),
    user_id: Optional[int] = Query(None, ge=1, le=MAX_SQLITE_INTEGER),
    db: Session = Depends(get_db),
):
    """List notifications, most recent first, optionally filtered.

    If `task_id` is provided, only notifications for that task are returned.
    Otherwise, if `user_id` is provided, notifications for all tasks assigned
    to that user are returned. If neither is provided, all notifications are
    returned. When both are provided, `task_id` takes precedence.
    """
    if task_id is not None:
        return NotificationService.get_notifications_by_task(
            db, task_id, skip=skip, limit=limit
        )
    if user_id is not None:
        return NotificationService.get_notifications_by_user(
            db, user_id, skip=skip, limit=limit
        )
    return NotificationService.get_notifications(db, skip=skip, limit=limit)
