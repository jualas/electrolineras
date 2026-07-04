#!/usr/bin/env bash
# Comprueba si Nominatim ya responde; entonces ejecuta finish_prod_setup (una sola vez).
#
# Uso manual:
#   bash scripts/nominatim/wait_and_finish_prod.sh
#
# Cron (cada 30 min mientras importa):
#   bash scripts/nominatim/install_finish_cron.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CRON_ENV="${ELECTROLINERAS_CRON_ENV:-$ROOT/scripts/cron/electrolineras.env}"
GEO_URL="${NOMINATIM_SMOKE_URL:-http://127.0.0.1:8092/search?q=Madrid&format=json&limit=1&countrycodes=es}"
DONE_MARKER="${NOMINATIM_FINISH_DONE_MARKER:-/mnt/datos/docker/volumes/nominatim-iberia/.prod-finish-done}"
LOG_DIR="${ELECTROLINERAS_LOG_DIR:-/mnt/datos/docker/volumes/electrolineras-data/logs/cron}"
LOG_FILE="$LOG_DIR/nominatim-finish.log"

log() {
  echo "[nominatim-wait $(date -Is)] $*" | tee -a "$LOG_FILE"
}

notify_success() {
  local webhook_url="${INGEST_WEBHOOK_URL:-}"
  [[ -n "$webhook_url" ]] || return 0
  command -v curl >/dev/null || return 0

  local body="Nominatim import completado. Prod configurado (sin fallback público, monitoring activo)."
  if [[ "$webhook_url" == *"ntfy.sh"* ]]; then
    curl -sf -X POST "$webhook_url" \
      -H "Title: Electrolineras Nominatim OK" \
      -H "Priority: default" \
      -H "Tags: white_check_mark,map" \
      -d "$body" \
      >/dev/null 2>&1 || true
  fi
}

mkdir -p "$LOG_DIR"

if [[ -f "$CRON_ENV" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$CRON_ENV"
  set +a
fi

if [[ -f "$DONE_MARKER" ]]; then
  exit 0
fi

if ! curl -sf --max-time "${NOMINATIM_WAIT_TIMEOUT_SECONDS:-15}" "$GEO_URL" | grep -q lat; then
  log "Nominatim aún no listo ($GEO_URL)"
  exit 0
fi

log "Nominatim responde — ejecutando finish_prod_setup…"

if bash "$SCRIPT_DIR/finish_prod_setup.sh" >>"$LOG_FILE" 2>&1; then
  date -Is >"$DONE_MARKER"
  log "Prod configurado. Marcador: $DONE_MARKER"
  notify_success
  log "Puedes quitar el cron con: bash scripts/nominatim/install_finish_cron.sh --remove"
else
  log "ERROR: finish_prod_setup falló (reintentará en el próximo cron)"
  exit 1
fi
