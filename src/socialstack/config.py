from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    environment: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"
    api_version: str = "v1"

    # Database
    database_url: str = "postgresql+asyncpg://socialstack:password@localhost:5432/socialstack"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_worker_concurrency: int = 4
    celery_task_soft_time_limit: int = 600
    celery_task_time_limit: int = 900

    # AI — text (OpenAI)
    ai_chat_model: str = "gpt-4o-mini"
    ai_max_retries: int = 3
    ai_retry_delay_seconds: float = 2.0
    openai_api_key: str = ""

    # AI — image (Google)
    ai_image_model: str = "nano-banana-pro"
    google_api_key: str = ""

    # Storage
    storage_backend: Literal["local", "s3", "supabase"] = "local"
    local_storage_path: str = "./data/media"
    local_storage_base_url: str = "http://localhost:8000/media"
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    supabase_url: str = ""
    supabase_service_key: str = ""

    # Security
    api_secret_key: str = "change-me-in-production"
    token_encryption_key: str = ""  # Fernet key for social platform tokens
    inbound_hmac_secret: str = ""

    # CRON schedule
    publish_cron_every_minutes: int = 5
    metrics_cron_every_hours: int = 6

    # Concurrency limits
    max_concurrent_image_tasks: int = 5

    # Rate limiting (per business per minute)
    rate_limit_requests_per_minute: int = 60

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_test(self) -> bool:
        return self.environment == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
