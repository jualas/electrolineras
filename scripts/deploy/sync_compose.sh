#!/usr/bin/env bash
# Copia ficheros Docker al directorio de despliegue del mini PC (#6038).
#
# Uso:
#   bash scripts/deploy/sync_compose.sh
#   DEPLOY_COMPOSE_DIR=/ruta bash scripts/deploy/sync_compose.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${ELECTROLINERAS_REPO:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
TARGET="${DEPLOY_COMPOSE_DIR:-/mnt/datos/docker/electrolineras}"

mkdir -p "$TARGET"

for f in docker-compose.yml docker-compose.prod.yml env.example; do
  src="$REPO/docker/$f"
  if [[ ! -f "$src" ]]; then
    echo "ERROR: falta $src" >&2
    exit 1
  fi
  cp "$src" "$TARGET/$f"
  echo "→ $TARGET/$f"
done

echo "Listo. Edita $TARGET/.env y ejecuta:"
echo "  cd $TARGET && docker compose -f docker-compose.prod.yml up -d --build"
