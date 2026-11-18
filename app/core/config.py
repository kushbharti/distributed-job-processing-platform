from decouple import Csv, config
from pathlib import Path

class Settings:
    APP_NAME: str = config("APP_NAME", default="Distributed Job Processing Platform")
    APP_ENV: str = config("APP_ENV", default="development")
    DEBUG: bool = config("DEBUG", default=False, cast=bool)
    API_V1_PREFIX: str = config("API_V1_PREFIX", default="/api/v1")

    SECRET_KEY: str = config("SECRET_KEY")

    ## CORS
    ALLOWED_ORIGINS: list[str] = config("ALLOWED_ORIGINS", default="", cast=Csv())
    
    ## DATABASE CONFIGURATIONS
    DATABASE_URL: str = config("DATABASE_URL")  
    
    ## Security
    SECRET_KEY: str = config("SECRET_KEY")
    JWT_ALGORITHM: str = config("JWT_ALGORITHM", default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = config("ACCESS_TOKEN_EXPIRE_MINUTES", default=30, cast=int)
    
    # Redis / Celery
    REDIS_URL: str = config("REDIS_URL")
    CELERY_BROKER_URL: str = config("CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = config("CELERY_RESULT_BACKEND")
    
    ## File Storage
    UPLOAD_DIR: str = config("UPLOAD_DIR", default="uploads")
    MAX_UPLOAD_SIZE_MB: int = config("MAX_UPLOAD_SIZE_MB", default=20, cast=int)
    
    # Job reliability
    JOB_MAX_RETRIES: int = config("JOB_MAX_RETRIES", default=3, cast=int)
    JOB_RETRY_BASE_SECONDS: int = config("JOB_RETRY_BASE_SECONDS", default=5, cast=int)
    JOB_RETRY_MAX_SECONDS: int = config("JOB_RETRY_MAX_SECONDS", default=300, cast=int)
    TASK_SOFT_TIME_LIMIT_SECONDS: int = config(
        "TASK_SOFT_TIME_LIMIT_SECONDS", default=540, cast=int
    )
    TASK_TIME_LIMIT_SECONDS: int = config("TASK_TIME_LIMIT_SECONDS", default=600, cast=int)
    
    STALE_JOB_MINUTES: int = config("STALE_JOB_MINUTES", default=15, cast=int)
    OUTBOX_DISPATCH_INTERVAL_SECONDS: int = config(
        "OUTBOX_DISPATCH_INTERVAL_SECONDS", default=5, cast=int
    )
    RECOVERY_INTERVAL_SECONDS: int = config("RECOVERY_INTERVAL_SECONDS", default=60, cast=int)

    DEV_STAGE_DELAY_SECONDS: float = config("DEV_STAGE_DELAY_SECONDS", default=0, cast=float)
    
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"
    
    @property
    def upload_path(self) -> Path:
        return Path(self.UPLOAD_DIR).resolve()
    
    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    
settings = Settings()