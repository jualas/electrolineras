#!/usr/bin/env bash
# Prepara volumen de datos de staging (copia stations.db desde prod si falta).
set -euo pipefail

PROD_DATA="${ELECTROLINERAS_DATA:-/mnt/datos/docker/volumes/electrolineras-data}"
STAGING_DATA="${ELECTROLINERAS_STAGING_DATA:-/mnt/datos/docker/volumes/electrolineras-staging-data}"

mkdir -p "$STAGING_DATA/db" "$STAGING_DATA/raw" "$STAGING_DATA/processed"

if [[ ! -f "$STAGING_DATA/db/stations.db" ]]; then
  if [[ -f "$PROD_DATA/db/stations.db" ]]; then
    echo "→ Copiando stations.db prod → staging"
    cp -a "$PROD_DATA/db/stations.db" "$STAGING_DATA/db/stations.db"
  else
    echo "WARN: no hay stations.db en prod ($PROD_DATA/db); staging arrancará con BD vacía" >&2
  fi
else
  echo "→ stations.db staging ya existe ($STAGING_DATA/db/stations.db)"
fi

echo "Staging data: $STAGING_DATA"
