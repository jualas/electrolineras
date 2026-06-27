#!/usr/bin/env bash
# Smoke test rápido — API local (no requiere Vite)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BASE_URL="${SMOKE_BASE_URL:-http://127.0.0.1:8000}"

if ! command -v curl >/dev/null; then
  echo "curl no encontrado"
  exit 1
fi

echo "==> Health"
curl -sf "${BASE_URL}/health" | head -c 200
echo

echo "==> Stats"
STATS=$(curl -sf "${BASE_URL}/api/v1/meta/stats")
TOTAL=$(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin)['total_stations'])")
echo "total_stations=$TOTAL"
if [[ "$TOTAL" -lt 1000 ]]; then
  echo "AVISO: pocas estaciones — ¿falta ingest?"
  exit 1
fi

echo "==> Stations sample (GeoJSON bbox Madrid)"
curl -sf "${BASE_URL}/api/v1/stations?format=geojson&bbox=-4.0,40.3,-3.5,40.5&limit=5" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'features={len(d[\"features\"])}')"

echo "OK smoke test"
