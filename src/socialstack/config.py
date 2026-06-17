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
    ai_image_model: str = "imagen-3.0-generate-002"
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
    supabase_service_key: str = ""       # legacy alias
    supabase_service_role_key: str = ""  # preferred name
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""        # JWT Settings → JWT Secret in Supabase dashboard

    # Security
    api_secret_key: str = "change-me-in-production"
    backend_api_key: str = ""            # for n8n / agent-to-agent calls (no user JWT)
    token_encryption_key: str = ""       # Fernet key for social platform tokens
    inbound_hmac_secret: str = ""
    social_webhook_secret: str = ""      # alias used by spec (falls back to inbound_hmac_secret)

    # Observability
    sentry_dsn: str = ""

    # CORS
    frontend_url: str = "*"              # set to https://app.welvom.com in production

    # CRON schedule
    publish_cron_every_minutes: int = 5
    metrics_cron_every_hours: int = 6

    # Concurrency limits
    max_concurrent_image_tasks: int = 5

    # Rate limiting (per business per minute)
    rate_limit_requests_per_minute: int = 60

    # Notifications
    slack_webhook_url: str = ""          # Slack incoming webhook for ops alerts
    notification_webhook_url: str = ""   # Generic outbound webhook for client events

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_test(self) -> bool:
        return self.environment == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
