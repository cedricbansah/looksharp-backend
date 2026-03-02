# Phase 1 Plan: Scaffold + Users App + Auth

**Status:** Approved
**Effective date:** 2026-03-02
**Repo:** `looksharp-backend` (`/Users/cedricbansah/Documents/looksharp-backend`)
**Depends on:** `BACKEND_CONTRACT_V1.md`, `DJANGO_SCAFFOLD_PLAN.md`

---

## Context

Phase 1 creates the `looksharp-backend` repo from scratch and implements the one piece
everything else depends on: Firebase token authentication wired to a live `User` model.
Until auth works end-to-end, no other endpoint can be built or verified.

The scaffold creates all 10 Django apps as empty stubs so the project is fully importable
from day one. The users app and FirebaseAuthentication are the only pieces with real
implementation at the end of this phase.

**Target repo:** `/Users/cedricbansah/Documents/looksharp-backend`
**Python:** 3.11 (install via brew) + pip + venv
**Django:** 4.2 LTS + DRF 3.15

---

## Step 1 — Install Python 3.11

Python 3.11 is not currently installed. Install via Homebrew:

```bash
brew install python@3.11
```

Verify: `/opt/homebrew/bin/python3.11 --version` → `Python 3.11.x`

---

## Step 2 — Create repo + venv

```bash
mkdir /Users/cedricbansah/Documents/looksharp-backend
cd /Users/cedricbansah/Documents/looksharp-backend
git init
/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate
```

---

## Step 3 — Write requirements files

**`requirements/base.txt`**
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

**`requirements/dev.txt`**
```
-r base.txt
pytest==8.*
pytest-django==4.*
pytest-mock==3.*
factory-boy==3.*
freezegun==1.*
black==24.*
ruff==0.4.*
```

**`requirements/prod.txt`**
```
-r base.txt
sentry-sdk==2.*
```

Install dev deps:
```bash
pip install -r requirements/dev.txt
```

---

## Step 4 — Django project scaffold

```bash
django-admin startproject config .
```

This creates `config/` (settings.py, urls.py, wsgi.py, asgi.py) and `manage.py` at root.

---

## Step 5 — Settings split

Delete `config/settings.py`. Create `config/settings/` directory with:

**`config/settings/__init__.py`** — empty

**`config/settings/base.py`**
```python
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "django_celery_beat",
    # Apps
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

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
AUTH_USER_MODEL = "users.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates",
              "DIRS": [], "APP_DIRS": True,
              "OPTIONS": {"context_processors": [
                  "django.template.context_processors.request",
                  "django.contrib.auth.context_processors.auth",
                  "django.contrib.messages.context_processors.messages",
              ]}}]

DATABASES = {"default": env.db("DATABASE_URL")}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.core.authentication.FirebaseAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
}

CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_TASK_SERIALIZER = "json"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

FIREBASE_SERVICE_ACCOUNT_KEY_PATH = env(
    "FIREBASE_SERVICE_ACCOUNT_KEY_PATH",
    default=str(BASE_DIR / "firebase-service-account.json")
)

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
```

**`config/settings/dev.py`**
```python
from .base import *

DEBUG = True
ALLOWED_HOSTS = ["*"]
```

**`config/settings/staging.py`** and **`config/settings/prod.py`** — stubs for now:
```python
from .base import *
# TODO: add Sentry, security headers
```

---

## Step 6 — Celery config

**`config/celery.py`**
```python
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
app = Celery("looksharp")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

**`config/__init__.py`**
```python
from .celery import app as celery_app
__all__ = ("celery_app",)
```

---

## Step 7 — Create all 10 apps (stubs)

```bash
mkdir apps && touch apps/__init__.py
python manage.py startapp core apps/core
python manage.py startapp users apps/users
python manage.py startapp surveys apps/surveys
python manage.py startapp responses apps/responses
python manage.py startapp offers apps/offers
python manage.py startapp verifications apps/verifications
python manage.py startapp withdrawals apps/withdrawals
python manage.py startapp paystack apps/paystack
python manage.py startapp counters apps/counters
python manage.py startapp webhooks apps/webhooks
```

For each app, update `apps.py` `name` field to `apps.<appname>`.
e.g. `apps/users/apps.py`:
```python
class UsersConfig(AppConfig):
    name = "apps.users"
```

Each stub app gets empty `serializers.py`, `tasks.py`, and `urls.py` with `urlpatterns = []`.

---

## Step 8 — Root URLs

**`config/urls.py`**
```python
from django.urls import path, include

urlpatterns = [
    path("api/v1/users/", include("apps.users.urls")),
    path("api/v1/surveys/", include("apps.surveys.urls")),
    path("api/v1/responses/", include("apps.responses.urls")),
    path("api/v1/offers/", include("apps.offers.urls")),
    path("api/v1/verifications/", include("apps.verifications.urls")),
    path("api/v1/withdrawals/", include("apps.withdrawals.urls")),
    path("api/v1/paystack/", include("apps.paystack.urls")),
    path("api/v1/webhooks/", include("apps.webhooks.urls")),
    path("api/v1/admin/dashboard/", include("apps.counters.urls")),
]
```

---

## Step 9 — Core app

**`apps/core/authentication.py`**
```python
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings


def _get_firebase_app():
    if not firebase_admin._apps:
        cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH)
        firebase_admin.initialize_app(cred)
    return firebase_admin.get_app()


class FirebaseAuthentication(BaseAuthentication):
    """
    Verify a Firebase ID token from the Authorization header.
    Resolves or creates a User row in Postgres keyed by Firebase UID.
    Returns (user, None) on success; raises AuthenticationFailed on bad token.
    """

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None  # Let other authenticators try
        id_token = auth_header.split("Bearer ", 1)[1].strip()
        if not id_token:
            return None
        try:
            _get_firebase_app()
            decoded = firebase_auth.verify_id_token(id_token)
        except firebase_auth.RevokedIdTokenError:
            raise AuthenticationFailed("Firebase token has been revoked.")
        except firebase_auth.ExpiredIdTokenError:
            raise AuthenticationFailed("Firebase token has expired.")
        except Exception:
            raise AuthenticationFailed("Invalid Firebase token.")

        uid = decoded["uid"]
        email = decoded.get("email", "")

        from apps.users.models import User
        user, _ = User.objects.get_or_create(
            id=uid,
            defaults={"email": email, "points": 0},
        )
        return (user, None)
```

**`apps/core/permissions.py`**
```python
from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """User must have is_admin=True."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)


class IsVerified(BasePermission):
    """User must have is_verified=True."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_verified)


class IsOwnerOrAdmin(BasePermission):
    """Object-level: user owns the resource or is admin."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin:
            return True
        return getattr(obj, "user_id", None) == request.user.id
```

**`apps/core/pagination.py`**
```python
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
```

**`apps/core/exceptions.py`**
```python
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        response.data = {"error": response.data}
    return response
```

---

## Step 10 — User model

**`apps/users/models.py`**
```python
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, id, email, **extra_fields):
        user = self.model(id=id, email=email, **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    # Firebase UID is the primary key — no auto-generated integer PK
    id = models.CharField(max_length=128, primary_key=True)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=100, default="Ghana")
    profile_photo_url = models.URLField(blank=True)

    # Server-controlled — never written directly by clients
    points = models.PositiveIntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    recipient_code = models.CharField(max_length=100, blank=True)
    is_admin = models.BooleanField(default=False)
    welcome_bonus_claimed = models.BooleanField(default=False)

    # JSON arrays — mirrors Firestore contract
    surveys_completed = models.JSONField(default=list)
    offers_claimed = models.JSONField(default=list)

    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Required by AbstractBaseUser
    last_login = None  # disable unused last_login field
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.email
```

---

## Step 11 — Users serializers

**`apps/users/serializers.py`**
```python
from rest_framework import serializers
from .models import User

# Fields the client is ALLOWED to update (backend contract §4.2)
CLIENT_WRITABLE_FIELDS = [
    "first_name", "last_name", "phone",
    "date_of_birth", "gender", "country", "profile_photo_url",
]

# Server-controlled fields — read-only in all client-facing serializers
SERVER_CONTROLLED_FIELDS = [
    "points", "is_verified", "recipient_code", "is_admin",
    "welcome_bonus_claimed", "surveys_completed", "offers_claimed",
]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "email",
            *CLIENT_WRITABLE_FIELDS,
            *SERVER_CONTROLLED_FIELDS,
            "is_deleted", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "email", *SERVER_CONTROLLED_FIELDS,
                            "is_deleted", "created_at", "updated_at"]


class UserUpdateSerializer(serializers.ModelSerializer):
    """PATCH /users/me/ — only client-writable fields accepted."""
    class Meta:
        model = User
        fields = CLIENT_WRITABLE_FIELDS
```

---

## Step 12 — Users views + URLs

**`apps/users/views.py`**
```python
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from .serializers import UserSerializer, UserUpdateSerializer


class MeView(RetrieveUpdateAPIView):
    """
    GET  /api/v1/users/me/  — return authenticated user's profile
    PATCH /api/v1/users/me/ — update client-writable fields only
    """
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return UserUpdateSerializer
        return UserSerializer
```

**`apps/users/urls.py`**
```python
from django.urls import path
from .views import MeView

urlpatterns = [
    path("me/", MeView.as_view(), name="users-me"),
]
```

---

## Step 13 — Services stubs

**`services/__init__.py`** — empty

**`services/paystack.py`** — stub
```python
"""
Paystack service — typed HTTP wrappers.
All methods raise requests.HTTPError on non-2xx responses.
Implemented in Phase 2 (payout path).
"""
```

**`services/hubtel.py`** — stub
```python
"""
Hubtel SMS service.
Migrated from send-sms-function and kyc-verification-sms-function.
Implemented in Phase 4 (SMS).
"""
```

---

## Step 14 — Docker Compose + Dockerfile

**`Dockerfile`**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements/base.txt requirements/base.txt
RUN pip install --no-cache-dir -r requirements/base.txt
COPY . .
```

**`docker-compose.yml`**
```yaml
version: "3.9"
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: looksharp
      POSTGRES_USER: looksharp
      POSTGRES_PASSWORD: looksharp
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

---

## Step 15 — Supporting files

**`.env`** (local only, gitignored)
```
DJANGO_SETTINGS_MODULE=config.settings.dev
SECRET_KEY=dev-secret-key-change-in-prod
DATABASE_URL=postgres://looksharp:looksharp@localhost:5432/looksharp
REDIS_URL=redis://localhost:6379/0
FIREBASE_SERVICE_ACCOUNT_KEY_PATH=./firebase-service-account.json
PAYSTACK_SECRET_KEY=sk_test_placeholder
HUBTEL_USERNAME=placeholder
HUBTEL_PASSWORD=placeholder
```

**`.env.example`** (committed) — same as above with placeholder values

**`.gitignore`**
```
.venv/
__pycache__/
*.pyc
*.pyo
.env
firebase-service-account.json
*.sqlite3
.DS_Store
dist/
*.egg-info/
.pytest_cache/
```

**`pytest.ini`**
```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings.dev
python_files = tests.py test_*.py *_test.py
```

---

## Step 16 — Tests

**`apps/users/tests.py`** — 6 test cases covering the full auth + profile contract:

```python
import pytest
from unittest.mock import patch
from rest_framework.test import APIClient
from apps.users.models import User


@pytest.fixture
def mock_firebase():
    """Patch firebase_auth.verify_id_token for all tests."""
    with patch("apps.core.authentication.firebase_auth.verify_id_token") as mock_verify, \
         patch("apps.core.authentication._get_firebase_app"):
        yield mock_verify


@pytest.mark.django_db
class TestMeEndpoint:

    def test_get_me_returns_profile(self, mock_firebase):
        mock_firebase.return_value = {"uid": "uid-1", "email": "a@b.com"}
        User.objects.create(id="uid-1", email="a@b.com", points=100)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        response = client.get("/api/v1/users/me/")
        assert response.status_code == 200
        assert response.data["email"] == "a@b.com"
        assert response.data["points"] == 100

    def test_get_me_creates_user_on_first_login(self, mock_firebase):
        mock_firebase.return_value = {"uid": "new-uid", "email": "new@example.com"}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        response = client.get("/api/v1/users/me/")
        assert response.status_code == 200
        assert User.objects.filter(id="new-uid").exists()

    def test_patch_me_updates_writable_fields(self, mock_firebase):
        mock_firebase.return_value = {"uid": "uid-2", "email": "b@b.com"}
        User.objects.create(id="uid-2", email="b@b.com")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        response = client.patch("/api/v1/users/me/", {"first_name": "Kofi"}, format="json")
        assert response.status_code == 200
        assert User.objects.get(id="uid-2").first_name == "Kofi"

    def test_patch_me_cannot_write_server_controlled_fields(self, mock_firebase):
        mock_firebase.return_value = {"uid": "uid-3", "email": "c@c.com"}
        User.objects.create(id="uid-3", email="c@c.com", points=50)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        response = client.patch("/api/v1/users/me/", {"points": 9999}, format="json")
        assert response.status_code == 200
        assert User.objects.get(id="uid-3").points == 50  # unchanged

    def test_get_me_without_token_returns_401(self):
        client = APIClient()
        response = client.get("/api/v1/users/me/")
        assert response.status_code == 401

    def test_get_me_with_invalid_token_returns_401(self):
        with patch("apps.core.authentication.firebase_auth.verify_id_token") as mock_verify, \
             patch("apps.core.authentication._get_firebase_app"):
            mock_verify.side_effect = Exception("invalid token")
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION="Bearer bad-token")
            response = client.get("/api/v1/users/me/")
            assert response.status_code == 401
```

---

## Step 17 — Initial git commit

```bash
git add .
git commit -m "Phase 1: scaffold looksharp-backend with users app and Firebase auth"
```

---

## Files Created (complete list)

```
looksharp-backend/
├── config/
│   ├── __init__.py              celery app export
│   ├── celery.py                Celery app config
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py              core settings
│   │   ├── dev.py               DEBUG=True
│   │   ├── staging.py           stub
│   │   └── prod.py              stub
│   ├── urls.py                  root URL routing
│   ├── wsgi.py                  (generated)
│   └── asgi.py                  (generated)
├── apps/
│   ├── __init__.py
│   ├── core/
│   │   ├── authentication.py    FirebaseAuthentication
│   │   ├── permissions.py       IsAdmin, IsVerified, IsOwnerOrAdmin
│   │   ├── pagination.py        StandardPagination
│   │   └── exceptions.py        custom_exception_handler
│   ├── users/
│   │   ├── models.py            User (Firebase UID PK)
│   │   ├── serializers.py       UserSerializer, UserUpdateSerializer
│   │   ├── views.py             MeView
│   │   ├── urls.py              /me/
│   │   └── tests.py             6 test cases
│   └── [surveys, responses, offers, verifications,
│        withdrawals, paystack, counters, webhooks]/
│       each has: models.py, serializers.py, views.py,
│                 urls.py (empty), tasks.py (empty)
├── services/
│   ├── __init__.py
│   ├── paystack.py              stub
│   └── hubtel.py                stub
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── manage.py                    (generated)
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
├── .env                         (gitignored)
├── .env.example
└── .gitignore
```

---

## Verification Checklist

```bash
python manage.py check          # "System check identified no issues"
python manage.py migrate        # runs without errors
pytest apps/users/tests.py -v   # 6 tests pass
python manage.py runserver      # starts on :8000
docker compose up               # all 5 services healthy
```

Manual smoke test (requires real Firebase service account + token):
```bash
curl -H "Authorization: Bearer <real-token>" http://localhost:8000/api/v1/users/me/
# → 200 with user JSON

curl http://localhost:8000/api/v1/users/me/
# → 401 Unauthorized
```
