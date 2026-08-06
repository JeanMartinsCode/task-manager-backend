"""Integration tests for scheduler startup/shutdown wiring (Task 4.2)."""

from fastapi.testclient import TestClient

try:
    from task_manager.main import app
    from task_manager.scheduler import ESCALATION_JOB_ID
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from task_manager.main import app
    from task_manager.scheduler import ESCALATION_JOB_ID


def test_scheduler_starts_and_stops_with_app_lifespan():
    """The scheduler should run only while the app's lifespan is active."""
    with TestClient(app):
        scheduler = app.state.scheduler
        assert scheduler.running is True
        assert scheduler.get_job(ESCALATION_JOB_ID) is not None

    assert scheduler.running is False
