#!/usr/bin/env bash
# Consulta trip-advice y opcionalmente pide narrativa al Cursor CLI.
set -euo pipefail

API_BASE="${ELECTROLINERAS_API:-http://127.0.0.1:8000}"
ORIGIN=""
DEST=""
SOC="55"
CAPACITY="57"
CONSUMPTION="150"
TERRAIN="1.0"
RESERVE="10"
LOCAL_KM="40"
DEST_RADIUS="10"
TOKEN="${AGENT_API_TOKEN:-}"
USE_CURSOR="${USE_CURSOR:-0}"

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --origin) ORIGIN="$2"; shift 2 ;;
    --dest) DEST="$2"; shift 2 ;;
    --soc) SOC="$2"; shift 2 ;;
    --capacity) CAPACITY="$2"; shift 2 ;;
    --consumption) CONSUMPTION="$2"; shift 2 ;;
    --terrain) TERRAIN="$2"; shift 2 ;;
    --reserve) RESERVE="$2"; shift 2 ;;
    --local-km) LOCAL_KM="$2"; shift 2 ;;
    --dest-radius) DEST_RADIUS="$2"; shift 2 ;;
    --api) API_BASE="$2"; shift 2 ;;
    --cursor) USE_CURSOR=1; shift ;;
    -h|--help) usage 0 ;;
    *) echo "Opción desconocida: $1" >&2; usage 1 ;;
  esac
done

if [[ -z "$ORIGIN" || -z "$DEST" ]]; then
  echo "Requiere --origin lat,lon y --dest lat,lon" >&2
  usage 1
fi

IFS=',' read -r ORIGIN_LAT ORIGIN_LON <<< "$ORIGIN"
IFS=',' read -r DEST_LAT DEST_LON <<< "$DEST"

URL="${API_BASE}/api/v1/agent/trip-advice"
QUERY="origin_lat=${ORIGIN_LAT}&origin_lon=${ORIGIN_LON}&dest_lat=${DEST_LAT}&dest_lon=${DEST_LON}"
QUERY+="&soc_percent=${SOC}&usable_capacity_kwh=${CAPACITY}&consumption_wh_per_km=${CONSUMPTION}"
QUERY+="&terrain_factor=${TERRAIN}&reserve_soc_percent=${RESERVE}"
QUERY+="&local_mobility_km=${LOCAL_KM}&destination_radius_km=${DEST_RADIUS}&include_route=false"

HEADERS=()
if [[ -n "$TOKEN" ]]; then
  HEADERS+=(-H "X-Agent-Token: ${TOKEN}")
fi

JSON=$(curl -fsS "${HEADERS[@]}" "${URL}?${QUERY}")
echo "$JSON" | python3 -m json.tool

if [[ "$USE_CURSOR" == "1" ]] && command -v cursor >/dev/null 2>&1; then
  PROMPT="Eres asistente de viaje EV. Usa SOLO los datos JSON siguientes. Explica en español claro el plan de carga y el SOC recomendado al llegar al destino según la infraestructura local. No inventes estaciones ni porcentajes.\n\n${JSON}"
  cursor agent --message "$PROMPT"
fi
