from fastapi import APIRouter
from app.core.config import settings

router = APIRouter(tags=["system"])

@router.get('/health')
def health_check() -> dict:
    return{
        "status": "ok",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV
    }