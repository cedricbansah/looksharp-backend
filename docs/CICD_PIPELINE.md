# CI/CD Pipeline (Single `main` Branch)

This repo uses a single branch workflow (`main`) with environment-based deployments.

## Workflows

## 1) CI (`.github/workflows/ci.yml`)

Runs on:
- `pull_request` (all PRs)
- `push` to `main`

Checks:
- dependency install (`requirements/dev.txt`)
- Django migrations + `manage.py check`
- lint (`ruff`)
- tests:
  - `apps/users/tests.py`
  - `apps/responses/tests.py`
  - `apps/withdrawals/tests.py`
  - `apps/webhooks/tests.py`
  - `apps/paystack/tests.py`

Infra in CI:
- Postgres 15 service
- Redis 7 service

## 2) CD (`.github/workflows/cd.yml`)

Runs on:
- `push` to `main` (auto staging path)
- `workflow_dispatch` (manual staging or production)

Behavior:
1. Build Docker image and push to GHCR:
   - `ghcr.io/<owner>/<repo>:sha-<12-char-sha>`
   - `ghcr.io/<owner>/<repo>:main` (on push to `main`)
2. Staging deploy:
   - auto on `main` pushes
   - or manual dispatch with `target=staging`
3. Production deploy:
   - manual dispatch only with `target=production`

Deployment trigger mechanism:
- HTTP webhook call with JSON payload:
  - `image` (image ref)
  - `sha` (git sha)

## Required GitHub setup

## Environments
Create:
- `staging`
- `production`

Recommended:
- require reviewers for `production` environment approvals.

## Repository/Environment Secrets

Required for deploy triggers:
- `STAGING_DEPLOY_WEBHOOK_URL`
- `PRODUCTION_DEPLOY_WEBHOOK_URL`

Optional:
- omit either secret to skip trigger for that environment (workflow still succeeds).

## Branch protection (`main`)

Recommended minimum rules:
- require pull request before merge
- require CI workflow to pass
- block force pushes

## Release flow (without `dev`/`staging` branches)

1. Open PR -> CI validates.
2. Merge to `main` -> CI validates again + staging deploy trigger runs.
3. Verify staging.
4. Run CD workflow manually with `target=production` to promote.

