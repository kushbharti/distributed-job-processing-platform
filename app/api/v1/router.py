from fastapi import APIRouter

from app.api.v1.endpoints import system, auth

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth.router)