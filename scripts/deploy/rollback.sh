#!/usr/bin/env bash
# Rollback al despliegue anterior (#6044, stack prod #6038)
#
# Uso:
#   bash scripts/deploy/rollback.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${DEPLOY_ENV:-$SCRIPT_DIR/deploy.env}"
COMPOSE_DIR="${DEPLOY_COMPOSE_DIR:-/mnt/datos/docker/electrolineras}"
HEALTH_URL="${DEPLOY_HEALTH_URL:-http://127.0.0.1:8015/health}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
fi

if [[ -z "${DEPLOY_COMPOSE_FILE:-}" ]]; then
  if [[ -f "$COMPOSE_DIR/docker-compose.prod.yml" ]]; then
    DEPLOY_COMPOSE_FILE=docker-compose.prod.yml
  else
    DEPLOY_COMPOSE_FILE=docker-compose.yml
  fi
fi

if [[ -z "${DEPLOY_SERVICES:-}" ]]; then
  if [[ "$DEPLOY_COMPOSE_FILE" == *prod* ]]; then
    DEPLOY_SERVICES="electrolineras-api electrolineras-nginx"
  else
    DEPLOY_SERVICES="electrolineras"
  fi
fi

COMPOSE=(docker compose -f "$DEPLOY_COMPOSE_FILE")

log() {
  echo "[rollback $(date -Is)] $*"
}

restore_images() {
  local svc image rollback_tag restored=0
  for svc in $DEPLOY_SERVICES; do
    image="$(docker compose -f "$DEPLOY_COMPOSE_FILE" config --images "$svc" 2>/dev/null || true)"
    if [[ -z "$image" ]]; then
      continue
    fi
    rollback_tag="${image%:*}:previous"
    if ! docker image inspect "$rollback_tag" >/dev/null 2>&1; then
      log "WARN: no hay imagen de rollback ($rollback_tag) para $svc"
      continue
    fi
    docker tag "$rollback_tag" "$image"
    log "Restaurado $rollback_tag → $image"
    restored=1
  done
  if [[ "$restored" -eq 0 ]]; then
    log "ERROR: no hay imágenes de rollback disponibles"
    exit 1
  fi
}

restore_images

cd "$COMPOSE_DIR"
"${COMPOSE[@]}" up -d --no-deps $DEPLOY_SERVICES

for ((i = 1; i <= 20; i++)); do
  if curl -sf "$HEALTH_URL" >/dev/null; then
    log "Rollback OK ($HEALTH_URL)"
    exit 0
  fi
  sleep 2
done

log "ERROR: health check fallido tras rollback"
exit 1
