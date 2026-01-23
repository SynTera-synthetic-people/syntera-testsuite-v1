"""Settings"""
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    APP_NAME: str = "SynTera Test Suite"
    DEBUG: bool = os.getenv("DEBUG", "False") == "True"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./syntera.db")
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: list = ["*"]
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    BATCH_SIZE: int = 32
    NUM_WORKERS: int = 4

    class Config:
        case_sensitive = True
        env_file = ".env"

