"""FastAPI application entry point."""

import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

try:
    from task_manager.api import notifications_router, status_router, tasks_router, users_router
    from task_manager.rate_limit import limiter
    from task_manager.scheduler import create_scheduler
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from src.task_manager.api import (
        notifications_router,
        status_router,
        tasks_router,
        users_router,
    )
    from src.task_manager.rate_limit import limiter
    from src.task_manager.scheduler import create_scheduler

logger = logging.getLogger("task_manager")


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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(SlowAPIMiddleware)

app.include_router(users_router)
app.include_router(tasks_router)
app.include_router(notifications_router)
app.include_router(status_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for anything a route/service didn't anticipate.

    FastAPI's own handlers for `HTTPException` and `RequestValidationError`
    are more specific and take precedence over this one, so normal 400/404/
    422 responses are unaffected. This only fires for genuine bugs (e.g. an
    `OverflowError` slipping past validation) — the client gets a generic
    message plus a correlation id, never a stack trace or internal detail;
    the full exception is logged server-side under that same id.
    """
    error_id = uuid.uuid4().hex
    logger.exception("Unhandled exception (error_id=%s)", error_id)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error_id": error_id},
    )


@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """Health check endpoint to verify API is running."""
    return JSONResponse({"status": "healthy"})
