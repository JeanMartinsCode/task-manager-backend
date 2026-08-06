"""API endpoint for system status."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from task_manager.database import get_db
from task_manager.models import PriorityEnum, Task, TaskStatusEnum
from task_manager.scheduler import get_last_run_info
from task_manager.security import require_api_key

router = APIRouter(tags=["status"], dependencies=[Depends(require_api_key)])


@router.get("/api/status")
def get_status(db: Session = Depends(get_db)):
    """Return DB connectivity, task counts by status/priority, and the last escalation run.

    Response fields: `db_connected`, `tasks_count`, `tasks_by_status`,
    `tasks_by_priority`, `last_escalation_time` (null if the job never ran),
    and `last_escalation_count`.
    """
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False

    tasks_by_status = {
        task_status.value: db.query(Task).filter(Task.status == task_status).count()
        for task_status in TaskStatusEnum
    }
    tasks_by_priority = {
        priority.value: db.query(Task).filter(Task.priority == priority).count()
        for priority in PriorityEnum
    }

    last_run = get_last_run_info()

    return {
        "db_connected": db_connected,
        "tasks_count": sum(tasks_by_status.values()),
        "tasks_by_status": tasks_by_status,
        "tasks_by_priority": tasks_by_priority,
        "last_escalation_time": last_run["timestamp"],
        "last_escalation_count": last_run["escalated_count"],
    }
