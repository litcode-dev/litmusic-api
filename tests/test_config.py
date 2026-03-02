from app.config import get_settings


def test_settings_loads(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-characters!")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket")
    monkeypatch.setenv("FLW_SECRET_KEY", "FLWSECK_TEST-test")
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "sk_test_paystack")
    monkeypatch.setenv("ONESIGNAL_APP_ID", "app-id")
    monkeypatch.setenv("ONESIGNAL_API_KEY", "api-key")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    get_settings.cache_clear()
    s = get_settings()
    assert s.access_token_expire_minutes > 0
    assert s.app_env == "development"
    assert s.aws_region  # region is set
