#!/usr/bin/env bash
# Arranca cursor-cli-bridge (Dify → Cursor CLI). Ver docs/DIFY_CURSOR.md
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${CURSOR_BRIDGE_ENV:-$ROOT/scripts/dify/cursor-bridge.env}"
DIFY_CURSOR_REPO="${DIFY_CURSOR_REPO:-/mnt/datos/docker/dify}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

BRIDGE_DIR="$DIFY_CURSOR_REPO/integrations/dify-cursor/cursor-cli-bridge"
if [[ ! -f "$BRIDGE_DIR/bridge.py" ]]; then
  echo "No se encuentra bridge.py en $BRIDGE_DIR" >&2
  exit 1
fi

echo "Puente Cursor: http://${CURSOR_BRIDGE_HOST:-0.0.0.0}:${CURSOR_BRIDGE_PORT:-18765}/invoke"
cd "$BRIDGE_DIR"
exec python3 bridge.py
