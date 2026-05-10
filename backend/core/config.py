from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://ragak_user:password@localhost:5432/ragak"
    database_url_sync: str = "postgresql+psycopg2://ragak_user:password@localhost:5432/ragak"

    # Redis
    redis_url: str = "redis://:password@localhost:6379/0"

    # External APIs
    gemini_api_key: str = ""
    openai_api_key: str = ""

    # Auth
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # App
    environment: str = "development"
    log_level: str = "INFO"
    upload_dir: str = "/app/uploads"
    max_upload_size_mb: int = 50
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # LangGraph
    langgraph_checkpoint_ttl_days: int = 30

    # Scoring
    default_ranking_profile_id: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
