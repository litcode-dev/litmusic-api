# Drone Pad Update Endpoints — Design Spec

**Date:** 2026-03-25

## Overview

Add two admin endpoints to the drone pad resource:

1. **Metadata update** — patch mutable fields without touching the audio file.
2. **File replacement** — replace the WAV, re-run the full encryption/preview pipeline via Celery.

## Endpoints

### 1. Metadata Update

```
PUT /admin/drones/{drone_id}
Auth: require_admin
Content-Type: application/json
```

**Request body** (`DronePadUpdate` — all fields optional):
- `title: str | None`
- `drone_type: DroneType | None`
- `key: MusicalKey | None`
- `price: Decimal | None`
- `is_free: bool | None`
- `category_id: uuid.UUID | None`

**Behaviour:**
- Fetch drone by ID (raise `NotFoundError` if missing).
- Patch only the fields that are not `None`.
- Commit and return `DronePadResponse`.

**Response:** `200 success` with updated `DronePadResponse` + message `"Drone pad updated"`.

---

### 2. File Replacement

```
PUT /admin/drones/{drone_id}/file
Auth: require_admin
Content-Type: multipart/form-data
```

**Form field:** `file: UploadFile` (WAV only).

**Behaviour:**
1. Fetch drone by ID.
2. If `drone.status == "processing"`, raise `409 Conflict` — a prior upload/replacement is still in flight. Concurrent replacements would race on the same S3 keys and DB row.
3. Validate the uploaded file via `validate_wav_upload`.
4. Upload raw bytes to `s3_key_for_raw_drone(drone_id)` (overwrites any leftover raw file).
5. Set `drone.status = "processing"`, commit.
6. Dispatch `process_drone_upload.delay(str(drone.id))`.
   - The existing task encrypts the WAV, generates the preview MP3, derives duration, stores new `aes_key`/`aes_iv`, sets `status = "ready"`, and deletes the raw file — same as the initial upload flow.
   - `s3_key_for_encrypted_drone` and `s3_key_for_drone_preview` are deterministic on `drone_id`, so the task's `put_object` calls implicitly overwrite the previous encrypted file and preview. No explicit pre-deletion of the old encrypted file is required.

**Response:** `202 success` with `{"id": ..., "status": "processing"}` + message `"Drone pad file replacement queued"`.

---

## Schema Changes

**New schema** in `app/schemas/drone_pad.py`:

```python
class DronePadUpdate(BaseModel):
    title: str | None = None
    drone_type: DroneType | None = None
    key: MusicalKey | None = None
    price: Decimal | None = None
    is_free: bool | None = None
    category_id: uuid.UUID | None = None
```

---

## Service Changes

**`app/services/drone_service.py`** — two new functions:

```python
async def update_drone(db, drone_id, data: DronePadUpdate) -> DronePad
async def replace_drone_file(db, drone_id, file: UploadFile) -> DronePad
```

`update_drone` mirrors `loop_service.update_loop` — iterates `data.model_dump(exclude_none=True)` and sets attributes.

`replace_drone_file` validates, uploads to S3 raw key, sets `status = "processing"`, commits, returns drone (caller dispatches Celery task).

---

## Router Changes

**`app/routers/admin.py`** — two new routes added after the existing `POST /drones` block:

```
PUT /drones/{drone_id}          → update_drone_metadata   (require_admin)
PUT /drones/{drone_id}/file     → replace_drone_file_endpoint (require_admin)
```

---

## Auth

| Endpoint | Guard | Rationale |
|---|---|---|
| Metadata update | `require_admin` | Matches `update_loop` precedent — mutation of existing record |
| File replacement | `require_admin` | Mutation of existing record; `require_producer` would allow any producer to overwrite any drone's audio without ownership check |

---

## Error Handling

- `NotFoundError` if `drone_id` not found (both endpoints) — existing exception handler returns 404.
- `validate_wav_upload` raises `400` on invalid audio — unchanged from upload flow.
- No special handling needed for Celery dispatch failure; the status check endpoint (`GET /admin/drones/{drone_id}/status`) already allows polling.

---

## Out of Scope

- Thumbnail replacement (handled separately if ever needed).
- Re-key existing encrypted file without replacing the WAV.
- Cache invalidation for drone listing (drone metadata is not currently cached per-item for public endpoints).
- The `drone:categories` cache stores `DronePadCategoryResponse` objects only (no embedded drone lists), so a `category_id` change on a drone does not require cache invalidation.
