# Config Enums Rollout Notes

## Admin Frontend

- Add `Manage Categories` entry points on both the surveys list page and the offers list page.
- Use the new admin APIs for category CRUD instead of Firestore reads:
  - `GET/POST /api/v1/admin/survey-categories/`
  - `PATCH/DELETE /api/v1/admin/survey-categories/{id}/`
  - `GET/POST /api/v1/admin/offer-categories/`
  - `PATCH/DELETE /api/v1/admin/offer-categories/{id}/`
- Survey and offer create/edit forms should load category options from `GET /api/v1/config/enums/`.
- The backend now validates survey and offer category values against the category tables. Unknown categories will be rejected with `400`.
- The response includes `survey_count` and `offer_count` so the UI can show usage on the category management screens.

## Mobile

- Stop reading `survey_categories` and `offer_categories` directly from Firestore.
- Load category lists and canonical labels from `GET /api/v1/config/enums/`.
- Cache the config response for up to one hour using the backend cache headers.
- Enum values are unchanged in this release:
  - network providers remain `MTN`, `Telecel`, `ATMoney`
  - statuses and ID type values remain unchanged
- Canonical display labels now come from the backend config response.

## Backend Operations

- New public endpoint: `GET /api/v1/config/enums/`
- New one-time backfill command:

```bash
python manage.py backfill_category_tables
```

- After backfill, Postgres is the runtime source of truth for survey and offer categories.
