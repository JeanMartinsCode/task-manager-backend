"""Unit tests for scheduler job wiring (Tasks 4.2, 4.3, and 6.1)."""

import json
import logging
from datetime import datetime, timedelta

import pytest
from apscheduler.triggers.interval import IntervalTrigger

from src.task_manager.database import SessionLocal

try:
    from task_manager import scheduler as scheduler_module
    from task_manager.models import Notification, PriorityEnum, Task, TaskStatusEnum, User
    from task_manager.scheduler import (
        ESCALATION_JOB_ID,
        create_scheduler,
        get_last_run_info,
        run_escalation_job,
    )
    from task_manager.services import EscalationService
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from src.task_manager import scheduler as scheduler_module
    from src.task_manager.models import Notification, PriorityEnum, Task, TaskStatusEnum, User
    from src.task_manager.scheduler import (
        ESCALATION_JOB_ID,
        create_scheduler,
        get_last_run_info,
        run_escalation_job,
    )
    from src.task_manager.services import EscalationService


@pytest.fixture(autouse=True)
def reset_last_run_info(monkeypatch):
    """Reset the module-level last-run state so tests don't depend on run order."""
    monkeypatch.setattr(
        scheduler_module, "_last_run_info", {"timestamp": None, "escalated_count": 0}
    )


@pytest.fixture
def db_session():
    """Provide a database session for testing."""
    db = SessionLocal()
    try:
        # Clean tables before each test (respect FK order)
        db.query(Notification).delete()
        db.query(Task).delete()
        db.query(User).delete()
        db.commit()
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user for task assignments."""
    user = User(name="Scheduler User", email="scheduler@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestCreateScheduler:
    """Tests for create_scheduler."""

    def test_registers_escalation_job_on_a_one_minute_interval(self):
        scheduler = create_scheduler()

        job = scheduler.get_job(ESCALATION_JOB_ID)

        assert job is not None
        assert isinstance(job.trigger, IntervalTrigger)
        assert job.trigger.interval.total_seconds() == 60
        assert job.func is run_escalation_job

    def test_scheduler_is_returned_stopped(self):
        scheduler = create_scheduler()

        assert scheduler.running is False


class TestRunEscalationJob:
    """Tests for run_escalation_job."""

    def test_escalates_eligible_task_using_its_own_session(self, db_session, test_user):
        task = Task(
            title="Job task",
            deadline=datetime.utcnow() + timedelta(hours=5),
            priority=PriorityEnum.LOW,
            status=TaskStatusEnum.PENDING,
            assigned_to=test_user.id,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        result = run_escalation_job()

        db_session.refresh(task)
        assert result["escalated_count"] == 1
        assert task.priority == PriorityEnum.HIGH
        datetime.fromisoformat(result["timestamp"])  # valida formato ISO

    def test_swallows_exceptions_without_raising(self, monkeypatch):
        def boom(db):
            raise RuntimeError("db exploded")

        monkeypatch.setattr(EscalationService, "escalate_urgent_tasks", staticmethod(boom))

        result = run_escalation_job()

        assert result["escalated_count"] == 0
        datetime.fromisoformat(result["timestamp"])


def _parsed_json_logs(records):
    """Parse caplog records whose message is a JSON object, skipping the rest."""
    parsed = []
    for record in records:
        try:
            parsed.append(json.loads(record.getMessage()))
        except (TypeError, ValueError):
            continue
    return parsed


class TestRunEscalationJobLogging:
    """Tests for structured (JSON) logging emitted by run_escalation_job."""

    def test_logs_structured_json_on_completion(self, db_session, test_user, caplog):
        with caplog.at_level(logging.INFO):
            run_escalation_job()

        logs = _parsed_json_logs(caplog.records)
        completed = next(log for log in logs if log.get("event") == "completed")
        assert completed["job_id"] == ESCALATION_JOB_ID
        assert "escalated_count" in completed
        assert "timestamp" in completed

    def test_logs_structured_json_on_failure(self, monkeypatch, caplog):
        def boom(db):
            raise RuntimeError("db exploded")

        monkeypatch.setattr(EscalationService, "escalate_urgent_tasks", staticmethod(boom))

        with caplog.at_level(logging.ERROR):
            run_escalation_job()

        logs = _parsed_json_logs(caplog.records)
        failed = next(log for log in logs if log.get("event") == "failed")
        assert failed["job_id"] == ESCALATION_JOB_ID
        assert "error" in failed
        assert "timestamp" in failed


class TestLastRunInfo:
    """Tests for get_last_run_info and its update by run_escalation_job (Task 6.1)."""

    def test_default_state_before_any_run(self):
        info = get_last_run_info()

        assert info == {"timestamp": None, "escalated_count": 0}

    def test_returns_a_copy_not_a_live_reference(self):
        info = get_last_run_info()
        info["escalated_count"] = 999

        assert get_last_run_info()["escalated_count"] == 0

    def test_updated_after_successful_run(self, db_session, test_user):
        task = Task(
            title="Job task",
            deadline=datetime.utcnow() + timedelta(hours=5),
            priority=PriorityEnum.LOW,
            status=TaskStatusEnum.PENDING,
            assigned_to=test_user.id,
        )
        db_session.add(task)
        db_session.commit()

        result = run_escalation_job()

        info = get_last_run_info()
        assert info["escalated_count"] == result["escalated_count"] == 1
        assert info["timestamp"] == result["timestamp"]

    def test_updated_after_failed_run(self, monkeypatch):
        def boom(db):
            raise RuntimeError("db exploded")

        monkeypatch.setattr(EscalationService, "escalate_urgent_tasks", staticmethod(boom))

        run_escalation_job()

        info = get_last_run_info()
        assert info["escalated_count"] == 0
        assert info["timestamp"] is not None
