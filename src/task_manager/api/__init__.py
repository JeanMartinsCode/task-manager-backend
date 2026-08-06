"""API module for task manager."""

from task_manager.api.notifications import router as notifications_router
from task_manager.api.status import router as status_router
from task_manager.api.tasks import router as tasks_router
from task_manager.api.users import router as users_router

__all__ = ["users_router", "tasks_router", "notifications_router", "status_router"]
