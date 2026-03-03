#!/usr/bin/env bash

set -euo pipefail

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: $name" >&2
    exit 1
  fi
}

bool_true() {
  local value="${1:-}"
  [[ "$value" == "true" || "$value" == "1" || "$value" == "yes" ]]
}

build_combined_env_vars() {
  local combined_env_vars=""

  combined_env_vars="DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE}"
  if [[ -n "${CLOUD_RUN_ENV_VARS:-}" ]]; then
    combined_env_vars="${combined_env_vars},${CLOUD_RUN_ENV_VARS}"
  fi
  echo "$combined_env_vars"
}

build_service_args() {
  local -n args_ref=$1
  local combined_env_vars=""
  combined_env_vars="$(build_combined_env_vars)"
  local service_command="${CLOUD_RUN_SERVICE_COMMAND:-gunicorn}"
  local service_args_csv="${CLOUD_RUN_SERVICE_ARGS:-config.wsgi:application,--bind,0.0.0.0:8080,--workers,2,--timeout,120}"

  args_ref+=(--project "$GCP_PROJECT_ID")
  args_ref+=(--region "$GCP_REGION")
  args_ref+=(--platform managed)
  args_ref+=(--set-env-vars "$combined_env_vars")
  args_ref+=(--command "$service_command")
  args_ref+=(--args "$service_args_csv")

  if bool_true "${ALLOW_UNAUTHENTICATED:-true}"; then
    args_ref+=(--allow-unauthenticated)
  else
    args_ref+=(--no-allow-unauthenticated)
  fi

  if [[ -n "${CLOUD_RUN_MEMORY:-}" ]]; then
    args_ref+=(--memory "$CLOUD_RUN_MEMORY")
  fi
  if [[ -n "${CLOUD_RUN_CPU:-}" ]]; then
    args_ref+=(--cpu "$CLOUD_RUN_CPU")
  fi
  if [[ -n "${CLOUD_RUN_MIN_INSTANCES:-}" ]]; then
    args_ref+=(--min-instances "$CLOUD_RUN_MIN_INSTANCES")
  fi
  if [[ -n "${CLOUD_RUN_MAX_INSTANCES:-}" ]]; then
    args_ref+=(--max-instances "$CLOUD_RUN_MAX_INSTANCES")
  fi
  if [[ -n "${CLOUD_RUN_TIMEOUT:-}" ]]; then
    args_ref+=(--timeout "$CLOUD_RUN_TIMEOUT")
  fi
  if [[ -n "${CLOUD_RUN_CONCURRENCY:-}" ]]; then
    args_ref+=(--concurrency "$CLOUD_RUN_CONCURRENCY")
  fi

  if [[ -n "${CLOUD_SQL_INSTANCE:-}" ]]; then
    args_ref+=(--add-cloudsql-instances "$CLOUD_SQL_INSTANCE")
  fi

  if [[ -n "${CLOUD_RUN_VPC_CONNECTOR:-}" ]]; then
    args_ref+=(--vpc-connector "$CLOUD_RUN_VPC_CONNECTOR")
    args_ref+=(--vpc-egress "${CLOUD_RUN_VPC_EGRESS:-private-ranges-only}")
  fi

  if [[ -n "${CLOUD_RUN_SERVICE_ACCOUNT:-}" ]]; then
    args_ref+=(--service-account "${CLOUD_RUN_SERVICE_ACCOUNT}")
  fi

  if [[ -n "${CLOUD_RUN_SECRET_VARS:-}" ]]; then
    args_ref+=(--set-secrets "$CLOUD_RUN_SECRET_VARS")
  fi
}

build_job_args() {
  local -n args_ref=$1
  local combined_env_vars=""
  combined_env_vars="$(build_combined_env_vars)"

  args_ref+=(--project "$GCP_PROJECT_ID")
  args_ref+=(--region "$GCP_REGION")
  args_ref+=(--set-env-vars "$combined_env_vars")

  if [[ -n "${CLOUD_RUN_JOB_MEMORY:-${CLOUD_RUN_MEMORY:-}}" ]]; then
    args_ref+=(--memory "${CLOUD_RUN_JOB_MEMORY:-${CLOUD_RUN_MEMORY}}")
  fi
  if [[ -n "${CLOUD_RUN_JOB_CPU:-${CLOUD_RUN_CPU:-}}" ]]; then
    args_ref+=(--cpu "${CLOUD_RUN_JOB_CPU:-${CLOUD_RUN_CPU}}")
  fi
  if [[ -n "${CLOUD_RUN_JOB_TASK_TIMEOUT:-}" ]]; then
    args_ref+=(--task-timeout "${CLOUD_RUN_JOB_TASK_TIMEOUT}")
  fi
  if [[ -n "${CLOUD_RUN_JOB_TASKS:-}" ]]; then
    args_ref+=(--tasks "${CLOUD_RUN_JOB_TASKS}")
  fi
  if [[ -n "${CLOUD_RUN_JOB_MAX_RETRIES:-}" ]]; then
    args_ref+=(--max-retries "${CLOUD_RUN_JOB_MAX_RETRIES}")
  fi

  if [[ -n "${CLOUD_SQL_INSTANCE:-}" ]]; then
    args_ref+=(--set-cloudsql-instances "$CLOUD_SQL_INSTANCE")
  fi

  if [[ -n "${CLOUD_RUN_VPC_CONNECTOR:-}" ]]; then
    args_ref+=(--vpc-connector "$CLOUD_RUN_VPC_CONNECTOR")
    args_ref+=(--vpc-egress "${CLOUD_RUN_VPC_EGRESS:-private-ranges-only}")
  fi

  if [[ -n "${CLOUD_RUN_JOB_SERVICE_ACCOUNT:-${CLOUD_RUN_SERVICE_ACCOUNT:-}}" ]]; then
    args_ref+=(--service-account "${CLOUD_RUN_JOB_SERVICE_ACCOUNT:-${CLOUD_RUN_SERVICE_ACCOUNT}}")
  fi

  if [[ -n "${CLOUD_RUN_SECRET_VARS:-}" ]]; then
    args_ref+=(--set-secrets "$CLOUD_RUN_SECRET_VARS")
  fi
}

require_env GCP_PROJECT_ID
require_env GCP_REGION
require_env ARTIFACT_REGISTRY_REPOSITORY
require_env IMAGE_NAME
require_env CLOUD_RUN_SERVICE
require_env DJANGO_SETTINGS_MODULE

IMAGE_TAG="${IMAGE_TAG:-sha-$(git rev-parse --short=12 HEAD)}"
IMAGE_URI="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REGISTRY_REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"

if ! bool_true "${SKIP_BUILD:-false}"; then
  echo "Building image: ${IMAGE_URI}"
  docker build -t "${IMAGE_URI}" .
  docker push "${IMAGE_URI}"
else
  echo "Skipping build. Using existing image: ${IMAGE_URI}"
fi

echo "Deploying Cloud Run service: ${CLOUD_RUN_SERVICE}"
service_args=(run deploy "${CLOUD_RUN_SERVICE}" --image "${IMAGE_URI}")
build_service_args service_args
gcloud "${service_args[@]}"

if bool_true "${RUN_MIGRATIONS:-true}"; then
  require_env CLOUD_RUN_MIGRATION_JOB

  echo "Deploying migration job: ${CLOUD_RUN_MIGRATION_JOB}"
  job_args=(run jobs deploy "${CLOUD_RUN_MIGRATION_JOB}" --image "${IMAGE_URI}")
  build_job_args job_args
  job_args+=(--command python)
  job_args+=(--args manage.py,migrate,--noinput)
  gcloud "${job_args[@]}"

  echo "Executing migration job: ${CLOUD_RUN_MIGRATION_JOB}"
  gcloud run jobs execute "${CLOUD_RUN_MIGRATION_JOB}" \
    --project "${GCP_PROJECT_ID}" \
    --region "${GCP_REGION}" \
    --wait
fi

echo "Cloud Run deploy complete."
echo "Image: ${IMAGE_URI}"
