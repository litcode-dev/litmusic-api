# Drone Titles Grouped Endpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the previous title-filter approach with `GET /drones/titles` (drones grouped by title) and `GET /drones/titles/{title}/download` (bulk download by exact title).

**Architecture:** Remove old `title` filter work from schema/service/router/tests, then add two new service functions (`list_drones_grouped_by_title`, new `get_title_downloads`) and two new router endpoints. Route ordering is critical — `/titles` and `/titles/{title}/download` must be registered before `/{drone_id}`.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL (`ilike` for case-insensitive exact match), existing `s3_service.get_download_url`, existing `NotFoundError`, existing auth middleware.

---

## Files

| Action | Path | Change |
|--------|------|--------|
| Modify | `app/schemas/drone_pad.py` | Remove `title` from `DronePadFilter` |
| Modify | `app/services/drone_service.py` | Remove old `get_title_downloads` + title filter in `list_drones`; add `list_drones_grouped_by_title` + new `get_title_downloads` |
| Modify | `app/routers/drones.py` | Remove `title` param + `GET /download`; add `GET /titles` + `GET /titles/{title}/download` |
| Modify | `tests/routers/test_drones.py` | Replace all old tests with new ones |

---

### Task 1: Remove old title-filter code

**Files:**
- Modify: `app/schemas/drone_pad.py`
- Modify: `app/services/drone_service.py`
- Modify: `app/routers/drones.py`
- Modify: `tests/routers/test_drones.py`

- [ ] **Step 1: Rewrite `tests/routers/test_drones.py` — keep only helpers**

Replace the entire file content with just the helpers (all old tests are removed; new tests come in Tasks 2 and 3):

```python
import pytest
import uuid
from decimal import Decimal
from unittest.mock import patch, AsyncMock
from app.models.drone_pad import DronePad, MusicalKey
from app.models.user import User, UserRole
from app.services.auth_service import hash_password, create_access_token


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
```

- [ ] **Step 2: Remove `title` from `DronePadFilter` in `app/schemas/drone_pad.py`**

Replace `DronePadFilter` with:

```python
class DronePadFilter(BaseModel):
    key: MusicalKey | None = None
    is_free: bool | None = None
    category_id: uuid.UUID | None = None
    page: int = 1
    page_size: int = 50
```

- [ ] **Step 3: Remove `title` filter from `list_drones` in `app/services/drone_service.py`**

Replace the `list_drones` function (lines ~110–128) with:

```python
async def list_drones(db: AsyncSession, filters: DronePadFilter) -> tuple[list[DronePad], int]:
    q = select(DronePad)
    if filters.key:
        q = q.where(DronePad.key == filters.key)
    if filters.is_free is not None:
        q = q.where(DronePad.is_free == filters.is_free)
    if filters.category_id is not None:
        q = q.where(DronePad.category_id == filters.category_id)

    count_q = select(func.count()).select_from(q.subquery())
    total = await db.scalar(count_q)

    q = q.options(selectinload(DronePad.category))
    q = q.order_by(DronePad.key)
    q = q.offset((filters.page - 1) * filters.page_size).limit(filters.page_size)
    result = await db.scalars(q)
    return list(result.all()), total or 0
```

Also remove the old `get_title_downloads` function entirely (lines ~266–311).

- [ ] **Step 4: Clean up `app/routers/drones.py`**

Replace the `list_drones` endpoint (remove `title` param) and remove the `GET /download` endpoint entirely.

The `list_drones` endpoint should be:

```python
@router.get("")
async def list_drones(
    key: MusicalKey | None = None,
    is_free: bool | None = None,
    category_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    filters = DronePadFilter(
        key=key, is_free=is_free, category_id=category_id,
        page=page, page_size=page_size,
    )
    drones, total = await drone_service.list_drones(db, filters)
    return success({
        "items": [DronePadResponse.model_validate(d).model_dump() for d in drones],
        "total": total,
        "page": page,
        "page_size": page_size,
    })
```

Remove the entire `GET /download` endpoint block (the `download_drones_by_title` function).

- [ ] **Step 5: Verify the test suite still passes**

```bash
source .venv/bin/activate && python -m pytest -v
```

Expected: 36 passed, ≥0 skipped, 0 failed. (The drone test file now has no tests — that's fine.)

- [ ] **Step 6: Commit**

```bash
git add app/schemas/drone_pad.py app/services/drone_service.py app/routers/drones.py tests/routers/test_drones.py
git commit -m "refactor: remove title filter approach, clear ground for titles endpoints"
```

---

### Task 2: Add `GET /drones/titles` grouped endpoint

**Files:**
- Modify: `app/services/drone_service.py`
- Modify: `app/routers/drones.py`
- Modify: `tests/routers/test_drones.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/routers/test_drones.py`:

```python
@pytest.mark.asyncio
async def test_list_drones_grouped_by_title(client, db_session):
    user = await _create_user(db_session)
    # Two drones same title (different keys) + one with different title
    await _create_drone(db_session, user.id, title="Dark Piano Pad", key=MusicalKey.C)
    await _create_drone(db_session, user.id, title="Dark Piano Pad", key=MusicalKey.D)
    await _create_drone(db_session, user.id, title="Jazz Guitar Loop", key=MusicalKey.A)

    resp = await client.get("/api/v1/drones/titles")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2  # 2 distinct titles
    titles = [item["title"] for item in data["items"]]
    assert "Dark Piano Pad" in titles
    assert "Jazz Guitar Loop" in titles
    piano_group = next(i for i in data["items"] if i["title"] == "Dark Piano Pad")
    assert len(piano_group["drones"]) == 2


@pytest.mark.asyncio
async def test_list_drones_by_title_excludes_processing(client, db_session):
    user = await _create_user(db_session)
    await _create_drone(db_session, user.id, title="Cello Pad", status="processing")
    resp = await client.get("/api/v1/drones/titles")
    assert resp.status_code == 200
    data = resp.json()["data"]
    titles = [item["title"] for item in data["items"]]
    assert "Cello Pad" not in titles
```

- [ ] **Step 2: Run to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_drones.py::test_list_drones_grouped_by_title tests/routers/test_drones.py::test_list_drones_by_title_excludes_processing -v
```

Expected: FAIL (404 — endpoint does not exist yet) or SKIP if DB unavailable.

- [ ] **Step 3: Add `list_drones_grouped_by_title` to `app/services/drone_service.py`**

Append after `list_drones` (before `get_drones_by_ids`):

```python
async def list_drones_grouped_by_title(db: AsyncSession) -> list[dict]:
    drones = list(await db.scalars(
        select(DronePad)
        .options(selectinload(DronePad.category))
        .where(DronePad.status == "ready")
        .order_by(DronePad.title, DronePad.key)
    ))
    groups: dict[str, list] = {}
    for drone in drones:
        groups.setdefault(drone.title, []).append(drone)
    return [{"title": title, "drones": drone_list} for title, drone_list in groups.items()]
```

- [ ] **Step 4: Add `GET /drones/titles` to `app/routers/drones.py`**

Add this endpoint after the `GET /categories/{category_id}/download` block and **before** the `GET ""` list endpoint — it must be before `GET /{drone_id}` in registration order:

```python
@router.get("/titles")
async def list_drones_by_title(db: AsyncSession = Depends(get_db)):
    groups = await drone_service.list_drones_grouped_by_title(db)
    items = [
        {
            "title": g["title"],
            "drones": [DronePadResponse.model_validate(d).model_dump() for d in g["drones"]],
        }
        for g in groups
    ]
    return success({"items": items, "total": len(items)})
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_drones.py -v
```

Expected: PASS (or SKIP if DB unavailable).

- [ ] **Step 6: Commit**

```bash
git add app/services/drone_service.py app/routers/drones.py tests/routers/test_drones.py
git commit -m "feat: add GET /drones/titles endpoint grouped by title"
```

---

### Task 3: Add `GET /drones/titles/{title}/download` endpoint

**Files:**
- Modify: `app/services/drone_service.py`
- Modify: `app/routers/drones.py`
- Modify: `tests/routers/test_drones.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/routers/test_drones.py`:

```python
@pytest.mark.asyncio
async def test_download_by_title_returns_signed_urls(client, db_session):
    user = await _create_user(db_session)
    drone = await _create_drone(db_session, user.id, title="Dark Piano Pad", key=MusicalKey.C, is_free=True, status="ready")
    drone.file_s3_key = "drones/fake-key.wav"
    await db_session.commit()

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    with patch(
        "app.services.s3_service.get_download_url",
        new=AsyncMock(return_value="https://signed.url/file.wav"),
    ):
        resp = await client.get(
            "/api/v1/drones/titles/Dark Piano Pad/download",
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
    resp = await client.get("/api/v1/drones/titles/Dark Piano Pad/download")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_download_by_title_not_found(client, db_session):
    user = await _create_user(db_session)
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    resp = await client.get(
        "/api/v1/drones/titles/NonExistentTitle/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_by_title_excludes_unpurchased_paid_drone(client, db_session):
    user = await _create_user(db_session)
    drone = await _create_drone(
        db_session, user.id, title="Paid Cello Pad", key=MusicalKey.C, is_free=False, status="ready"
    )
    drone.file_s3_key = "drones/paid-key.wav"
    await db_session.commit()

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    resp = await client.get(
        "/api/v1/drones/titles/Paid Cello Pad/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 0
    assert data["items"] == []
```

- [ ] **Step 2: Run to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_drones.py::test_download_by_title_returns_signed_urls tests/routers/test_drones.py::test_download_by_title_requires_auth tests/routers/test_drones.py::test_download_by_title_not_found tests/routers/test_drones.py::test_download_by_title_excludes_unpurchased_paid_drone -v
```

Expected: FAIL (404 — endpoint does not exist yet) or SKIP if DB unavailable.

- [ ] **Step 3: Add `get_title_downloads` to `app/services/drone_service.py`**

Append after `get_category_downloads`:

```python
async def get_title_downloads(
    db: AsyncSession,
    user: User,
    title: str,
) -> list[dict]:
    drones = list(await db.scalars(
        select(DronePad)
        .options(selectinload(DronePad.category))
        .where(DronePad.title.ilike(title), DronePad.status == "ready")
        .order_by(DronePad.key)
    ))

    if not drones:
        raise NotFoundError(f"No drone pads found with title '{title}'")

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

Note: `NotFoundError` is already imported at the top of `drone_service.py`.

- [ ] **Step 4: Add `GET /drones/titles/{title}/download` to `app/routers/drones.py`**

Add after the `GET /titles` endpoint (before `GET ""`):

```python
@router.get("/titles/{title}/download")
async def download_drones_by_title(
    title: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    items = await drone_service.get_title_downloads(db, user, title)
    return success({"items": items, "total": len(items)})
```

- [ ] **Step 5: Verify final route order in `app/routers/drones.py`**

Confirm routes appear in this order (read the file and check):
1. `GET /categories`
2. `GET /categories/{category_id}`
3. `GET /categories/{category_id}/download`
4. `GET /titles` ← new
5. `GET /titles/{title}/download` ← new
6. `GET ""` (list)
7. `GET /{drone_id}`
8. `GET /{drone_id}/preview`
9. `GET /{drone_id}/download`

- [ ] **Step 6: Run all tests**

```bash
source .venv/bin/activate && python -m pytest -v
```

Expected: 36+ passed, ≥0 skipped, 0 failed.

- [ ] **Step 7: Commit**

```bash
git add app/services/drone_service.py app/routers/drones.py tests/routers/test_drones.py
git commit -m "feat: add GET /drones/titles/{title}/download endpoint"
```
