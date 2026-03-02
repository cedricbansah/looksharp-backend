# Function Migration Matrix v1

**Status:** Planning baseline  
**Effective date:** 2026-02-26  
**Depends on:** `BACKEND_CONTRACT_V1.md`, `RUNTIME_ARCHITECTURE_V1.md`

## 1. Scope

This matrix maps current Firebase/Cloud Functions behavior to target Django runtime components.

Target component types:
- `API` (DRF endpoint)
- `Webhook` (DRF endpoint with signature validation)
- `Worker` (Celery task)
- `Scheduler` (Celery Beat job)

## 2. Existing Function Inventory

## 2.1 `looksharp-functions` (primary backend repo)

| Current Function | Current Trigger | Current Role | Target Component | Target Implementation | Migration Notes |
|---|---|---|---|---|---|
| `addFcmToken` | Callable | Save/remove user FCM token links | API | `POST /api/v1/notifications/fcm-tokens` | Keep only if push remains in scope; otherwise retire. |
| `sendPushNotificationsTrigger` | Firestore create (`ff_push_notifications`) | Broadcast push dispatch | Worker | Task: `notifications.send_broadcast` | Replace Firestore-trigger with queue publish on notification create endpoint. |
| `sendUserPushNotificationsTrigger` | Firestore create (`ff_user_push_notifications`) | Targeted push dispatch | Worker | Task: `notifications.send_targeted` | Same as above with explicit audience list. |
| `pstkLsPrivateCalls` | Callable | Proxy Paystack requests | API | Replace with typed payout endpoints | Avoid generic proxy design; expose strict domain endpoints only. |
| `pstkLsPrivateCallsV2` | HTTP | Authenticated Paystack proxy | API | Replace with typed payout endpoints | Preserve auth + request audit trails. |
| `claimWelcomeBonus` | Callable | One-time user bonus award | API | `POST /api/v1/users/me/welcome-bonus/claim` | Must be idempotent and transaction-protected. |
| `onUserDeleted` | Firebase Auth delete | Soft-delete user profile | Worker | Task: `users.soft_delete_on_auth_delete` | For full Firebase exit, replace with in-app account deletion workflow. |
| `on_response_created` | Firestore create (`responses`) | Increment survey count + points + surveys_completed | Worker | Task: `responses.apply_side_effects` | Critical to keep idempotent behavior. |
| `update_offers` | HTTP (scheduler-invoked) | Expire offers + days remaining update | Scheduler + Worker | Beat job: `offers.recompute_status` | Daily cadence; same behavior as current. |
| `approval` (paystack-approval) | HTTP webhook | Validate and transition withdrawal states | Webhook + Worker | `POST /api/v1/webhooks/paystack` + task handoff | Enforce signature verification + idempotency key storage. |
| `on_survey_created` (sms) | Firestore write (`surveys`) | SMS blast when survey becomes active | Worker | Task: `sms.send_survey_activation` | Trigger from survey status transition service event. |
| `on_offer_created` (sms) | Firestore write (`offers`) | SMS blast when offer becomes active | Worker | Task: `sms.send_offer_activation` | Trigger from offer status transition service event. |
| `on_verification_updated` | Firestore write (`verifications`) | SMS on KYC decision | Worker | Task: `sms.send_kyc_decision` | Trigger from verification review service event. |

## 2.2 `looksharp-web/functions` (admin repo function set; consolidate into primary backend)

| Current Function | Current Trigger | Current Role | Target Component | Target Implementation | Migration Notes |
|---|---|---|---|---|---|
| `onSurveyWrite` | Firestore write (`surveys`) | Update active survey counter | Worker | Task: `counters.recompute_active_surveys` | Consolidate with counters module in primary backend. |
| `onResponseCreate` | Firestore create (`responses`) | Increment total responses counter | Worker | Task: `counters.bump_total_responses` | Can be combined with response side-effects task. |
| `onOfferWrite` | Firestore write (`offers`) | Update active offers counter | Worker | Task: `counters.recompute_active_offers` | Consolidate with counters module. |
| `onWithdrawalUpdate` | Firestore update (`withdrawals`) | Recalculate paid-out total on completion | Worker | Task: `counters.recompute_total_paid_out` | Move to payout completion event consumer. |
| `initializeDashboardCounters` | Callable (admin) | One-shot full counter rebuild | API + Worker | `POST /api/v1/admin/counters/rebuild` | Admin-only endpoint queues rebuild task. |
| `setAdminClaim` | Callable | Grant admin privileges | API | `POST /api/v1/admin/users/{id}/grant-admin` | Replace custom claim flow with backend role assignment. |
| `createTransferRecipient` | Callable | Create Paystack recipient from KYC | API | `POST /api/v1/admin/verifications/{id}/create-recipient` | Should be part of approval workflow service. |

## 3. Consolidation Decisions

- Keep one backend authority: migrate admin-repo functions into main Django backend domain services.
- Remove duplicated counter logic spread across repos.
- Replace generic Paystack proxy with strict domain commands.

## 4. Rollout Order

1. P0: payout safety path
- `approval` webhook replacement
- withdrawal transition service
- recipient creation service

2. P0: reward correctness path
- `on_response_created` replacement
- counter updates linked to responses

3. P1: admin workflows
- `setAdminClaim` replacement
- `initializeDashboardCounters` replacement

4. P1: scheduler and messaging
- offer daily scheduler
- SMS event handlers

5. P2: push notifications
- keep or retire based on product decision

## 5. Non-Functional Requirements per Migrated Function

- Idempotency: required for webhook and reward/payout tasks.
- Observability: structured logs + correlation IDs + task status metrics.
- Security: strict auth/role checks on admin and payout endpoints.
- Retry policy: bounded retries with dead-letter handling for external providers.

## 6. Decommission Checklist (Firebase)

A function can be decommissioned only when:
- Equivalent Django path is live in production.
- Backfill/reconciliation confirms parity.
- Monitoring shows stable behavior over agreed observation window.
- Calling clients have been cut over.

