"""Background job scheduling for automatic task escalation."""

import json
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from task_manager.database import SessionLocal
from task_manager.services import EscalationService

logger = logging.getLogger(__name__)

ESCALATION_JOB_ID = "escalate_urgent_tasks"

_last_run_info: dict = {"timestamp": None, "escalated_count": 0}


def get_last_run_info() -> dict:
    """Return a copy of the most recent escalation job run's result.

    Before the job has ever run, `timestamp` is None and `escalated_count`
    is 0.
    """
    return dict(_last_run_info)


def run_escalation_job() -> dict:
    """Run the escalation check in its own database session.

    Returns a dict with `escalated_count` and an ISO-8601 UTC `timestamp`.
    Emits structured (JSON) log records for start, completion, and failure.
    Any exception raised while escalating is logged and swallowed so a
    failure here never crashes the scheduler thread or the application.
    """
    logger.info(json.dumps({"event": "started", "job_id": ESCALATION_JOB_ID}))
    db = SessionLocal()
    try:
        escalated_count = EscalationService.escalate_urgent_tasks(db)
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(
            json.dumps(
                {
                    "event": "completed",
                    "job_id": ESCALATION_JOB_ID,
                    "escalated_count": escalated_count,
                    "timestamp": timestamp,
                }
            )
        )
        result = {"escalated_count": escalated_count, "timestamp": timestamp}
        _last_run_info.update(result)
        return result
    except Exception as exc:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.error(
            json.dumps(
                {
                    "event": "failed",
                    "job_id": ESCALATION_JOB_ID,
                    "error": str(exc),
                    "timestamp": timestamp,
                }
            ),
            exc_info=True,
        )
        result = {"escalated_count": 0, "timestamp": timestamp}
        _last_run_info.update(result)
        return result
    finally:
        db.close()


def create_scheduler() -> BackgroundScheduler:
    """Build a BackgroundScheduler with the escalation job registered.

    The job runs every minute. The scheduler is returned in a stopped
    state; callers are responsible for calling `start()` / `shutdown()`.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_escalation_job,
        trigger=IntervalTrigger(minutes=1),
        id=ESCALATION_JOB_ID,
        replace_existing=True,
    )
    return scheduler
