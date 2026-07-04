#!/usr/bin/env bash
# Instala o elimina cron que ejecuta wait_and_finish_prod cada 30 min (#6046).
#
# Uso:
#   bash scripts/nominatim/install_finish_cron.sh
#   bash scripts/nominatim/install_finish_cron.sh --remove
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WAIT_SCRIPT="$ROOT/scripts/nominatim/wait_and_finish_prod.sh"
LOG_DIR="/mnt/datos/docker/volumes/electrolineras-data/logs/cron"
CRON_LINE="*/30 * * * * $WAIT_SCRIPT >> $LOG_DIR/nominatim-finish.log 2>&1"
CRON_TAG="# electrolineras-nominatim-finish"

chmod +x "$WAIT_SCRIPT"
chmod +x "$ROOT/scripts/nominatim/finish_prod_setup.sh"
mkdir -p "$LOG_DIR"

remove_cron() {
  local tmp
  tmp="$(mktemp)"
  crontab -l 2>/dev/null | grep -v "$CRON_TAG" | grep -vF "$WAIT_SCRIPT" >"$tmp" || true
  if [[ -s "$tmp" ]]; then
    crontab "$tmp"
  else
    crontab -r 2>/dev/null || true
  fi
  rm -f "$tmp"
  echo "Cron Nominatim finish eliminado."
}

install_cron() {
  if crontab -l 2>/dev/null | grep -qF "$WAIT_SCRIPT"; then
    echo "Cron ya instalado:"
    crontab -l | grep -F "$WAIT_SCRIPT"
    exit 0
  fi

  local tmp
  tmp="$(mktemp)"
  crontab -l 2>/dev/null >"$tmp" || true
  {
    cat "$tmp"
    echo "$CRON_TAG"
    echo "$CRON_LINE"
  } | crontab -
  rm -f "$tmp"
  echo "Cron instalado (cada 30 min hasta que Nominatim responda):"
  crontab -l | grep -F "$WAIT_SCRIPT"
  echo
  echo "Log: $LOG_DIR/nominatim-finish.log"
  echo "Probar ahora: bash $WAIT_SCRIPT"
}

case "${1:-}" in
  --remove|-r)
    remove_cron
    ;;
  *)
    install_cron
    ;;
esac
