#!/usr/bin/env bash
# Despliegue STAGING en mini PC (puerto 8016). No toca prod (:8015).
#
# Uso (desde la rama a probar, p. ej. feature/viaje-activo-6131):
#   bash scripts/deploy/deploy-staging.sh
#
# Opcional: refrescar BD desde prod antes del build
#   STAGING_REFRESH_DB=1 bash scripts/deploy/deploy-staging.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${ELECTROLINERAS_REPO:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
COMPOSE_DIR="${DEPLOY_COMPOSE_DIR:-/mnt/datos/docker/electrolineras}"
ENV_FILE="${DEPLOY_ENV:-$SCRIPT_DIR/deploy.env}"

export DEPLOY_COMPOSE_FILE="${DEPLOY_COMPOSE_FILE:-docker-compose.staging.yml}"
export DEPLOY_SERVICES="${DEPLOY_SERVICES:-electrolineras-staging-api electrolineras-staging-nginx}"
export DEPLOY_HEALTH_URL="${DEPLOY_HEALTH_URL:-http://127.0.0.1:8016/health}"
export ELECTROLINERAS_STAGING_DATA="${ELECTROLINERAS_STAGING_DATA:-/mnt/datos/docker/volumes/electrolineras-staging-data}"
# Origen CORS por IP LAN del host (sin IP fija en el repo); se puede fijar en deploy.env.
export STAGING_LAN_ORIGIN="${STAGING_LAN_ORIGIN:-http://$(hostname -I | awk '{print $1}'):8016}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
fi

# Re-aplicar overrides staging por si deploy.env fija prod
export DEPLOY_COMPOSE_FILE=docker-compose.staging.yml
export DEPLOY_SERVICES="electrolineras-staging-api electrolineras-staging-nginx"
export DEPLOY_HEALTH_URL=http://127.0.0.1:8016/health

log() {
  echo "[staging $(date -Is)] $*"
}

log "Preparando datos staging…"
bash "$SCRIPT_DIR/prepare_staging_data.sh"

if [[ "${STAGING_REFRESH_DB:-0}" == "1" ]]; then
  PROD_DB="${ELECTROLINERAS_DATA:-/mnt/datos/docker/volumes/electrolineras-data}/db/stations.db"
  STAGING_DB="$ELECTROLINERAS_STAGING_DATA/db/stations.db"
  if [[ -f "$PROD_DB" ]]; then
    log "Refrescando stations.db desde prod"
    cp -a "$PROD_DB" "$STAGING_DB"
  fi
fi

# No hacer git pull a otra rama: staging usa el working tree actual del repo
export DEPLOY_REF="${DEPLOY_REF:-}"
# Evitar que deploy.sh haga pull destructivo: usamos el HEAD actual
# (deploy.sh solo hace pull si no hay DEPLOY_REF y hay upstream)

log "Sync compose + build staging desde repo=$REPO"
bash "$SCRIPT_DIR/sync_compose.sh"

cd "$COMPOSE_DIR"
log "docker compose -f docker-compose.staging.yml build"
docker compose -f docker-compose.staging.yml build $DEPLOY_SERVICES
log "docker compose -f docker-compose.staging.yml up -d --no-deps"
docker compose -f docker-compose.staging.yml up -d --no-deps $DEPLOY_SERVICES

attempts="${DEPLOY_HEALTH_ATTEMPTS:-30}"
sleep_s="${DEPLOY_HEALTH_SLEEP_SECONDS:-2}"
for ((i = 1; i <= attempts; i++)); do
  if curl -sf "$DEPLOY_HEALTH_URL" >/dev/null; then
    log "Health OK ($DEPLOY_HEALTH_URL)"
    cat >"$COMPOSE_DIR/.deploy-state-staging" <<EOF
deployed_at=$(date -Is)
git_ref=$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)
git_branch=$(git -C "$REPO" branch --show-current 2>/dev/null || echo unknown)
compose_file=docker-compose.staging.yml
services=$DEPLOY_SERVICES
health_url=$DEPLOY_HEALTH_URL
EOF
    log "Staging listo: http://127.0.0.1:8016  (LAN: $STAGING_LAN_ORIGIN)"
    log "Prod intacto en :8015 / https://electro.jualas.es"
    exit 0
  fi
  sleep "$sleep_s"
done

log "ERROR: health staging fallido"
docker compose -f docker-compose.staging.yml ps || true
exit 1
