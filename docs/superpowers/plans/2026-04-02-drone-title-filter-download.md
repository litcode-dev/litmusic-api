# Drone Title Filter & Download Endpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `title` query filter to `GET /drones` and a new `GET /drones/download?title=<str>` endpoint that returns signed download URLs for all drones matching the title.

**Architecture:** Extend `DronePadFilter` with a `title` field, apply an `ilike` filter in `list_drones`, and add a new `get_title_downloads` service function (mirroring `get_category_downloads`) that checks entitlement and returns presigned URLs. The router gets a single new endpoint wired to that service function.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL (`ilike`), existing `s3_service.get_download_url`, existing auth middleware.

---

## Files

| Action | Path | Change |
|--------|------|--------|
| Modify | `app/schemas/drone_pad.py` | Add `title: str \| None = None` to `DronePadFilter` |
| Modify | `app/services/drone_service.py` | Add `ilike` branch in `list_drones`; add `get_title_downloads` |
| Modify | `app/routers/drones.py` | Add `GET /drones/download` endpoint |
| Create | `tests/routers/test_drones.py` | Integration tests for new behaviour |

---

### Task 1: Add `title` filter to `DronePadFilter` schema

**Files:**
- Modify: `app/schemas/drone_pad.py`

- [ ] **Step 1: Write the failing test**

Create `tests/routers/test_drones.py`:

```python
import pytest
import uuid
from decimal import Decimal
from app.models.drone_pad import DronePad, MusicalKey
from app.models.user import User, UserRole
from app.services.auth_service import hash_password
from app.schemas.drone_pad import DronePadFilter


async def _create_user(db, role=UserRole.user):
    user = User(
        id=uuid.uuid4(), email=f"{uuid.uuid4()}@test.com",
        password_hash=await hash_password("pass"), full_name="Test", role=role,
    )
    db.add(user)
    await db.commit()
    return user


async def _create_drone(db, user_id, title="Dark Piano Pad", key=MusicalKey.C, is_free=True, status="ready"):
    drone = DronePad(
        id=uuid.uuid4(), title=title, key=key,
        duration=30, price=Decimal("0.00"), is_free=is_free,
        created_by=user_id, status=status,
    )
    db.add(drone)
    await db.commit()
    return drone


@pytest.mark.asyncio
async def test_list_drones_filter_by_title(client, db_session):
    user = await _create_user(db_session)
    await _create_drone(db_session, user.id, title="Dark Piano Pad")
    await _create_drone(db_session, user.id, title="Jazz Guitar Loop")
    resp = await client.get("/api/v1/drones?title=piano")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Dark Piano Pad"
```

- [ ] **Step 2: Run to verify it fails**

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_drones.py::test_list_drones_filter_by_title -v
```

Expected: FAIL — `DronePadFilter` has no `title` field, filter is ignored, `total` will be 2 not 1.

- [ ] **Step 3: Add `title` to `DronePadFilter`**

In `app/schemas/drone_pad.py`, update `DronePadFilter`:

```python
class DronePadFilter(BaseModel):
    key: MusicalKey | None = None
    is_free: bool | None = None
    category_id: uuid.UUID | None = None
    title: str | None = None
    page: int = 1
    page_size: int = 50
```

- [ ] **Step 4: Apply `ilike` filter in `list_drones`**

In `app/services/drone_service.py`, inside `list_drones`, add after the `category_id` block:

```python
    if filters.title is not None:
        q = q.where(DronePad.title.ilike(f"%{filters.title}%"))
```

The full updated function body (filters section only — keep the rest unchanged):

```python
async def list_drones(db: AsyncSession, filters: DronePadFilter) -> tuple[list[DronePad], int]:
    q = select(DronePad)
    if filters.key:
        q = q.where(DronePad.key == filters.key)
    if filters.is_free is not None:
        q = q.where(DronePad.is_free == filters.is_free)
    if filters.category_id is not None:
        q = q.where(DronePad.category_id == filters.category_id)
    if filters.title is not None:
        q = q.where(DronePad.title.ilike(f"%{filters.title}%"))

    count_q = select(func.count()).select_from(q.subquery())
    total = await db.scalar(count_q)

    q = q.options(selectinload(DronePad.category))
    q = q.order_by(DronePad.key)
    q = q.offset((filters.page - 1) * filters.page_size).limit(filters.page_size)
    result = await db.scalars(q)
    return list(result.all()), total or 0
```

- [ ] **Step 5: Run test to verify it passes**

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_drones.py::test_list_drones_filter_by_title -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/schemas/drone_pad.py app/services/drone_service.py tests/routers/test_drones.py
git commit -m "feat: add title filter to drone list endpoint"
```

---

### Task 2: Add `get_title_downloads` service function

**Files:**
- Modify: `app/services/drone_service.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/routers/test_drones.py`:

```python
from app.services.auth_service import create_access_token
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_download_by_title_returns_items_for_free_drones(client, db_session):
    user = await _create_user(db_session)
    await _create_drone(db_session, user.id, title="Dark Piano Pad", key=MusicalKey.C, is_free=True, status="ready")

    # Give the drone a fake file_s3_key so it qualifies for download
    from sqlalchemy import select
    from app.models.drone_pad import DronePad
    drone = (await db_session.scalars(select(DronePad).where(DronePad.title == "Dark Piano Pad"))).first()
    drone.file_s3_key = "drones/fake-key.wav"
    await db_session.commit()

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    with patch(
        "app.services.s3_service.get_download_url",
        new=AsyncMock(return_value="https://signed.url/file.wav"),
    ):
        resp = await client.get(
            "/api/v1/drones/download?title=piano",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Dark Piano Pad"
    assert data["items"][0]["signed_url"] == "https://signed.url/file.wav"
    assert data["items"][0]["expires_in_seconds"] == 900


@pytest.mark.asyncio
async def test_download_by_title_requires_auth(client):
    resp = await client.get("/api/v1/drones/download?title=piano")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_download_by_title_empty_string_returns_400(client, db_session):
    user = await _create_user(db_session)
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    resp = await client.get(
        "/api/v1/drones/download?title=",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: Run to verify tests fail**

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_drones.py::test_download_by_title_returns_items_for_free_drones tests/routers/test_drones.py::test_download_by_title_requires_auth tests/routers/test_drones.py::test_download_by_title_empty_string_returns_400 -v
```

Expected: FAIL — endpoint does not exist yet (404).

- [ ] **Step 3: Add `get_title_downloads` to `drone_service.py`**

Append to `app/services/drone_service.py` (after `get_category_downloads`):

```python
async def get_title_downloads(
    db: AsyncSession,
    user: User,
    title: str,
) -> list[dict]:
    from app.exceptions import AppError
    if not title.strip():
        raise AppError("title must not be empty", status_code=400)

    drones = list(await db.scalars(
        select(DronePad)
        .options(selectinload(DronePad.category))
        .where(DronePad.title.ilike(f"%{title}%"), DronePad.status == "ready")
        .order_by(DronePad.key)
    ))

    if not drones:
        return []

    purchased_ids = set(await db.scalars(
        select(Purchase.drone_pad_id).where(
            Purchase.user_id == user.id,
            Purchase.drone_pad_id.in_([d.id for d in drones]),
        )
    ))

    results = []
    for drone in drones:
        if not drone.is_free and drone.id not in purchased_ids:
            continue
        if not drone.file_s3_key:
            continue
        download_url = await s3_service.get_download_url(drone.file_s3_key, expiry_seconds=900)
        drone.download_count += 1
        results.append({
            "drone_pad_id": str(drone.id),
            "title": drone.title,
            "key": drone.key,
            "signed_url": download_url,
            "aes_key": drone.aes_key,
            "aes_iv": drone.aes_iv,
            "expires_in_seconds": 900,
        })

    await db.commit()
    return results
```

- [ ] **Step 4: Add `GET /drones/download` to the router**

In `app/routers/drones.py`, add the import for `get_title_downloads` (update the existing import line):

```python
from app.services import drone_service, s3_service, cache_service
```

(No import change needed — `drone_service` is already imported; `get_title_downloads` will be called as `drone_service.get_title_downloads`.)

Add this endpoint **before** `@router.get("/{drone_id}")` (must come before parameterised routes to avoid `/download` being swallowed as a `drone_id`):

```python
@router.get("/download")
async def download_drones_by_title(
    title: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    items = await drone_service.get_title_downloads(db, user, title)
    return success({"items": items, "total": len(items)})
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_drones.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/services/drone_service.py app/routers/drones.py tests/routers/test_drones.py
git commit -m "feat: add GET /drones/download endpoint with title filter"
```

---

### Task 3: Final smoke check

- [ ] **Step 1: Run the full test suite**

```bash
source .venv/bin/activate && python -m pytest -v
```

Expected: All tests pass, no regressions.

- [ ] **Step 2: Verify route ordering in the router**

Open `app/routers/drones.py` and confirm the route order is:
1. `GET /categories`
2. `GET /categories/{category_id}`
3. `GET /categories/{category_id}/download`
4. `GET /download` ← new
5. `GET ""` (list)
6. `GET /{drone_id}`
7. `GET /{drone_id}/preview`
8. `GET /{drone_id}/download`

This ensures `/download` is matched before `/{drone_id}`.
