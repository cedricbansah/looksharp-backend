# Common Commands

## Local Development

```bash
# Start backing services (Postgres + Redis)
docker-compose up -d db redis

# Run Django dev server
python manage.py runserver

# Run Celery worker (separate terminal)
celery -A config worker -Q critical,default,bulk -l info

# Run Celery Beat scheduler (separate terminal)
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Run all migrations
python manage.py migrate

# Check for migration drift
python manage.py makemigrations --check --dry-run
```

## Testing

```bash
# Run all tests
pytest

# Run tests for a specific app
pytest apps/users/
pytest apps/responses/tests.py

# Run a single test class or function
pytest apps/users/tests.py::TestMeEndpoint
pytest apps/users/tests.py::TestMeEndpoint::test_get_me_returns_profile
```

## Linting

```bash
# Lint a specific app (ruff)
ruff check apps/users/

# Lint all CI-checked files
ruff check apps/ config/settings/base.py config/urls.py services/paystack.py
```

## Firestore Migration

```bash
# Dry-run Firestore -> Postgres migration
python manage.py migrate_firestore_to_postgres \
  --config apps/core/migration/firestore_to_postgres.mapping.json \
  --settings=config.settings.prod \
  --dry-run

# Live run
python manage.py migrate_firestore_to_postgres \
  --config apps/core/migration/firestore_to_postgres.mapping.json \
  --settings=config.settings.prod
```

See `docs/firestore-to-postgres-migration.md` for full runbook and verification SQL.
