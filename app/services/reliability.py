import random

from app.core.config import settings


def backoff_seconds(attempt: int) -> float:
    """Delay before retry number `attempt` (0-based): 5s, 10s, 20s, 40s ... capped, plus jitter."""
    delay = min(settings.JOB_RETRY_BASE_SECONDS * (2**attempt), settings.JOB_RETRY_MAX_SECONDS)
 
    return delay + random.uniform(0, delay * 0.25)