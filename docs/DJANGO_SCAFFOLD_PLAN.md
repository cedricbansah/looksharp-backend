# Django Backend Scaffold Plan

**Status:** Approved
**Effective date:** 2026-03-01
**Repo:** `looksharp-backend` (separate repo, `/Users/cedricbansah/Documents/looksharp-backend`)
**Depends on:** `BACKEND_CONTRACT_V1.md`, `RUNTIME_ARCHITECTURE_V1.md`, `FUNCTION_MIGRATION_MATRIX.md`

---

## Context

This plan scaffolds the Django + DRF project that will replace Firebase Cloud Functions and
Firestore as the backend for LookSharp. The mobile app (Flutter) and admin app (Next.js)
currently read/write Firestore directly; this backend will own all business logic, enforce the
backend contract, and expose a versioned REST API under `/api/v1/`.

**Auth stays on Firebase (Phase A):** Django verifies Firebase ID tokens per request.
Firebase Auth and Firebase Storage are not replaced at this stage.

**Stack:**
- Python 3.11 + pip + venv
- Django 4.2 LTS + Django REST Framework 3.15
- PostgreSQL 15
- Celery 5 + Redis 7 (queue + cache)
- Docker Compose (local dev: api + worker + scheduler + db + redis)

---

## Directory Structure

```
looksharp-backend/
│
├── config/
│   ├── settings/
│   │   ├── base.py        # Core settings, INSTALLED_APPS, DRF, Celery, logging
│   │   ├── dev.py         # DEBUG=True, local Postgres/Redis
│   │   ├── staging.py     # DEBUG=False, env-driven
│   │   └── prod.py        # Hardened headers + Sentry
│   ├── urls.py            # Root URL routing (/api/v1/...)
│   ├── celery.py          # Celery app + autodiscover
│   ├── wsgi.py
│   └── asgi.py
│
├── apps/
│   ├── core/              # Shared infra — no domain logic
│   │   ├── authentication.py   # Firebase token → User resolution
│   │   ├── permissions.py      # IsAdmin, IsVerified, IsResourceOwner
│   │   ├── pagination.py       # StandardPagination (page_size=50)
│   │   └── exceptions.py
│   │
│   ├── users/             # User model + profile endpoints
│   ├── surveys/           # Survey, Question, SurveyCategory
│   ├── responses/         # Response (answers as JSONField) + reward task
│   ├── offers/            # Offer, Redemption, OfferCategory + expiry task
│   ├── verifications/     # KYC Verification + approve/reject + KYC SMS task
│   ├── withdrawals/       # Withdrawal + payout side-effect task
│   ├── paystack/          # Typed proxy endpoints (replaces generic Cloud Function proxy)
│   ├── counters/          # DashboardCounter + recompute tasks
│   └── webhooks/          # POST /webhooks/paystack/ (HMAC verified)
│
├── services/
│   ├── paystack.py        # All Paystack HTTP calls (typed methods)
│   └── hubtel.py          # SMS via Hubtel (bulk + single, phone normalisation)
│
├── requirements/
│   ├── base.txt           # Production dependencies
│   ├── dev.txt            # + pytest, factory-boy, black, ruff
│   └── prod.txt           # + sentry-sdk
│
├── manage.py
├── Dockerfile             # python:3.11-slim
├── docker-compose.yml     # api + worker + scheduler + db + redis
├── pytest.ini
└── .env.example
```

---

## Key Files — Content Spec

### `requirements/base.txt`
```
Django==4.2.*
djangorestframework==3.15.*
django-environ==0.11.*
psycopg2-binary==2.9.*
celery[redis]==5.3.*
django-celery-beat==2.6.*
firebase-admin==6.5.*
requests==2.31.*
gunicorn==21.*
```

### `config/settings/base.py` — key sections

```python
INSTALLED_APPS = [
    # Django built-ins ...
    "rest_framework",
    "django_celery_beat",
    "apps.core",
    "apps.users",
    "apps.surveys",
    "apps.responses",
    "apps.offers",
    "apps.verifications",
    "apps.withdrawals",
    "apps.paystack",
    "apps.counters",
    "apps.webhooks",
]

AUTH_USER_MODEL = "users.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.core.authentication.FirebaseAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 50,
}

CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_TASK_SERIALIZER = "json"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
```

### `apps/core/authentication.py` — Firebase Phase A auth

```python
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

class FirebaseAuthentication(BaseAuthentication):
    """Verify Firebase ID token → resolve/create User row in Postgres."""
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        id_token = auth_header.split("Bearer ")[1]
        try:
            decoded = firebase_auth.verify_id_token(id_token)
        except Exception:
            raise AuthenticationFailed("Invalid or expired Firebase token")
        from apps.users.models import User
        user, _ = User.objects.get_or_create(
            id=decoded["uid"],
            defaults={"email": decoded.get("email", ""), "points": 0},
        )
        return (user, None)
```

### `apps/users/models.py` — Firebase UID as primary key

```python
class User(AbstractBaseUser):
    id = models.CharField(max_length=128, primary_key=True)  # Firebase UID
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=100, default="Ghana")
    profile_photo_url = models.URLField(blank=True)
    # Server-controlled fields — never written directly by clients
    points = models.PositiveIntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    recipient_code = models.CharField(max_length=100, blank=True)
    is_admin = models.BooleanField(default=False)
    welcome_bonus_claimed = models.BooleanField(default=False)
    surveys_completed = models.JSONField(default=list)
    offers_claimed = models.JSONField(default=list)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    USERNAME_FIELD = "email"
    class Meta:
        db_table = "users"
```

### `config/celery.py`

```python
import os
from celery import Celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
app = Celery("looksharp")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

### `docker-compose.yml`

```yaml
version: "3.9"
services:
  db:
    image: postgres:15
    environment: { POSTGRES_DB: looksharp, POSTGRES_USER: looksharp, POSTGRES_PASSWORD: looksharp }
    ports: ["5432:5432"]
    volumes: [postgres_data:/var/lib/postgresql/data]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
  api:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes: [.:/app]
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [db, redis]
  worker:
    build: .
    command: celery -A config worker -Q critical,default,bulk -l info
    volumes: [.:/app]
    env_file: .env
    depends_on: [db, redis]
  scheduler:
    build: .
    command: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    volumes: [.:/app]
    env_file: .env
    depends_on: [db, redis]
volumes:
  postgres_data:
```

### `.env.example`

```
DJANGO_SETTINGS_MODULE=config.settings.dev
SECRET_KEY=change-me
DATABASE_URL=postgres://looksharp:looksharp@localhost:5432/looksharp
REDIS_URL=redis://localhost:6379/0
FIREBASE_SERVICE_ACCOUNT_KEY_PATH=./firebase-service-account.json
PAYSTACK_SECRET_KEY=sk_test_...
HUBTEL_USERNAME=...
HUBTEL_PASSWORD=...
```

---

## API Surface (full list)

### Mobile — Firebase token auth

| Method | Endpoint |
|---|---|
| GET/PATCH | `/api/v1/users/me/` |
| POST | `/api/v1/users/me/welcome-bonus/claim/` |
| GET | `/api/v1/surveys/` |
| GET | `/api/v1/surveys/{id}/` |
| POST | `/api/v1/responses/` |
| GET | `/api/v1/responses/` |
| GET | `/api/v1/offers/` |
| POST | `/api/v1/redemptions/` |
| GET | `/api/v1/redemptions/` |
| POST | `/api/v1/verifications/` |
| GET | `/api/v1/verifications/` |
| POST | `/api/v1/withdrawals/` |
| GET | `/api/v1/withdrawals/` |
| GET | `/api/v1/paystack/banks/` |
| POST | `/api/v1/paystack/transfer-recipients/` |
| POST | `/api/v1/paystack/transfers/` |
| POST | `/api/v1/paystack/transfers/{code}/finalize/` |

### Admin — `is_admin` required

| Method | Endpoint |
|---|---|
| GET | `/api/v1/admin/dashboard/` |
| CRUD | `/api/v1/admin/surveys/` |
| CRUD | `/api/v1/admin/surveys/{id}/questions/` |
| CRUD | `/api/v1/admin/clients/` |
| CRUD | `/api/v1/admin/offers/` |
| GET | `/api/v1/admin/responses/` |
| GET | `/api/v1/admin/users/` |
| POST | `/api/v1/admin/users/{id}/grant-admin/` |
| GET | `/api/v1/admin/verifications/` |
| POST | `/api/v1/admin/verifications/{id}/approve/` |
| POST | `/api/v1/admin/verifications/{id}/reject/` |
| POST | `/api/v1/admin/verifications/{id}/create-recipient/` |
| GET | `/api/v1/admin/withdrawals/` |
| POST | `/api/v1/admin/counters/rebuild/` |

### Webhook — HMAC verified, no auth

| Method | Endpoint |
|---|---|
| POST | `/api/v1/webhooks/paystack/` |

---

## Celery Queues

| Queue | Tasks |
|---|---|
| `critical` | Paystack webhook processing, response reward application |
| `default` | KYC SMS, counter updates, offer expiry |
| `bulk` | Survey/offer activation SMS fanout (all users) |

---

## Scaffold Execution Order

1. `mkdir looksharp-backend && git init`
2. `python3.11 -m venv .venv && source .venv/bin/activate`
3. Write `requirements/` files
4. `pip install -r requirements/dev.txt`
5. `django-admin startproject config .`
6. Replace `config/settings.py` → `config/settings/` split
7. `mkdir apps && python manage.py startapp <name> apps/<name>` × 10
8. Write `apps/core/authentication.py`, `permissions.py`, `pagination.py`
9. Write `apps/users/models.py`
10. Write `config/celery.py` + update `config/__init__.py`
11. Write `config/urls.py` (all routes, empty app urls)
12. Write `services/paystack.py` + `services/hubtel.py` (stubs)
13. Write `docker-compose.yml`, `Dockerfile`, `.env.example`, `pytest.ini`, `.gitignore`
14. `python manage.py check` — must pass with no errors
15. `python manage.py migrate` — initial migrations
16. `git add . && git commit -m "Initial Django project scaffold"`

---

## Verification Checklist

- [ ] `python manage.py check` → `System check identified no issues`
- [ ] `python manage.py migrate` → no errors
- [ ] `python manage.py runserver` → starts on port 8000
- [ ] `docker compose up` → all 5 services healthy
- [ ] `GET /api/v1/users/me/` with no token → `401 Unauthorized`
- [ ] `pytest` → test suite runs (0 tests, no collection errors)
