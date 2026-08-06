"""API endpoints for task management."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session

from task_manager.constants import MAX_SQLITE_INTEGER
from task_manager.database import get_db
from task_manager.models import PriorityEnum, TaskStatusEnum
from task_manager.rate_limit import RATE_LIMIT_WRITE, limiter
from task_manager.schemas import PaginatedTaskResponse, TaskCreate, TaskRead, TaskUpdate
from task_manager.security import require_api_key
from task_manager.services import TaskService

router = APIRouter(
    prefix="/api/tasks", tags=["tasks"], dependencies=[Depends(require_api_key)]
)


@router.post("", status_code=201, response_model=TaskRead)
@limiter.limit(RATE_LIMIT_WRITE)
def create_task(request: Request, task_in: TaskCreate, db: Session = Depends(get_db)):
    """Create a new task. Returns 400 if assigned_to_id does not exist."""
    try:
        task = TaskService.create_task(
            db,
            title=task_in.title,
            description=task_in.description,
            deadline=task_in.deadline,
            priority=task_in.priority,
            assigned_to_id=task_in.assigned_to_id,
        )
        return task
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=PaginatedTaskResponse)
def get_all_tasks(
    skip: int = Query(0, ge=0, le=MAX_SQLITE_INTEGER),
    limit: int = Query(100, ge=1, le=100),
    status: Optional[TaskStatusEnum] = Query(None),
    priority: Optional[PriorityEnum] = Query(None),
    assigned_to_id: Optional[int] = Query(None, ge=1, le=MAX_SQLITE_INTEGER),
    db: Session = Depends(get_db),
):
    """Get all tasks with optional filters and pagination."""
    filters = {}
    if status is not None:
        filters["status"] = status
    if priority is not None:
        filters["priority"] = priority
    if assigned_to_id is not None:
        filters["assigned_to_id"] = assigned_to_id

    tasks = TaskService.get_all_tasks(db, skip=skip, limit=limit, filters=filters or None)
    total = TaskService.count_tasks(db, filters=filters or None)
    return {"items": tasks, "total": total}


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: int = Path(..., ge=1, le=MAX_SQLITE_INTEGER),
    db: Session = Depends(get_db),
):
    """Get a task by ID. Returns 404 if not found."""
    task = TaskService.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=TaskRead)
@limiter.limit(RATE_LIMIT_WRITE)
def update_task(
    request: Request,
    task_update: TaskUpdate,
    task_id: int = Path(..., ge=1, le=MAX_SQLITE_INTEGER),
    db: Session = Depends(get_db),
):
    """Update an existing task. Returns 404 if not found."""
    try:
        return TaskService.update_task(
            db,
            task_id,
            {
                "title": task_update.title,
                "description": task_update.description,
                "deadline": task_update.deadline,
                "priority": task_update.priority,
                "status": task_update.status,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{task_id}", status_code=204)
@limiter.limit(RATE_LIMIT_WRITE)
def delete_task(
    request: Request,
    task_id: int = Path(..., ge=1, le=MAX_SQLITE_INTEGER),
    db: Session = Depends(get_db),
):
    """Delete a task. Returns 404 if not found."""
    try:
        TaskService.delete_task(db, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
