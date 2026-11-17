from fastapi import APIRouter, HTTPException, status
from app.core.config import settings
from app.db.dependencies import DbSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import text


router = APIRouter(tags=["system"])

@router.get('/health')
def health_check() -> dict:
    return{
        "status": "ok",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV
    }
    
@router.get('/ready')
def readiness_check(db:DbSession) -> dict:
    """Readiness: can the app reach its dependencies?"""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    return {"status": "ready", "checks": {"database": "ok"}}