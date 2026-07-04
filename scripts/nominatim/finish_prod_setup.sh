#!/usr/bin/env bash
# Tras import Nominatim OK: quitar fallback público, activar monitoring, reiniciar API.
#
# Uso (cuando curl Madrid responde JSON):
#   bash scripts/nominatim/finish_prod_setup.sh
set -euo pipefail

GEO_URL="${NOMINATIM_SMOKE_URL:-http://127.0.0.1:8092/search?q=Madrid&format=json&limit=1&countrycodes=es}"
PROD_ENV="${ELECTROLINERAS_PROD_ENV:-/mnt/datos/docker/electrolineras/.env}"
CRON_ENV="${ELECTROLINERAS_CRON_ENV:-/mnt/datos/Proyectos/Electrolineras/scripts/cron/electrolineras.env}"
COMPOSE_DIR="${DEPLOY_COMPOSE_DIR:-/mnt/datos/docker/electrolineras}"

log() { echo "[nominatim-finish $(date -Is)] $*"; }

if ! curl -sf "$GEO_URL" | grep -q lat; then
  log "ERROR: Nominatim aún no responde en $GEO_URL"
  log "Sigue con: make nominatim-logs"
  exit 1
fi

log "Nominatim OK"

if [[ -f "$PROD_ENV" ]]; then
  if grep -q '^NOMINATIM_FALLBACK_BASE_URL=' "$PROD_ENV"; then
    sed -i 's|^NOMINATIM_FALLBACK_BASE_URL=.*|NOMINATIM_FALLBACK_BASE_URL=|' "$PROD_ENV"
    log "Fallback público desactivado en $PROD_ENV"
  fi
fi

MONITOR_LINE='MONITOR_NOMINATIM_URL=http://127.0.0.1:8092/search?q=Madrid&format=json&limit=1&countrycodes=es'
if [[ -f "$CRON_ENV" ]]; then
  if grep -q '^MONITOR_NOMINATIM_URL=' "$CRON_ENV"; then
    sed -i "s|^MONITOR_NOMINATIM_URL=.*|$MONITOR_LINE|" "$CRON_ENV"
  else
    echo "$MONITOR_LINE" >>"$CRON_ENV"
  fi
  log "Monitoring activado en $CRON_ENV"
fi

if [[ -d "$COMPOSE_DIR" ]]; then
  cd "$COMPOSE_DIR"
  docker compose -f docker-compose.prod.yml up -d --no-deps electrolineras-api
  log "API reiniciada (recarga env)"
fi

curl -sf "http://127.0.0.1:8015/api/v1/meta/geocode?q=Granada&limit=1" | head -c 200
echo
log "Listo. Ejecuta: make monitor-check"

DONE_MARKER="${NOMINATIM_FINISH_DONE_MARKER:-/mnt/datos/docker/volumes/nominatim-iberia/.prod-finish-done}"
mkdir -p "$(dirname "$DONE_MARKER")"
date -Is >"$DONE_MARKER"
log "Marcador escrito: $DONE_MARKER"
