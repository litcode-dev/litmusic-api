# LitMusic API — Design Document
**Date:** 2026-03-02
**Status:** Approved

---

## 1. Overview

LitMusic is a commercial music loop and stem pack marketplace. Producers,
content creators, DJs, and church musicians can browse, preview, and purchase
individual loops or stem packs. There are no subscriptions — all purchases are
one-time transactions.

**Target segments:** Afrobeat / Amapiano producers, Hip-hop / Trap beat makers,
Content creators (YouTube / TikTok), Live performers / DJs, Church musicians
(Gospel, Afrobeat Worship, Contemporary Worship).

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python, async) |
| Database | PostgreSQL via SQLAlchemy ORM (async) |
| Cache / Broker | Redis |
| Task Queue | Celery + Redis |
| File Storage | AWS S3 |
| Encryption | AES-256-GCM (per-file key + IV) |
| Auth | JWT — access (15 min) + refresh (30 days, Redis-stored) |
| Payments | Stripe (one-time checkout only) |
| Notifications | OneSignal push |
| Containers | Docker + docker-compose |
| Hosting | Railway / Render (initial), AWS-ready |

---

## 3. Data Models

### 3.1 User
```
id                  UUID PK
email               unique, indexed
password_hash       bcrypt
full_name           string
role                enum: free | admin
stripe_customer_id  nullable string
onesignal_player_id nullable string
created_at          timestamp
updated_at          timestamp
```

### 3.2 Loop
```
id                  UUID PK
title               string
slug                unique string (auto-generated)
genre               enum: Afrobeat | Amapiano | Trap | Boom Bap | Lo-fi |
                          Gospel | Afrobeat Worship | Contemporary Worship |
                          Dancehall | Afrohouse | Highlife Gospel
bpm                 integer (60–140)
key                 string (e.g. "A minor")
duration            integer (seconds)
tempo_feel          enum: slow | mid | fast
tags                string[] (PostgreSQL ARRAY)
price               Decimal(10,2)
is_free             boolean (default false)
is_paid             boolean (default true)  -- replaces is_premium_only
file_s3_key         string (encrypted WAV path in S3)
preview_s3_key      string (MP3 preview path in S3)
aes_key             string (base64, per-file AES key)
aes_iv              string (base64, per-file IV)
waveform_data       JSONB (peak-normalised float array)
download_count      integer (default 0)
play_count          integer (default 0)
created_by          UUID FK → User
created_at          timestamp
```

### 3.3 StemPack
```
id                  UUID PK
title               string
slug                unique string
loop_id             UUID FK → Loop (nullable — pack may exist independently)
genre               enum (same as Loop)
bpm                 integer
key                 string
tags                string[]
price               Decimal(10,2)
description         text
created_by          UUID FK → User
created_at          timestamp
```

### 3.4 Stem
```
id                  UUID PK
stem_pack_id        UUID FK → StemPack
label               string (e.g. "Drums", "Bass", "Melody")
file_s3_key         string (encrypted WAV)
preview_s3_key      string (MP3 preview, optional)
aes_key             string (base64)
aes_iv              string (base64)
duration            integer (seconds)
created_at          timestamp
```

### 3.5 Purchase
```
id                      UUID PK
user_id                 UUID FK → User
loop_id                 UUID FK → Loop (nullable)
stem_pack_id            UUID FK → StemPack (nullable)
stripe_payment_intent_id string unique
amount_paid             Decimal(10,2)
purchase_type           enum: one_time
created_at              timestamp

CONSTRAINT: exactly one of loop_id / stem_pack_id is non-null (service-layer enforced)
```

### 3.6 Download
```
id              UUID PK
user_id         UUID FK → User
loop_id         UUID FK → Loop (nullable)
stem_id         UUID FK → Stem (nullable)
download_url    text (signed S3 URL, stored for audit)
expires_at      timestamp
downloaded_at   timestamp
```

---

## 4. API Surface

All routes prefixed with `/api/v1/`. Every response uses the envelope:
```json
{ "status": "success" | "error", "data": {}, "message": "string" }
```

### Auth  `/api/v1/auth/`
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | /register | — | Create account |
| POST | /login | — | Returns access + refresh tokens |
| POST | /refresh | — | Rotate access token |
| POST | /logout | Bearer | Revoke refresh token in Redis |
| GET | /me | Bearer | Current user profile |

### Loops  `/api/v1/loops/`
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | / | — | Paginated list, full filter + sort |
| GET | /{id} | — | Single loop details |
| GET | /{id}/preview | — | Stream 15-sec MP3 |
| POST | /{id}/play | Optional | Increment play_count |
| GET | /{id}/download | Bearer | Entitlement check → signed URL + AES key |

**Filters:** `genre`, `bpm_min`, `bpm_max`, `key`, `tempo_feel`, `tags`,
`is_free`, `is_paid`
**Sort:** `newest` | `most_downloaded` | `most_played`

### Stem Packs  `/api/v1/stem-packs/`
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | / | — | Paginated list |
| GET | /{id} | — | Details + stem list (no file URLs) |
| GET | /{id}/download | Bearer | Entitlement check → signed URLs for all stems |

### Payments  `/api/v1/payments/`
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | /create-checkout | Bearer | Stripe Checkout for loop or stem pack |
| POST | /webhook | — (sig verified) | Handle Stripe events |

### Admin  `/api/v1/admin/`
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | /loops | admin | Upload loop (WAV + metadata) |
| PUT | /loops/{id} | admin | Update metadata |
| DELETE | /loops/{id} | admin | Remove loop |
| POST | /stem-packs | admin | Create stem pack |
| POST | /stem-packs/{id}/stems | admin | Add stem to pack |
| PUT | /stem-packs/{id} | admin | Update stem pack metadata |
| DELETE | /stem-packs/{id} | admin | Remove stem pack |

### System
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | /health | — | Liveness + DB + Redis check |

---

## 5. Entitlement Rules

1. Loop with `is_free = true` → any authenticated user can download
2. Loop with `is_free = false` → Purchase row must exist (`user_id + loop_id`)
3. StemPack → Purchase row must exist (`user_id + stem_pack_id`)
4. Free (unauthenticated) users → preview only

---

## 6. File Handling

### Upload (admin)
1. Accept WAV ≤ 30 MB; validate format + 44.1 kHz
2. Generate 15-sec MP3 preview via `ffmpeg`
3. Generate per-file AES-256-GCM key + IV (stored in DB row)
4. Encrypt WAV in memory; upload `.wav.enc` to S3
5. Upload MP3 preview unencrypted to S3
6. Dispatch `generate_waveform_data` Celery task
7. Store all S3 paths, AES key, IV in DB

### Download (user)
1. Entitlement check (Purchase row or `is_free`)
2. Generate 15-min pre-signed S3 URL for encrypted file
3. Return `{ signed_url, aes_key, aes_iv }` to authenticated client over HTTPS
4. Client decrypts locally (AES-256-GCM)
5. Log Download record

---

## 7. Background Tasks (Celery)

| Task | Trigger | Description |
|---|---|---|
| `generate_waveform_data` | After loop/stem upload | Peak-normalised float array → stored in DB |
| `send_purchase_confirmation` | After payment webhook | OneSignal push to buyer |
| `send_new_loop_notification` | After admin uploads loop | Fan-out to users with matching favourite genre |
| `cleanup_expired_download_urls` | Scheduled (hourly) | Delete expired Download records |
| `send_renewal_reminders` | Scheduled (daily) | (Reserved for future; no-op in v1 without subscriptions) |

---

## 8. Security

- **Rate limiting:** `slowapi` — 60 req/min public, 200 req/min authenticated,
  10 req/min on `/payments`
- **CORS:** allowlist from `ALLOWED_ORIGINS` env var
- **Stripe webhook:** signature verified via `stripe.Webhook.construct_event`
- **Admin routes:** FastAPI dependency checks `role == admin`
- **No leakage:** S3 keys, AES keys, internal paths never in logs or error responses
- **Structured logging:** JSON format, `request_id` UUID injected per request
- **Input validation:** Pydantic v2 on all request bodies and query params

---

## 9. Project Structure

```
app/
├── main.py
├── config.py
├── database.py
├── models/
│   ├── user.py
│   ├── loop.py
│   ├── stem_pack.py
│   ├── stem.py
│   ├── purchase.py
│   └── download.py
├── schemas/
│   ├── user.py
│   ├── loop.py
│   ├── stem_pack.py
│   ├── purchase.py
│   └── common.py          # response envelope
├── routers/
│   ├── auth.py
│   ├── loops.py
│   ├── stem_packs.py
│   ├── payments.py
│   ├── downloads.py
│   └── admin.py
├── services/
│   ├── auth_service.py
│   ├── loop_service.py
│   ├── stem_pack_service.py
│   ├── payment_service.py
│   ├── s3_service.py
│   ├── encryption_service.py
│   ├── onesignal_service.py
│   └── waveform_service.py
├── tasks/
│   ├── celery_app.py
│   ├── notification_tasks.py
│   ├── download_tasks.py
│   └── scheduled_tasks.py
├── middleware/
│   ├── auth_middleware.py
│   ├── logging_middleware.py
│   └── rate_limit.py
└── utils/
    ├── audio_validator.py
    └── s3_helpers.py
alembic/
tests/
Dockerfile
docker-compose.yml
.env.example
```

---

## 10. Docker Services

| Service | Image | Purpose |
|---|---|---|
| `api` | ./Dockerfile | FastAPI app |
| `db` | postgres:16-alpine | PostgreSQL |
| `redis` | redis:7-alpine | Cache + Celery broker |
| `worker` | ./Dockerfile | Celery worker |
| `beat` | ./Dockerfile | Celery beat (scheduled tasks) |
