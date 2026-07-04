#!/usr/bin/env bash
# Monitoring producción (#6045) — API, OSRM, ingest, disco, integridad SQLite.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${ELECTROLINERAS_REPO:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
CRON_ENV="${ELECTROLINERAS_CRON_ENV:-$REPO/scripts/cron/electrolineras.env}"
PYTHON="${ELECTROLINERAS_VENV:-$REPO/.venv/bin}/python"

if [[ -f "$CRON_ENV" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$CRON_ENV"
  set +a
fi

LOG_DIR="${MONITOR_LOG_DIR:-${ELECTROLINERAS_DATA:-$REPO/data}/logs/monitor}"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/health-$(date +%Y%m%d).log"

{
  echo "======== $(date -Is) START health checks ========"
  set +e
  "$PYTHON" "$SCRIPT_DIR/check_health.py" --notify --json
  status=$?
  set -e
  echo "======== $(date -Is) END status=$status ========"
} >>"$LOG_FILE" 2>&1

exit "$status"
