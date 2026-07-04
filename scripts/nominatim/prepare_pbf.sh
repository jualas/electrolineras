#!/usr/bin/env bash
# Asegura PBF Iberia (ES+PT) para Nominatim — reutiliza volumen OSRM (#6046).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_DIR="${OSRM_DATA_DIR:-/mnt/datos/docker/volumes/osrm-iberia}"
PBF="${DATA_DIR}/iberia-latest.osm.pbf"
MIN_BYTES=50000000

if [[ -f "${PBF}" ]] && [[ $(stat -c%s "${PBF}") -ge ${MIN_BYTES} ]]; then
  echo "OK: ${PBF} ($(du -h "${PBF}" | cut -f1))"
  exit 0
fi

echo "PBF Iberia no encontrado; ejecutando build OSRM (descarga + merge ES+PT)…"
bash "${ROOT}/scripts/osrm/build_iberia.sh"

if [[ ! -f "${PBF}" ]]; then
  echo "ERROR: no se generó ${PBF}" >&2
  exit 1
fi

echo "Listo: ${PBF}"
