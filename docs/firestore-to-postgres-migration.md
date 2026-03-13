# Firestore to Postgres Migration Runbook

This runbook migrates production Firestore data into the deployed Postgres database.

## 1. Preconditions

- Postgres schema is current:

```bash
python manage.py migrate --settings=config.settings.prod
```

- You have:
  - Production `DATABASE_URL`
  - Firebase service account (either file path or base64 JSON)
  - (Optional) Firestore project id

## 2. Dry-run first (required)

Use this to validate mappings and transforms without writing rows.

```bash
python manage.py migrate_firestore_to_postgres \
  --config apps/core/migration/firestore_to_postgres.mapping.json \
  --settings=config.settings.prod \
  --dry-run \
  --log-level INFO
```

Alternative if you have a key file instead of base64 JSON:

```bash
python manage.py migrate_firestore_to_postgres \
  --config apps/core/migration/firestore_to_postgres.mapping.json \
  --settings=config.settings.prod \
  --service-account /absolute/path/to/firebase-service-account.json \
  --project-id "$FIREBASE_PROJECT_ID" \
  --dry-run \
  --log-level INFO
```

## 3. Live migration

When dry-run logs look clean:

```bash
python manage.py migrate_firestore_to_postgres \
  --config apps/core/migration/firestore_to_postgres.mapping.json \
  --settings=config.settings.prod \
  --batch-size 500 \
  --log-level INFO
```

Notes:
- The migration is idempotent (`ON CONFLICT DO UPDATE/DO NOTHING`).
- Mapping order loads `clients` before `surveys/offers` to satisfy FK dependencies.
- Invalid foreign references are skipped and logged instead of aborting the full run.

## 4. Post-migration verification

Run row counts:

```sql
SELECT 'users' AS table, COUNT(*) FROM users
UNION ALL SELECT 'clients', COUNT(*) FROM clients
UNION ALL SELECT 'surveys', COUNT(*) FROM surveys
UNION ALL SELECT 'offers', COUNT(*) FROM offers
UNION ALL SELECT 'questions', COUNT(*) FROM questions
UNION ALL SELECT 'responses', COUNT(*) FROM responses
UNION ALL SELECT 'redemptions', COUNT(*) FROM redemptions
UNION ALL SELECT 'verifications', COUNT(*) FROM verifications
UNION ALL SELECT 'dashboard_counters', COUNT(*) FROM dashboard_counters;
```

Check key uniqueness constraints:

```sql
SELECT user_id, survey_id, COUNT(*)
FROM responses
GROUP BY 1,2
HAVING COUNT(*) > 1;

SELECT user_id, offer_id, COUNT(*)
FROM redemptions
GROUP BY 1,2
HAVING COUNT(*) > 1;
```

Expected result for both queries: `0 rows`.

## 5. Optional backfill of computed counters

After migration, recalculate dashboard counters from source tables:

```bash
python manage.py shell --settings=config.settings.prod -c "from apps.counters.tasks import recompute_active_surveys,recompute_total_responses,recompute_active_offers,recompute_total_paid_out,recompute_extended_dashboard; [f() for f in [recompute_active_surveys,recompute_total_responses,recompute_active_offers,recompute_total_paid_out,recompute_extended_dashboard]]"
```
