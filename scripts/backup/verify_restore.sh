#!/usr/bin/env bash
# Prueba de restauración en directorio temporal (#6041).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ENV="${ELECTROLINERAS_CRON_ENV:-$SCRIPT_DIR/../cron/electrolineras.env}"

if [[ -f "$CRON_ENV" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$CRON_ENV"
  set +a
fi

BACKUP_ROOT="${BACKUP_ROOT:-/mnt/datos/docker/backups/electrolineras}"
LATEST="$(find "$BACKUP_ROOT/daily" -maxdepth 1 -mindepth 1 -type d -name '20*' | sort | tail -1)"

if [[ -z "$LATEST" ]]; then
  echo "ERROR: no hay backups daily en $BACKUP_ROOT/daily — ejecuta run_backup.sh daily primero"
  exit 1
fi

TMP="$(mktemp -d /tmp/electrolineras-restore-test.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

echo "Backup: $LATEST"
echo "Temp:   $TMP"

bash "$SCRIPT_DIR/restore_backup.sh" --path "$LATEST" --dry-run

cp -a "$LATEST/stations.db" "$TMP/stations.db"
COUNT="$(
  python3 - <<PY
import sqlite3
conn = sqlite3.connect("$TMP/stations.db")
cur = conn.execute("SELECT COUNT(*) FROM station")
print(cur.fetchone()[0])
conn.close()
PY
)"

MIN_TOTAL="${MIN_TOTAL_STATIONS:-18000}"
echo "Estaciones en backup: $COUNT (mínimo esperado $MIN_TOTAL)"
if [[ "$COUNT" -lt "$MIN_TOTAL" ]]; then
  echo "WARN: conteo por debajo del umbral de verify_ingest"
  exit 1
fi

echo "OK — prueba de restauración superada."
