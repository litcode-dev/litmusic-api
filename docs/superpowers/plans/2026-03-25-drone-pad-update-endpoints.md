# Drone Pad Update Endpoints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two admin endpoints — `PUT /admin/drones/{drone_id}` for metadata updates and `PUT /admin/drones/{drone_id}/file` for WAV file replacement.

**Architecture:** Metadata update follows the existing `update_loop` pattern (JSON body, all-optional fields, `require_admin`). File replacement validates a new WAV, overwrites the raw S3 key, sets status to `"processing"`, and dispatches the existing `process_drone_upload` Celery task — identical to the initial upload pipeline. The `/file` sub-route is registered before the `/{drone_id}` wildcard route in the router to avoid any ambiguity.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, boto3 (via `s3_service`), Celery (`process_drone_upload`), pytest-asyncio, httpx.

---

## Files Changed

| File | Change |
|---|---|
| `app/schemas/drone_pad.py` | Add `DronePadUpdate` schema |
| `app/services/drone_service.py` | Add `update_drone` and `replace_drone_file` functions |
| `app/routers/admin.py` | Add two new route handlers (`/file` registered before `/{drone_id}`) |
| `tests/routers/test_drones_admin.py` | New test file covering both endpoints |

---

### Task 1: Add `DronePadUpdate` schema

**Files:**
- Modify: `app/schemas/drone_pad.py`
- Create: `tests/routers/test_drones_admin.py`

- [ ] **Step 1: Write the failing test**

Create `tests/routers/test_drones_admin.py`:

```python
import pytest
import uuid
from decimal import Decimal
from unittest.mock import patch, AsyncMock, MagicMock
from app.models.drone_pad import DronePad, DroneType, MusicalKey
from app.models.user import User, UserRole
from app.services.auth_service import hash_password, create_access_token


async def _create_admin(db):
    user = User(
        id=uuid.uuid4(), email=f"{uuid.uuid4()}@test.com",
        password_hash=await hash_password("pass"), full_name="Admin",
        role=UserRole.admin,
    )
    db.add(user)
    await db.commit()
    return user


async def _create_drone(db, user_id, status="ready"):
    drone = DronePad(
        id=uuid.uuid4(), title="Test Drone",
        drone_type=DroneType.warm, key=MusicalKey.C,
        duration=30, price=Decimal("4.99"), is_free=False,
        file_s3_key="drones/enc/test.wav",
        aes_key="aabbcc", aes_iv="ddeeff",
        status=status, created_by=user_id,
    )
    db.add(drone)
    await db.commit()
    return drone


@pytest.mark.asyncio
async def test_update_drone_metadata_changes_title(client, db_session):
    admin = await _create_admin(db_session)
    drone = await _create_drone(db_session, admin.id)
    token = create_access_token(str(admin.id), admin.role.value)
    resp = await client.put(
        f"/api/v1/admin/drones/{drone.id}",
        json={"title": "New Title"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "New Title"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_drones_admin.py::test_update_drone_metadata_changes_title -v
```

Expected: FAIL — 404 or 405 (endpoint does not exist yet).

- [ ] **Step 3: Add `DronePadUpdate` to `app/schemas/drone_pad.py`**

Add after the `DronePadCreate` class (around line 29):

```python
class DronePadUpdate(BaseModel):
    title: str | None = None
    drone_type: DroneType | None = None
    key: MusicalKey | None = None
    price: Decimal | None = None
    is_free: bool | None = None
    category_id: uuid.UUID | None = None
```

No new imports needed — `Decimal` and `uuid` are already imported at the top of the file.

- [ ] **Step 4: Commit**

```bash
git add app/schemas/drone_pad.py tests/routers/test_drones_admin.py
git commit -m "feat: add DronePadUpdate schema and initial drone admin test"
```

---

### Task 2: Add `update_drone` service function

**Files:**
- Modify: `app/services/drone_service.py`

- [ ] **Step 1: Confirm the failing test still fails (TDD gate)**

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_drones_admin.py::test_update_drone_metadata_changes_title -v
```

Expected: FAIL — endpoint still not wired.

- [ ] **Step 2: Add `update_drone` to `app/services/drone_service.py`**

Add after `delete_drone` (end of file) — mirrors `loop_service.update_loop` exactly:

```python
async def update_drone(
    db: AsyncSession, drone_id: uuid.UUID, data: "DronePadUpdate"
) -> DronePad:
    from app.schemas.drone_pad import DronePadUpdate  # local import avoids circular
    drone = await get_drone(db, drone_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(drone, field, value)
    await db.commit()
    await db.refresh(drone)
    return drone
```

- [ ] **Step 3: Commit**

```bash
git add app/services/drone_service.py
git commit -m "feat: add update_drone service function"
```

---

### Task 3: Wire metadata update endpoint

**Files:**
- Modify: `app/routers/admin.py`

- [ ] **Step 1: Add import and route to `app/routers/admin.py`**

Extend the drone_pad schema import line (find the existing import and add `DronePadUpdate`):

```python
from app.schemas.drone_pad import DronePadCreate, DronePadUpdate, DronePadResponse, DronePadCategoryCreate, DronePadCategoryResponse
```

Add the new route **after** `POST /drones` (after line ~282) and **before** `GET /drones/{drone_id}/status`. The file-replacement route (`PUT /drones/{drone_id}/file`) will be added in Task 5 and must appear first in the file — leave a comment as a placeholder:

```python
# PUT /drones/{drone_id}/file is declared in Task 5 — it MUST be registered before this route
@router.put("/drones/{drone_id}")
async def update_drone_metadata(
    drone_id: uuid.UUID,
    body: DronePadUpdate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    drone = await drone_service.update_drone(db, drone_id, body)
    return success(DronePadResponse.model_validate(drone).model_dump(), "Drone pad updated")
```

- [ ] **Step 2: Run the metadata test**

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_drones_admin.py::test_update_drone_metadata_changes_title -v
```

Expected: PASS.

- [ ] **Step 3: Add remaining metadata tests to `tests/routers/test_drones_admin.py`**

```python
@pytest.mark.asyncio
async def test_update_drone_metadata_partial_fields(client, db_session):
    """Only provided fields change; others are unchanged."""
    admin = await _create_admin(db_session)
    drone = await _create_drone(db_session, admin.id)
    original_price = str(drone.price)
    token = create_access_token(str(admin.id), admin.role.value)
    resp = await client.put(
        f"/api/v1/admin/drones/{drone.id}",
        json={"is_free": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_free"] is True
    assert data["price"] == original_price


@pytest.mark.asyncio
async def test_update_drone_metadata_not_found(client, db_session):
    admin = await _create_admin(db_session)
    token = create_access_token(str(admin.id), admin.role.value)
    resp = await client.put(
        f"/api/v1/admin/drones/{uuid.uuid4()}",
        json={"title": "Ghost"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_drone_metadata_requires_admin(client, db_session):
    admin = await _create_admin(db_session)
    drone = await _create_drone(db_session, admin.id)
    regular = User(
        id=uuid.uuid4(), email=f"{uuid.uuid4()}@test.com",
        password_hash=await hash_password("pass"), full_name="User",
        role=UserRole.user,
    )
    db_session.add(regular)
    await db_session.commit()
    token = create_access_token(str(regular.id), regular.role.value)
    resp = await client.put(
        f"/api/v1/admin/drones/{drone.id}",
        json={"title": "Hack"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 4: Run all metadata tests**

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_drones_admin.py -v -k "metadata"
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routers/admin.py tests/routers/test_drones_admin.py
git commit -m "feat: add PUT /admin/drones/{id} metadata update endpoint"
```

---

### Task 4: Add `replace_drone_file` service function

**Files:**
- Modify: `app/services/drone_service.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/routers/test_drones_admin.py`:

```python
@pytest.mark.asyncio
async def test_replace_drone_file_queues_processing(client, db_session):
    admin = await _create_admin(db_session)
    drone = await _create_drone(db_session, admin.id, status="ready")
    token = create_access_token(str(admin.id), admin.role.value)

    with patch("app.utils.audio_validator.validate_wav_upload", new_callable=AsyncMock, return_value=b"fakewav"), \
         patch("app.services.drone_service.s3_service.upload_bytes", new_callable=AsyncMock), \
         patch("app.routers.admin.process_drone_upload") as mock_task:
        mock_task.delay = MagicMock()
        resp = await client.put(
            f"/api/v1/admin/drones/{drone.id}/file",
            files={"file": ("new.wav", b"anything", "audio/wav")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 202
    assert resp.json()["data"]["status"] == "processing"
    mock_task.delay.assert_called_once_with(str(drone.id))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_drones_admin.py::test_replace_drone_file_queues_processing -v
```

Expected: FAIL — endpoint does not exist yet.

- [ ] **Step 3: Add `replace_drone_file` to `app/services/drone_service.py`**

Add after `update_drone` (end of file):

```python
async def replace_drone_file(
    db: AsyncSession, drone_id: uuid.UUID, file: UploadFile
) -> DronePad:
    drone = await get_drone(db, drone_id)
    if drone.status == "processing":
        raise ConflictError("Drone pad is already processing. Wait for the current upload to complete.")

    wav_bytes = await validate_wav_upload(file)
    raw_key = s3_service.s3_key_for_raw_drone(str(drone_id))
    await s3_service.upload_bytes(raw_key, wav_bytes, "audio/wav")

    drone.status = "processing"
    await db.commit()
    await db.refresh(drone)
    return drone
```

`ConflictError` and `validate_wav_upload` are already imported at the top of `drone_service.py` — no new imports needed.

> **Check:** Verify `from app.exceptions import NotFoundError, EntitlementError` at the top of `drone_service.py`. If `ConflictError` is not yet imported there, add it to that line. Also verify `from app.utils.audio_validator import validate_wav_upload` is already present (it is, used by `create_drone`).

- [ ] **Step 4: Commit**

```bash
git add app/services/drone_service.py
git commit -m "feat: add replace_drone_file service function"
```

---

### Task 5: Wire file replacement endpoint

**Files:**
- Modify: `app/routers/admin.py`

- [ ] **Step 1: Add the `/file` route to `app/routers/admin.py` — BEFORE the `PUT /{drone_id}` route**

FastAPI matches routes in registration order. The literal path `/drones/{drone_id}/file` must be declared before the wildcard `/drones/{drone_id}` to ensure it is not shadowed. Insert the new route **before** the `PUT /drones/{drone_id}` route added in Task 3 (and remove the placeholder comment):

```python
@router.put("/drones/{drone_id}/file")
async def replace_drone_file_endpoint(
    drone_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    from app.tasks.upload_tasks import process_drone_upload
    drone = await drone_service.replace_drone_file(db, drone_id, file)
    process_drone_upload.delay(str(drone.id))
    return success({"id": str(drone.id), "status": drone.status}, "Drone pad file replacement queued")


@router.put("/drones/{drone_id}")
async def update_drone_metadata(
    ...
```

The local `from app.tasks.upload_tasks import process_drone_upload` import matches the existing pattern in `upload_drone` (line 280).

- [ ] **Step 2: Run the file replacement happy-path test**

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_drones_admin.py::test_replace_drone_file_queues_processing -v
```

Expected: PASS.

- [ ] **Step 3: Add edge case tests to `tests/routers/test_drones_admin.py`**

```python
@pytest.mark.asyncio
async def test_replace_drone_file_rejects_while_processing(client, db_session):
    admin = await _create_admin(db_session)
    drone = await _create_drone(db_session, admin.id, status="processing")
    token = create_access_token(str(admin.id), admin.role.value)
    resp = await client.put(
        f"/api/v1/admin/drones/{drone.id}/file",
        files={"file": ("new.wav", b"anything", "audio/wav")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_replace_drone_file_not_found(client, db_session):
    admin = await _create_admin(db_session)
    token = create_access_token(str(admin.id), admin.role.value)
    resp = await client.put(
        f"/api/v1/admin/drones/{uuid.uuid4()}/file",
        files={"file": ("new.wav", b"anything", "audio/wav")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_replace_drone_file_requires_admin(client, db_session):
    admin = await _create_admin(db_session)
    drone = await _create_drone(db_session, admin.id)
    regular = User(
        id=uuid.uuid4(), email=f"{uuid.uuid4()}@test.com",
        password_hash=await hash_password("pass"), full_name="User",
        role=UserRole.user,
    )
    db_session.add(regular)
    await db_session.commit()
    token = create_access_token(str(regular.id), regular.role.value)
    resp = await client.put(
        f"/api/v1/admin/drones/{drone.id}/file",
        files={"file": ("new.wav", b"anything", "audio/wav")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
```

Note: `test_replace_drone_file_rejects_while_processing` and the auth/not-found tests do **not** need to patch `validate_wav_upload` — the service raises `ConflictError` before validation, and the auth/not-found checks fire before the service is called.

- [ ] **Step 4: Run all tests in the file**

```bash
source .venv/bin/activate && python -m pytest tests/routers/test_drones_admin.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routers/admin.py tests/routers/test_drones_admin.py
git commit -m "feat: add PUT /admin/drones/{id}/file endpoint for WAV replacement"
```

---

### Task 6: Final check

- [ ] **Step 1: Run full test suite**

```bash
source .venv/bin/activate && python -m pytest -v
```

Expected: all existing tests still pass, all new tests pass.

- [ ] **Step 2: Verify routes are registered in correct order**

```bash
source .venv/bin/activate && python -c "
from app.main import app
for r in app.routes:
    if hasattr(r, 'methods') and 'drones' in getattr(r, 'path', ''):
        print(r.methods, r.path)
"
```

Expected — `/file` must appear before `/{drone_id}` for PUT:
```
{'PUT'} /api/v1/admin/drones/{drone_id}/file
{'PUT'} /api/v1/admin/drones/{drone_id}
```
