# Drone Title Filter & Download Endpoint

**Date:** 2026-04-02
**Status:** Approved

## Summary

Add a `title` filter to the existing drone list endpoint and a new bulk-download endpoint that returns signed URLs for all drones matching a given title.

## Changes

### 1. Schema — `app/schemas/drone_pad.py`

Add `title: str | None = None` to `DronePadFilter`.

### 2. Service — `app/services/drone_service.py`

**`list_drones`:** When `filters.title` is set, apply a case-insensitive partial match:
```python
DronePad.title.ilike(f"%{filters.title}%")
```

**New `get_title_downloads(db, user, title)`:**
- Validate `title` is non-empty (raise `AppError` 400 if blank)
- Query `DronePad` where `title ilike %...%` and `status == "ready"`, ordered by `key`
- Filter to drones the user has entitlement for (free or purchased)
- Skip drones with no `file_s3_key`
- Generate presigned URLs, increment `download_count`, commit
- Return list of dicts matching the category download shape

### 3. Router — `app/routers/drones.py`

**`GET /drones`** — no router change needed; `title` flows through `DronePadFilter` automatically.

**New `GET /drones/download?title=<str>`:**
- Requires authentication (`get_current_user`)
- `title` is a required query parameter
- Calls `get_title_downloads(db, user, title)`
- Returns: `{"items": [...], "total": N}`

## Response Shape (`/drones/download`)

```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "drone_pad_id": "uuid",
        "title": "Dark Piano Pad",
        "key": "C",
        "signed_url": "https://...",
        "aes_key": "...",
        "aes_iv": "...",
        "expires_in_seconds": 900
      }
    ],
    "total": 2
  }
}
```

## Error Cases

| Condition | Response |
|-----------|----------|
| `title` is empty string | 400 AppError |
| No matching drones found | 200 with `items: [], total: 0` |
| User has no entitlement for any match | 200 with `items: [], total: 0` |

## Notes

- Mirrors the shape and auth pattern of `GET /drones/categories/{category_id}/download`
- No new DB migrations required
- No caching on the download endpoint (signed URLs are per-user and short-lived)
