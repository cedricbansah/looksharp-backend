from pathlib import Path

import environ
from celery.schedules import crontab

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
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
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
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
AUTH_USER_MODEL = "users.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

DATABASES = {"default": env.db("DATABASE_URL")}

AUTH_PASSWORD_VALIDATORS = []

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.core.authentication.FirebaseAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "300/min",
        "withdrawal_create": "10/hour",
        "verification_create": "10/hour",
        "paystack_webhook": "120/min",
    },
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = env.bool("CORS_ALLOW_CREDENTIALS", default=False)
SPECTACULAR_SETTINGS = {
    "TITLE": "LookSharp Backend API",
    "DESCRIPTION": "Django REST API for LookSharp mobile and admin clients.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
}

CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_TASK_SERIALIZER = "json"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    "offers-recompute-status-daily": {
        "task": "apps.offers.tasks.recompute_status",
        "schedule": crontab(minute=0, hour=0),
    },
    "counters-recompute-active-surveys-hourly": {
        "task": "apps.counters.tasks.recompute_active_surveys",
        "schedule": crontab(minute=0),
    },
    "counters-recompute-active-offers-hourly": {
        "task": "apps.counters.tasks.recompute_active_offers",
        "schedule": crontab(minute=5),
    },
    "counters-recompute-total-responses-hourly": {
        "task": "apps.counters.tasks.recompute_total_responses",
        "schedule": crontab(minute=10),
    },
    "counters-recompute-total-paid-out-hourly": {
        "task": "apps.counters.tasks.recompute_total_paid_out",
        "schedule": crontab(minute=15),
    },
    "counters-recompute-extended-hourly": {
        "task": "apps.counters.tasks.recompute_extended_dashboard",
        "schedule": crontab(minute=20),
    },
}

FIREBASE_SERVICE_ACCOUNT_KEY_PATH = env(
    "FIREBASE_SERVICE_ACCOUNT_KEY_PATH",
    default=str(BASE_DIR / "firebase-service-account.json"),
)
PAYSTACK_SECRET_KEY = env("PAYSTACK_SECRET_KEY", default="")
HUBTEL_USERNAME = env("HUBTEL_USERNAME", default="")
HUBTEL_PASSWORD = env("HUBTEL_PASSWORD", default="")

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
