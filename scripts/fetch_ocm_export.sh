#!/usr/bin/env bash
# Descarga POIs de Open Charge Map desde GitHub (sin API key).
# Uso: scripts/fetch_ocm_export.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="${ROOT}/data/raw/ocm-export"
REPO_URL="https://github.com/openchargemap/ocm-export.git"

if [[ -d "${DEST}/.git" ]]; then
  echo "Actualizando ${DEST} (sparse checkout ES, PT)…"
  git -C "${DEST}" sparse-checkout set data/ES data/PT referencedata.json
  git -C "${DEST}" pull --ff-only
else
  echo "Clonando ocm-export en ${DEST} (solo ES, PT)…"
  rm -rf "${DEST}"
  git clone --filter=blob:none --sparse "${REPO_URL}" "${DEST}"
  git -C "${DEST}" sparse-checkout set data/ES data/PT referencedata.json
fi

ES_COUNT="$(find "${DEST}/data/ES" -name '*.json' 2>/dev/null | wc -l | tr -d ' ')"
PT_COUNT="$(find "${DEST}/data/PT" -name '*.json' 2>/dev/null | wc -l | tr -d ' ')"
echo "Listo: ES=${ES_COUNT} POIs, PT=${PT_COUNT} POIs"
echo "Sincronizar: cd src && python -m ingest.ocm_cli --from-export --summary"
