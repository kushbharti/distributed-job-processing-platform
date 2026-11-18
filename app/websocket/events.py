import json
import logging
import uuid
from datetime import UTC, datetime

from redis.exceptions import RedisError

from app.core.redis import redis_client

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})


def channel_for(job_id: uuid.UUID | str) -> str:
    return f"job-events:{job_id}"


def build_event(
    job_id: uuid.UUID | str,
    status: str,
    progress: int,
    stage: str | None,
    error: str | None = None,
) -> dict:
    return {
        "job_id": str(job_id),
        "status": status,
        "progress": progress,
        "current_stage": stage,
        "message": error or stage or "",
        "error_message": error,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def publish_job_event(
    job_id: uuid.UUID | str,
    status: str,
    progress: int,
    stage: str | None,
    error: str | None = None,
) -> None:
    """Best effort. PostgreSQL already holds the truth; a lost event must never fail a job."""
    try:
        redis_client.publish(
            channel_for(job_id), json.dumps(build_event(job_id, status, progress, stage, error))
        )
    except RedisError:
        logger.warning("Could not publish event for job %s", job_id, exc_info=True)


def snapshot_from_job(job) -> dict:
    return build_event(job.id, job.status, job.progress, job.current_stage, job.error_message)