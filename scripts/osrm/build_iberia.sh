#!/usr/bin/env bash
# Construye grafos OSRM MLD para península (ES+PT): car + shortest.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_DIR="${OSRM_DATA_DIR:-/mnt/datos/docker/volumes/osrm-iberia}"
PROFILES_DIR="${ROOT}/docker/osrm/profiles"
IMAGE="${OSRM_BUILD_IMAGE:-ghcr.io/project-osrm/osrm-backend:v5.27.1}"
OSMIUM_IMAGE="${OSMIUM_IMAGE:-stefda/osmium-tool:latest}"
SPAIN_URL="${OSRM_SPAIN_PBF_URL:-https://download.geofabrik.de/europe/spain-latest.osm.pbf}"
PORTUGAL_URL="${OSRM_PORTUGAL_PBF_URL:-https://download.geofabrik.de/europe/portugal-latest.osm.pbf}"
PBF_NAME="iberia-latest.osm.pbf"
SPAIN_NAME="spain-latest.osm.pbf"
PORTUGAL_NAME="portugal-latest.osm.pbf"
OSRM_BASE="iberia-latest.osrm"
MIN_PBF_BYTES=50000000

mkdir -p "${DATA_DIR}/car" "${DATA_DIR}/shortest"

download_pbf() {
  local url="$1"
  local dest="$2"
  if [[ -f "${dest}" ]] && [[ $(stat -c%s "${dest}") -ge ${MIN_PBF_BYTES} ]]; then
    echo "Usando $(basename "${dest}") existente ($(du -h "${dest}" | cut -f1))"
    return 0
  fi
  echo "Descargando ${url} → ${dest}"
  curl -L --fail --retry 3 --retry-delay 5 -o "${dest}.partial" "${url}"
  mv "${dest}.partial" "${dest}"
  local size
  size=$(stat -c%s "${dest}")
  if [[ "${size}" -lt ${MIN_PBF_BYTES} ]]; then
    echo "ERROR: descarga inválida (${size} bytes). ¿URL caída?" >&2
    exit 1
  fi
}

download_pbf "${SPAIN_URL}" "${DATA_DIR}/${SPAIN_NAME}"
download_pbf "${PORTUGAL_URL}" "${DATA_DIR}/${PORTUGAL_NAME}"

if [[ ! -f "${DATA_DIR}/${PBF_NAME}" ]] || [[ $(stat -c%s "${DATA_DIR}/${PBF_NAME}") -lt ${MIN_PBF_BYTES} ]]; then
  echo "Fusionando España + Portugal → ${PBF_NAME}"
  docker run --rm \
    -v "${DATA_DIR}:/data" \
    "${OSMIUM_IMAGE}" \
    osmium merge "/data/${SPAIN_NAME}" "/data/${PORTUGAL_NAME}" -o "/data/${PBF_NAME}" --overwrite
fi

build_profile() {
  local profile_lua="$1"
  local target_dir="$2"
  echo "=== Perfil ${profile_lua} → ${target_dir} ==="
  docker run --rm \
    -v "${DATA_DIR}:/data" \
    -v "${PROFILES_DIR}:/profiles:ro" \
    "${IMAGE}" \
    osrm-extract -p "/profiles/${profile_lua}" "/data/${PBF_NAME}"
  docker run --rm -v "${DATA_DIR}:/data" "${IMAGE}" osrm-partition "/data/${OSRM_BASE}"
  docker run --rm -v "${DATA_DIR}:/data" "${IMAGE}" osrm-customize "/data/${OSRM_BASE}"
  rm -rf "${DATA_DIR}/${target_dir:?}"/*
  mv "${DATA_DIR}/${OSRM_BASE}"* "${DATA_DIR}/${target_dir}/"
  echo "OK: ${target_dir}"
}

build_profile car.lua car
build_profile shortest.lua shortest

echo ""
echo "Listo."
echo "  car/      → ruta rápida + convencionales (exclude=motorway)"
echo "  shortest/ → ruta más directa"
echo ""
echo "Arranca: cd ${ROOT}/docker/osrm && docker compose up -d"
