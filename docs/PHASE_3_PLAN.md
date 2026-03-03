# Phase 3 Plan: Domain APIs + Admin Workflows

**Status:** Implemented (ready for merge)  
**Effective date:** 2026-03-02  
**Repo:** `looksharp-backend` (`/Users/cedricbansah/Documents/looksharp-backend`)  
**Depends on:** `BACKEND_CONTRACT_V1.md`, `FUNCTION_MIGRATION_MATRIX.md`, `RUNTIME_ARCHITECTURE_V1.md`, `PHASE_1_PLAN.md`, `PHASE_2_PLAN.md`

---

## Overview

Phase 3 delivers the missing domain surface after Phase 2:
- Mobile/read-write domain APIs (`surveys`, `offers`, `redemptions`, `verifications`, `welcome bonus`)
- Admin workflows (`grant admin`, verification review, dashboard counters, core list/CRUD paths)
- Counter reconciliation and offer scheduler jobs

This phase closed the largest implementation gaps in the repo: `offers`, `verifications`, and `counters` now have domain implementations and `surveys` has been extended with questions/domain APIs.

---

## Requirements Summary

### Functional requirements
- Implement contract-aligned domain models for:
  - `questions`, `offers`, `redemptions`, `verifications`, `counters/dashboard`
- Implement mobile endpoints:
  - `POST /api/v1/users/me/welcome-bonus/claim/`
  - `GET /api/v1/surveys/`, `GET /api/v1/surveys/{id}/`
  - `GET /api/v1/offers/`
  - `POST /api/v1/redemptions/`, `GET /api/v1/redemptions/`
  - `POST /api/v1/verifications/`, `GET /api/v1/verifications/`
- Implement admin endpoints:
  - `GET /api/v1/admin/dashboard/`
  - `GET /api/v1/admin/users/`, `POST /api/v1/admin/users/{id}/grant-admin/`
  - `GET /api/v1/admin/responses/`
  - `GET /api/v1/admin/withdrawals/`
  - `GET /api/v1/admin/verifications/`
  - `POST /api/v1/admin/verifications/{id}/approve/`
  - `POST /api/v1/admin/verifications/{id}/reject/`
  - `POST /api/v1/admin/verifications/{id}/create-recipient/`
  - `POST /api/v1/admin/counters/rebuild/`
- Implement scheduled/domain tasks:
  - `offers.recompute_status` (daily beat job)
  - `counters.recompute_active_surveys`
  - `counters.recompute_active_offers`
  - `counters.recompute_total_responses`
  - `counters.recompute_total_paid_out`

### Non-functional requirements
- **Security**: strict `IsAuthenticated`, `IsAdmin`, `IsVerified`; no client writes to server-controlled fields.
- **Correctness**: idempotent points/reward/bonus/redemption paths with transaction boundaries.
- **Observability**: structured logs for admin actions and state transitions.
- **Reliability**: Celery retries on external calls; no double-application of points/deductions.

### Out of scope (Phase 4+)
- SMS fanout (Hubtel integration), push notifications, and storage migration to R2.

---

## Implementation Phases

## Phase 3.1 — Data Model Foundation
**Goal:** add missing schema for contract entities.

1. Create/extend models and migrations:
   - `apps/surveys/models.py`: add `Question` and optional category relation primitives.
   - `apps/offers/models.py`: `Offer`, `Redemption`.
   - `apps/verifications/models.py`: `Verification`.
   - `apps/counters/models.py`: `DashboardCounter`.
2. Add indexes/unique constraints:
   - `redemptions` uniqueness (`user_id`, `offer_id`) for idempotency.
   - `verifications` indexed by `user_id`, `status`, `submitted_at`.
3. Run `makemigrations` + `migrate`.

**Deliverable:** contract-aligned relational schema in place.

## Phase 3.2 — Mobile Domain APIs
**Goal:** deliver missing participant endpoints.

1. Users:
   - add `POST /users/me/welcome-bonus/claim/` (one-time transactional increment).
2. Surveys:
   - add list/detail endpoints (`active` + not deleted for mobile reads).
3. Offers + redemptions:
   - `GET /offers/` and redemption create/list endpoints.
   - server-side points checks and atomic deduction path for redemption.
4. Verifications:
   - submission endpoint (`pending` only on create).
   - list endpoint scoped to authenticated user.

**Deliverable:** mobile contract surface implemented for phase scope.

## Phase 3.3 — Admin APIs and Workflows
**Goal:** replace remaining P1 admin function paths.

1. Create admin views/serializers/urls under existing app modules with `IsAdmin`.
2. Implement:
   - users list + `grant-admin`
   - responses list + withdrawals list
   - verification review (`approve`/`reject`)
   - create Paystack recipient for verification and persist `users.recipient_code`
3. Wire admin dashboard endpoint to `counters/dashboard`.

**Deliverable:** admin workflows migrated behind authenticated backend APIs.

## Phase 3.4 — Counters + Scheduler Jobs
**Goal:** restore periodic/reconciliation behavior outside Firestore triggers.

1. Implement counter recompute tasks in `apps/counters/tasks.py`.
2. Implement daily offer status job in `apps/offers/tasks.py`.
3. Register beat schedules in settings / `django_celery_beat`.
4. Implement admin counter rebuild endpoint that dispatches recompute tasks.
5. Wire existing reward/payout flows to counter recompute hooks where needed.

**Deliverable:** periodic and reconciliation jobs live in Celery/Beat.

## Phase 3.5 — Test + Hardening + Cutover Readiness
**Goal:** verify safety before moving client writes.

1. Add full tests for new APIs and tasks:
   - `apps/surveys/tests.py`
   - `apps/offers/tests.py`
   - `apps/verifications/tests.py`
   - `apps/counters/tests.py`
   - extend `apps/users/tests.py` for welcome bonus.
2. Run deploy checks and focused smoke tests in staging.
3. Validate permission boundaries and idempotency behavior.

**Deliverable:** phase sign-off evidence and release checklist.

---

## File Map (Implemented)

| File | Action |
|---|---|
| `apps/surveys/models.py` | Add `Question` model and relationships |
| `apps/surveys/serializers.py` | Add survey/question serializers |
| `apps/surveys/views.py` | Add mobile list/detail + admin CRUD surface |
| `apps/surveys/urls.py` | Wire survey endpoints |
| `apps/surveys/tests.py` | Add tests |
| `apps/offers/models.py` | Add `Offer`, `Redemption` |
| `apps/offers/serializers.py` | Add offer/redemption serializers |
| `apps/offers/views.py` | Add mobile + admin offer/redemption endpoints |
| `apps/offers/tasks.py` | Add `recompute_status` scheduler task |
| `apps/offers/urls.py` | Wire offer/redemption endpoints |
| `apps/offers/tests.py` | Add tests |
| `apps/verifications/models.py` | Add verification model |
| `apps/verifications/serializers.py` | Add verification serializers |
| `apps/verifications/views.py` | Add submit/list + admin approve/reject/create-recipient |
| `apps/verifications/urls.py` | Wire verification endpoints |
| `apps/verifications/tests.py` | Add tests |
| `apps/counters/models.py` | Add dashboard counters model |
| `apps/counters/views.py` | Add dashboard + rebuild endpoint |
| `apps/counters/tasks.py` | Add recompute tasks |
| `apps/counters/urls.py` | Wire admin dashboard routes |
| `apps/counters/tests.py` | Add tests |
| `apps/users/views.py` | Add welcome bonus claim endpoint |
| `apps/users/urls.py` | Wire welcome bonus route |
| `apps/users/tests.py` | Add welcome bonus tests |
| `config/urls.py` | Ensure admin subpaths are routed cleanly |
| `config/settings/base.py` | Register beat schedules / task settings updates |

---

## Risks and Mitigation

1. **Race conditions on points updates** (welcome bonus, redemption, rewards)
- Mitigation: `transaction.atomic()` + row locks on `User` where points mutate.

2. **Permission regressions on admin APIs**
- Mitigation: explicit `IsAdmin` + endpoint-level tests for `401/403` and object ownership.

3. **Counter drift from async ordering**
- Mitigation: periodic full recompute tasks and admin-triggered rebuild endpoint.

4. **Spec ambiguity on survey/questions/admin CRUD depth**
- Mitigation: ship minimal contract-compliant fields first; defer optional metadata to Phase 3.x.

---

## Acceptance Criteria (Phase 3 Exit Gates)

- [x] All Phase 3 endpoints above implemented and routed.
- [x] Contract enums/fields respected (`approved|rejected`, `pending|processing|completed|failed`, etc.).
- [x] Server-controlled user fields cannot be client-mutated.
- [x] Welcome bonus and redemption are idempotent and transaction-protected.
- [x] Counter recompute and offer scheduler jobs are wired and test-covered.
- [x] Admin-only endpoints reject non-admin callers.
- [x] Test suite for `users/surveys/offers/verifications/counters` passes.

---

## Verification Checklist

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py check --deploy
pytest apps/users/tests.py apps/surveys/tests.py apps/offers/tests.py apps/verifications/tests.py apps/counters/tests.py -v
pytest apps/responses/tests.py apps/withdrawals/tests.py apps/webhooks/tests.py apps/paystack/tests.py -v
```

Manual smoke tests (staging):
- Firebase-authenticated survey and offer reads.
- Welcome bonus claim idempotency.
- Verification submit + admin approve/reject.
- Admin grant-admin and dashboard counter rebuild.

## Validation Snapshot (2026-03-03)

- `python manage.py makemigrations --check --dry-run` -> `No changes detected`
- `python manage.py check` -> no system check issues
- `pytest -q` -> `59 passed`
- CI expanded to include:
  - migration drift gate (`makemigrations --check --dry-run`)
  - lint/test coverage for `users/surveys/offers/verifications/counters`
