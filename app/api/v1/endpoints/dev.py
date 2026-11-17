from celery.result import AsyncResult
from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser
from app.tasks.celery_app import celery_app
from app.tasks.debug_tasks import slow_add

router = APIRouter(prefix="/dev", tags=["dev (temporary)"])


@router.post("/tasks/slow-add", status_code=status.HTTP_202_ACCEPTED)
def submit_slow_add(
    user: CurrentUser,
    x: int = 2,
    y: int = 3,
    seconds: int = Query(5, ge=1, le=60),
) -> dict:
    result = slow_add.delay(x, y, seconds)
    return {"task_id": result.id}


@router.get("/tasks/{task_id}")
def get_task_state(task_id: str, user: CurrentUser) -> dict:
    result = AsyncResult(task_id, app=celery_app)
    info = result.info
    if isinstance(info, Exception):
        info = str(info)
    return {"task_id": task_id, "state": result.state, "info": info}