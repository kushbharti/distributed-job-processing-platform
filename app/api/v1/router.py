from fastapi import APIRouter

from app.api.v1.endpoints import auth, dev, documents, system
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(documents.router)

if settings.DEBUG:
    api_router.include_router(dev.router)