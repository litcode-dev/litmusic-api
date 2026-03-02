from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_env: str = "development"
    secret_key: str
    allowed_origins: list[str] = ["http://localhost:3000"]

    # Database
    database_url: str

    # Redis
    redis_url: str

    # AWS S3
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    s3_bucket_name: str
    s3_cloudfront_url: str = ""  # e.g. https://d2q7nhojr9v45l.cloudfront.net

    # Stripe
    stripe_secret_key: str
    stripe_webhook_secret: str

    # OneSignal
    onesignal_app_id: str
    onesignal_api_key: str

    # JWT
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Celery
    celery_broker_url: str
    celery_result_backend: str

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:3000/auth/google/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
