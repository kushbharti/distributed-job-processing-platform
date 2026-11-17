from decouple import Csv, config

class Settings:
    APP_NAME: str = config("APP_NAME", default="Distributed Job Processing Platform")
    APP_ENV: str = config("APP_ENV", default="development")
    DEBUG: bool = config("DEBUG", default=False, cast=bool)
    API_V1_PREFIX: str = config("API_V1_PREFIX", default="/api/v1")

    SECRET_KEY: str = config("SECRET_KEY")

    ## CORS
    ALLOWED_ORIGINS: list[str] = config("ALLOWED_ORIGINS", default="", cast=Csv())
    
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"
    
settings = Settings()