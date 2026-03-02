# LitMusic API Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Build a production-ready music loop and stem pack marketplace backend with FastAPI, PostgreSQL, Redis, Celery, S3, AES-256 encryption, Stripe payments, and OneSignal push notifications.

**Architecture:** Layered FastAPI app — routers call service functions, services own all business logic, models are pure SQLAlchemy ORM, no raw SQL anywhere. All endpoints async. Consistent `{status, data, message}` response envelope.

**Tech Stack:** FastAPI, SQLAlchemy 2.x (async), Alembic, Redis (aioredis), Celery, boto3, pycryptodome (AES-256-GCM), python-jose (JWT), passlib[bcrypt], stripe, slowapi, pydantic v2, ffmpeg-python, soundfile, docker-compose.

---

## Phase 1: Project Foundation

---

### Task 1: Initialise project structure and dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `app/__init__.py`

**Step 1: Create directory skeleton**

```bash
mkdir -p app/{models,schemas,routers,services,tasks,middleware,utils}
touch app/__init__.py
touch app/{models,schemas,routers,services,tasks,middleware,utils}/__init__.py
mkdir -p tests/{routers,services,utils}
touch tests/__init__.py tests/conftest.py
mkdir -p alembic
```

**Step 2: Write `pyproject.toml`**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 88
```

**Step 3: Write `requirements.txt`**

```text
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.13.3
redis==5.2.0
celery[redis]==5.4.0
boto3==1.35.40
pycryptodome==3.21.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
stripe==11.1.0
slowapi==0.1.9
pydantic[email]==2.9.2
pydantic-settings==2.5.2
python-multipart==0.0.12
soundfile==0.12.1
ffmpeg-python==0.2.0
httpx==0.27.2
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-mock==3.14.0
aiofiles==24.1.0
structlog==24.4.0
```

**Step 4: Write `.env.example`**

```env
# Application
APP_ENV=development
SECRET_KEY=change-me-in-production-minimum-32-chars
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# Database
DATABASE_URL=postgresql+asyncpg://litmusic:litmusic@db:5432/litmusic

# Redis
REDIS_URL=redis://redis:6379/0

# AWS S3
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
S3_BUCKET_NAME=litmusic-files

# Stripe
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# OneSignal
ONESIGNAL_APP_ID=your-onesignal-app-id
ONESIGNAL_API_KEY=your-onesignal-api-key

# JWT
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# Celery
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
```

**Step 5: Commit**

```bash
git init
git add .
git commit -m "feat: initialise project structure and dependencies"
```

---

### Task 2: Configuration and application settings

**Files:**
- Create: `app/config.py`

**Step 1: Write `app/config.py`**

```python
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Step 2: Write failing test**

```python
# tests/test_config.py
from app.config import get_settings


def test_settings_loads(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-characters")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec")
    monkeypatch.setenv("ONESIGNAL_APP_ID", "app-id")
    monkeypatch.setenv("ONESIGNAL_API_KEY", "api-key")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    get_settings.cache_clear()
    s = get_settings()
    assert s.access_token_expire_minutes == 15
```

**Step 3: Run test**

```bash
pytest tests/test_config.py -v
```
Expected: PASS

**Step 4: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat: add settings configuration with pydantic-settings"
```

---

### Task 3: Database engine and session factory

**Files:**
- Create: `app/database.py`

**Step 1: Write `app/database.py`**

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.app_env == "development",
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

**Step 2: Commit**

```bash
git add app/database.py
git commit -m "feat: add async SQLAlchemy engine and session factory"
```

---

## Phase 2: Models

---

### Task 4: User model

**Files:**
- Create: `app/models/user.py`
- Modify: `app/models/__init__.py`

**Step 1: Write `app/models/user.py`**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    free = "free"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.free, nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    onesignal_player_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

**Step 2: Update `app/models/__init__.py`**

```python
from app.models.user import User, UserRole
```

**Step 3: Commit**

```bash
git add app/models/
git commit -m "feat: add User model"
```

---

### Task 5: Loop model

**Files:**
- Create: `app/models/loop.py`
- Modify: `app/models/__init__.py`

**Step 1: Write `app/models/loop.py`**

```python
import uuid
import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    String, Integer, Boolean, Numeric, Text,
    DateTime, Enum as SAEnum, ForeignKey, func, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Genre(str, enum.Enum):
    afrobeat = "Afrobeat"
    amapiano = "Amapiano"
    trap = "Trap"
    boom_bap = "Boom Bap"
    lo_fi = "Lo-fi"
    gospel = "Gospel"
    afrobeat_worship = "Afrobeat Worship"
    contemporary_worship = "Contemporary Worship"
    dancehall = "Dancehall"
    afrohouse = "Afrohouse"
    highlife_gospel = "Highlife Gospel"


class TempoFeel(str, enum.Enum):
    slow = "slow"
    mid = "mid"
    fast = "fast"


class Loop(Base):
    __tablename__ = "loops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(300), unique=True, index=True, nullable=False)
    genre: Mapped[Genre] = mapped_column(SAEnum(Genre), nullable=False, index=True)
    bpm: Mapped[int] = mapped_column(Integer, nullable=False)
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    tempo_feel: Mapped[TempoFeel] = mapped_column(SAEnum(TempoFeel), nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_free: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    file_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preview_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    aes_key: Mapped[str | None] = mapped_column(Text, nullable=True)   # base64
    aes_iv: Mapped[str | None] = mapped_column(Text, nullable=True)    # base64
    waveform_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    play_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**Step 2: Update `app/models/__init__.py`**

```python
from app.models.user import User, UserRole
from app.models.loop import Loop, Genre, TempoFeel
```

**Step 3: Commit**

```bash
git add app/models/loop.py app/models/__init__.py
git commit -m "feat: add Loop model with genre and tempo enums"
```

---

### Task 6: StemPack and Stem models

**Files:**
- Create: `app/models/stem_pack.py`
- Modify: `app/models/__init__.py`

**Step 1: Write `app/models/stem_pack.py`**

```python
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Integer, Numeric, Text, DateTime, ForeignKey, func, ARRAY, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.loop import Genre


class StemPack(Base):
    __tablename__ = "stem_packs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(300), unique=True, index=True, nullable=False)
    loop_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("loops.id"), nullable=True)
    genre: Mapped[Genre] = mapped_column(SAEnum(Genre), nullable=False, index=True)
    bpm: Mapped[int] = mapped_column(Integer, nullable=False)
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Stem(Base):
    __tablename__ = "stems"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stem_pack_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stem_packs.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    file_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preview_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    aes_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    aes_iv: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**Step 2: Update `app/models/__init__.py`**

```python
from app.models.user import User, UserRole
from app.models.loop import Loop, Genre, TempoFeel
from app.models.stem_pack import StemPack, Stem
```

**Step 3: Commit**

```bash
git add app/models/stem_pack.py app/models/__init__.py
git commit -m "feat: add StemPack and Stem models"
```

---

### Task 7: Purchase and Download models

**Files:**
- Create: `app/models/purchase.py`
- Create: `app/models/download.py`
- Modify: `app/models/__init__.py`

**Step 1: Write `app/models/purchase.py`**

```python
import uuid
import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, ForeignKey, func, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PurchaseType(str, enum.Enum):
    one_time = "one_time"


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    loop_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("loops.id"), nullable=True, index=True)
    stem_pack_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stem_packs.id"), nullable=True, index=True)
    stripe_payment_intent_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    purchase_type: Mapped[PurchaseType] = mapped_column(SAEnum(PurchaseType), default=PurchaseType.one_time)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**Step 2: Write `app/models/download.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Download(Base):
    __tablename__ = "downloads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    loop_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("loops.id"), nullable=True)
    stem_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stems.id"), nullable=True)
    download_url: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**Step 3: Update `app/models/__init__.py`**

```python
from app.models.user import User, UserRole
from app.models.loop import Loop, Genre, TempoFeel
from app.models.stem_pack import StemPack, Stem
from app.models.purchase import Purchase, PurchaseType
from app.models.download import Download
```

**Step 4: Commit**

```bash
git add app/models/purchase.py app/models/download.py app/models/__init__.py
git commit -m "feat: add Purchase and Download models"
```

---

## Phase 3: Alembic Migrations

---

### Task 8: Alembic setup and initial migration

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`

**Step 1: Initialise Alembic**

```bash
alembic init alembic
```

**Step 2: Replace `alembic/env.py`**

```python
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from app.database import Base
from app.config import get_settings
import app.models  # noqa: F401 — ensure all models are imported

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Step 3: Generate initial migration**

```bash
alembic revision --autogenerate -m "initial schema"
```

**Step 4: Review the generated migration file in `alembic/versions/`. Ensure all tables appear.**

**Step 5: Commit**

```bash
git add alembic/
git commit -m "feat: add Alembic config and initial schema migration"
```

---

## Phase 4: Schemas (Pydantic v2)

---

### Task 9: Common response envelope and shared schemas

**Files:**
- Create: `app/schemas/common.py`

**Step 1: Write `app/schemas/common.py`**

```python
from typing import Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ResponseEnvelope(BaseModel, Generic[T]):
    status: str  # "success" | "error"
    data: T | None = None
    message: str = ""


def success(data: Any = None, message: str = "OK") -> dict:
    return {"status": "success", "data": data, "message": message}


def error(message: str, data: Any = None) -> dict:
    return {"status": "error", "data": data, "message": message}
```

**Step 2: Write failing test**

```python
# tests/test_schemas_common.py
from app.schemas.common import success, error


def test_success_envelope():
    result = success(data={"id": 1}, message="created")
    assert result["status"] == "success"
    assert result["data"]["id"] == 1


def test_error_envelope():
    result = error(message="not found")
    assert result["status"] == "error"
    assert result["message"] == "not found"
```

**Step 3: Run test**

```bash
pytest tests/test_schemas_common.py -v
```
Expected: PASS

**Step 4: Commit**

```bash
git add app/schemas/common.py tests/test_schemas_common.py
git commit -m "feat: add response envelope schema helpers"
```

---

### Task 10: User schemas

**Files:**
- Create: `app/schemas/user.py`

**Step 1: Write `app/schemas/user.py`**

```python
import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator
from app.models.user import UserRole


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    stripe_customer_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
```

**Step 2: Commit**

```bash
git add app/schemas/user.py
git commit -m "feat: add User request/response schemas"
```

---

### Task 11: Loop and StemPack schemas

**Files:**
- Create: `app/schemas/loop.py`
- Create: `app/schemas/stem_pack.py`

**Step 1: Write `app/schemas/loop.py`**

```python
import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, field_validator
from app.models.loop import Genre, TempoFeel


class LoopCreate(BaseModel):
    title: str
    genre: Genre
    bpm: int
    key: str
    duration: int
    tempo_feel: TempoFeel
    tags: list[str] = []
    price: Decimal
    is_free: bool = False

    @field_validator("bpm")
    @classmethod
    def bpm_range(cls, v: int) -> int:
        if not (60 <= v <= 140):
            raise ValueError("BPM must be between 60 and 140")
        return v


class LoopUpdate(BaseModel):
    title: str | None = None
    genre: Genre | None = None
    bpm: int | None = None
    key: str | None = None
    tempo_feel: TempoFeel | None = None
    tags: list[str] | None = None
    price: Decimal | None = None
    is_free: bool | None = None


class LoopResponse(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    genre: Genre
    bpm: int
    key: str
    duration: int
    tempo_feel: TempoFeel
    tags: list[str]
    price: Decimal
    is_free: bool
    is_paid: bool
    preview_s3_key: str | None
    waveform_data: list | None
    download_count: int
    play_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class LoopFilter(BaseModel):
    genre: Genre | None = None
    bpm_min: int | None = None
    bpm_max: int | None = None
    key: str | None = None
    tempo_feel: TempoFeel | None = None
    tags: list[str] | None = None
    is_free: bool | None = None
    sort: str = "newest"
    page: int = 1
    page_size: int = 20
```

**Step 2: Write `app/schemas/stem_pack.py`**

```python
import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel
from app.models.loop import Genre


class StemPackCreate(BaseModel):
    title: str
    loop_id: uuid.UUID | None = None
    genre: Genre
    bpm: int
    key: str
    tags: list[str] = []
    price: Decimal
    description: str | None = None


class StemCreate(BaseModel):
    label: str
    duration: int


class StemResponse(BaseModel):
    id: uuid.UUID
    label: str
    duration: int
    created_at: datetime

    model_config = {"from_attributes": True}


class StemPackResponse(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    loop_id: uuid.UUID | None
    genre: Genre
    bpm: int
    key: str
    tags: list[str]
    price: Decimal
    description: str | None
    stems: list[StemResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}
```

**Step 3: Commit**

```bash
git add app/schemas/loop.py app/schemas/stem_pack.py
git commit -m "feat: add Loop and StemPack schemas"
```

---

### Task 12: Purchase schema

**Files:**
- Create: `app/schemas/purchase.py`

**Step 1: Write `app/schemas/purchase.py`**

```python
import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, model_validator


class CheckoutRequest(BaseModel):
    loop_id: uuid.UUID | None = None
    stem_pack_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def exactly_one_product(self) -> "CheckoutRequest":
        if bool(self.loop_id) == bool(self.stem_pack_id):
            raise ValueError("Provide exactly one of loop_id or stem_pack_id")
        return self


class PurchaseResponse(BaseModel):
    id: uuid.UUID
    loop_id: uuid.UUID | None
    stem_pack_id: uuid.UUID | None
    amount_paid: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str
```

**Step 2: Write failing test**

```python
# tests/test_schemas_purchase.py
import pytest
from pydantic import ValidationError
from app.schemas.purchase import CheckoutRequest
import uuid


def test_checkout_requires_exactly_one_product():
    with pytest.raises(ValidationError):
        CheckoutRequest()  # neither


def test_checkout_rejects_both_products():
    with pytest.raises(ValidationError):
        CheckoutRequest(loop_id=uuid.uuid4(), stem_pack_id=uuid.uuid4())


def test_checkout_accepts_loop_only():
    req = CheckoutRequest(loop_id=uuid.uuid4())
    assert req.stem_pack_id is None


def test_checkout_accepts_stem_pack_only():
    req = CheckoutRequest(stem_pack_id=uuid.uuid4())
    assert req.loop_id is None
```

**Step 3: Run test**

```bash
pytest tests/test_schemas_purchase.py -v
```
Expected: PASS

**Step 4: Commit**

```bash
git add app/schemas/purchase.py tests/test_schemas_purchase.py
git commit -m "feat: add Purchase and Checkout schemas with validation"
```

---

## Phase 5: Custom Exceptions and Error Handling

---

### Task 13: Custom exception classes and global handler

**Files:**
- Create: `app/exceptions.py`

**Step 1: Write `app/exceptions.py`**

```python
from fastapi import Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400, data=None):
        self.message = message
        self.status_code = status_code
        self.data = data
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Not found"):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict"):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class PaymentError(AppError):
    def __init__(self, message: str = "Payment failed"):
        super().__init__(message, status_code=status.HTTP_402_PAYMENT_REQUIRED)


class EntitlementError(AppError):
    def __init__(self, message: str = "Purchase required to access this file"):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "data": exc.data, "message": exc.message},
    )
```

**Step 2: Commit**

```bash
git add app/exceptions.py
git commit -m "feat: add custom exception classes and error handler"
```

---

## Phase 6: Services

---

### Task 14: Encryption service (AES-256-GCM)

**Files:**
- Create: `app/services/encryption_service.py`

**Step 1: Write `app/services/encryption_service.py`**

```python
import base64
import os
from Crypto.Cipher import AES


def generate_key_and_iv() -> tuple[str, str]:
    """Generate a fresh AES-256-GCM key and IV. Returns (key_b64, iv_b64)."""
    key = os.urandom(32)  # 256-bit
    iv = os.urandom(16)
    return base64.b64encode(key).decode(), base64.b64encode(iv).decode()


def encrypt_bytes(plaintext: bytes, key_b64: str, iv_b64: str) -> bytes:
    key = base64.b64decode(key_b64)
    iv = base64.b64decode(iv_b64)
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    # Prepend tag for verification on decrypt
    return tag + ciphertext


def decrypt_bytes(ciphertext_with_tag: bytes, key_b64: str, iv_b64: str) -> bytes:
    key = base64.b64decode(key_b64)
    iv = base64.b64decode(iv_b64)
    tag = ciphertext_with_tag[:16]
    ciphertext = ciphertext_with_tag[16:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    return cipher.decrypt_and_verify(ciphertext, tag)
```

**Step 2: Write failing test**

```python
# tests/services/test_encryption_service.py
from app.services.encryption_service import generate_key_and_iv, encrypt_bytes, decrypt_bytes


def test_encrypt_decrypt_roundtrip():
    plaintext = b"Hello, LitMusic!"
    key, iv = generate_key_and_iv()
    encrypted = encrypt_bytes(plaintext, key, iv)
    decrypted = decrypt_bytes(encrypted, key, iv)
    assert decrypted == plaintext


def test_different_keys_fail():
    import pytest
    from Crypto.Cipher import AES
    plaintext = b"test data"
    key, iv = generate_key_and_iv()
    wrong_key, _ = generate_key_and_iv()
    encrypted = encrypt_bytes(plaintext, key, iv)
    with pytest.raises(ValueError):
        decrypt_bytes(encrypted, wrong_key, iv)


def test_key_is_256_bits():
    import base64
    key, iv = generate_key_and_iv()
    assert len(base64.b64decode(key)) == 32
```

**Step 3: Run tests**

```bash
pytest tests/services/test_encryption_service.py -v
```
Expected: PASS

**Step 4: Commit**

```bash
git add app/services/encryption_service.py tests/services/test_encryption_service.py
git commit -m "feat: add AES-256-GCM encryption service"
```

---

### Task 15: Auth service (JWT + bcrypt + Redis)

**Files:**
- Create: `app/services/auth_service.py`

**Step 1: Write `app/services/auth_service.py`**

```python
import uuid
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.models.user import User, UserRole
from app.exceptions import UnauthorizedError, ConflictError

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
REFRESH_PREFIX = "refresh:"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "role": role, "exp": expire},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def create_refresh_token() -> str:
    return str(uuid.uuid4())


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise UnauthorizedError("Invalid or expired token")


async def store_refresh_token(redis: Redis, token: str, user_id: str) -> None:
    key = f"{REFRESH_PREFIX}{token}"
    expire_seconds = settings.refresh_token_expire_days * 86400
    await redis.setex(key, expire_seconds, user_id)


async def validate_refresh_token(redis: Redis, token: str) -> str:
    key = f"{REFRESH_PREFIX}{token}"
    user_id = await redis.get(key)
    if not user_id:
        raise UnauthorizedError("Refresh token invalid or expired")
    return user_id.decode() if isinstance(user_id, bytes) else user_id


async def revoke_refresh_token(redis: Redis, token: str) -> None:
    await redis.delete(f"{REFRESH_PREFIX}{token}")


async def register_user(db: AsyncSession, email: str, password: str, full_name: str) -> User:
    existing = await db.scalar(select(User).where(User.email == email))
    if existing:
        raise ConflictError("Email already registered")
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=UserRole.free,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Invalid credentials")
    return user


async def get_user_by_id(db: AsyncSession, user_id: str) -> User:
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise UnauthorizedError("User not found")
    return user
```

**Step 2: Write failing tests**

```python
# tests/services/test_auth_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.auth_service import (
    hash_password, verify_password, create_access_token,
    decode_access_token, create_refresh_token
)
from app.exceptions import UnauthorizedError


def test_password_hash_and_verify():
    hashed = hash_password("mysecret")
    assert verify_password("mysecret", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_encodes_user_info():
    token = create_access_token("user-123", "free")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "free"


def test_invalid_token_raises():
    with pytest.raises(UnauthorizedError):
        decode_access_token("not.a.valid.token")
```

**Step 3: Run tests**

```bash
pytest tests/services/test_auth_service.py -v
```
Expected: PASS

**Step 4: Commit**

```bash
git add app/services/auth_service.py tests/services/test_auth_service.py
git commit -m "feat: add auth service with JWT, bcrypt, and Redis refresh tokens"
```

---

### Task 16: S3 service

**Files:**
- Create: `app/services/s3_service.py`

**Step 1: Write `app/services/s3_service.py`**

```python
import boto3
from botocore.exceptions import ClientError
from app.config import get_settings

settings = get_settings()


def _get_client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )


async def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to S3. Returns the S3 key."""
    client = _get_client()
    client.put_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return key


async def generate_presigned_url(key: str, expiry_seconds: int = 900) -> str:
    """Generate a pre-signed GET URL valid for expiry_seconds (default 15 min)."""
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": key},
        ExpiresIn=expiry_seconds,
    )


async def delete_object(key: str) -> None:
    client = _get_client()
    client.delete_object(Bucket=settings.s3_bucket_name, Key=key)


def s3_key_for_encrypted_loop(loop_id: str) -> str:
    return f"loops/encrypted/{loop_id}.wav.enc"


def s3_key_for_loop_preview(loop_id: str) -> str:
    return f"previews/{loop_id}_preview.mp3"


def s3_key_for_encrypted_stem(stem_id: str) -> str:
    return f"stems/encrypted/{stem_id}.wav.enc"


def s3_key_for_stem_preview(stem_id: str) -> str:
    return f"stems/previews/{stem_id}_preview.mp3"
```

**Step 2: Commit**

```bash
git add app/services/s3_service.py
git commit -m "feat: add S3 service with presigned URL generation"
```

---

### Task 17: Audio validator and waveform service

**Files:**
- Create: `app/utils/audio_validator.py`
- Create: `app/services/waveform_service.py`

**Step 1: Write `app/utils/audio_validator.py`**

```python
import io
import soundfile as sf
from fastapi import UploadFile
from app.exceptions import AppError

MAX_FILE_SIZE_BYTES = 30 * 1024 * 1024  # 30 MB
REQUIRED_SAMPLE_RATE = 44100


async def validate_wav_upload(file: UploadFile) -> bytes:
    """Read, size-check, and format-validate an uploaded WAV. Returns raw bytes."""
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise AppError("File exceeds 30 MB limit", status_code=413)

    try:
        audio, sample_rate = sf.read(io.BytesIO(content))
    except Exception:
        raise AppError("Invalid audio file — must be a valid WAV", status_code=422)

    if sample_rate != REQUIRED_SAMPLE_RATE:
        raise AppError(
            f"Sample rate must be 44100 Hz, got {sample_rate} Hz", status_code=422
        )

    return content
```

**Step 2: Write `app/services/waveform_service.py`**

```python
import io
import numpy as np
import soundfile as sf


def generate_waveform(audio_bytes: bytes, num_points: int = 200) -> list[float]:
    """
    Compute peak-normalised waveform data for frontend visualiser.
    Returns a list of `num_points` floats in [0.0, 1.0].
    """
    audio, _ = sf.read(io.BytesIO(audio_bytes))
    # Mix to mono if stereo
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    # Split into chunks and take peak amplitude per chunk
    chunk_size = max(1, len(audio) // num_points)
    peaks = []
    for i in range(num_points):
        start = i * chunk_size
        chunk = audio[start : start + chunk_size]
        peaks.append(float(np.abs(chunk).max()) if len(chunk) else 0.0)

    # Normalise to [0, 1]
    max_peak = max(peaks) if peaks else 1.0
    if max_peak == 0:
        return [0.0] * num_points
    return [round(p / max_peak, 4) for p in peaks]
```

**Step 3: Write failing test**

```python
# tests/services/test_waveform_service.py
import numpy as np
import soundfile as sf
import io
from app.services.waveform_service import generate_waveform


def _make_wav_bytes(duration_sec: float = 1.0, sr: int = 44100) -> bytes:
    samples = np.sin(2 * np.pi * 440 * np.linspace(0, duration_sec, int(sr * duration_sec)))
    buf = io.BytesIO()
    sf.write(buf, samples, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_waveform_has_correct_length():
    wav = _make_wav_bytes()
    result = generate_waveform(wav, num_points=100)
    assert len(result) == 100


def test_waveform_values_normalised():
    wav = _make_wav_bytes()
    result = generate_waveform(wav)
    assert all(0.0 <= v <= 1.0 for v in result)
    assert max(result) == 1.0
```

**Step 4: Run tests**

```bash
pytest tests/services/test_waveform_service.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/utils/audio_validator.py app/services/waveform_service.py tests/services/test_waveform_service.py
git commit -m "feat: add audio validator and waveform generator"
```

---

### Task 18: FFmpeg preview generator

**Files:**
- Create: `app/utils/ffmpeg_helpers.py`

**Step 1: Write `app/utils/ffmpeg_helpers.py`**

```python
import subprocess
import io
import tempfile
import os


def generate_preview_mp3(wav_bytes: bytes, duration_seconds: int = 15) -> bytes:
    """
    Cut the first `duration_seconds` of a WAV and encode to MP3 using ffmpeg.
    Returns MP3 bytes.
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_in:
        tmp_in.write(wav_bytes)
        tmp_in_path = tmp_in.name

    tmp_out_path = tmp_in_path.replace(".wav", "_preview.mp3")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", tmp_in_path,
                "-t", str(duration_seconds),
                "-q:a", "2",
                "-vn",
                tmp_out_path,
            ],
            check=True,
            capture_output=True,
        )
        with open(tmp_out_path, "rb") as f:
            return f.read()
    finally:
        os.unlink(tmp_in_path)
        if os.path.exists(tmp_out_path):
            os.unlink(tmp_out_path)
```

**Step 2: Commit**

```bash
git add app/utils/ffmpeg_helpers.py
git commit -m "feat: add ffmpeg preview generator (WAV -> 15s MP3)"
```

---

### Task 19: Loop service

**Files:**
- Create: `app/services/loop_service.py`

**Step 1: Write `app/services/loop_service.py`**

```python
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import array
from app.models.loop import Loop, Genre, TempoFeel
from app.models.purchase import Purchase
from app.models.user import User
from app.schemas.loop import LoopCreate, LoopUpdate, LoopFilter
from app.exceptions import NotFoundError, EntitlementError
from app.services import s3_service, encryption_service
from app.utils.audio_validator import validate_wav_upload
from app.utils.ffmpeg_helpers import generate_preview_mp3
from fastapi import UploadFile
import re


def _slugify(title: str, uid: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return f"{slug}-{uid[:8]}"


async def create_loop(
    db: AsyncSession,
    file: UploadFile,
    data: LoopCreate,
    created_by: uuid.UUID,
) -> Loop:
    wav_bytes = await validate_wav_upload(file)
    preview_mp3 = generate_preview_mp3(wav_bytes)
    aes_key, aes_iv = encryption_service.generate_key_and_iv()
    encrypted_wav = encryption_service.encrypt_bytes(wav_bytes, aes_key, aes_iv)

    loop_id = str(uuid.uuid4())
    enc_key = s3_service.s3_key_for_encrypted_loop(loop_id)
    prev_key = s3_service.s3_key_for_loop_preview(loop_id)

    await s3_service.upload_bytes(enc_key, encrypted_wav)
    await s3_service.upload_bytes(prev_key, preview_mp3, "audio/mpeg")

    import soundfile as sf, io as _io
    audio, _ = sf.read(_io.BytesIO(wav_bytes))
    duration = int(len(audio) / 44100)

    loop = Loop(
        id=uuid.UUID(loop_id),
        title=data.title,
        slug=_slugify(data.title, loop_id),
        genre=data.genre,
        bpm=data.bpm,
        key=data.key,
        duration=duration,
        tempo_feel=data.tempo_feel,
        tags=data.tags,
        price=data.price,
        is_free=data.is_free,
        is_paid=not data.is_free,
        file_s3_key=enc_key,
        preview_s3_key=prev_key,
        aes_key=aes_key,
        aes_iv=aes_iv,
        created_by=created_by,
    )
    db.add(loop)
    await db.commit()
    await db.refresh(loop)
    return loop


async def get_loop(db: AsyncSession, loop_id: uuid.UUID) -> Loop:
    loop = await db.get(Loop, loop_id)
    if not loop:
        raise NotFoundError(f"Loop {loop_id} not found")
    return loop


async def list_loops(db: AsyncSession, filters: LoopFilter) -> tuple[list[Loop], int]:
    q = select(Loop)
    if filters.genre:
        q = q.where(Loop.genre == filters.genre)
    if filters.bpm_min:
        q = q.where(Loop.bpm >= filters.bpm_min)
    if filters.bpm_max:
        q = q.where(Loop.bpm <= filters.bpm_max)
    if filters.key:
        q = q.where(Loop.key.ilike(f"%{filters.key}%"))
    if filters.tempo_feel:
        q = q.where(Loop.tempo_feel == filters.tempo_feel)
    if filters.is_free is not None:
        q = q.where(Loop.is_free == filters.is_free)
    if filters.tags:
        q = q.where(Loop.tags.overlap(filters.tags))

    count_q = select(func.count()).select_from(q.subquery())
    total = await db.scalar(count_q)

    sort_map = {
        "newest": Loop.created_at.desc(),
        "most_downloaded": Loop.download_count.desc(),
        "most_played": Loop.play_count.desc(),
    }
    q = q.order_by(sort_map.get(filters.sort, Loop.created_at.desc()))
    q = q.offset((filters.page - 1) * filters.page_size).limit(filters.page_size)
    result = await db.scalars(q)
    return list(result.all()), total


async def increment_play_count(db: AsyncSession, loop_id: uuid.UUID) -> None:
    loop = await get_loop(db, loop_id)
    loop.play_count += 1
    await db.commit()


async def check_download_entitlement(
    db: AsyncSession, user: User, loop: Loop
) -> None:
    if loop.is_free:
        return
    purchase = await db.scalar(
        select(Purchase).where(
            Purchase.user_id == user.id,
            Purchase.loop_id == loop.id,
        )
    )
    if not purchase:
        raise EntitlementError()


async def update_loop(db: AsyncSession, loop_id: uuid.UUID, data: LoopUpdate) -> Loop:
    loop = await get_loop(db, loop_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(loop, field, value)
    await db.commit()
    await db.refresh(loop)
    return loop


async def delete_loop(db: AsyncSession, loop_id: uuid.UUID) -> None:
    loop = await get_loop(db, loop_id)
    if loop.file_s3_key:
        await s3_service.delete_object(loop.file_s3_key)
    if loop.preview_s3_key:
        await s3_service.delete_object(loop.preview_s3_key)
    await db.delete(loop)
    await db.commit()
```

**Step 2: Commit**

```bash
git add app/services/loop_service.py
git commit -m "feat: add loop service (create, list, entitlement check, delete)"
```

---

### Task 20: StemPack service

**Files:**
- Create: `app/services/stem_pack_service.py`

**Step 1: Write `app/services/stem_pack_service.py`**

```python
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.stem_pack import StemPack, Stem
from app.models.purchase import Purchase
from app.models.user import User
from app.schemas.stem_pack import StemPackCreate, StemCreate
from app.exceptions import NotFoundError, EntitlementError
from app.services import s3_service, encryption_service
from app.utils.audio_validator import validate_wav_upload
from app.utils.ffmpeg_helpers import generate_preview_mp3
from fastapi import UploadFile
import re


def _slugify(title: str, uid: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return f"{slug}-{uid[:8]}"


async def create_stem_pack(db: AsyncSession, data: StemPackCreate, created_by: uuid.UUID) -> StemPack:
    pack_id = uuid.uuid4()
    pack = StemPack(
        id=pack_id,
        title=data.title,
        slug=_slugify(data.title, str(pack_id)),
        loop_id=data.loop_id,
        genre=data.genre,
        bpm=data.bpm,
        key=data.key,
        tags=data.tags,
        price=data.price,
        description=data.description,
        created_by=created_by,
    )
    db.add(pack)
    await db.commit()
    await db.refresh(pack)
    return pack


async def add_stem_to_pack(
    db: AsyncSession,
    pack_id: uuid.UUID,
    file: UploadFile,
    data: StemCreate,
) -> Stem:
    pack = await db.get(StemPack, pack_id)
    if not pack:
        raise NotFoundError("StemPack not found")

    wav_bytes = await validate_wav_upload(file)
    preview_mp3 = generate_preview_mp3(wav_bytes)
    aes_key, aes_iv = encryption_service.generate_key_and_iv()
    encrypted_wav = encryption_service.encrypt_bytes(wav_bytes, aes_key, aes_iv)

    stem_id = str(uuid.uuid4())
    enc_key = s3_service.s3_key_for_encrypted_stem(stem_id)
    prev_key = s3_service.s3_key_for_stem_preview(stem_id)
    await s3_service.upload_bytes(enc_key, encrypted_wav)
    await s3_service.upload_bytes(prev_key, preview_mp3, "audio/mpeg")

    stem = Stem(
        id=uuid.UUID(stem_id),
        stem_pack_id=pack_id,
        label=data.label,
        file_s3_key=enc_key,
        preview_s3_key=prev_key,
        aes_key=aes_key,
        aes_iv=aes_iv,
        duration=data.duration,
    )
    db.add(stem)
    await db.commit()
    await db.refresh(stem)
    return stem


async def get_stem_pack_with_stems(db: AsyncSession, pack_id: uuid.UUID) -> StemPack:
    pack = await db.get(StemPack, pack_id)
    if not pack:
        raise NotFoundError("StemPack not found")
    stems = await db.scalars(select(Stem).where(Stem.stem_pack_id == pack_id))
    pack.__dict__["stems"] = list(stems.all())
    return pack


async def check_stem_pack_entitlement(db: AsyncSession, user: User, pack_id: uuid.UUID) -> None:
    purchase = await db.scalar(
        select(Purchase).where(
            Purchase.user_id == user.id,
            Purchase.stem_pack_id == pack_id,
        )
    )
    if not purchase:
        raise EntitlementError("Purchase this stem pack to download")
```

**Step 2: Commit**

```bash
git add app/services/stem_pack_service.py
git commit -m "feat: add StemPack service (create pack, add stems, entitlement)"
```

---

### Task 21: Payment service (Stripe)

**Files:**
- Create: `app/services/payment_service.py`

**Step 1: Write `app/services/payment_service.py`**

```python
import stripe
import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.models.purchase import Purchase, PurchaseType
from app.models.loop import Loop
from app.models.stem_pack import StemPack
from app.models.user import User
from app.exceptions import NotFoundError, PaymentError
from app.schemas.purchase import CheckoutRequest

settings = get_settings()
stripe.api_key = settings.stripe_secret_key


async def create_checkout_session(
    db: AsyncSession,
    user: User,
    request: CheckoutRequest,
) -> dict:
    if request.loop_id:
        product = await db.get(Loop, request.loop_id)
        if not product:
            raise NotFoundError("Loop not found")
        name = product.title
        price_cents = int(product.price * 100)
        metadata = {"loop_id": str(request.loop_id), "user_id": str(user.id)}
    else:
        product = await db.get(StemPack, request.stem_pack_id)
        if not product:
            raise NotFoundError("StemPack not found")
        name = product.title
        price_cents = int(product.price * 100)
        metadata = {"stem_pack_id": str(request.stem_pack_id), "user_id": str(user.id)}

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": price_cents,
                    "product_data": {"name": name},
                },
                "quantity": 1,
            }],
            mode="payment",
            metadata=metadata,
            customer_email=user.email,
            success_url="https://litmusic.app/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://litmusic.app/cancel",
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except stripe.StripeError as e:
        raise PaymentError(str(e))


async def handle_webhook(db: AsyncSession, payload: bytes, sig_header: str) -> None:
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.SignatureVerificationError):
        raise PaymentError("Invalid webhook signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        loop_id = metadata.get("loop_id")
        stem_pack_id = metadata.get("stem_pack_id")
        amount = Decimal(session["amount_total"]) / 100

        # Idempotency: skip if purchase already recorded
        existing = await db.scalar(
            select(Purchase).where(
                Purchase.stripe_payment_intent_id == session["payment_intent"]
            )
        )
        if existing:
            return

        purchase = Purchase(
            user_id=uuid.UUID(user_id),
            loop_id=uuid.UUID(loop_id) if loop_id else None,
            stem_pack_id=uuid.UUID(stem_pack_id) if stem_pack_id else None,
            stripe_payment_intent_id=session["payment_intent"],
            amount_paid=amount,
            purchase_type=PurchaseType.one_time,
        )
        db.add(purchase)
        await db.commit()

        # Trigger notification task (imported lazily to avoid circular)
        from app.tasks.notification_tasks import send_purchase_confirmation
        send_purchase_confirmation.delay(str(user_id), str(purchase.id))
```

**Step 2: Commit**

```bash
git add app/services/payment_service.py
git commit -m "feat: add Stripe payment service (checkout + webhook handler)"
```

---

### Task 22: OneSignal notification service

**Files:**
- Create: `app/services/onesignal_service.py`

**Step 1: Write `app/services/onesignal_service.py`**

```python
import httpx
from app.config import get_settings

settings = get_settings()
ONESIGNAL_API_URL = "https://onesignal.com/api/v1/notifications"


async def send_notification(
    player_id: str,
    title: str,
    message: str,
    data: dict | None = None,
) -> bool:
    """Send a push notification to a single device. Returns True on success."""
    payload = {
        "app_id": settings.onesignal_app_id,
        "include_player_ids": [player_id],
        "headings": {"en": title},
        "contents": {"en": message},
        "data": data or {},
    }
    headers = {
        "Authorization": f"Basic {settings.onesignal_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(ONESIGNAL_API_URL, json=payload, headers=headers)
        return response.status_code == 200


async def send_purchase_confirmation_notification(player_id: str, loop_title: str) -> bool:
    return await send_notification(
        player_id=player_id,
        title="Purchase Successful!",
        message=f'You now own "{loop_title}". Download it anytime.',
        data={"type": "purchase_confirmation"},
    )


async def send_new_loop_notification(player_id: str, genre: str, loop_title: str, loop_id: str) -> bool:
    return await send_notification(
        player_id=player_id,
        title=f"New {genre} Loop!",
        message=f'"{loop_title}" just dropped. Check it out.',
        data={"type": "new_loop", "loop_id": loop_id},
    )
```

**Step 2: Write failing test**

```python
# tests/services/test_onesignal_service.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.onesignal_service import send_notification


@pytest.mark.asyncio
async def test_send_notification_calls_api(monkeypatch):
    mock_response = AsyncMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.services.onesignal_service.httpx.AsyncClient", return_value=mock_client):
        result = await send_notification("player-1", "Title", "Body")
    assert result is True
```

**Step 3: Run test**

```bash
pytest tests/services/test_onesignal_service.py -v
```
Expected: PASS

**Step 4: Commit**

```bash
git add app/services/onesignal_service.py tests/services/test_onesignal_service.py
git commit -m "feat: add OneSignal push notification service"
```

---

## Phase 7: Middleware

---

### Task 23: Request ID and structured logging middleware

**Files:**
- Create: `app/middleware/logging_middleware.py`

**Step 1: Write `app/middleware/logging_middleware.py`**

```python
import uuid
import time
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response
```

**Step 2: Commit**

```bash
git add app/middleware/logging_middleware.py
git commit -m "feat: add structured JSON logging middleware with request IDs"
```

---

### Task 24: Auth dependency and rate limiting middleware

**Files:**
- Create: `app/middleware/auth_middleware.py`
- Create: `app/middleware/rate_limit.py`

**Step 1: Write `app/middleware/auth_middleware.py`**

```python
from fastapi import Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from app.database import get_db
from app.services.auth_service import decode_access_token, get_user_by_id
from app.models.user import User, UserRole
from app.exceptions import UnauthorizedError, ForbiddenError

bearer = HTTPBearer()


async def get_redis() -> Redis:
    from app.config import get_settings
    settings = get_settings()
    r = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield r
    finally:
        await r.aclose()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_access_token(token)
    user = await get_user_by_id(db, payload["sub"])
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise ForbiddenError("Admin access required")
    return user
```

**Step 2: Write `app/middleware/rate_limit.py`**

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

**Step 3: Commit**

```bash
git add app/middleware/auth_middleware.py app/middleware/rate_limit.py
git commit -m "feat: add auth dependency, admin guard, and rate limiter"
```

---

## Phase 8: Routers

---

### Task 25: Auth router

**Files:**
- Create: `app/routers/auth.py`

**Step 1: Write `app/routers/auth.py`**

```python
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from app.database import get_db
from app.middleware.auth_middleware import get_current_user, get_redis
from app.middleware.rate_limit import limiter
from app.services import auth_service
from app.schemas.user import UserRegister, UserLogin, UserResponse, TokenResponse, RefreshRequest
from app.schemas.common import success

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
@limiter.limit("10/minute")
async def register(request: Request, body: UserRegister, db: AsyncSession = Depends(get_db)):
    user = await auth_service.register_user(db, body.email, body.password, body.full_name)
    return success(UserResponse.model_validate(user).model_dump(), "Registration successful")


@router.post("/login")
@limiter.limit("20/minute")
async def login(
    request: Request,
    body: UserLogin,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    user = await auth_service.authenticate_user(db, body.email, body.password)
    access_token = auth_service.create_access_token(str(user.id), user.role.value)
    refresh_token = auth_service.create_refresh_token()
    await auth_service.store_refresh_token(redis, refresh_token, str(user.id))
    return success(
        TokenResponse(access_token=access_token, refresh_token=refresh_token).model_dump(),
        "Login successful",
    )


@router.post("/refresh")
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    user_id = await auth_service.validate_refresh_token(redis, body.refresh_token)
    user = await auth_service.get_user_by_id(db, user_id)
    await auth_service.revoke_refresh_token(redis, body.refresh_token)
    new_refresh = auth_service.create_refresh_token()
    await auth_service.store_refresh_token(redis, new_refresh, user_id)
    access_token = auth_service.create_access_token(user_id, user.role.value)
    return success(
        TokenResponse(access_token=access_token, refresh_token=new_refresh).model_dump(),
        "Token refreshed",
    )


@router.post("/logout")
async def logout(
    body: RefreshRequest,
    redis: Redis = Depends(get_redis),
):
    await auth_service.revoke_refresh_token(redis, body.refresh_token)
    return success(message="Logged out")


@router.get("/me")
async def me(user=Depends(get_current_user)):
    return success(UserResponse.model_validate(user).model_dump())
```

**Step 2: Commit**

```bash
git add app/routers/auth.py
git commit -m "feat: add auth router (register, login, refresh, logout, me)"
```

---

### Task 26: Loops router

**Files:**
- Create: `app/routers/loops.py`

**Step 1: Write `app/routers/loops.py`**

```python
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.middleware.rate_limit import limiter
from app.services import loop_service, s3_service
from app.schemas.loop import LoopFilter, LoopResponse
from app.schemas.common import success
from app.models.loop import Genre, TempoFeel
import uuid

router = APIRouter(prefix="/loops", tags=["loops"])


@router.get("")
async def list_loops(
    genre: Genre | None = None,
    bpm_min: int | None = None,
    bpm_max: int | None = None,
    key: str | None = None,
    tempo_feel: TempoFeel | None = None,
    is_free: bool | None = None,
    sort: str = "newest",
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    filters = LoopFilter(
        genre=genre, bpm_min=bpm_min, bpm_max=bpm_max,
        key=key, tempo_feel=tempo_feel, is_free=is_free,
        sort=sort, page=page, page_size=page_size,
    )
    loops, total = await loop_service.list_loops(db, filters)
    return success({
        "items": [LoopResponse.model_validate(l).model_dump() for l in loops],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.get("/{loop_id}")
async def get_loop(loop_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    loop = await loop_service.get_loop(db, loop_id)
    return success(LoopResponse.model_validate(loop).model_dump())


@router.get("/{loop_id}/preview")
async def stream_preview(loop_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    loop = await loop_service.get_loop(db, loop_id)
    url = await s3_service.generate_presigned_url(loop.preview_s3_key, expiry_seconds=300)
    # Proxy the MP3 stream
    async def _stream():
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url) as resp:
                async for chunk in resp.aiter_bytes(8192):
                    yield chunk
    return StreamingResponse(_stream(), media_type="audio/mpeg")


@router.post("/{loop_id}/play")
async def record_play(loop_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await loop_service.increment_play_count(db, loop_id)
    return success(message="Play recorded")


@router.get("/{loop_id}/download")
async def download_loop(
    loop_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    from datetime import datetime, timedelta, timezone
    from app.models.download import Download

    loop = await loop_service.get_loop(db, loop_id)
    await loop_service.check_download_entitlement(db, user, loop)

    signed_url = await s3_service.generate_presigned_url(loop.file_s3_key, expiry_seconds=900)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    dl = Download(
        user_id=user.id,
        loop_id=loop.id,
        download_url=signed_url,
        expires_at=expires_at,
    )
    db.add(dl)
    loop.download_count += 1
    await db.commit()

    return success({
        "signed_url": signed_url,
        "aes_key": loop.aes_key,
        "aes_iv": loop.aes_iv,
        "expires_in_seconds": 900,
    })
```

**Step 2: Commit**

```bash
git add app/routers/loops.py
git commit -m "feat: add loops router (list, detail, preview, play, download)"
```

---

### Task 27: StemPacks router

**Files:**
- Create: `app/routers/stem_packs.py`

**Step 1: Write `app/routers/stem_packs.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.services import stem_pack_service, s3_service
from app.models.stem_pack import Stem
from app.schemas.stem_pack import StemPackResponse
from app.schemas.common import success
from app.models.download import Download
from datetime import datetime, timedelta, timezone
import uuid

router = APIRouter(prefix="/stem-packs", tags=["stem-packs"])


@router.get("")
async def list_stem_packs(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func
    from app.models.stem_pack import StemPack
    q = select(StemPack).offset((page - 1) * page_size).limit(page_size)
    packs = await db.scalars(q)
    return success({"items": [StemPackResponse.model_validate(p).model_dump() for p in packs.all()]})


@router.get("/{pack_id}")
async def get_stem_pack(pack_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    pack = await stem_pack_service.get_stem_pack_with_stems(db, pack_id)
    return success(StemPackResponse.model_validate(pack).model_dump())


@router.get("/{pack_id}/download")
async def download_stem_pack(
    pack_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    await stem_pack_service.check_stem_pack_entitlement(db, user, pack_id)
    stems = await db.scalars(select(Stem).where(Stem.stem_pack_id == pack_id))
    stem_list = list(stems.all())

    download_links = []
    for stem in stem_list:
        signed_url = await s3_service.generate_presigned_url(stem.file_s3_key, expiry_seconds=900)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        dl = Download(
            user_id=user.id,
            stem_id=stem.id,
            download_url=signed_url,
            expires_at=expires_at,
        )
        db.add(dl)
        download_links.append({
            "stem_id": str(stem.id),
            "label": stem.label,
            "signed_url": signed_url,
            "aes_key": stem.aes_key,
            "aes_iv": stem.aes_iv,
            "expires_in_seconds": 900,
        })

    await db.commit()
    return success({"stems": download_links})
```

**Step 2: Commit**

```bash
git add app/routers/stem_packs.py
git commit -m "feat: add stem-packs router (list, detail, download)"
```

---

### Task 28: Payments router

**Files:**
- Create: `app/routers/payments.py`

**Step 1: Write `app/routers/payments.py`**

```python
from fastapi import APIRouter, Depends, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.middleware.rate_limit import limiter
from app.services import payment_service
from app.schemas.purchase import CheckoutRequest
from app.schemas.common import success

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/create-checkout")
@limiter.limit("10/minute")
async def create_checkout(
    request: Request,
    body: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await payment_service.create_checkout_session(db, user, body)
    return success(result, "Checkout session created")


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str = Header(None, alias="stripe-signature"),
):
    payload = await request.body()
    await payment_service.handle_webhook(db, payload, stripe_signature)
    return {"received": True}
```

**Step 2: Commit**

```bash
git add app/routers/payments.py
git commit -m "feat: add payments router (checkout creation, Stripe webhook)"
```

---

### Task 29: Admin router

**Files:**
- Create: `app/routers/admin.py`

**Step 1: Write `app/routers/admin.py`**

```python
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
from app.database import get_db
from app.middleware.auth_middleware import require_admin
from app.services import loop_service, stem_pack_service
from app.schemas.loop import LoopCreate, LoopUpdate, LoopResponse
from app.schemas.stem_pack import StemPackCreate, StemCreate, StemPackResponse, StemResponse
from app.schemas.common import success
from app.models.loop import Genre, TempoFeel
import uuid

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/loops")
async def upload_loop(
    file: UploadFile = File(...),
    title: str = Form(...),
    genre: Genre = Form(...),
    bpm: int = Form(...),
    key: str = Form(...),
    tempo_feel: TempoFeel = Form(...),
    price: Decimal = Form(...),
    is_free: bool = Form(False),
    tags: str = Form(""),  # comma-separated
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    data = LoopCreate(
        title=title, genre=genre, bpm=bpm, key=key,
        tempo_feel=tempo_feel, price=price, is_free=is_free,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
    )
    loop = await loop_service.create_loop(db, file, data, admin.id)
    # Trigger waveform generation
    from app.tasks.download_tasks import generate_waveform_task
    generate_waveform_task.delay(str(loop.id))
    return success(LoopResponse.model_validate(loop).model_dump(), "Loop uploaded")


@router.put("/loops/{loop_id}")
async def update_loop(
    loop_id: uuid.UUID,
    body: LoopUpdate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    loop = await loop_service.update_loop(db, loop_id, body)
    return success(LoopResponse.model_validate(loop).model_dump(), "Loop updated")


@router.delete("/loops/{loop_id}")
async def delete_loop(
    loop_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    await loop_service.delete_loop(db, loop_id)
    return success(message="Loop deleted")


@router.post("/stem-packs")
async def create_stem_pack(
    body: StemPackCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    pack = await stem_pack_service.create_stem_pack(db, body, admin.id)
    return success(StemPackResponse.model_validate(pack).model_dump(), "StemPack created")


@router.post("/stem-packs/{pack_id}/stems")
async def add_stem(
    pack_id: uuid.UUID,
    file: UploadFile = File(...),
    label: str = Form(...),
    duration: int = Form(...),
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    data = StemCreate(label=label, duration=duration)
    stem = await stem_pack_service.add_stem_to_pack(db, pack_id, file, data)
    return success(StemResponse.model_validate(stem).model_dump(), "Stem added")


@router.put("/stem-packs/{pack_id}")
async def update_stem_pack(
    pack_id: uuid.UUID,
    body: StemPackCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    from app.exceptions import NotFoundError
    from app.models.stem_pack import StemPack
    pack = await db.get(StemPack, pack_id)
    if not pack:
        raise NotFoundError("StemPack not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(pack, field, value)
    await db.commit()
    await db.refresh(pack)
    return success(StemPackResponse.model_validate(pack).model_dump(), "StemPack updated")


@router.delete("/stem-packs/{pack_id}")
async def delete_stem_pack(
    pack_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    from app.models.stem_pack import StemPack, Stem
    from sqlalchemy import select
    from app.services import s3_service
    pack = await db.get(StemPack, pack_id)
    stems = await db.scalars(select(Stem).where(Stem.stem_pack_id == pack_id))
    for stem in stems.all():
        if stem.file_s3_key:
            await s3_service.delete_object(stem.file_s3_key)
        await db.delete(stem)
    await db.delete(pack)
    await db.commit()
    return success(message="StemPack deleted")
```

**Step 2: Commit**

```bash
git add app/routers/admin.py
git commit -m "feat: add admin router (loop upload, stem pack management)"
```

---

## Phase 9: Celery Tasks

---

### Task 30: Celery app and notification tasks

**Files:**
- Create: `app/tasks/celery_app.py`
- Create: `app/tasks/notification_tasks.py`
- Create: `app/tasks/download_tasks.py`
- Create: `app/tasks/scheduled_tasks.py`

**Step 1: Write `app/tasks/celery_app.py`**

```python
from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "litmusic",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.notification_tasks",
        "app.tasks.download_tasks",
        "app.tasks.scheduled_tasks",
    ],
)

celery_app.conf.beat_schedule = {
    "cleanup-expired-downloads-hourly": {
        "task": "app.tasks.download_tasks.cleanup_expired_downloads",
        "schedule": 3600.0,
    },
}
celery_app.conf.timezone = "UTC"
```

**Step 2: Write `app/tasks/notification_tasks.py`**

```python
import asyncio
from app.tasks.celery_app import celery_app


@celery_app.task(name="notification_tasks.send_purchase_confirmation")
def send_purchase_confirmation(user_id: str, purchase_id: str):
    async def _run():
        from app.database import AsyncSessionLocal
        from app.models.user import User
        from app.models.purchase import Purchase
        from app.models.loop import Loop
        from app.models.stem_pack import StemPack
        from app.services.onesignal_service import send_purchase_confirmation_notification
        from sqlalchemy import select
        import uuid

        async with AsyncSessionLocal() as db:
            user = await db.get(User, uuid.UUID(user_id))
            purchase = await db.get(Purchase, uuid.UUID(purchase_id))
            if not user or not purchase or not user.onesignal_player_id:
                return
            if purchase.loop_id:
                product = await db.get(Loop, purchase.loop_id)
            else:
                product = await db.get(StemPack, purchase.stem_pack_id)
            if product:
                await send_purchase_confirmation_notification(
                    user.onesignal_player_id, product.title
                )
    asyncio.run(_run())


@celery_app.task(name="notification_tasks.send_new_loop_notification")
def send_new_loop_notification(loop_id: str):
    async def _run():
        from app.database import AsyncSessionLocal
        from app.models.loop import Loop
        from app.models.user import User
        from app.services.onesignal_service import send_new_loop_notification as _notify
        from sqlalchemy import select
        import uuid

        async with AsyncSessionLocal() as db:
            loop = await db.get(Loop, uuid.UUID(loop_id))
            if not loop:
                return
            # Fan-out: notify all users with onesignal_player_id
            # (v2: filter by favourite genre preference)
            users = await db.scalars(
                select(User).where(User.onesignal_player_id.is_not(None))
            )
            for user in users.all():
                await _notify(
                    user.onesignal_player_id,
                    loop.genre.value,
                    loop.title,
                    loop_id,
                )
    asyncio.run(_run())
```

**Step 3: Write `app/tasks/download_tasks.py`**

```python
import asyncio
from app.tasks.celery_app import celery_app


@celery_app.task(name="download_tasks.generate_waveform_task")
def generate_waveform_task(loop_id: str):
    async def _run():
        import uuid
        import boto3
        from app.database import AsyncSessionLocal
        from app.models.loop import Loop
        from app.services.waveform_service import generate_waveform
        from app.services.encryption_service import decrypt_bytes
        from app.config import get_settings
        import base64

        settings = get_settings()
        async with AsyncSessionLocal() as db:
            loop = await db.get(Loop, uuid.UUID(loop_id))
            if not loop or not loop.file_s3_key:
                return
            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region,
            )
            obj = s3.get_object(Bucket=settings.s3_bucket_name, Key=loop.file_s3_key)
            encrypted = obj["Body"].read()
            wav_bytes = decrypt_bytes(encrypted, loop.aes_key, loop.aes_iv)
            waveform = generate_waveform(wav_bytes)
            loop.waveform_data = waveform
            await db.commit()
    asyncio.run(_run())


@celery_app.task(name="download_tasks.cleanup_expired_downloads")
def cleanup_expired_downloads():
    async def _run():
        from app.database import AsyncSessionLocal
        from app.models.download import Download
        from sqlalchemy import select, delete
        from datetime import datetime, timezone

        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(Download).where(Download.expires_at < datetime.now(timezone.utc))
            )
            await db.commit()
    asyncio.run(_run())
```

**Step 4: Write `app/tasks/scheduled_tasks.py`**

```python
# Reserved for future scheduled tasks (e.g. marketing emails, analytics)
# Currently cleanup_expired_downloads is scheduled via celery beat in celery_app.py
```

**Step 5: Commit**

```bash
git add app/tasks/
git commit -m "feat: add Celery tasks (notifications, waveform generation, cleanup)"
```

---

## Phase 10: Main App Assembly

---

### Task 31: main.py — wire everything together

**Files:**
- Create: `app/main.py`

**Step 1: Write `app/main.py`**

```python
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.config import get_settings
from app.exceptions import AppError, app_error_handler
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.rate_limit import limiter
from app.routers import auth, loops, stem_packs, payments, admin

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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
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
```

**Step 2: Commit**

```bash
git add app/main.py
git commit -m "feat: assemble FastAPI application with all routers and middleware"
```

---

## Phase 11: Docker

---

### Task 32: Dockerfile and docker-compose

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

**Step 1: Write `Dockerfile`**

```dockerfile
FROM python:3.12-slim

# Install ffmpeg and system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 2: Write `docker-compose.yml`**

```yaml
version: "3.9"

services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - .:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: litmusic
      POSTGRES_PASSWORD: litmusic
      POSTGRES_DB: litmusic
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U litmusic"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  worker:
    build: .
    env_file: .env
    depends_on:
      - db
      - redis
    command: celery -A app.tasks.celery_app.celery_app worker --loglevel=info

  beat:
    build: .
    env_file: .env
    depends_on:
      - redis
    command: celery -A app.tasks.celery_app.celery_app beat --loglevel=info

volumes:
  postgres_data:
```

**Step 3: Write `.dockerignore`**

```
__pycache__
*.pyc
*.pyo
.env
.git
.pytest_cache
*.egg-info
dist/
build/
```

**Step 4: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore
git commit -m "feat: add Dockerfile and docker-compose with all services"
```

---

## Phase 12: Seed Script and Tests

---

### Task 33: Database seed script

**Files:**
- Create: `scripts/seed.py`

**Step 1: Write `scripts/seed.py`**

```python
"""
Seed the database with test users and loops.
Run: python scripts/seed.py
"""
import asyncio
import uuid
from decimal import Decimal
from app.database import AsyncSessionLocal, engine, Base
from app.models.user import User, UserRole
from app.models.loop import Loop, Genre, TempoFeel
from app.services.auth_service import hash_password


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        admin = User(
            id=uuid.uuid4(),
            email="admin@litmusic.app",
            password_hash=hash_password("admin1234"),
            full_name="LitMusic Admin",
            role=UserRole.admin,
        )
        user = User(
            id=uuid.uuid4(),
            email="producer@litmusic.app",
            password_hash=hash_password("producer1234"),
            full_name="Test Producer",
            role=UserRole.free,
        )
        db.add_all([admin, user])
        await db.flush()

        loop = Loop(
            id=uuid.uuid4(),
            title="Afro Vibes Loop 1",
            slug="afro-vibes-loop-1-seed",
            genre=Genre.afrobeat,
            bpm=100,
            key="A minor",
            duration=32,
            tempo_feel=TempoFeel.mid,
            tags=["afrobeat", "drums", "vibes"],
            price=Decimal("4.99"),
            is_free=True,
            is_paid=False,
            created_by=admin.id,
        )
        db.add(loop)
        await db.commit()
        print("Seed complete.")
        print(f"  Admin:    admin@litmusic.app / admin1234")
        print(f"  Producer: producer@litmusic.app / producer1234")


if __name__ == "__main__":
    asyncio.run(seed())
```

**Step 2: Commit**

```bash
mkdir -p scripts
git add scripts/seed.py
git commit -m "feat: add database seed script with test users and loops"
```

---

### Task 34: Test fixtures and integration tests

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/routers/test_auth.py`
- Create: `tests/routers/test_loops.py`

**Step 1: Write `tests/conftest.py`**

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.database import Base, get_db
from app.middleware.auth_middleware import get_redis
from unittest.mock import AsyncMock, MagicMock

TEST_DB_URL = "postgresql+asyncpg://litmusic:litmusic@localhost:5432/litmusic_test"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.delete = AsyncMock()
    mock_redis.ping = AsyncMock()
    mock_redis.aclose = AsyncMock()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: mock_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
```

**Step 2: Write `tests/routers/test_auth.py`**

```python
import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "new@test.com",
        "password": "securepass",
        "full_name": "Test User",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["email"] == "new@test.com"


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {"email": "dup@test.com", "password": "pass1234", "full_name": "Dup"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_returns_tokens(client):
    await client.post("/api/v1/auth/register", json={
        "email": "user@test.com", "password": "pass1234", "full_name": "User"
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "user@test.com", "password": "pass1234"
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/register", json={
        "email": "x@test.com", "password": "correct", "full_name": "X"
    })
    resp = await client.post("/api/v1/auth/login", json={"email": "x@test.com", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 403
```

**Step 3: Write `tests/routers/test_loops.py`**

```python
import pytest
import uuid
from decimal import Decimal
from app.models.loop import Loop, Genre, TempoFeel
from app.models.user import User, UserRole
from app.services.auth_service import hash_password, create_access_token


async def _create_user(db, role=UserRole.free):
    user = User(
        id=uuid.uuid4(), email=f"{uuid.uuid4()}@test.com",
        password_hash=hash_password("pass"), full_name="Test", role=role,
    )
    db.add(user)
    await db.commit()
    return user


async def _create_loop(db, user_id, is_free=True):
    loop = Loop(
        id=uuid.uuid4(), title="Test Loop", slug=f"test-loop-{uuid.uuid4().hex[:6]}",
        genre=Genre.afrobeat, bpm=100, key="C major", duration=30,
        tempo_feel=TempoFeel.mid, tags=["test"], price=Decimal("4.99"),
        is_free=is_free, is_paid=not is_free, created_by=user_id,
    )
    db.add(loop)
    await db.commit()
    return loop


@pytest.mark.asyncio
async def test_list_loops_public(client, db_session):
    user = await _create_user(db_session)
    await _create_loop(db_session, user.id)
    resp = await client.get("/api/v1/loops")
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] >= 1


@pytest.mark.asyncio
async def test_get_loop_not_found(client):
    resp = await client.get(f"/api/v1/loops/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_free_loop_requires_auth(client, db_session):
    user = await _create_user(db_session)
    loop = await _create_loop(db_session, user.id, is_free=True)
    resp = await client.get(f"/api/v1/loops/{loop.id}/download")
    assert resp.status_code == 403  # no auth header
```

**Step 4: Run all tests**

```bash
pytest tests/ -v
```
Expected: All pass (some may be skipped if test DB unavailable)

**Step 5: Commit**

```bash
git add tests/
git commit -m "test: add auth and loop router integration tests with fixtures"
```

---

## Phase 13: Memory and Final Wiring

---

### Task 35: Apply Alembic migration and smoke test

**Step 1: Start services**

```bash
docker-compose up -d db redis
```

**Step 2: Run migration**

```bash
alembic upgrade head
```
Expected: "Running upgrade ... -> <hash>, initial schema"

**Step 3: Seed database**

```bash
python scripts/seed.py
```
Expected: "Seed complete."

**Step 4: Start API**

```bash
docker-compose up api
```

**Step 5: Verify health**

```bash
curl http://localhost:8000/health
```
Expected:
```json
{"status": "healthy", "database": "ok", "redis": "ok"}
```

**Step 6: Verify OpenAPI docs load**

Open `http://localhost:8000/docs` — should show all routes grouped by tag.

**Step 7: Final commit**

```bash
git add .
git commit -m "chore: verified migration, seed, and health check all pass"
```

---

## Task Dependency Summary

```
Task 1 (structure) → Task 2 (config) → Task 3 (database)
Task 3 → Task 4-7 (models)
Task 7 → Task 8 (alembic)
Task 8 → Task 9-12 (schemas)
Task 12 → Task 13 (exceptions)
Task 13 → Task 14-22 (services)
Task 22 → Task 23-24 (middleware)
Task 24 → Task 25-29 (routers)
Task 29 → Task 30 (celery tasks)
Task 30 → Task 31 (main.py)
Task 31 → Task 32 (docker)
Task 32 → Task 33-34 (seed + tests)
Task 34 → Task 35 (smoke test)
```

---

## Post-Launch Checklist

- [ ] Set all env vars in Railway/Render dashboard (never commit `.env`)
- [ ] Configure Stripe webhook endpoint URL in Stripe dashboard
- [ ] Register OneSignal app and copy App ID + API Key
- [ ] Create S3 bucket with private ACL; set bucket policy
- [ ] Run `alembic upgrade head` on production DB before first deploy
- [ ] Set `APP_ENV=production` to disable SQLAlchemy echo logging
- [ ] Enable HTTPS-only (handled by Railway/Render automatically)
