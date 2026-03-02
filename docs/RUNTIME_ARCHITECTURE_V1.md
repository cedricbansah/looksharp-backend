# LookSharp Runtime Architecture v1

**Status:** Target design for Firestore/Functions exit (Firebase Auth retained)  
**Effective date:** 2026-03-02  
**Depends on:** `docs/BACKEND_CONTRACT_V1.md`

## 1. Objective

Build a single backend platform that primarily replaces:
- Firestore
- Cloud Functions
- Firestore rules

with a self-owned Django + Postgres architecture.

Scope decisions:
- Firebase Auth remains in place for now.
- Storage migration to Cloudflare R2 is a separate, later workstream.

## 2. Target Runtime Topology

One codebase, multiple runtime processes:

- `api` process: Django + DRF (HTTP APIs + webhook endpoints + admin endpoints)
- `worker` process: Celery workers (async side effects)
- `scheduler` process: Celery Beat (scheduled jobs)
- `redis` service: queue + short-lived cache
- `postgres` service: primary relational store

Optional:
- `realtime` process (Django Channels or SSE service) if we need true push updates
- `object-storage` service: Cloudflare R2 for file blobs (separate storage phase)

## 3. Service Replacement Map

- Firestore -> Postgres
- Firebase callable functions -> DRF endpoints
- Firestore-triggered functions -> domain events + Celery tasks
- Cloud Scheduler -> Celery Beat jobs
- Firestore rules -> Django authorization + object-level permission checks
- Firebase Auth -> retained; Django verifies Firebase ID tokens
- Firebase Storage -> Cloudflare R2 + presigned URLs (planned, deferred)

## 4. API Layer (Django/DRF)

Responsibilities:
- Mobile participant APIs
- Admin dashboard APIs
- Webhook receivers (Paystack)
- Presigned upload URL generation
- Permission enforcement from `BACKEND_CONTRACT_V1`

Standards:
- Versioned API namespace: `/api/v1/...`
- Idempotency keys for write endpoints with external side effects
- Soft-delete semantics preserved (`is_deleted` where applicable)

## 5. Async Layer (Celery)

Use Celery tasks for:
- Survey response rewards/counter updates
- Offer-activation SMS fanout
- KYC decision SMS notifications
- Dashboard counter recalculation/reconciliation
- Any long-running external API retries

Queue design:
- `critical` queue: payouts/webhooks/rewarding
- `default` queue: normal domain side-effects
- `bulk` queue: large fanout and backfills

## 6. Scheduler Layer (Celery Beat)

Scheduled jobs:
- Daily offer expiry/days remaining update
- Periodic counter reconciliation
- Data integrity sweeps (optional)

## 7. Authentication Strategy (Firebase Retained)

## 7.1 Current approach
- Django verifies Firebase ID tokens.
- Existing mobile/admin login UX remains unchanged while APIs move.

## 7.2 Scope boundary
- Replacing Firebase Auth is out of scope for this migration.
- Any future auth migration should be treated as a separate project.

## 7.3 Required capabilities now
- Verify Firebase bearer tokens at API boundary.
- Resolve/create backend user records keyed by Firebase UID.
- Enforce server-managed role/permission checks in Django.

## 8. File Storage Strategy (Cloudflare R2, Deferred)

Storage is not part of the primary cutover in this document.
Planned direction is Cloudflare R2 with private buckets and short-lived presigned URLs.

Contract-aligned key prefixes:
- `users/{user_id}/profile_photos/...`
- `users/{user_id}/verification/...`
- `offers/{offer_id}/...`
- `clients/{client_id}/logo...`

Controls to enforce in backend:
- MIME/type checks (image-only where required)
- Size limits (5MB where contract defines)
- Ownership/role checks for write/read issuance
- Malware scanning pipeline (recommended for KYC uploads)

## 9. Data Layer (Postgres)

Core requirements:
- Relational schema matching `BACKEND_CONTRACT_V1`
- Unique constraints for idempotency-critical flows
- Audit columns on money/KYC state transitions
- Optimistic/transactional locking for payout and reward paths

Must-have constraints:
- Unique logical key for `withdrawals.transfer_reference`
- Controlled state transition validation in service layer
- Referential integrity for user/survey/offer relations

## 10. Security Baseline

- Firebase ID token verification + role-based authorization
- Object-level permission checks on every read/write
- Rate limiting on auth, payouts, and webhook endpoints
- HMAC verification for webhook signatures
- Secret management via cloud secret store
- PII handling policy (field-level encryption where needed)

## 11. Observability & Operations

- Structured logs across API/worker/scheduler
- Metrics:
  - request latency/error rates
  - queue depth/retry/dead-letter counts
  - payout and webhook processing success rates
- Error tracking and alerting
- Tracing across request -> task chains

## 12. Backups & Disaster Recovery

- Automated Postgres backups + point-in-time recovery
- Object storage versioning/lifecycle policies
- Restore runbooks and periodic restore drills

## 13. Environments

At minimum:
- `dev`
- `staging`
- `prod`

Each environment needs isolated:
- database
- redis
- object bucket namespace
- secrets
- webhook endpoints/credentials

## 14. CI/CD Requirements

- Separate deploy targets for API, worker, scheduler
- Migration pipeline with rollback guardrails
- Smoke tests post-deploy:
  - Firebase token auth
  - survey submission
  - payout webhook path
  - admin verification review path

## 15. Cutover Sequence (High-level)

1. Deploy Django stack in parallel.
2. Migrate reads first where low risk.
3. Move write paths behind APIs.
4. Move async/scheduled workloads.
5. Decommission Firestore, Cloud Functions, and Firestore rules after parity verification.
6. Plan and execute Cloudflare R2 storage migration in a separate phase.
7. Keep Firebase Auth in place until a dedicated auth migration is approved.
