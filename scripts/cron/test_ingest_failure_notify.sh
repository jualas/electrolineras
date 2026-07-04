#!/usr/bin/env bash
# Simula el camino real de fallo del cron: notify_failure tras job es (#6052).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ELECTROLINERAS_CRON_ENV:-$SCRIPT_DIR/electrolineras.env}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
fi

JOB=es
LOG_FILE="${ELECTROLINERAS_LOG_DIR:-/mnt/datos/docker/volumes/electrolineras-data/logs/cron}/ingest-${JOB}.log"

# shellcheck disable=SC1091
source "$SCRIPT_DIR/notify_ingest_failure.sh"
notify_ingest_failure "$JOB" "SIMULATED FAILURE — ver log $LOG_FILE"

echo "Simulación enviada. En un fallo real run_scheduled_job.sh llama a notify_failure con el mismo mecanismo."
