#!/usr/bin/env bash
# Prueba monitoring sin enviar alertas (#6045).
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

"$PYTHON" "$SCRIPT_DIR/check_health.py" --json
