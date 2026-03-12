# Production Deployment Checklist

Target platform: Railway. Complete every item before going live.

---

## 1. Pre-deploy Code Checks

- [ ] Run `python manage.py check --deploy` — zero warnings
- [ ] Run `python manage.py makemigrations --check --dry-run` — no pending migrations
- [ ] Run `.venv/bin/pytest` — all tests pass
- [ ] **Fix**: `Dockerfile` installs `requirements/base.txt` — change to `requirements/prod.txt` so Sentry is included
- [ ] **Fix**: `config/celery.py` hardcodes `DJANGO_SETTINGS_MODULE=config.settings.dev` — must read from env
- [ ] **Fix**: `config/settings/prod.py` leaves API docs open (`/api/docs/`, `AllowAny`) — restrict or disable in prod
- [ ] **Fix**: No `LOGGING` config in any settings file — add structured logging to `prod.py`
- [ ] Confirm `DEBUG` is `False` throughout the prod settings chain

---

## 2. Railway Infrastructure

| Service | Notes |
|---|---|
| PostgreSQL | Add via **+ New → Database → PostgreSQL**. `DATABASE_URL` auto-injected. |
| Redis | Add via **+ New → Database → Redis**. `REDIS_URL` auto-injected. |
| Web (API) | Connect GitHub repo → main branch. `railway.toml` picks up `Dockerfile` automatically. |
| Worker | Empty service. Start command: `celery -A config worker -l info -Q critical,default,bulk --concurrency 2` |
| Beat | Empty service. Start command: `celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler` |

- [ ] **Web service → Settings → Networking → Exposed Port = `8080`**
- [ ] Worker and Beat services linked to the same PostgreSQL and Redis instances

---

## 3. Environment Variables

All three services (web, worker, beat) need identical env vars. Set in each service's **Variables** tab.

### Django / Security
```
DJANGO_SETTINGS_MODULE=config.settings.prod
SECRET_KEY=<generate — see below>
ALLOWED_HOSTS=<your-app>.up.railway.app
PORT=8080
USE_SECURE_PROXY_SSL_HEADER=true
```

### CORS / CSRF
```
CORS_ALLOWED_ORIGINS=https://your-admin.vercel.app
CORS_ALLOW_CREDENTIALS=false
CSRF_TRUSTED_ORIGINS=https://your-admin.vercel.app
```
> No trailing slashes on origins — Django CORS will reject them.

### Firebase
```
FIREBASE_SERVICE_ACCOUNT_JSON=<base64-encoded — see below>
```

### Paystack (live keys)
```
PAYSTACK_SECRET_KEY=sk_live_xxx
```

### Hubtel SMS
```
HUBTEL_USERNAME=<live-value>
HUBTEL_PASSWORD=<live-value>
```

### Cloudflare R2 Storage
```
CLOUDFLARE_ACCOUNT_ID=<value>
R2_ACCESS_KEY_ID=<value>
R2_SECRET_ACCESS_KEY=<value>
R2_BUCKET_NAME=looksharp-prod
R2_PUBLIC_URL=https://pub-xxx.r2.dev
```

### Error Tracking
```
SENTRY_DSN=<value from sentry.io project>
```

### Checklist
- [ ] All variables set on web service
- [ ] All variables copied to worker service
- [ ] All variables copied to beat service

---

## 4. Generate Secrets

**SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

**FIREBASE_SERVICE_ACCOUNT_JSON (base64, no newlines):**
```bash
base64 -i firebase-service-account.json | tr -d '\n'
```

---

## 5. First Deploy

- [ ] Trigger deploy on web service — watch deploy logs
- [ ] Confirm `release` process (`python manage.py migrate --noinput`) exits 0
- [ ] Create `DashboardCounter` singleton (run once via Railway shell or one-off command):
  ```bash
  python manage.py shell -c "from apps.counters.models import DashboardCounter; DashboardCounter.objects.get_or_create(id='dashboard')"
  ```
- [ ] Confirm Celery Beat periodic tasks are registered in the DB (`django_celery_beat` tables populated — check worker logs on first run)

---

## 6. Smoke Tests

```bash
# Health check
curl https://<app>.up.railway.app/api/v1/health/
# Expected: {"status": "healthy", "database": "connected"}

# Authenticated endpoint (replace TOKEN with a valid Firebase ID token)
curl -H "Authorization: Bearer <TOKEN>" https://<app>.up.railway.app/api/v1/users/me/
# Expected: 200 with user profile
```

- [ ] Health check returns `{"status": "healthy"}`
- [ ] Authenticated request returns `200`
- [ ] Send a test Paystack webhook event from the Paystack dashboard — verify HMAC check passes and worker processes it
- [ ] Submit a survey response — confirm points are awarded (check user balance)

---

## 7. Monitoring

- [ ] Sentry project created and `SENTRY_DSN` set — trigger a test error to confirm events arrive
- [ ] Bookmark Railway metrics dashboard (CPU, memory, request count) for baseline
- [ ] Optionally set Railway health check URL: `https://<app>.up.railway.app/api/v1/health/`

---

## Known Code Issues to Fix Before or After Launch

| Severity | File | Issue |
|---|---|---|
| Critical | `Dockerfile` | Installs `base.txt` not `prod.txt` — Sentry missing |
| Critical | `config/celery.py` | Hardcodes `DJANGO_SETTINGS_MODULE=dev` |
| High | `config/settings/prod.py` | API docs (`/api/docs/`) open with `AllowAny` |
| High | `config/settings/base.py` | No `LOGGING` config |
| Medium | `config/settings/prod.py` | No `CACHES` (Redis) or `STORAGES` config |
