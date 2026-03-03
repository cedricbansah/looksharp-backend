# Cloud Run Deployment Setup (Staging + Production Scaffolding)

This repo now includes Cloud Run deployment scaffolding in:
- `.github/workflows/cd.yml`
- `scripts/deploy_cloud_run.sh`

## 1) Configure GitHub environments

Create two GitHub environments:
- `staging`
- `production`

Add these secrets in each environment:
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOYER_SERVICE_ACCOUNT`

Add these variables in each environment:
- `GCP_PROJECT_ID`
- `GCP_REGION`
- `ARTIFACT_REGISTRY_REPOSITORY`
- `IMAGE_NAME`
- `CLOUD_RUN_SERVICE`
- `CLOUD_RUN_MIGRATION_JOB`
- `DJANGO_SETTINGS_MODULE`

Recommended optional variables:
- `RUN_MIGRATIONS=true`
- `ALLOW_UNAUTHENTICATED=true` (or `false` if fronted by gateway)
- `CLOUD_SQL_INSTANCE=<project>:<region>:<instance>`
- `CLOUD_RUN_VPC_CONNECTOR=<connector-name>`
- `CLOUD_RUN_VPC_EGRESS=private-ranges-only`
- `CLOUD_RUN_MEMORY=1Gi`
- `CLOUD_RUN_CPU=1`
- `CLOUD_RUN_MIN_INSTANCES=0` (staging), `1` (production)
- `CLOUD_RUN_MAX_INSTANCES=10`
- `CLOUD_RUN_TIMEOUT=120s`
- `CLOUD_RUN_CONCURRENCY=80`
- `CLOUD_RUN_SERVICE_ACCOUNT=<runtime-service-account-email>`
- `CLOUD_RUN_ENV_VARS=KEY1=VALUE1,KEY2=VALUE2`
- `CLOUD_RUN_SECRET_VARS=SECRET_KEY=DJANGO_SECRET_KEY_STAGING:latest,DATABASE_URL=DATABASE_URL_STAGING:latest,REDIS_URL=REDIS_URL_STAGING:latest`

Optional job-specific variables:
- `CLOUD_RUN_JOB_SERVICE_ACCOUNT`
- `CLOUD_RUN_JOB_MEMORY`
- `CLOUD_RUN_JOB_CPU`
- `CLOUD_RUN_JOB_TASK_TIMEOUT`
- `CLOUD_RUN_JOB_TASKS`
- `CLOUD_RUN_JOB_MAX_RETRIES`

Repo-level variable for auto staging deploy:
- `ENABLE_AUTO_STAGING_DEPLOY=true`

Auth mode toggle variable (set per environment):
- `USE_GCP_SERVICE_ACCOUNT_KEY=true` to use `GCP_SERVICE_ACCOUNT_KEY`
- leave unset/`false` to use Workload Identity Federation

## 2) Required GCP resources

- Artifact Registry Docker repository.
- Cloud Run service target names for staging/prod.
- Cloud Run migration jobs for staging/prod.
- Optional: Cloud SQL instance and VPC connector.

## 3) Trigger deploys

Automatic staging:
- Push to `dev` when `ENABLE_AUTO_STAGING_DEPLOY=true`.

Manual staging:
```bash
gh workflow run cd.yml -f target=staging
```

Manual production:
```bash
gh workflow run cd.yml -f target=production
```

Promote previously built image:
```bash
gh workflow run cd.yml -f target=production -f image_tag=sha-<12-char-sha>
```

## 4) Notes

- The workflow deploys API + migration job.
- Celery worker/beat are not deployed by this workflow and should be provisioned separately.
