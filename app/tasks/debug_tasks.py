import time

from app.tasks.celery_app import celery_app


@celery_app.task(name="debug.slow_add", bind=True)
def slow_add(self, x: int, y: int, seconds: int = 5) -> dict:
    """A fake long-running job: sleeps, reports progress, returns x + y."""
    for step in range(1, seconds + 1):
        time.sleep(1)
        self.update_state(state="PROGRESS", meta={"step": step, "total": seconds})
    return {"result": x + y}