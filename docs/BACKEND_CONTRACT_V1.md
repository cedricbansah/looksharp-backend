# LookSharp Backend Contract v1

**Status:** Approved baseline  
**Effective date:** 2026-02-26  
**Source of truth repo:** `looksharp-functions`  
**Primary consumers:** `looksharp-mobile`, `looksharp-web` (admin)

## 1. Purpose

This contract defines the canonical backend domain model and behavior that all clients and services must follow during and after migration from Firebase-first architecture to Django + Postgres.

If this document conflicts with older notes/specs, this document wins.

## 2. Canonical Enums

### 2.1 Survey Status
- `draft`
- `active`
- `completed`

### 2.2 Offer Status
- `active`
- `inactive`

### 2.3 Verification Status
- `pending`
- `approved`
- `rejected`

`verified` is **not** a valid `verifications.status` value.  
User-level verification is represented by `users.is_verified` (boolean).

### 2.4 Withdrawal Status
- `pending`
- `processing`
- `completed`
- `failed`

`initiated` and `pending_approval` are legacy values and are deprecated.

## 3. Canonical Collections

- `users`
- `surveys`
- `questions`
- `responses`
- `clients`
- `offers`
- `redemptions`
- `verifications`
- `withdrawals`
- `survey_categories`
- `offer_categories`
- `question_types`
- `countries`
- `counters` (`dashboard` doc)

Legacy collections (`response`, `choice`, etc.) are out of contract for new writes.

## 4. Ownership Model

### 4.1 Server-controlled user fields
Clients must not directly mutate:
- `users.points`
- `users.surveys_completed`
- `users.welcome_bonus_claimed`
- `users.is_verified`
- `users.recipient_code`
- `users.is_admin`

### 4.2 Client-managed user profile fields
Clients may update:
- `first_name`, `last_name`, `phone`, `date_of_birth`, `gender`, `country`, `profile_photo_url`, `updated_at`

### 4.3 Admin-only writes
- `surveys`, `questions`, `offers`, `clients`
- verification review decisions (`verifications.status`, `rejection_reason`, `reviewed_by`, `reviewed_at`)

## 5. Lifecycle Contracts

### 5.1 Survey Response
1. Client creates `responses` doc with:
   - `user_id`, `survey_id`, `submitted_at`, `answers` (required)
   - `survey_title`, `user_email`, `points_earned`, `is_deleted` (optional/derived)
2. Server side-effect (idempotent):
   - increment `surveys.response_count`
   - increment `users.points` by survey points
   - append survey id to `users.surveys_completed`
3. Duplicate submissions for same `(user_id, survey_id)` must not double-award points.

### 5.2 Verification
1. User submits verification with `status = pending`.
2. Admin reviews and sets:
   - `approved` or `rejected`
3. On approval:
   - `users.is_verified = true`
   - `users.recipient_code` set from Paystack recipient creation flow
4. Resubmission model:
   - create a new verification document (recommended)
   - historical verification docs remain immutable records.

### 5.3 Withdrawal
1. Client creates withdrawal with `status = pending`.
2. Server/worker may move `pending -> processing` after Paystack initiation/validation.
3. Terminal states:
   - `processing -> completed` (set `completed_at`)
   - `pending|processing -> failed` (set `failure_reason` when available)
4. Points deduction happens server-side only, on successful processing path.

## 6. Canonical Field Contracts (Core)

### 6.1 `users`
- `id` (doc id / auth uid), `email`
- `points` (int, default `0`)
- `is_verified` (bool, default `false`)
- `recipient_code` (nullable string)
- `is_admin` (bool, default `false`)
- `surveys_completed` (string[])
- `offers_claimed` (string[])

### 6.2 `responses`
- `survey_id` (string, required)
- `user_id` (string, required)
- `submitted_at` (timestamp, required)
- `answers` (array, required)
- `is_deleted` (bool, default `false`)

### 6.3 `verifications`
- `user_id`, `full_name`, `mobile_number`, `network_provider`, `id_type`, `id_number`
- `id_front_url`, `id_back_url`, `selfie_url`
- `status` (`pending|approved|rejected`)
- `rejection_reason` (optional)
- `reviewed_by`, `reviewed_at` (admin write)
- `submitted_at` (required)

### 6.4 `withdrawals`
- `user_id` (required)
- `amount_ghs` (number, minimum `5.0`)
- `points_converted` (int)
- `recipient_code` (string)
- `transfer_reference` (string, unique logical key)
- `transfer_code` (optional)
- `status` (`pending|processing|completed|failed`)
- `failure_reason` (optional)
- `created_at`, `updated_at`, `completed_at` (timestamps)

## 7. Counters Contract

Canonical required fields on `counters/dashboard`:
- `active_surveys`
- `total_responses`
- `active_offers`
- `total_paid_out`
- `updated_at`

Additional counter fields may exist, but consumers must treat them as optional unless promoted in a future contract version.

## 8. Storage Contract

Canonical storage paths:
- `/users/{user_id}/profile_photos/...`
- `/users/{user_id}/verification/...`
- `/offers/{offer_id}/...`
- `/clients/{client_id}/logo[.<ext>]`

Constraints:
- image uploads only
- max size: 5MB

## 9. Legacy Compatibility Mapping

For migration adapters only:
- verification `verified` -> `approved`
- withdrawal `initiated` -> `pending`
- withdrawal `pending_approval` -> `processing`
- `transfer_status` -> `status`

New writes must never emit legacy values/fields above.

## 10. API Direction (Django Migration)

This contract is backend-technology agnostic, but for Django migration:
- Firebase ID token verification can remain initial auth boundary.
- Business writes move behind server APIs/services enforcing this contract.
- Background jobs (rewarding, counters, offer expiry, SMS, webhook handling) move to worker processes.

## 11. Change Control

Any change to enum values, lifecycle transitions, or server/client field ownership requires:
1. Contract version bump (`v1 -> v1.x` or `v2`)
2. Migration note with backward-compat plan
3. Updates in `looksharp-mobile`, `looksharp-web`, and backend services before rollout
