#!/usr/bin/env bash
# Restaura stations.db desde backup (#6041).
#
# Uso:
#   restore_backup.sh --date 2026-07-04 [--dry-run]
#   restore_backup.sh --path /mnt/datos/docker/backups/electrolineras/daily/2026-07-04
#
# IMPORTANTE: detener la API Docker antes de restaurar la BD en producción:
#   cd /mnt/datos/docker/electrolineras && docker compose stop electrolineras
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ENV="${ELECTROLINERAS_CRON_ENV:-$SCRIPT_DIR/../cron/electrolineras.env}"

if [[ -f "$CRON_ENV" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$CRON_ENV"
  set +a
fi

REPO="${ELECTROLINERAS_REPO:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
DATA="${ELECTROLINERAS_DATA:-$REPO/data}"
BACKUP_ROOT="${BACKUP_ROOT:-/mnt/datos/docker/backups/electrolineras}"
DB_PATH="${DATABASE_URL#sqlite:///}"
if [[ "$DB_PATH" == "$DATABASE_URL" ]]; then
  DB_PATH="$DATA/db/stations.db"
fi

BACKUP_PATH=""
BACKUP_DATE=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --date)
      BACKUP_DATE="$2"
      shift 2
      ;;
    --path)
      BACKUP_PATH="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    *)
      echo "Uso: restore_backup.sh --date YYYY-MM-DD | --path DIR [--dry-run]"
      exit 2
      ;;
  esac
done

if [[ -z "$BACKUP_PATH" ]]; then
  if [[ -z "$BACKUP_DATE" ]]; then
    echo "ERROR: indica --date o --path"
    exit 2
  fi
  BACKUP_PATH="$BACKUP_ROOT/daily/$BACKUP_DATE"
fi

SRC_DB="$BACKUP_PATH/stations.db"
if [[ ! -f "$SRC_DB" ]]; then
  echo "ERROR: no existe $SRC_DB"
  exit 1
fi

echo "Origen:  $SRC_DB"
echo "Destino: $DB_PATH"
if [[ -f "$BACKUP_PATH/manifest.json" ]]; then
  echo "Manifiesto:"
  head -20 "$BACKUP_PATH/manifest.json"
fi

if [[ "$DRY_RUN" == true ]]; then
  echo "DRY-RUN — no se modificó nada."
  exit 0
fi

mkdir -p "$(dirname "$DB_PATH")"
TS="$(date +%Y%m%dT%H%M%S)"
if [[ -f "$DB_PATH" ]]; then
  cp -a "$DB_PATH" "${DB_PATH}.before-restore-${TS}"
  echo "Copia de seguridad previa: ${DB_PATH}.before-restore-${TS}"
fi
cp -a "$SRC_DB" "$DB_PATH"
rm -f "${DB_PATH}-wal" "${DB_PATH}-shm"
echo "Restauración completada. Reinicia la API: docker compose up -d electrolineras"
