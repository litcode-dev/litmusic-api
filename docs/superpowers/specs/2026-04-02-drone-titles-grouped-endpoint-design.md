# Drone Titles Grouped Endpoint Design

**Date:** 2026-04-02
**Status:** Approved

## Summary

Replace the previous title-filter approach (`GET /drones?title=` + `GET /drones/download?title=`) with two new endpoints:

1. `GET /drones/titles` — lists all drone pads grouped by title
2. `GET /drones/titles/{title}/download` — bulk-downloads all drones under a given title the user has entitlement for

## Cleanup (remove previous work)

- Remove `title: str | None` from `DronePadFilter` in `app/schemas/drone_pad.py`
- Remove `title` query param from `GET /drones` router endpoint in `app/routers/drones.py`
- Remove `GET /drones/download` endpoint from `app/routers/drones.py`
- Remove `get_title_downloads` function from `app/services/drone_service.py`
- Remove or update affected tests in `tests/routers/test_drones.py`

## New Endpoints

### `GET /drones/titles`

- Public (no auth required)
- Queries all `DronePad` rows where `status == "ready"`, ordered by `title` then `key`
- Groups results in Python by `title`
- Each group contains the full `DronePadResponse` shape for each drone

**Response:**
```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "title": "Dark Piano Pad",
        "drones": [
          {"id": "...", "key": "C", "duration": 30, "price": "0.00", "is_free": true, ...}
        ]
      }
    ],
    "total": 2
  }
}
```

`total` = number of distinct title groups.

### `GET /drones/titles/{title}/download`

- Requires authentication (`get_current_user`)
- `title` is a path parameter (URL-encoded, exact case-insensitive match via `ilike`)
- Raises `NotFoundError` (404) if no ready drones exist with that title
- Checks entitlement per drone (free or purchased)
- Skips drones with no `file_s3_key`
- Generates presigned URLs via `s3_service.get_download_url(..., expiry_seconds=900)`
- Increments `download_count` and commits

**Response shape** (same as category download):
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
    "total": 1
  }
}
```

## Service Functions

### New: `list_drones_grouped_by_title(db) -> list[dict]`

In `app/services/drone_service.py`:
- Query all ready drones with `selectinload(category)`, ordered by `title`, then `key`
- Group in Python using `itertools.groupby` or manual dict accumulation
- Return `[{"title": str, "drones": [DronePad, ...]}, ...]`

### New: `get_title_downloads(db, user, title) -> list[dict]`

In `app/services/drone_service.py`:
- Query drones where `title ilike title` and `status == "ready"`, ordered by `key`
- Raise `NotFoundError` if result is empty
- Check entitlement (free or purchased), skip no-`file_s3_key` drones
- Return download dicts

## Route Ordering

In `app/routers/drones.py`, `GET /titles` and `GET /titles/{title}/download` must be registered before `GET /{drone_id}`:

```
GET /categories
GET /categories/{category_id}
GET /categories/{category_id}/download
GET /titles                          ← new
GET /titles/{title}/download         ← new
GET ""                               (list)
GET /{drone_id}
GET /{drone_id}/preview
GET /{drone_id}/download
```

## Error Cases

| Condition | Response |
|-----------|----------|
| No drones with that title exist | 404 NotFoundError |
| User has no entitlement for any drone under the title | 200 `items: [], total: 0` |
| All matching drones have no `file_s3_key` | 200 `items: [], total: 0` |

## Tests

Update `tests/routers/test_drones.py`:
- Remove tests for old `GET /drones/download?title=` and `GET /drones?title=` filter
- Add: `test_list_drones_grouped_by_title` — creates 2 drones with same title, 1 with different, asserts grouping
- Add: `test_download_by_title_returns_signed_urls` — free drone, patched S3, asserts response shape
- Add: `test_download_by_title_requires_auth` — 403 without token
- Add: `test_download_by_title_not_found` — 404 when no drones match title
- Add: `test_download_by_title_excludes_unpurchased_paid_drone`
