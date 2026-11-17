from fastapi import APIRouter, HTTPException, status
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.redis import redis_client
from app.db.dependencies import DbSession

router = APIRouter(tags=["system"])


@router.get("/health")
def health_check() -> dict:
    """Liveness: is the process running?"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
    }


@router.get("/ready")
def readiness_check(db: DbSession) -> dict:
    """Readiness: can the app reach its dependencies?"""
    checks = {"database": "ok", "redis": "ok"}

    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        checks["database"] = "unavailable"

    try:
        redis_client.ping()
    except RedisError:
        checks["redis"] = "unavailable"

    if any(value != "ok" for value in checks.values()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not ready", "checks": checks},
        )
    return {"status": "ready", "checks": checks}