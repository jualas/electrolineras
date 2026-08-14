#!/usr/bin/env bash
# Cron wrapper — ciclo de vida OSRM on-demand.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${ELECTROLINERAS_REPO:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
CRON_ENV="${ELECTROLINERAS_CRON_ENV:-$REPO/scripts/cron/electrolineras.env}"
LOG_DIR="${MONITOR_LOG_DIR:-/mnt/datos/docker/volumes/electrolineras-data/logs/monitor}"

if [[ -f "$CRON_ENV" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$CRON_ENV"
  set +a
fi

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/osrm-lifecycle-$(date +%Y%m%d).log"

{
  echo "======== $(date -Is) START osrm lifecycle ========"
  bash "$SCRIPT_DIR/manage_osrm.sh" once
  echo "======== $(date -Is) END ========"
} >>"$LOG_FILE" 2>&1
