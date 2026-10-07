#!/usr/bin/env bash
# Restringe permisos de ficheros .env con secretos (#6043).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEFAULT_FILES=(
  "/mnt/datos/docker/electrolineras/.env"
  "$REPO_ROOT/scripts/cron/electrolineras.env"
  "$REPO_ROOT/.env"
)

if (($# == 0)); then
  set -- "${DEFAULT_FILES[@]}"
fi

for file in "$@"; do
  if [[ ! -f "$file" ]]; then
    echo "SKIP (no existe): $file"
    continue
  fi
  chmod 600 "$file"
  owner="$(stat -c '%U:%G' "$file" 2>/dev/null || stat -f '%Su:%Sg' "$file")"
  echo "OK chmod 600 $file ($owner)"
done
