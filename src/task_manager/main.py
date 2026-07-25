"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

try:
    from task_manager.api import notifications_router, status_router, tasks_router, users_router
    from task_manager.scheduler import create_scheduler
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from src.task_manager.api import (
        notifications_router,
        status_router,
        tasks_router,
        users_router,
    )
    from src.task_manager.scheduler import create_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start the escalation scheduler on startup, stop it on shutdown."""
    scheduler = create_scheduler()
    scheduler.start()
    app.state.scheduler = scheduler
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Task Manager Backend",
    description="Task Management System with Automatic Priority Escalation",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(users_router)
app.include_router(tasks_router)
app.include_router(notifications_router)
app.include_router(status_router)


@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """Health check endpoint to verify API is running."""
    return JSONResponse({"status": "healthy"})
