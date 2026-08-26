#!/usr/bin/env bash
# Despliegue en mini PC / VPS (#6044, stack prod #6038)
#
# Uso:
#   bash scripts/deploy/deploy.sh
#   DEPLOY_REF=v0.1.0 bash scripts/deploy/deploy.sh
#
# Variables (scripts/deploy/deploy.env o entorno):
#   ELECTROLINERAS_REPO, DEPLOY_COMPOSE_DIR, DEPLOY_HEALTH_URL
#   DEPLOY_COMPOSE_FILE (default: docker-compose.prod.yml si existe)
#   DEPLOY_SERVICES (default: electrolineras-api electrolineras-nginx)
#
# Staging (pruebas, no toca prod): make deploy-staging → docs/STAGING.md
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${ELECTROLINERAS_REPO:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
ENV_FILE="${DEPLOY_ENV:-$SCRIPT_DIR/deploy.env}"
COMPOSE_DIR="${DEPLOY_COMPOSE_DIR:-/mnt/datos/docker/electrolineras}"
HEALTH_URL="${DEPLOY_HEALTH_URL:-http://127.0.0.1:8015/health}"
REF="${DEPLOY_REF:-}"
STATE_FILE="$COMPOSE_DIR/.deploy-state"

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
  echo "[deploy $(date -Is)] $*"
}

save_previous_images() {
  local svc image rollback_tag
  for svc in $DEPLOY_SERVICES; do
    image="$(docker compose -f "$DEPLOY_COMPOSE_FILE" config --images "$svc" 2>/dev/null || true)"
    if [[ -z "$image" ]]; then
      continue
    fi
    rollback_tag="${image%:*}:previous"
    if docker image inspect "$image" >/dev/null 2>&1; then
      docker tag "$image" "$rollback_tag"
      log "Imagen anterior guardada: $image → $rollback_tag"
    fi
  done
}

write_state() {
  mkdir -p "$(dirname "$STATE_FILE")"
  cat >"$STATE_FILE" <<EOF
deployed_at=$(date -Is)
git_ref=$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)
git_describe=$(git -C "$REPO" describe --tags --always 2>/dev/null || echo unknown)
compose_file=$DEPLOY_COMPOSE_FILE
services=$DEPLOY_SERVICES
health_url=$HEALTH_URL
EOF
}

wait_for_health() {
  local attempts="${DEPLOY_HEALTH_ATTEMPTS:-30}"
  local sleep_s="${DEPLOY_HEALTH_SLEEP_SECONDS:-2}"
  for ((i = 1; i <= attempts; i++)); do
    if curl -sf "$HEALTH_URL" >/dev/null; then
      log "Health OK ($HEALTH_URL)"
      return 0
    fi
    sleep "$sleep_s"
  done
  log "ERROR: health check fallido tras $attempts intentos"
  return 1
}

log "repo=$REPO compose_dir=$COMPOSE_DIR compose_file=$DEPLOY_COMPOSE_FILE services=$DEPLOY_SERVICES"

cd "$REPO"
if [[ -d .git ]]; then
  git fetch --tags origin 2>/dev/null || git fetch --tags 2>/dev/null || true
  if [[ -n "$REF" ]]; then
    log "Checkout ref=$REF"
    git checkout "$REF"
    if git rev-parse "@{u}" >/dev/null 2>&1; then
      git pull --ff-only
    fi
  elif git rev-parse "@{u}" >/dev/null 2>&1; then
    log "git pull --ff-only"
    git pull --ff-only
  fi
else
  log "WARN: $REPO no es un repositorio git; omitiendo pull"
fi

bash "$SCRIPT_DIR/sync_compose.sh"

if [[ ! -d "$COMPOSE_DIR" ]]; then
  log "ERROR: no existe DEPLOY_COMPOSE_DIR=$COMPOSE_DIR"
  exit 1
fi

save_previous_images

cd "$COMPOSE_DIR"
log "docker compose build $DEPLOY_SERVICES"
"${COMPOSE[@]}" build $DEPLOY_SERVICES
log "docker compose up -d --no-deps $DEPLOY_SERVICES"
"${COMPOSE[@]}" up -d --no-deps $DEPLOY_SERVICES

if ! wait_for_health; then
  log "Intentando rollback automático…"
  bash "$SCRIPT_DIR/rollback.sh" || true
  exit 1
fi

write_state
log "Deploy completado"
