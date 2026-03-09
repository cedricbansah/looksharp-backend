# Railway Deployment Guide

Deploy LookSharp Backend to Railway with PostgreSQL and Redis.

## Prerequisites

- Railway account (https://railway.app)
- GitHub repo connected to Railway
- Firebase service account JSON file
- Paystack API keys (test for staging)

## Step 1: Create Railway Project

1. Go to https://railway.app/new
2. Click **"Deploy from GitHub repo"**
3. Select `looksharp-backend` repository
4. Railway will auto-detect the Dockerfile

## Step 2: Add PostgreSQL

1. In your Railway project, click **"+ New"**
2. Select **"Database" → "PostgreSQL"**
3. Railway automatically sets `DATABASE_URL` for your app

## Step 3: Add Redis

1. Click **"+ New"**
2. Select **"Database" → "Redis"**
3. Railway automatically sets `REDIS_URL` for your app

## Step 4: Configure Environment Variables

Click on your service (the GitHub one), go to **Variables** tab, and add:

### Required Variables

```bash
# Django settings
DJANGO_SETTINGS_MODULE=config.settings.staging
SECRET_KEY=<generate-a-secure-key>
ALLOWED_HOSTS=*.up.railway.app

# CORS (your admin dashboard URL)
CORS_ALLOWED_ORIGINS=https://looksharp-staging.web.app,https://your-admin.vercel.app
CSRF_TRUSTED_ORIGINS=https://looksharp-staging.web.app

# Security (Railway handles SSL termination)
USE_SECURE_PROXY_SSL_HEADER=true

# Firebase (base64-encoded service account JSON)
FIREBASE_SERVICE_ACCOUNT_JSON=<base64-encoded-json>

# Paystack (use test key for staging)
PAYSTACK_SECRET_KEY=sk_test_xxx

# Hubtel SMS (optional for staging)
HUBTEL_USERNAME=placeholder
HUBTEL_PASSWORD=placeholder

# Cloudflare R2 Storage
CLOUDFLARE_ACCOUNT_ID=xxx
R2_ACCESS_KEY_ID=xxx
R2_SECRET_ACCESS_KEY=xxx
R2_BUCKET_NAME=looksharp-staging
R2_PUBLIC_URL=https://pub-xxx.r2.dev
```

### Generate SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Encode Firebase Service Account

```bash
# On Mac/Linux
base64 -i firebase-service-account.json | tr -d '\n'

# Or with Python
python -c "import base64; print(base64.b64encode(open('firebase-service-account.json', 'rb').read()).decode())"
```

## Step 5: Deploy

Railway will auto-deploy when you push to the connected branch.

To trigger a manual deploy:
1. Go to your service in Railway
2. Click **"Deploy"** → **"Deploy Now"**

The `release` command in Procfile runs migrations automatically.

## Step 6: Verify Deployment

1. Get your Railway URL from the **Settings** tab
2. Test the health endpoint:
   ```bash
   curl https://your-app.up.railway.app/api/v1/health/
   ```
3. Test the API docs:
   ```
   https://your-app.up.railway.app/api/docs/
   ```

## Adding Celery Worker (Optional)

For background tasks, create a separate service:

1. Click **"+ New"** → **"Empty Service"**
2. Name it `looksharp-worker`
3. Connect the same GitHub repo
4. In **Settings**, set the start command:
   ```
   celery -A config worker -l info -Q critical,default,bulk
   ```
5. Add the same environment variables (copy from main service)
6. Link the same PostgreSQL and Redis instances

## Adding Celery Beat (Optional)

For scheduled tasks:

1. Create another empty service named `looksharp-beat`
2. Set start command:
   ```
   celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
   ```
3. Add same env vars and database links

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DJANGO_SETTINGS_MODULE` | Yes | `config.settings.staging` or `config.settings.prod` |
| `SECRET_KEY` | Yes | Django secret key (50+ chars) |
| `DATABASE_URL` | Auto | Set by Railway PostgreSQL |
| `REDIS_URL` | Auto | Set by Railway Redis |
| `ALLOWED_HOSTS` | Yes | `*.up.railway.app` or your domain |
| `CORS_ALLOWED_ORIGINS` | Yes | Comma-separated admin URLs |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Yes | Base64-encoded Firebase SA |
| `PAYSTACK_SECRET_KEY` | Yes | Paystack secret key |
| `USE_SECURE_PROXY_SSL_HEADER` | Yes | `true` (Railway handles SSL) |

## Troubleshooting

### Migrations fail
Check logs for database connection issues. Ensure PostgreSQL service is running.

### Firebase auth fails
Verify `FIREBASE_SERVICE_ACCOUNT_JSON` is correctly base64-encoded with no newlines.

### CORS errors
Add your admin dashboard URL to `CORS_ALLOWED_ORIGINS`.

### Health check fails
Check DATABASE_URL is set and PostgreSQL is accessible.

## Staging URL

After deployment, your API will be available at:
```
https://<your-service>.up.railway.app
```

Update your admin dashboard's `NEXT_PUBLIC_API_BASE_URL` to point to this URL.
