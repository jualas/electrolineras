#!/usr/bin/env bash
# Ejecutor de ingestión programada — Electrolineras (#6040)
#
# Uso:
#   run_scheduled_job.sh es|pt|reve|ocm
#
# Variables (scripts/cron/electrolineras.env o entorno):
#   ELECTROLINERAS_REPO, ELECTROLINERAS_VENV, ELECTROLINERAS_DATA, DATABASE_URL
#   INGEST_WEBHOOK_URL (opcional — POST JSON en fallo)
set -euo pipefail

JOB="${1:?job requerido: es|pt|reve|ocm}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${ELECTROLINERAS_REPO:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
ENV_FILE="${ELECTROLINERAS_CRON_ENV:-$SCRIPT_DIR/electrolineras.env}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
fi

VENV="${ELECTROLINERAS_VENV:-$REPO/.venv/bin}"
DATA="${ELECTROLINERAS_DATA:-$REPO/data}"
LOG_DIR="${ELECTROLINERAS_LOG_DIR:-$DATA/logs/cron}"
LOCK_DIR="${ELECTROLINERAS_LOCK_DIR:-/tmp/electrolineras-cron-locks}"
DATABASE_URL="${DATABASE_URL:-sqlite:///$DATA/db/stations.db}"

mkdir -p "$LOG_DIR" "$LOCK_DIR"
LOG_FILE="$LOG_DIR/ingest-${JOB}.log"
LOCK_FILE="$LOCK_DIR/${JOB}.lock"

export DATABASE_URL
export PYTHONPATH="$REPO/src${PYTHONPATH:+:$PYTHONPATH}"

notify_failure() {
  local message="$1"
  if [[ -n "${INGEST_WEBHOOK_URL:-}" ]] && command -v curl >/dev/null; then
    curl -sf -X POST "$INGEST_WEBHOOK_URL" \
      -H "Content-Type: application/json" \
      -d "{\"text\":\"Electrolineras cron ${JOB} FAILED: ${message}\"}" \
      >/dev/null 2>&1 || true
  fi
}

exec 200>"$LOCK_FILE"
if ! flock -n 200; then
  echo "$(date -Is) SKIP ${JOB}: job anterior aún en curso" >>"$LOG_FILE"
  exit 0
fi

set +e
{
  echo "======== $(date -Is) START job=${JOB} ========"
  echo "repo=$REPO"
  echo "database_url=$DATABASE_URL"

  case "$JOB" in
    es)
      "$VENV/electrolineras-ingest" --es-only --summary
      ;;
    pt)
      "$VENV/electrolineras-ingest" --pt-only --summary
      ;;
    reve)
      "$VENV/electrolineras-sync-reve" --summary
      ;;
    ocm)
      if [[ -n "${OCM_API_KEY:-}" ]]; then
        "$VENV/electrolineras-sync-ocm" --summary
      elif [[ -d "${REPO}/data/raw/ocm-export/data/ES" ]]; then
        "$VENV/electrolineras-sync-ocm" --from-export --summary
      else
        echo "WARN: sin OCM_API_KEY ni export local; omitiendo sync OCM"
        ingest_status=0
      fi
      ;;
    *)
      echo "ERROR: job desconocido: $JOB"
      exit 2
      ;;
  esac
  ingest_status=$?

  if [[ $ingest_status -eq 0 ]]; then
    "$VENV/python" "$SCRIPT_DIR/verify_ingest.py" "$JOB"
    verify_status=$?
  else
    verify_status=$ingest_status
  fi

  if [[ $ingest_status -eq 0 && $verify_status -eq 0 ]]; then
    echo "======== $(date -Is) OK job=${JOB} ========"
    exit 0
  fi

  echo "======== $(date -Is) FAIL job=${JOB} ingest=$ingest_status verify=$verify_status ========"
  exit 1
} >>"$LOG_FILE" 2>&1
job_status=$?
set -e

if [[ $job_status -ne 0 ]]; then
  notify_failure "ver log $LOG_FILE"
  exit "$job_status"
fi

exit 0
