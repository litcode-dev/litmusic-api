# Subscription Plans + AI Loop Generation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add monthly premium subscriptions (Flutterwave/Paystack + webhooks) that gate AI loop generation via Suno or a self-hosted endpoint, with per-user admin toggles and quota enforcement.

**Architecture:** New `subscriptions` and `ai_generations` tables track billing and generation history. Subscription webhooks create/renew subscriptions and reset monthly quota. The AI router guards every generation request (user enabled → active sub → quota/extra credits), then dispatches a Celery task that calls the provider, converts audio, builds a Loop via existing S3/encryption pipeline, and writes back the result.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL, Redis, Celery, httpx (no SDK), slowapi, ffmpeg (already installed), Alembic.

---

## Task 1: Update User model + create Subscription and AIGeneration models

**Files:**
- Modify: `app/models/user.py`
- Create: `app/models/subscription.py`
- Create: `app/models/ai_generation.py`
- Modify: `app/models/__init__.py`

### Step 1: Add two columns to User

In `app/models/user.py`, add these two imports and columns after the existing `updated_at` column:

```python
# Add to imports
from sqlalchemy import String, DateTime, Enum as SAEnum, func, Boolean, Integer

# Add these two columns inside class User, after updated_at:
ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
ai_extra_credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
```

### Step 2: Create `app/models/subscription.py`

```python
import uuid
import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Integer, Numeric, DateTime, Enum as SAEnum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.purchase import PaymentProvider


class SubscriptionPlan(str, enum.Enum):
    premium = "premium"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    cancelled = "cancelled"
    expired = "expired"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    plan: Mapped[SubscriptionPlan] = mapped_column(SAEnum(SubscriptionPlan), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(SAEnum(SubscriptionStatus), default=SubscriptionStatus.active, nullable=False)
    provider: Mapped[PaymentProvider] = mapped_column(SAEnum(PaymentProvider), nullable=False)
    payment_reference: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    ai_quota: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    ai_quota_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    billing_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### Step 3: Create `app/models/ai_generation.py`

```python
import uuid
import enum
from datetime import datetime
from sqlalchemy import Boolean, Text, DateTime, Enum as SAEnum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class AIProvider(str, enum.Enum):
    suno = "suno"
    self_hosted = "self_hosted"


class AIGenerationStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class AIGeneration(Base):
    __tablename__ = "ai_generations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True)
    provider: Mapped[AIProvider] = mapped_column(SAEnum(AIProvider), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    style_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AIGenerationStatus] = mapped_column(SAEnum(AIGenerationStatus), default=AIGenerationStatus.pending, nullable=False)
    result_loop_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("loops.id"), nullable=True)
    is_extra: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### Step 4: Import new models in `app/models/__init__.py`

Open the file and add:
```python
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus  # noqa: F401
from app.models.ai_generation import AIGeneration, AIProvider, AIGenerationStatus  # noqa: F401
```

### Step 5: Commit
```bash
git add app/models/user.py app/models/subscription.py app/models/ai_generation.py app/models/__init__.py
git commit -m "feat: add Subscription and AIGeneration models, extend User with ai_enabled/ai_extra_credits"
```

---

## Task 2: Alembic migration

**Files:**
- Modify: `alembic/versions/` (autogenerated)

### Step 1: Generate migration

```bash
source .venv/bin/activate
alembic revision --autogenerate -m "add_subscription_ai_generation"
```

### Step 2: Review generated file

Open the new file in `alembic/versions/`. Verify it adds:
- `ai_enabled` (boolean) and `ai_extra_credits` (integer) to `users`
- Creates `subscriptions` table with all columns
- Creates `ai_generations` table with all columns

### Step 3: Apply migration

```bash
alembic upgrade head
```

Expected: no errors. If the DB is managed via `Base.metadata.create_all` (no prior migrations), run:
```bash
alembic stamp head  # mark current DB as up-to-date, then upgrade
```

### Step 4: Commit
```bash
git add alembic/
git commit -m "feat: migration - subscriptions and ai_generations tables"
```

---

## Task 3: Config additions

**Files:**
- Modify: `app/config.py`

### Step 1: Add new settings to the Settings class

Add after the Google OAuth section:

```python
# AI Music Generation
suno_api_key: str = ""
suno_api_url: str = "https://api.suno.ai"
ai_selfhosted_url: str = ""
ai_selfhosted_api_key: str = ""

# Subscription pricing (amounts in kobo/pesewas for Paystack; divide by 100 for Flutterwave)
subscription_monthly_price: int = 200000   # ₦2,000 in kobo
ai_extra_credits_price: int = 50000        # ₦500 in kobo
ai_extra_credits_quantity: int = 5         # slots per extra purchase
```

### Step 2: Add to `.env.example` (or `.env` for local dev)

```
SUNO_API_KEY=
SUNO_API_URL=https://api.suno.ai
AI_SELFHOSTED_URL=
AI_SELFHOSTED_API_KEY=
SUBSCRIPTION_MONTHLY_PRICE=200000
AI_EXTRA_CREDITS_PRICE=50000
AI_EXTRA_CREDITS_QUANTITY=5
```

### Step 3: Commit
```bash
git add app/config.py
git commit -m "feat: add subscription and AI generation config settings"
```

---

## Task 4: Schemas

**Files:**
- Create: `app/schemas/subscription.py`
- Create: `app/schemas/ai_generation.py`

### Step 1: Create `app/schemas/subscription.py`

```python
import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel
from app.models.subscription import SubscriptionPlan, SubscriptionStatus
from app.models.purchase import PaymentProvider


class SubscriptionInitiateRequest(BaseModel):
    provider: PaymentProvider


class ExtraCreditsInitiateRequest(BaseModel):
    provider: PaymentProvider


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    plan: SubscriptionPlan
    status: SubscriptionStatus
    ai_quota: int
    ai_quota_used: int
    billing_period_start: datetime
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
```

### Step 2: Create `app/schemas/ai_generation.py`

```python
import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.ai_generation import AIProvider, AIGenerationStatus


class AIGenerateRequest(BaseModel):
    prompt: str
    style_prompt: str | None = None
    provider: AIProvider


class AIGenerationResponse(BaseModel):
    id: uuid.UUID
    provider: AIProvider
    prompt: str
    style_prompt: str | None
    status: AIGenerationStatus
    result_loop_id: uuid.UUID | None
    is_extra: bool
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

### Step 3: Commit
```bash
git add app/schemas/subscription.py app/schemas/ai_generation.py
git commit -m "feat: add subscription and ai_generation schemas"
```

---

## Task 5: Subscription service

**Files:**
- Create: `app/services/subscription_service.py`

### Step 1: Write the failing test

Create `tests/services/test_subscription_service.py`:

```python
import pytest
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionPlan
from app.models.purchase import PaymentProvider
from app.models.user import User, UserRole
from app.services.auth_service import hash_password
from app.services import subscription_service


async def _create_user(db):
    user = User(
        id=uuid.uuid4(), email=f"{uuid.uuid4()}@test.com",
        password_hash=await hash_password("pass"), full_name="Test",
        role=UserRole.user,
    )
    db.add(user)
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_create_subscription(db_session):
    user = await _create_user(db_session)
    sub = await subscription_service.create_subscription(
        db_session, user.id, PaymentProvider.paystack, "ref-001", Decimal("2000")
    )
    assert sub.status == SubscriptionStatus.active
    assert sub.ai_quota == 10
    assert sub.ai_quota_used == 0
    assert sub.expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_get_active_subscription_returns_none_when_expired(db_session):
    user = await _create_user(db_session)
    now = datetime.now(timezone.utc)
    expired_sub = Subscription(
        id=uuid.uuid4(), user_id=user.id, plan=SubscriptionPlan.premium,
        status=SubscriptionStatus.active, provider=PaymentProvider.paystack,
        payment_reference="expired-ref", amount_paid=Decimal("2000"),
        ai_quota=10, ai_quota_used=0,
        billing_period_start=now - timedelta(days=31),
        expires_at=now - timedelta(days=1),
    )
    db_session.add(expired_sub)
    await db_session.commit()
    result = await subscription_service.get_active_subscription(db_session, user.id)
    assert result is None


@pytest.mark.asyncio
async def test_renew_creates_new_row_and_expires_old(db_session):
    user = await _create_user(db_session)
    sub = await subscription_service.create_subscription(
        db_session, user.id, PaymentProvider.paystack, "ref-002", Decimal("2000")
    )
    sub.ai_quota_used = 7
    await db_session.commit()

    new_sub = await subscription_service.renew_subscription(
        db_session, user.id, PaymentProvider.paystack, "ref-003", Decimal("2000")
    )
    await db_session.refresh(sub)
    assert sub.status == SubscriptionStatus.expired
    assert new_sub.ai_quota_used == 0
    assert new_sub.status == SubscriptionStatus.active
```

### Step 2: Run test to verify it fails

```bash
source .venv/bin/activate && python -m pytest tests/services/test_subscription_service.py -v
```
Expected: FAIL — `ImportError: cannot import name 'subscription_service'`

### Step 3: Create `app/services/subscription_service.py`

```python
import uuid
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
from app.models.ai_generation import AIGeneration, AIGenerationStatus
from app.models.purchase import PaymentProvider
from app.models.user import User
from app.exceptions import AppError
from app.services import flutterwave_service, paystack_service


async def get_active_subscription(db: AsyncSession, user_id: uuid.UUID) -> Subscription | None:
    now = datetime.now(timezone.utc)
    return await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.active,
            Subscription.expires_at > now,
        )
    )


async def create_subscription(
    db: AsyncSession,
    user_id: uuid.UUID,
    provider: PaymentProvider,
    payment_reference: str,
    amount: Decimal,
) -> Subscription:
    now = datetime.now(timezone.utc)
    sub = Subscription(
        user_id=user_id,
        plan=SubscriptionPlan.premium,
        status=SubscriptionStatus.active,
        provider=provider,
        payment_reference=payment_reference,
        amount_paid=amount,
        ai_quota=10,
        ai_quota_used=0,
        billing_period_start=now,
        expires_at=now + timedelta(days=30),
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub


async def renew_subscription(
    db: AsyncSession,
    user_id: uuid.UUID,
    provider: PaymentProvider,
    payment_reference: str,
    amount: Decimal,
) -> Subscription:
    """Expire the current active subscription and create a fresh one for the new period."""
    existing = await get_active_subscription(db, user_id)
    if existing:
        existing.status = SubscriptionStatus.expired
        await db.commit()
    return await create_subscription(db, user_id, provider, payment_reference, amount)


async def _process_subscription_webhook(
    db: AsyncSession,
    user_id: str,
    payment_reference: str,
    amount: Decimal,
    provider: PaymentProvider,
) -> None:
    """Create or renew subscription based on whether user already has one."""
    uid = uuid.UUID(user_id)
    existing = await get_active_subscription(db, uid)
    if existing:
        await renew_subscription(db, uid, provider, payment_reference, amount)
    else:
        await create_subscription(db, uid, provider, payment_reference, amount)


async def _process_extras_webhook(
    db: AsyncSession, user_id: str, quantity: int
) -> None:
    user = await db.get(User, uuid.UUID(user_id))
    if not user:
        return
    user.ai_extra_credits += quantity
    await db.commit()


async def handle_flutterwave_webhook(
    db: AsyncSession, payload: bytes, verif_hash: str
) -> None:
    if not flutterwave_service.verify_webhook_signature(verif_hash):
        raise AppError("Invalid webhook signature", status_code=400)

    event = json.loads(payload)
    if event.get("event") != "charge.completed":
        return
    data = event.get("data", {})
    if data.get("status") != "successful":
        return

    tx_ref = data.get("tx_ref")
    transaction_id = str(data.get("id"))
    amount = Decimal(str(data.get("amount", 0)))

    verification = await flutterwave_service.verify_transaction(transaction_id)
    if verification.get("data", {}).get("status") != "successful":
        return

    # Deduplicate by payment_reference
    existing = await db.scalar(
        select(Subscription).where(Subscription.payment_reference == tx_ref)
    )
    if existing:
        return

    meta = data.get("meta", {})
    user_id = meta.get("user_id")
    payment_type = meta.get("type")

    if payment_type == "subscription":
        await _process_subscription_webhook(
            db, user_id, tx_ref, amount, PaymentProvider.flutterwave
        )
    elif payment_type == "ai_extras":
        from app.config import get_settings
        quantity = meta.get("quantity", get_settings().ai_extra_credits_quantity)
        await _process_extras_webhook(db, user_id, int(quantity))


async def handle_paystack_webhook(
    db: AsyncSession, payload: bytes, x_paystack_signature: str
) -> None:
    if not paystack_service.verify_webhook_signature(payload, x_paystack_signature):
        raise AppError("Invalid webhook signature", status_code=400)

    event = json.loads(payload)
    if event.get("event") != "charge.success":
        return
    data = event.get("data", {})
    reference = data.get("reference")
    amount = Decimal(str(data.get("amount", 0))) / 100

    verification = await paystack_service.verify_transaction(reference)
    if not verification.get("status") or verification.get("data", {}).get("status") != "success":
        return

    existing = await db.scalar(
        select(Subscription).where(Subscription.payment_reference == reference)
    )
    if existing:
        return

    meta = data.get("metadata", {})
    user_id = meta.get("user_id")
    payment_type = meta.get("type")

    if payment_type == "subscription":
        await _process_subscription_webhook(
            db, user_id, reference, amount, PaymentProvider.paystack
        )
    elif payment_type == "ai_extras":
        from app.config import get_settings
        quantity = meta.get("quantity", get_settings().ai_extra_credits_quantity)
        await _process_extras_webhook(db, user_id, int(quantity))
```

### Step 4: Run tests to verify they pass

```bash
source .venv/bin/activate && python -m pytest tests/services/test_subscription_service.py -v
```
Expected: all 3 tests PASS

### Step 5: Commit
```bash
git add app/services/subscription_service.py tests/services/test_subscription_service.py
git commit -m "feat: add subscription_service with create/renew/webhook handlers"
```

---

## Task 6: AI service (provider abstraction)

**Files:**
- Create: `app/services/ai_service.py`

### Step 1: Write the failing test

Create `tests/services/test_ai_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services import ai_service
from app.models.ai_generation import AIProvider


@pytest.mark.asyncio
async def test_generate_audio_suno_calls_suno(monkeypatch):
    mock_bytes = b"fake-audio"
    monkeypatch.setattr(ai_service, "_call_suno", AsyncMock(return_value=mock_bytes))
    result = await ai_service.generate_audio(AIProvider.suno, "chill afrobeat", None)
    assert result == mock_bytes


@pytest.mark.asyncio
async def test_generate_audio_self_hosted_calls_self_hosted(monkeypatch):
    mock_bytes = b"fake-wav"
    monkeypatch.setattr(ai_service, "_call_self_hosted", AsyncMock(return_value=mock_bytes))
    result = await ai_service.generate_audio(AIProvider.self_hosted, "lo-fi trap", "dark")
    assert result == mock_bytes


@pytest.mark.asyncio
async def test_self_hosted_raises_when_url_not_configured():
    from app.exceptions import AppError
    with patch("app.services.ai_service.get_settings") as mock_settings:
        mock_settings.return_value.ai_selfhosted_url = ""
        with pytest.raises(AppError, match="not configured"):
            await ai_service._call_self_hosted("prompt", None)
```

### Step 2: Run test to verify it fails

```bash
source .venv/bin/activate && python -m pytest tests/services/test_ai_service.py -v
```
Expected: FAIL — `ImportError`

### Step 3: Create `app/services/ai_service.py`

```python
import asyncio
import httpx
from app.config import get_settings
from app.models.ai_generation import AIProvider
from app.exceptions import AppError


async def _call_suno(prompt: str, style_prompt: str | None) -> bytes:
    """Call Suno API: submit generation, poll until complete, return audio bytes (MP3)."""
    settings = get_settings()
    if not settings.suno_api_key:
        raise AppError("Suno API key not configured", status_code=503)

    headers = {"Authorization": f"Bearer {settings.suno_api_key}"}
    payload = {"prompt": prompt, "make_instrumental": True, "wait_audio": False}
    if style_prompt:
        payload["tags"] = style_prompt

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.suno_api_url}/api/generate",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        clips = resp.json()

    clip_id = clips[0]["id"]
    audio_url: str | None = None

    for _ in range(60):  # poll up to 5 minutes (60 × 5s)
        await asyncio.sleep(5)
        async with httpx.AsyncClient(timeout=15.0) as client:
            poll = await client.get(
                f"{settings.suno_api_url}/api/get?ids={clip_id}",
                headers=headers,
            )
            poll.raise_for_status()
            items = poll.json()

        clip = items[0]
        if clip.get("status") == "streaming":
            audio_url = clip["audio_url"]
            break
        if clip.get("status") in ("error", "failed"):
            raise AppError(f"Suno generation failed: {clip.get('error', 'unknown')}")

    if not audio_url:
        raise AppError("Suno generation timed out after 5 minutes")

    async with httpx.AsyncClient(timeout=60.0) as client:
        audio_resp = await client.get(audio_url)
        audio_resp.raise_for_status()
        return audio_resp.content


async def _call_self_hosted(prompt: str, style_prompt: str | None) -> bytes:
    """Call self-hosted generation API. Expects a POST /generate returning audio bytes (WAV)."""
    settings = get_settings()
    if not settings.ai_selfhosted_url:
        raise AppError("Self-hosted AI URL not configured", status_code=503)

    headers = {}
    if settings.ai_selfhosted_api_key:
        headers["Authorization"] = f"Bearer {settings.ai_selfhosted_api_key}"

    payload: dict = {"prompt": prompt}
    if style_prompt:
        payload["style"] = style_prompt

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.ai_selfhosted_url}/generate",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.content


async def generate_audio(
    provider: AIProvider, prompt: str, style_prompt: str | None
) -> bytes:
    """Dispatch to the correct AI provider. Returns raw audio bytes."""
    if provider == AIProvider.suno:
        return await _call_suno(prompt, style_prompt)
    if provider == AIProvider.self_hosted:
        return await _call_self_hosted(prompt, style_prompt)
    raise AppError(f"Unknown AI provider: {provider}", status_code=400)
```

### Step 4: Run tests to verify they pass

```bash
source .venv/bin/activate && python -m pytest tests/services/test_ai_service.py -v
```
Expected: all 3 tests PASS

### Step 5: Commit
```bash
git add app/services/ai_service.py tests/services/test_ai_service.py
git commit -m "feat: add ai_service with Suno and self-hosted provider abstraction"
```

---

## Task 7: Add `convert_mp3_to_wav` to ffmpeg helpers

**Files:**
- Modify: `app/utils/ffmpeg_helpers.py`

Suno returns MP3. The loop pipeline expects WAV (soundfile reads it). Add this function:

### Step 1: Add function to `app/utils/ffmpeg_helpers.py`

```python
def convert_mp3_to_wav(mp3_bytes: bytes) -> bytes:
    """Convert MP3 bytes to WAV bytes using ffmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_in:
        tmp_in.write(mp3_bytes)
        tmp_in_path = tmp_in.name

    tmp_out_path = str(Path(tmp_in_path).with_suffix("")) + "_converted.wav"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_in_path, "-ar", "44100", "-ac", "2", tmp_out_path],
            check=True,
            capture_output=True,
        )
        with open(tmp_out_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_in_path):
            os.unlink(tmp_in_path)
        if os.path.exists(tmp_out_path):
            os.unlink(tmp_out_path)
```

### Step 2: Commit
```bash
git add app/utils/ffmpeg_helpers.py
git commit -m "feat: add convert_mp3_to_wav helper using ffmpeg"
```

---

## Task 8: AI Celery task

**Files:**
- Create: `app/tasks/ai_tasks.py`
- Modify: `app/tasks/celery_app.py`

### Step 1: Create `app/tasks/ai_tasks.py`

The task pattern mirrors `download_tasks.py`: define an inner `async def _run()` and call `asyncio.run(_run())`.

```python
import asyncio
from decimal import Decimal
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def generate_ai_loop_task(self, generation_id: str):
    asyncio.run(_run(generation_id))


async def _run(generation_id: str):
    import uuid
    import io
    import soundfile as sf
    from app.database import AsyncSessionLocal
    from app.models.ai_generation import AIGeneration, AIGenerationStatus, AIProvider
    from app.models.loop import Loop, Genre, TempoFeel
    from app.models.subscription import Subscription
    from app.models.user import User
    from app.services import ai_service, s3_service, encryption_service
    from app.services.loop_service import _slugify
    from app.utils.ffmpeg_helpers import generate_preview_mp3, convert_mp3_to_wav
    from app.tasks.download_tasks import generate_waveform_task

    async with AsyncSessionLocal() as db:
        gen = await db.get(AIGeneration, uuid.UUID(generation_id))
        if not gen:
            return

        gen.status = AIGenerationStatus.processing
        await db.commit()

        try:
            # Call AI provider
            audio_bytes = await ai_service.generate_audio(
                gen.provider, gen.prompt, gen.style_prompt
            )

            # Suno returns MP3 — convert to WAV for the pipeline
            if gen.provider == AIProvider.suno:
                wav_bytes = convert_mp3_to_wav(audio_bytes)
            else:
                wav_bytes = audio_bytes  # self-hosted must return WAV

            # Build Loop using the same pipeline as create_loop()
            loop_id = str(uuid.uuid4())
            aes_key, aes_iv = encryption_service.generate_key_and_iv()
            encrypted_wav = encryption_service.encrypt_bytes(wav_bytes, aes_key, aes_iv)
            preview_mp3 = generate_preview_mp3(wav_bytes)

            enc_key = s3_service.s3_key_for_encrypted_loop(loop_id)
            prev_key = s3_service.s3_key_for_loop_preview(loop_id)
            await s3_service.upload_bytes(enc_key, encrypted_wav)
            await s3_service.upload_bytes(prev_key, preview_mp3, "audio/mpeg")

            audio_data, sr = sf.read(io.BytesIO(wav_bytes))
            duration = int(len(audio_data) / sr)

            title = gen.prompt[:100]
            loop = Loop(
                id=uuid.UUID(loop_id),
                title=title,
                slug=_slugify(title, loop_id),
                genre=Genre.afrobeat,       # sensible default; producer can update
                bpm=120,
                key="C major",
                duration=duration,
                tempo_feel=TempoFeel.mid,
                tags=["ai-generated"],
                price=Decimal("0"),
                is_free=True,
                is_paid=False,
                file_s3_key=enc_key,
                preview_s3_key=prev_key,
                aes_key=aes_key,
                aes_iv=aes_iv,
                created_by=gen.user_id,
            )
            db.add(loop)
            gen.result_loop_id = loop.id
            gen.status = AIGenerationStatus.completed
            await db.commit()

            # Queue waveform generation
            generate_waveform_task.delay(loop_id)

        except Exception as exc:
            gen.status = AIGenerationStatus.failed
            gen.error_message = str(exc)[:500]

            # Refund quota or extra credit
            if gen.is_extra:
                user = await db.get(User, gen.user_id)
                if user:
                    user.ai_extra_credits += 1
            elif gen.subscription_id:
                sub = await db.get(Subscription, gen.subscription_id)
                if sub and sub.ai_quota_used > 0:
                    sub.ai_quota_used -= 1

            await db.commit()
            raise
```

### Step 2: Add `ai_tasks` to celery_app include list

In `app/tasks/celery_app.py`, update the `include` list:

```python
include=[
    "app.tasks.notification_tasks",
    "app.tasks.download_tasks",
    "app.tasks.scheduled_tasks",
    "app.tasks.ai_tasks",
],
```

### Step 3: Commit
```bash
git add app/tasks/ai_tasks.py app/tasks/celery_app.py
git commit -m "feat: add Celery AI generation task with quota refund on failure"
```

---

## Task 9: Rate limiting — user-ID key function

**Files:**
- Modify: `app/middleware/rate_limit.py`

### Step 1: Add user-ID-keyed limiter

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

limiter = Limiter(key_func=get_remote_address)


def _get_user_id_key(request: Request) -> str:
    """Key AI rate limits by user ID (extracted from JWT), falling back to IP."""
    from app.services.auth_service import decode_access_token
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = decode_access_token(auth[7:])
            return f"user:{payload.get('sub', '')}"
        except Exception:
            pass
    return get_remote_address(request)


ai_limiter = Limiter(key_func=_get_user_id_key)
```

### Step 2: Commit
```bash
git add app/middleware/rate_limit.py
git commit -m "feat: add user-ID-keyed ai_limiter for AI endpoint rate limiting"
```

---

## Task 10: Subscriptions router

**Files:**
- Create: `app/routers/subscriptions.py`

### Step 1: Create `app/routers/subscriptions.py`

```python
import uuid
from fastapi import APIRouter, Depends, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.services import subscription_service, flutterwave_service, paystack_service
from app.schemas.subscription import (
    SubscriptionInitiateRequest, ExtraCreditsInitiateRequest, SubscriptionResponse
)
from app.schemas.common import success
from app.models.purchase import PaymentProvider
from app.exceptions import PaymentError

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.post("/initiate")
async def initiate_subscription(
    body: SubscriptionInitiateRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    from app.config import get_settings
    settings = get_settings()
    ref = str(uuid.uuid4())
    metadata = {"user_id": str(user.id), "type": "subscription", "plan": "premium"}

    if body.provider == PaymentProvider.flutterwave:
        result = await flutterwave_service.initialize_payment(
            amount=settings.subscription_monthly_price / 100,
            email=user.email,
            name=user.full_name,
            product_name="LitMusic Premium – Monthly",
            metadata=metadata,
            tx_ref=ref,
        )
        return success({"checkout_url": result["payment_link"], "payment_reference": ref})

    result = await paystack_service.initialize_payment(
        amount_kobo=settings.subscription_monthly_price,
        email=user.email,
        reference=ref,
        metadata=metadata,
    )
    return success({"checkout_url": result["authorization_url"], "payment_reference": ref})


@router.get("/me")
async def get_my_subscription(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    sub = await subscription_service.get_active_subscription(db, user.id)
    if not sub:
        return success(None, "No active subscription")
    return success(SubscriptionResponse.model_validate(sub).model_dump())


@router.post("/extras/initiate")
async def initiate_extra_credits(
    body: ExtraCreditsInitiateRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    from app.config import get_settings
    settings = get_settings()

    sub = await subscription_service.get_active_subscription(db, user.id)
    if not sub:
        raise PaymentError("Active premium subscription required to purchase extra credits")

    ref = str(uuid.uuid4())
    qty = settings.ai_extra_credits_quantity
    metadata = {"user_id": str(user.id), "type": "ai_extras", "quantity": qty}

    if body.provider == PaymentProvider.flutterwave:
        result = await flutterwave_service.initialize_payment(
            amount=settings.ai_extra_credits_price / 100,
            email=user.email,
            name=user.full_name,
            product_name=f"LitMusic AI Credits ×{qty}",
            metadata=metadata,
            tx_ref=ref,
        )
        return success({"checkout_url": result["payment_link"], "payment_reference": ref})

    result = await paystack_service.initialize_payment(
        amount_kobo=settings.ai_extra_credits_price,
        email=user.email,
        reference=ref,
        metadata=metadata,
    )
    return success({"checkout_url": result["authorization_url"], "payment_reference": ref})


@router.post("/webhook/flutterwave")
async def subscription_flutterwave_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    verif_hash: str = Header(None, alias="verif-hash"),
):
    payload = await request.body()
    await subscription_service.handle_flutterwave_webhook(db, payload, verif_hash)
    return {"received": True}


@router.post("/webhook/paystack")
async def subscription_paystack_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_paystack_signature: str = Header(None, alias="x-paystack-signature"),
):
    payload = await request.body()
    await subscription_service.handle_paystack_webhook(db, payload, x_paystack_signature)
    return {"received": True}
```

### Step 2: Commit
```bash
git add app/routers/subscriptions.py
git commit -m "feat: add subscriptions router (initiate, webhook, me, extras)"
```

---

## Task 11: AI router

**Files:**
- Create: `app/routers/ai.py`

### Step 1: Write failing router tests

Create `tests/routers/test_ai.py`:

```python
import pytest
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from app.models.user import User, UserRole
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
from app.models.purchase import PaymentProvider
from app.services.auth_service import hash_password, create_access_token


async def _create_user(db, ai_enabled=True, ai_extra_credits=0):
    user = User(
        id=uuid.uuid4(), email=f"{uuid.uuid4()}@test.com",
        password_hash=await hash_password("pass"), full_name="Test",
        role=UserRole.user, ai_enabled=ai_enabled, ai_extra_credits=ai_extra_credits,
    )
    db.add(user)
    await db.commit()
    return user


async def _create_active_sub(db, user_id, quota_used=0):
    now = datetime.now(timezone.utc)
    sub = Subscription(
        id=uuid.uuid4(), user_id=user_id, plan=SubscriptionPlan.premium,
        status=SubscriptionStatus.active, provider=PaymentProvider.paystack,
        payment_reference=f"ref-{uuid.uuid4().hex[:8]}", amount_paid=Decimal("2000"),
        ai_quota=10, ai_quota_used=quota_used,
        billing_period_start=now, expires_at=now + timedelta(days=30),
    )
    db.add(sub)
    await db.commit()
    return sub


def _auth_headers(user):
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_generate_requires_auth(client):
    resp = await client.post("/api/v1/ai/generate", json={"prompt": "test", "provider": "suno"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_generate_blocked_when_ai_disabled(client, db_session):
    user = await _create_user(db_session, ai_enabled=False)
    resp = await client.post(
        "/api/v1/ai/generate",
        json={"prompt": "test", "provider": "suno"},
        headers=_auth_headers(user),
    )
    assert resp.status_code == 403
    assert "disabled" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_generate_blocked_without_subscription(client, db_session):
    user = await _create_user(db_session)
    resp = await client.post(
        "/api/v1/ai/generate",
        json={"prompt": "test", "provider": "suno"},
        headers=_auth_headers(user),
    )
    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_generate_blocked_when_quota_exhausted_no_extras(client, db_session):
    user = await _create_user(db_session, ai_extra_credits=0)
    await _create_active_sub(db_session, user.id, quota_used=10)
    resp = await client.post(
        "/api/v1/ai/generate",
        json={"prompt": "test", "provider": "suno"},
        headers=_auth_headers(user),
    )
    assert resp.status_code == 402
    assert "extra credits" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_generate_succeeds_with_active_subscription(client, db_session, monkeypatch):
    from app.tasks import ai_tasks
    monkeypatch.setattr(ai_tasks.generate_ai_loop_task, "delay", lambda *a, **kw: None)

    user = await _create_user(db_session)
    await _create_active_sub(db_session, user.id, quota_used=0)

    resp = await client.post(
        "/api/v1/ai/generate",
        json={"prompt": "chill afrobeat loop", "provider": "suno"},
        headers=_auth_headers(user),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "pending"


@pytest.mark.asyncio
async def test_generate_uses_extra_credits_when_quota_full(client, db_session, monkeypatch):
    from app.tasks import ai_tasks
    monkeypatch.setattr(ai_tasks.generate_ai_loop_task, "delay", lambda *a, **kw: None)

    user = await _create_user(db_session, ai_extra_credits=2)
    await _create_active_sub(db_session, user.id, quota_used=10)

    resp = await client.post(
        "/api/v1/ai/generate",
        json={"prompt": "trap loop", "provider": "self_hosted"},
        headers=_auth_headers(user),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_extra"] is True
    await db_session.refresh(user)
    assert user.ai_extra_credits == 1
```

### Step 2: Run tests to verify they fail

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_ai.py -v
```
Expected: FAIL — `404` (router not registered yet) or `ImportError`

### Step 3: Create `app/routers/ai.py`

```python
import uuid
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.middleware.rate_limit import ai_limiter
from app.services import subscription_service
from app.models.ai_generation import AIGeneration, AIGenerationStatus
from app.schemas.ai_generation import AIGenerateRequest, AIGenerationResponse
from app.schemas.common import success
from app.exceptions import ForbiddenError, PaymentError, NotFoundError

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/generate")
@ai_limiter.limit("10/minute")
async def generate_loop(
    request: Request,
    body: AIGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    # Guard 1: per-user AI toggle
    if not user.ai_enabled:
        raise ForbiddenError("AI generation has been disabled for your account")

    # Guard 2: active subscription
    sub = await subscription_service.get_active_subscription(db, user.id)
    if not sub:
        raise PaymentError("Premium subscription required for AI generation")

    # Guard 3: quota check
    is_extra = False
    if sub.ai_quota_used >= sub.ai_quota:
        if user.ai_extra_credits <= 0:
            raise PaymentError(
                "Monthly AI quota exhausted. Purchase extra credits to continue."
            )
        user.ai_extra_credits -= 1
        is_extra = True
    else:
        sub.ai_quota_used += 1

    gen = AIGeneration(
        user_id=user.id,
        subscription_id=sub.id if not is_extra else None,
        provider=body.provider,
        prompt=body.prompt,
        style_prompt=body.style_prompt,
        status=AIGenerationStatus.pending,
        is_extra=is_extra,
    )
    db.add(gen)
    await db.commit()
    await db.refresh(gen)

    from app.tasks.ai_tasks import generate_ai_loop_task
    generate_ai_loop_task.delay(str(gen.id))

    return success(AIGenerationResponse.model_validate(gen).model_dump(), "Generation started")


@router.get("/generations")
async def list_my_generations(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    offset = (page - 1) * page_size
    total = await db.scalar(
        select(func.count()).select_from(AIGeneration).where(AIGeneration.user_id == user.id)
    )
    gens = await db.scalars(
        select(AIGeneration)
        .where(AIGeneration.user_id == user.id)
        .order_by(AIGeneration.created_at.desc())
        .offset(offset).limit(page_size)
    )
    return success({
        "items": [AIGenerationResponse.model_validate(g).model_dump() for g in gens.all()],
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    })


@router.get("/generations/{generation_id}")
async def get_generation(
    generation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    gen = await db.get(AIGeneration, generation_id)
    if not gen:
        raise NotFoundError("Generation not found")
    if gen.user_id != user.id:
        raise ForbiddenError()
    return success(AIGenerationResponse.model_validate(gen).model_dump())
```

### Step 4: Register new routers in `app/main.py`

In `app/main.py`, update the imports line:

```python
from app.routers import auth, loops, stem_packs, payments, admin, downloads, likes, subscriptions, ai
```

Add the two new routers after the existing ones:

```python
app.include_router(subscriptions.router, prefix=PREFIX)
app.include_router(ai.router, prefix=PREFIX)
```

### Step 5: Run all AI router tests

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_ai.py -v
```
Expected: all 6 tests PASS

### Step 6: Commit
```bash
git add app/routers/ai.py app/routers/subscriptions.py app/main.py tests/routers/test_ai.py
git commit -m "feat: add AI generation router with quota guards and subscription router"
```

---

## Task 12: Admin router additions

**Files:**
- Modify: `app/routers/admin.py`

### Step 1: Write failing test

Add to `tests/routers/test_ai.py` (or a new `tests/routers/test_admin_ai.py`):

```python
@pytest.mark.asyncio
async def test_admin_can_disable_user_ai(client, db_session):
    from app.models.user import UserRole
    admin = await _create_user(db_session)
    admin.role = UserRole.admin
    await db_session.commit()

    target = await _create_user(db_session)
    assert target.ai_enabled is True

    resp = await client.put(
        f"/api/v1/admin/users/{target.id}/ai-enabled",
        params={"enabled": "false"},
        headers=_auth_headers(admin),
    )
    assert resp.status_code == 200
    await db_session.refresh(target)
    assert target.ai_enabled is False
```

### Step 2: Run to verify it fails

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_ai.py::test_admin_can_disable_user_ai -v
```
Expected: FAIL — 404

### Step 3: Add endpoints to `app/routers/admin.py`

Add at the end of the file (after the existing user management section):

```python
# --- AI administration ---

@router.put("/users/{user_id}/ai-enabled")
async def toggle_user_ai(
    user_id: uuid.UUID,
    enabled: bool,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")
    user.ai_enabled = enabled
    await db.commit()
    return success(
        {"ai_enabled": user.ai_enabled},
        f"AI {'enabled' if enabled else 'disabled'} for user",
    )


@router.get("/ai/generations")
async def list_all_generations(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    from app.models.ai_generation import AIGeneration
    from app.schemas.ai_generation import AIGenerationResponse
    offset = (page - 1) * page_size
    total = await db.scalar(select(func.count()).select_from(AIGeneration))
    gens = await db.scalars(
        select(AIGeneration)
        .order_by(AIGeneration.created_at.desc())
        .offset(offset).limit(page_size)
    )
    return success({
        "items": [AIGenerationResponse.model_validate(g).model_dump() for g in gens.all()],
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    })
```

### Step 4: Run tests

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_ai.py -v
```
Expected: all tests PASS

### Step 5: Commit
```bash
git add app/routers/admin.py
git commit -m "feat: add admin AI toggle and generation log endpoints"
```

---

## Task 13: Full test run + smoke check

### Step 1: Run the full test suite

```bash
source .venv/bin/activate && python -m pytest -v
```
Expected: all existing tests pass, all new tests pass.

### Step 2: Start the dev server and verify new routes appear

```bash
source .venv/bin/activate && uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` and verify these routes exist:
- `POST /api/v1/subscriptions/initiate`
- `GET /api/v1/subscriptions/me`
- `POST /api/v1/subscriptions/extras/initiate`
- `POST /api/v1/subscriptions/webhook/flutterwave`
- `POST /api/v1/subscriptions/webhook/paystack`
- `POST /api/v1/ai/generate`
- `GET /api/v1/ai/generations`
- `GET /api/v1/ai/generations/{generation_id}`
- `PUT /api/v1/admin/users/{user_id}/ai-enabled`
- `GET /api/v1/admin/ai/generations`

### Step 3: Final commit (if any cleanup needed)

```bash
git add -p
git commit -m "chore: final cleanup for subscription + AI generation feature"
```

---

## Summary of New/Modified Files

| Action | File |
|---|---|
| Modify | `app/models/user.py` |
| Create | `app/models/subscription.py` |
| Create | `app/models/ai_generation.py` |
| Modify | `app/models/__init__.py` |
| Modify | `app/config.py` |
| Create | `app/schemas/subscription.py` |
| Create | `app/schemas/ai_generation.py` |
| Create | `app/services/subscription_service.py` |
| Create | `app/services/ai_service.py` |
| Modify | `app/utils/ffmpeg_helpers.py` |
| Create | `app/tasks/ai_tasks.py` |
| Modify | `app/tasks/celery_app.py` |
| Modify | `app/middleware/rate_limit.py` |
| Create | `app/routers/subscriptions.py` |
| Create | `app/routers/ai.py` |
| Modify | `app/routers/admin.py` |
| Modify | `app/main.py` |
| Create | `tests/services/test_subscription_service.py` |
| Create | `tests/services/test_ai_service.py` |
| Create | `tests/routers/test_ai.py` |
| Generate | `alembic/versions/xxxx_add_subscription_ai_generation.py` |
