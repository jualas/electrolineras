#!/usr/bin/env bash
# Lanza el MCP Grafana (solo lectura) para Cursor en el mini PC.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="${ELECTROLINERAS_PYTHON:-$ROOT/.venv/bin/python}"
SERVER="$ROOT/tools/mcp_grafana/server.py"

TOKEN_FILE="${GRAFANA_TOKEN_FILE:-/mnt/datos/docker/electrolineras/.grafana-token}"
if [[ -z "${GRAFANA_API_TOKEN:-}" && -f "$TOKEN_FILE" ]]; then
  GRAFANA_API_TOKEN="$(tr -d '[:space:]' <"$TOKEN_FILE")"
  export GRAFANA_API_TOKEN
fi

export GRAFANA_BASE_URL="${GRAFANA_BASE_URL:-http://127.0.0.1:3000}"
export GRAFANA_DATASOURCE_UID="${GRAFANA_DATASOURCE_UID:-TeslaMate}"
export CONSUMPTION_PROFILE_LOOKBACK_DAYS="${CONSUMPTION_PROFILE_LOOKBACK_DAYS:-0}"
export CONSUMPTION_PROFILE_MIN_DISTANCE_KM="${CONSUMPTION_PROFILE_MIN_DISTANCE_KM:-20}"

exec "$PYTHON" "$SERVER"
