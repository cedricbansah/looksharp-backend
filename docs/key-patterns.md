# Key Patterns

**Idempotency:** Enforced at the DB layer via unique constraints on `(user_id, survey_id)` for responses, `(user_id, offer)` for redemptions, and `transfer_reference` for withdrawals. Tasks also check application-level guards before writing.

**Soft deletes:** Models use `is_deleted` boolean; queries always filter `is_deleted=False`.

**Row-level locking:** `select_for_update()` used in critical write paths (response rewards, offer expiry, withdrawal processing) to prevent race conditions.

**Dashboard counters:** A singleton `DashboardCounter` (id=`'dashboard'`) is recalculated by staggered hourly Celery Beat tasks (`:00`, `:05`, `:10`, `:15`, `:20`) to spread DB load.
