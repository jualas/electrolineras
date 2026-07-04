#!/usr/bin/env bash
# Envía alerta de fallo de cron ingest (#6040 / #6052).
# Uso: notify_ingest_failure.sh <job> <mensaje>
set -euo pipefail

notify_ingest_failure() {
  local job="${1:?job}"
  local message="${2:?message}"
  local webhook_url="${INGEST_WEBHOOK_URL:-}"

  if [[ -z "$webhook_url" ]] || ! command -v curl >/dev/null; then
    return 0
  fi

  local body="Electrolineras cron ${job} FAILED: ${message}"
  if [[ "$job" == "monitor" ]]; then
    body="Electrolineras MONITOR: ${message}"
  fi

  if [[ "$webhook_url" == *"ntfy.sh"* ]]; then
    local title="Electrolineras ingest ${job}"
    if [[ "$job" == "monitor" ]]; then
      title="Electrolineras monitor"
    fi
    curl -sf -X POST "$webhook_url" \
      -H "Title: ${title}" \
      -H "Priority: high" \
      -H "Tags: warning,electric_car" \
      -d "$body" \
      >/dev/null 2>&1 || true
    return 0
  fi

  if [[ "$webhook_url" == *"discord.com/api/webhooks"* ]]; then
    curl -sf -X POST "$webhook_url" \
      -H "Content-Type: application/json" \
      -d "$(python3 -c "import json,sys; print(json.dumps({'content': sys.argv[1]}))" "$body")" \
      >/dev/null 2>&1 || true
    return 0
  fi

  curl -sf -X POST "$webhook_url" \
    -H "Content-Type: application/json" \
    -d "$(python3 -c "import json,sys; print(json.dumps({'text': sys.argv[1]}))" "$body")" \
    >/dev/null 2>&1 || true
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  notify_ingest_failure "${1:?job}" "${2:?message}"
  echo "OK — alerta enviada (si INGEST_WEBHOOK_URL está configurado)."
fi
