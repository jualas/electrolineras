#!/usr/bin/env bash
# Backup SQLite + GeoJSON + raw reciente (#6041).
#
# Uso:
#   run_backup.sh daily          # cron 05:30 — BD + geojson + último XML es/pt
#   run_backup.sh pre-pt         # snapshot BD antes de ingest PT (~180 MB)
set -euo pipefail

MODE="${1:-daily}"
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
RAW_DIR="${BACKUP_RAW_DIR:-$REPO/data/raw}"
PROCESSED_DIR="${BACKUP_PROCESSED_DIR:-$REPO/data/processed}"
BACKUP_ROOT="${BACKUP_ROOT:-/mnt/datos/docker/backups/electrolineras}"
LOG_DIR="${BACKUP_LOG_DIR:-$DATA/logs/backup}"
VENV="${ELECTROLINERAS_VENV:-$REPO/.venv/bin}"

DB_PATH="${DATABASE_URL#sqlite:///}"
if [[ "$DB_PATH" == "$DATABASE_URL" ]]; then
  DB_PATH="$DATA/db/stations.db"
fi

DAILY_RETENTION="${BACKUP_DAILY_RETENTION_DAYS:-7}"
WEEKLY_RETENTION="${BACKUP_WEEKLY_RETENTION_DAYS:-30}"
PRE_PT_RETENTION="${BACKUP_PRE_PT_RETENTION_DAYS:-7}"

mkdir -p "$LOG_DIR" "$BACKUP_ROOT/daily" "$BACKUP_ROOT/pre-pt"
LOG_FILE="$LOG_DIR/backup-${MODE}-$(date +%Y%m%d).log"

log() {
  echo "$(date -Is) $*" | tee -a "$LOG_FILE"
}

notify_backup_failure() {
  local message="$1"
  if [[ -f "$SCRIPT_DIR/../cron/notify_ingest_failure.sh" ]]; then
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/../cron/notify_ingest_failure.sh"
    notify_ingest_failure "backup-${MODE}" "$message"
  fi
}

backup_sqlite() {
  local dest_db="$1"
  mkdir -p "$(dirname "$dest_db")"
  if [[ ! -f "$DB_PATH" ]]; then
    log "ERROR: no existe $DB_PATH"
    return 1
  fi
  python3 - "$DB_PATH" "$dest_db" <<'PY'
import sqlite3
import sys

source, dest = sys.argv[1], sys.argv[2]
src = sqlite3.connect(source, timeout=120)
try:
    src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
finally:
    src.close()
PY
}

copy_latest_raw() {
  local country="$1"
  local dest_raw="$2"
  local manifest="$RAW_DIR/$country/manifest.json"
  if [[ ! -f "$manifest" ]]; then
    log "WARN: sin manifest $manifest"
    return 0
  fi
  mkdir -p "$dest_raw/$country"
  cp -a "$manifest" "$dest_raw/$country/manifest.json"
  local latest_file
  latest_file="$(
    python3 -c "import json; print(json.load(open('$manifest'))['file'])"
  )"
  local src="$RAW_DIR/$country/$latest_file"
  if [[ -f "$src" ]]; then
    cp -a "$src" "$dest_raw/$country/$latest_file"
    log "raw $country: $latest_file"
  else
    log "WARN: falta $src"
  fi
}

write_backup_manifest() {
  local dest_dir="$1"
  local kind="$2"
  python3 - "$dest_dir" "$kind" "$DB_PATH" <<'PY'
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

dest = Path(sys.argv[1])
kind = sys.argv[2]
source_db = Path(sys.argv[3])

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

files = []
for path in sorted(dest.rglob("*")):
    if path.is_file() and path.name != "manifest.json":
        files.append(
            {
                "path": str(path.relative_to(dest)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )

payload = {
    "kind": kind,
    "created_at": datetime.now(UTC).isoformat(),
    "source_database": str(source_db),
    "files": files,
}
(dest / "manifest.json").write_text(
    json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
PY
}

prune_backups() {
  python3 - "$BACKUP_ROOT" "$DAILY_RETENTION" "$WEEKLY_RETENTION" "$PRE_PT_RETENTION" <<'PY'
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

root = Path(sys.argv[1])
daily_keep = int(sys.argv[2])
weekly_keep = int(sys.argv[3])
pre_pt_keep = int(sys.argv[4])
now = datetime.now(UTC)

def parse_day(name: str):
    return datetime.strptime(name, "%Y-%m-%d").replace(tzinfo=UTC)

for path in sorted((root / "daily").glob("20*")):
    if not path.is_dir():
        continue
    try:
        day = parse_day(path.name)
    except ValueError:
        continue
    age = (now - day).days
    is_sunday = day.weekday() == 6
    if is_sunday and age <= weekly_keep:
        continue
    if age <= daily_keep:
        continue
    import shutil
    shutil.rmtree(path)
    print(f"pruned daily {path.name}")

for path in sorted((root / "pre-pt").glob("20*")):
    if not path.is_dir():
        continue
    try:
        stamp = datetime.strptime(path.name, "%Y-%m-%dT%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        continue
    if (now - stamp).days <= pre_pt_keep:
        continue
    import shutil
    shutil.rmtree(path)
    print(f"pruned pre-pt {path.name}")
PY
}

run_daily() {
  local day
  day="$(date +%Y-%m-%d)"
  local dest="$BACKUP_ROOT/daily/$day"
  if [[ -d "$dest" && -f "$dest/stations.db" ]]; then
    log "SKIP daily: ya existe $dest"
    return 0
  fi
  mkdir -p "$dest/raw"
  log "START daily -> $dest"
  if ! backup_sqlite "$dest/stations.db"; then
    log "ERROR: backup SQLite falló"
    rm -rf "$dest"
    return 1
  fi
  if [[ -f "$PROCESSED_DIR/stations.geojson" ]]; then
    cp -a "$PROCESSED_DIR/stations.geojson" "$dest/stations.geojson"
    log "geojson copiado"
  fi
  copy_latest_raw es "$dest/raw"
  copy_latest_raw pt "$dest/raw"
  write_backup_manifest "$dest" "daily"
  prune_backups
  log "OK daily $dest ($(du -sh "$dest" | awk '{print $1}'))"
}

run_pre_pt() {
  local stamp dest
  stamp="$(date +%Y-%m-%dT%H%M%S)"
  dest="$BACKUP_ROOT/pre-pt/$stamp"
  mkdir -p "$dest"
  log "START pre-pt -> $dest"
  if ! backup_sqlite "$dest/stations.db"; then
    log "ERROR: backup pre-pt falló"
    rm -rf "$dest"
    return 1
  fi
  write_backup_manifest "$dest" "pre-pt"
  prune_backups
  log "OK pre-pt $dest ($(du -sh "$dest" | awk '{print $1}'))"
}

main() {
  log "======== START mode=$MODE ========"
  case "$MODE" in
    daily) run_daily ;;
    pre-pt) run_pre_pt ;;
    *)
      log "ERROR: modo desconocido: $MODE"
      exit 2
      ;;
  esac
  log "======== END mode=$MODE ========"
}

if ! main; then
  notify_backup_failure "ver log $LOG_FILE"
  exit 1
fi
