from pathlib import Path

from fastapi.staticfiles import StaticFiles

from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.router import api_router
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        debug=settings.DEBUG,
        docs_url="/docs",
        redoc_url="/redoc",
        )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    
    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {"message": f"{settings.APP_NAME} is running", "docs": "/docs"}
    
    return app

app = create_app()