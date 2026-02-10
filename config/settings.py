"""Settings"""
from pydantic_settings import BaseSettings
from typing import Optional
import os

# Resolve project root (directory containing config/ and backend/) so .env is found regardless of cwd
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_ENV_PATH = os.path.join(_PROJECT_ROOT, ".env")

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
    LOG_LEVEL: str = "INFO"
    # Optional: Market Research Reverse Engineering (AI) – use OpenAI and/or Anthropic (Claude)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    class Config:
        case_sensitive = True
        env_file = _ENV_PATH
        env_file_encoding = "utf-8"

