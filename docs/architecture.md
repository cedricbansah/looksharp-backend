# Architecture

## App Layout (`apps/`)

Each Django app owns its models, serializers, views, URLs, tasks, and tests. The `admin_urls.py` pattern separates admin-only routes from user-facing routes within the same app.

| App | Responsibility |
|---|---|
| `core` | `FirebaseAuthentication`, permission classes (`IsAdmin`, `IsVerified`, `IsOwnerOrAdmin`), pagination, exception handler |
| `users` | User profiles; server controls `points`, `is_verified`, `is_admin`. Firebase UID is the PK (CharField, not auto-int). |
| `surveys` | Survey definitions + `Question` models |
| `responses` | Survey submissions; unique constraint on `(user_id, survey_id)` prevents duplicates |
| `offers` | Offer catalog + `Redemption` model; unique constraint on `(user_id, offer)` |
| `verifications` | KYC workflow: submit → pending → approved/rejected by admin |
| `withdrawals` | Payout requests via Paystack; `transfer_reference` is the idempotency key |
| `paystack` | Thin Paystack API proxy |
| `webhooks` | Paystack webhook receiver (HMAC-SHA512 verified, `AllowAny`) |
| `counters` | Singleton `DashboardCounter` row recalculated by hourly Celery Beat jobs |

## Authentication

All endpoints use `FirebaseAuthentication` (Bearer token). The middleware verifies the Firebase ID token and calls `User.objects.get_or_create(id=uid)` — user rows are created automatically on first request. Webhooks use `AllowAny` with HMAC signature verification instead.

Admin endpoints use the `IsAdmin` permission class (checks `user.is_admin`), not Django's built-in admin system.

## Celery Queues

- `critical` — response rewards, payout processing, webhook handling (3 retries)
- `default` — scheduled counter recalculation, offer expiry
- `bulk` — SMS campaigns, backfills

Side-effects on response submission (`apply_side_effects` task) run on `critical` and use `select_for_update()` + `transaction.atomic()` to award points idempotently.

## URL Routing

`config/urls.py` mounts all apps. Admin endpoints from multiple apps share the `/api/v1/admin/` prefix via separate `admin_urls.py` files per app.

## Settings

`config/settings/base.py` → `dev.py` / `staging.py` / `prod.py`. Active settings are controlled by the `DJANGO_SETTINGS_MODULE` env var.
