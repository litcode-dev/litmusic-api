# Subscription Plans + AI Loop Generation — Design

**Date:** 2026-03-07
**Status:** Approved

---

## Overview

Add monthly premium subscriptions (Flutterwave/Paystack with webhooks) that unlock AI loop generation via Suno or a self-hosted endpoint. Premium users get 10 AI-generated loops per billing cycle, with pay-per-extra credits when quota is exhausted. Admins can disable AI on a per-user basis.

---

## Data Models

### `users` table — new columns
| Column | Type | Default | Notes |
|---|---|---|---|
| `ai_enabled` | bool | `True` | Admin-controlled per-user AI toggle |
| `ai_extra_credits` | int | `0` | Paid extra generation slots |

### `subscriptions` table (new)
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK → users | indexed |
| `plan` | enum: `premium` | extensible later |
| `status` | enum: `active`, `cancelled`, `expired` | |
| `provider` | enum: `flutterwave`, `paystack` | |
| `payment_reference` | str unique | from webhook |
| `amount_paid` | Numeric(10,2) | |
| `ai_quota` | int | default 10 |
| `ai_quota_used` | int | default 0, reset on renewal |
| `billing_period_start` | DateTime(tz) | |
| `expires_at` | DateTime(tz) | now + 30 days |
| `created_at` | DateTime(tz) | server_default |

### `ai_generations` table (new)
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK → users | indexed |
| `subscription_id` | UUID FK → subscriptions | nullable (extra credits have no subscription row) |
| `provider` | enum: `suno`, `self_hosted` | |
| `prompt` | Text | |
| `style_prompt` | Text | nullable |
| `status` | enum: `pending`, `processing`, `completed`, `failed` | |
| `result_loop_id` | UUID FK → loops | nullable, set on completion |
| `is_extra` | bool | True if deducted from `ai_extra_credits` |
| `error_message` | Text | nullable |
| `created_at` | DateTime(tz) | server_default |

---

## API Endpoints

### Subscriptions (`/api/v1/subscriptions`)
```
POST   /subscriptions/initiate                      → initiate monthly premium payment, returns payment URL
POST   /subscriptions/webhook/flutterwave           → on success: create/renew subscription, reset quota
POST   /subscriptions/webhook/paystack              → same
GET    /subscriptions/me                            → active subscription + quota used (auth required)
POST   /subscriptions/extras/initiate               → buy extra generation slots
POST   /subscriptions/extras/webhook/flutterwave    → on success: increment ai_extra_credits
POST   /subscriptions/extras/webhook/paystack       → same
```

### AI Generation (`/api/v1/ai`)
```
POST   /ai/generate                  → submit {prompt, style_prompt?, provider}
GET    /ai/generations               → user's generation history (paginated)
GET    /ai/generations/{id}          → poll single generation status
```

### Admin additions (`/api/v1/admin`)
```
PUT    /admin/users/{user_id}/ai-enabled   → body: {"enabled": true|false}
GET    /admin/ai/generations               → all generation logs, paginated
```

---

## AI Generation Flow

`POST /ai/generate` guard order:
1. User authenticated (JWT)
2. `user.ai_enabled == True` → 403 if disabled
3. Active subscription exists (`status=active`, `expires_at > now`) → 402 if not subscribed
4. `subscription.ai_quota_used < subscription.ai_quota` → if exhausted, check `user.ai_extra_credits > 0` → 402 if none
5. Atomically deduct quota or extra credit; create `ai_generations` row (`status=pending`)
6. Dispatch Celery task:
   - Call Suno or self-hosted API with prompt
   - Poll/await result
   - Download audio bytes
   - Run through existing `create_loop()` pipeline (WAV validation, preview MP3, S3 upload, AES encryption, waveform)
   - Update `ai_generations.result_loop_id` and `status=completed`
   - On failure: set `status=failed`, `error_message`, refund quota/credit

### Suno integration
- `POST {suno_api_url}/generate` with `{prompt, style, make_instrumental}`
- Poll `GET {suno_api_url}/generations/{id}` until `status=complete`
- Download MP3 from result URL

### Self-hosted integration
- `POST {ai_selfhosted_url}/generate` → returns audio bytes directly

---

## Rate Limiting

- AI endpoints rate-limited by **user ID** (not IP) via slowapi custom key function
- Limit: **10 requests/minute** per user (prevents runaway polling/abuse)

---

## Subscription Renewal Webhook

On successful recurring payment event:
1. Look up user's existing active subscription by `user_id`
2. Reset `ai_quota_used = 0`
3. Update `expires_at = now + 30 days`, `billing_period_start = now`
4. Store new `payment_reference` (each cycle has a unique reference)

On first payment (new subscription):
1. Create new `Subscription` row with `status=active`

---

## Configuration (new env vars)
```
SUNO_API_KEY=
SUNO_API_URL=https://api.suno.ai
AI_SELFHOSTED_URL=http://localhost:8001
AI_SELFHOSTED_API_KEY=
AI_EXTRA_CREDITS_PRICE=500        # price in lowest currency unit (kobo/pesewas)
AI_EXTRA_CREDITS_QUANTITY=5       # how many credits per extra purchase
SUBSCRIPTION_MONTHLY_PRICE=2000
```

---

## Files to Create / Modify

### New files
- `app/models/subscription.py` — Subscription, SubscriptionPlan, SubscriptionStatus
- `app/models/ai_generation.py` — AIGeneration, AIProvider, AIGenerationStatus
- `app/schemas/subscription.py`
- `app/schemas/ai_generation.py`
- `app/services/subscription_service.py`
- `app/services/ai_service.py` — provider abstraction (suno + self_hosted)
- `app/routers/subscriptions.py`
- `app/routers/ai.py`
- `app/tasks/ai_tasks.py` — Celery task for async generation
- `alembic/versions/xxxx_add_subscription_ai.py`

### Modified files
- `app/models/user.py` — add `ai_enabled`, `ai_extra_credits`
- `app/config.py` — add AI + subscription env vars
- `app/routers/admin.py` — add AI enable/disable + generation log endpoints
- `app/middleware/rate_limit.py` — add user-ID-keyed limiter
- `app/main.py` — register new routers
- `app/models/__init__.py` — import new models
