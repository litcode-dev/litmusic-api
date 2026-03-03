import json
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.config import get_settings
from app.exceptions import AppError, app_error_handler
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.rate_limit import limiter
from app.routers import auth, loops, stem_packs, payments, admin

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

settings = get_settings()

app = FastAPI(
    title="LitMusic API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

def _parse_origins(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("["):
        return json.loads(raw)
    return [o.strip() for o in raw.split(",") if o.strip()]


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_origins(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging
app.add_middleware(LoggingMiddleware)

# Error handler
app.add_exception_handler(AppError, app_error_handler)

# Routers
PREFIX = "/api/v1"
app.include_router(auth.router, prefix=PREFIX)
app.include_router(loops.router, prefix=PREFIX)
app.include_router(stem_packs.router, prefix=PREFIX)
app.include_router(payments.router, prefix=PREFIX)
app.include_router(admin.router, prefix=PREFIX)


@app.get("/health", tags=["health"])
async def health_check():
    from app.database import engine
    from redis.asyncio import Redis
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    try:
        r = Redis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        redis_ok = True
    except Exception:
        redis_ok = False

    overall = "healthy" if db_ok and redis_ok else "degraded"
    return {
        "status": overall,
        "database": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
    }
